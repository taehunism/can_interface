"""
TSMaster 스타일의 고급 CAN 데이터 처리 클래스
TSMaster에서 사용하는 오픈소스 라이브러리들과 패턴을 참고하여 구현
"""

import can
import cantools
import time
import threading
import queue
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
import logging
import json
from collections import defaultdict, deque
import numpy as np

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MessagePriority(Enum):
    """메시지 우선순위"""
    HIGH = 1
    NORMAL = 2
    LOW = 3

class MessageStatus(Enum):
    """메시지 상태"""
    VALID = "valid"
    INVALID = "invalid"
    TIMEOUT = "timeout"
    ERROR = "error"

@dataclass
class AdvancedCanMessage:
    """고급 CAN 메시지 데이터 구조"""
    message_id: int
    message_name: str
    raw_data: bytes
    signals: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0
    dlc: int = 0
    status: MessageStatus = MessageStatus.VALID
    priority: MessagePriority = MessagePriority.NORMAL
    error_message: Optional[str] = None
    retry_count: int = 0
    processing_time: float = 0.0
    
    # 메타데이터
    source: str = "unknown"
    cycle_time: float = 0.0
    last_update: float = 0.0
    update_count: int = 0

@dataclass
class MessageFilter:
    """메시지 필터 설정"""
    message_ids: List[int] = field(default_factory=list)
    signal_names: List[str] = field(default_factory=list)
    min_dlc: int = 0
    max_dlc: int = 8
    priority_filter: Optional[MessagePriority] = None
    time_range: Optional[Tuple[float, float]] = None

class TSMasterCanProcessor:
    """TSMaster 스타일의 고급 CAN 데이터 처리기"""
    
    def __init__(self, dbc_path: str, config: Optional[Dict] = None):
        self.dbc_path = dbc_path
        self.config = config or self._default_config()
        
        # DBC 데이터베이스
        self.db = None
        self.message_definitions = {}
        self.signal_definitions = {}
        
        # 메시지 처리
        self.message_queue = queue.PriorityQueue()
        self.processed_messages = deque(maxlen=self.config['max_message_history'])
        self.message_callbacks = defaultdict(list)
        
        # 통계 및 모니터링
        self.stats = {
            'total_messages': 0,
            'valid_messages': 0,
            'invalid_messages': 0,
            'dlc_mismatches': 0,
            'decoding_errors': 0,
            'timeout_errors': 0,
            'processing_errors': 0,
            'average_processing_time': 0.0,
            'messages_per_second': 0.0
        }
        
        # 실시간 모니터링
        self.message_frequency = defaultdict(int)
        self.last_frequency_reset = time.time()
        self.processing_times = deque(maxlen=1000)
        
        # 스레드 관리
        self.processing_thread = None
        self.monitoring_thread = None
        self.running = False
        
        # 메시지 검증 규칙
        self.validation_rules = self._setup_validation_rules()
        
        # 초기화
        self._load_dbc()
        self._start_processing()
    
    def _default_config(self) -> Dict:
        """기본 설정 - 강력한 DLC 처리"""
        return {
            'dlc_validation': True,
            'flexible_dlc': True,  # DLC 불일치 시 자동 조정
            'force_decode': True,  # 강제 디코딩 시도
            'auto_retry': True,
            'max_retries': 3,
            'timeout_threshold': 1.0,
            'max_message_history': 10000,
            'frequency_monitoring': True,
            'performance_monitoring': True,
            'message_prioritization': True,
            'signal_validation': True,  # 경고만 출력, 디코딩은 계속
            'cycle_time_tracking': True,
            'tolerant_decoding': True,  # 관대한 디코딩 모드
            'use_default_on_decode_error': False,  # 디코딩 실패 시 기본값 사용 여부
            'unknown_id_basic_signals': True  # 미정의 ID에 RawBytes/Length 표시
        }
    
    def _load_dbc(self):
        """DBC 파일 로드 및 메시지 정의 생성"""
        try:
            self.db = cantools.database.load_file(self.dbc_path)
            logger.info(f"DBC 파일 로드 성공: {self.dbc_path}")
            
            # 메시지 정의 생성
            for message in self.db.messages:
                self.message_definitions[message.frame_id] = {
                    'message': message,
                    'expected_dlc': message.length,
                    'signals': {signal.name: signal for signal in message.signals},
                    'cycle_time': getattr(message, 'cycle_time', 0.0),
                    'priority': self._determine_priority(message),
                    'message_id': message.frame_id
                }
                
                # 신호 정의도 저장
                for signal in message.signals:
                    self.signal_definitions[signal.name] = {
                        'signal': signal,
                        'message_id': message.frame_id,
                        'message_name': message.name
                    }
            
            logger.info(f"로드된 메시지 수: {len(self.message_definitions)}")
            logger.info(f"로드된 신호 수: {len(self.signal_definitions)}")
            
        except Exception as e:
            logger.error(f"DBC 파일 로드 실패: {e}")
            self.db = None

    def reload_dbc(self, dbc_path: str):
        """DBC 파일을 재로드하고 메시지/신호 정의를 업데이트"""
        try:
            self.dbc_path = dbc_path
            self.message_definitions.clear()
            self.signal_definitions.clear()
            self._load_dbc()
            logger.info(f"DBC 재로드 완료: {dbc_path}")
            return True
        except Exception as e:
            logger.error(f"DBC 재로드 실패: {e}")
            return False
    
    def _determine_priority(self, message) -> MessagePriority:
        """메시지 우선순위 결정"""
        # 레이더 데이터는 높은 우선순위
        if 200 <= message.frame_id <= 209:
            return MessagePriority.HIGH
        # 차량 상태 데이터는 보통 우선순위
        elif message.frame_id in [100, 101, 102]:
            return MessagePriority.NORMAL
        else:
            return MessagePriority.LOW
    
    def _setup_validation_rules(self) -> Dict:
        """메시지 검증 규칙 설정 - CAN FD 지원"""
        return {
            'dlc_range': (0, 64),  # CAN FD 최대 DLC (0-64바이트)
            'message_id_range': (0, 0x1FFFFFFF),
            'signal_range_checks': True,
            'cycle_time_validation': True,
            'signal_consistency': True,
            'can_fd_support': True  # CAN FD 지원 활성화
        }
    
    def _start_processing(self):
        """메시지 처리 스레드 시작"""
        self.running = True
        self.processing_thread = threading.Thread(target=self._message_processor, daemon=True)
        self.monitoring_thread = threading.Thread(target=self._monitoring_processor, daemon=True)
        
        self.processing_thread.start()
        self.monitoring_thread.start()
        
        logger.info("메시지 처리 스레드 시작")
    
    def _message_processor(self):
        """메시지 처리 메인 루프"""
        while self.running:
            try:
                # 우선순위 큐에서 메시지 처리
                if not self.message_queue.empty():
                    priority, timestamp, message = self.message_queue.get_nowait()
                    self._process_single_message(message)
                else:
                    time.sleep(0.001)  # 1ms 대기
                    
            except queue.Empty:
                time.sleep(0.001)
            except Exception as e:
                logger.error(f"메시지 처리 중 오류: {e}")
                self.stats['processing_errors'] += 1
    
    def _monitoring_processor(self):
        """모니터링 및 통계 업데이트"""
        while self.running:
            try:
                self._update_statistics()
                self._update_frequency_monitoring()
                time.sleep(1.0)  # 1초마다 업데이트
            except Exception as e:
                logger.error(f"모니터링 중 오류: {e}")
    
    def process_message(self, can_message: can.Message) -> AdvancedCanMessage:
        """CAN 메시지 처리 (TSMaster 스타일)"""
        start_time = time.time()
        
        # 기본 메시지 생성
        advanced_msg = AdvancedCanMessage(
            message_id=can_message.arbitration_id,
            message_name=f"Unknown_{can_message.arbitration_id}",
            raw_data=can_message.data,
            timestamp=can_message.timestamp or time.time(),
            dlc=len(can_message.data),
            source="can_interface"
        )
        
        # 메시지 검증
        if not self._validate_message(can_message):
            advanced_msg.status = MessageStatus.INVALID
            advanced_msg.error_message = "Message validation failed"
            return advanced_msg
        
        # 메시지 정의 확인
        if can_message.arbitration_id in self.message_definitions:
            message_def = self.message_definitions[can_message.arbitration_id]
            advanced_msg.message_name = message_def['message'].name
            advanced_msg.priority = message_def['priority']
            advanced_msg.cycle_time = message_def['cycle_time']
            
            # DLC 검증 및 처리
            if not self._handle_dlc_mismatch(advanced_msg, message_def):
                return advanced_msg
            
            # 신호 디코딩 - 강력한 오류 처리
            try:
                signals = self._decode_signals(message_def, advanced_msg.raw_data)
                advanced_msg.signals = signals
                advanced_msg.status = MessageStatus.VALID
                
                # 신호 검증 (경고만 출력, 상태는 유지)
                if self.config['signal_validation']:
                    self._validate_signals(advanced_msg, message_def)
                
                logger.debug(f"메시지 처리 완료 - ID: {advanced_msg.message_id}, 신호 수: {len(signals)}")
                
            except Exception as e:
                logger.error(f"신호 디코딩 중 예외 발생 - ID: {advanced_msg.message_id}, 오류: {e}")

                if self.config.get('use_default_on_decode_error', False):
                    # 최후의 수단: 기본값으로 신호 생성 (옵션)
                    try:
                        default_signals = self._create_default_signals(message_def)
                        advanced_msg.signals = default_signals
                        advanced_msg.status = MessageStatus.VALID
                        advanced_msg.error_message = f"Used default values due to: {e}"
                        logger.warning(f"기본값으로 처리 완료 - ID: {advanced_msg.message_id}")
                    except Exception as e2:
                        advanced_msg.status = MessageStatus.ERROR
                        advanced_msg.error_message = f"Complete decoding failure: {e2}"
                        self.stats['decoding_errors'] += 1
                        logger.error(f"완전한 디코딩 실패 - ID: {advanced_msg.message_id}, 오류: {e2}")
                else:
                    advanced_msg.status = MessageStatus.ERROR
                    advanced_msg.error_message = str(e)
                    self.stats['decoding_errors'] += 1
        
        else:
            # DBC에 정의가 없는 메시지: 최소 표시용 폴백 (옵션)
            if self.config.get('unknown_id_basic_signals', True):
                try:
                    basic_signals = {
                        'RawBytes': advanced_msg.raw_data.hex(),
                        'Length': len(advanced_msg.raw_data),
                    }
                    advanced_msg.signals = basic_signals
                    advanced_msg.status = MessageStatus.VALID
                except Exception as e:
                    advanced_msg.status = MessageStatus.ERROR
                    advanced_msg.error_message = f"Unknown ID handling failed: {e}"

        # 처리 시간 기록
        processing_time = time.time() - start_time
        advanced_msg.processing_time = processing_time
        self.processing_times.append(processing_time)
        
        # 통계 업데이트
        self.stats['total_messages'] += 1
        if advanced_msg.status == MessageStatus.VALID:
            self.stats['valid_messages'] += 1
        else:
            self.stats['invalid_messages'] += 1
        
        # 메시지 히스토리에 추가
        self.processed_messages.append(advanced_msg)
        
        # 콜백 실행
        self._execute_callbacks(advanced_msg)
        
        return advanced_msg
    
    def _validate_message(self, can_message: can.Message) -> bool:
        """메시지 기본 검증"""
        # DLC 범위 검사
        if not (self.validation_rules['dlc_range'][0] <= len(can_message.data) <= self.validation_rules['dlc_range'][1]):
            return False
        
        # 메시지 ID 범위 검사
        if not (self.validation_rules['message_id_range'][0] <= can_message.arbitration_id <= self.validation_rules['message_id_range'][1]):
            return False
        
        return True
    
    def _handle_dlc_mismatch(self, advanced_msg: AdvancedCanMessage, message_def: Dict) -> bool:
        """DLC 불일치 처리 - CAN FD 지원 강화"""
        expected_dlc = message_def['expected_dlc']  # bytes expected by DBC
        # 실제 데이터 길이는 payload 바이트 수로 판단 (CAN/CAN FD 모두 적용)
        actual_bytes = len(advanced_msg.raw_data)
        
        if actual_bytes != expected_dlc:
            self.stats['dlc_mismatches'] += 1
            logger.warning(f"DLC 불일치 감지 - ID: {advanced_msg.message_id}, 예상: {expected_dlc}바이트, 실제: {actual_bytes}바이트 (수신길이 기준)")
            
            # 강제로 DLC 조정하여 디코딩 성공 보장
            original_data = bytes(advanced_msg.raw_data)
            
            if actual_bytes < expected_dlc:
                # 패딩: 부족한 바이트를 0으로 채움
                padding_needed = expected_dlc - actual_bytes
                advanced_msg.raw_data += bytes(padding_needed)
                logger.info(f"데이터 패딩 완료 - ID: {advanced_msg.message_id}, {padding_needed}바이트 추가")
            else:
                # 자르기: 초과하는 바이트를 제거
                advanced_msg.raw_data = advanced_msg.raw_data[:expected_dlc]
                logger.info(f"데이터 자르기 완료 - ID: {advanced_msg.message_id}, {actual_bytes - expected_dlc}바이트 제거")
            
            # DLC 필드는 화면 표시에 사용: 기대 바이트 수로 동기화
            advanced_msg.dlc = expected_dlc
            
            # 디코딩 시도 전 데이터 검증
            if len(advanced_msg.raw_data) != expected_dlc:
                logger.error(f"DLC 조정 실패 - ID: {advanced_msg.message_id}")
                return False
            
            logger.info(f"DLC 조정 성공 - ID: {advanced_msg.message_id}, 최종 길이: {len(advanced_msg.raw_data)}바이트")
        
        return True
    
    def _bytes_to_can_fd_dlc(self, byte_count: int) -> int:
        """바이트 수를 CAN FD DLC로 변환"""
        if byte_count <= 15:
            return byte_count
        elif byte_count <= 20:
            return 16
        elif byte_count <= 24:
            return 17
        elif byte_count <= 32:
            return 18
        elif byte_count <= 48:
            return 19
        elif byte_count <= 64:
            return 20
        else:
            return 20  # 최대 DLC
    
    def _decode_signals(self, message_def: Dict, raw_data: bytes) -> Dict[str, Any]:
        """신호 디코딩 - 강력한 오류 처리"""
        message = message_def['message']
        
        try:
            # 1차 디코딩 시도
            signals = message.decode(raw_data)
            logger.debug(f"디코딩 성공 - ID: {message_def['message_id']}")
            
        except Exception as e:
            logger.warning(f"1차 디코딩 실패 - ID: {message_def['message_id']}, 오류: {e}")
            
            # 2차 시도: 데이터 길이 재조정
            try:
                expected_dlc = message_def['expected_dlc']
                if len(raw_data) != expected_dlc:
                    logger.info(f"데이터 길이 재조정 시도 - ID: {message_def['message_id']}")
                    
                    if len(raw_data) < expected_dlc:
                        # 패딩
                        adjusted_data = raw_data + bytes(expected_dlc - len(raw_data))
                    else:
                        # 자르기
                        adjusted_data = raw_data[:expected_dlc]
                    
                    signals = message.decode(adjusted_data)
                    logger.info(f"2차 디코딩 성공 - ID: {message_def['message_id']}")
                else:
                    raise e
                    
            except Exception as e2:
                logger.error(f"2차 디코딩도 실패 - ID: {message_def['message_id']}, 오류: {e2}")
                
                # 3차 시도: 기본값으로 채우기
                signals = self._create_default_signals(message_def)
                logger.warning(f"기본값으로 대체 - ID: {message_def['message_id']}")
        
        # 신호 값 검증 및 정규화
        validated_signals = {}
        for signal_name, value in signals.items():
            signal_def = message_def['signals'][signal_name]

            # 범위 검사 (경고만 출력, 디코딩은 계속). minimum/maximum가 None인 경우 비교하지 않음
            minimum_value = getattr(signal_def, 'minimum', None)
            maximum_value = getattr(signal_def, 'maximum', None)
            if minimum_value is not None and maximum_value is not None:
                try:
                    if not (minimum_value <= value <= maximum_value):
                        logger.warning(f"신호 범위 초과 - {signal_name}: {value} (범위: {minimum_value}~{maximum_value})")
                except TypeError:
                    # 값 타입이 비교 불가능한 경우 범위 검사를 건너뜀
                    pass

            validated_signals[signal_name] = value
        
        return validated_signals
    
    def _create_default_signals(self, message_def: Dict) -> Dict[str, Any]:
        """기본값으로 신호 생성"""
        default_signals = {}
        for signal_name, signal_def in message_def['signals'].items():
            if hasattr(signal_def, 'initial') and signal_def.initial is not None:
                default_signals[signal_name] = signal_def.initial
            elif hasattr(signal_def, 'minimum') and signal_def.minimum is not None:
                default_signals[signal_name] = signal_def.minimum
            else:
                default_signals[signal_name] = 0.0
        return default_signals
    
    def _validate_signals(self, advanced_msg: AdvancedCanMessage, message_def: Dict):
        """신호 값 검증"""
        for signal_name, value in advanced_msg.signals.items():
            signal_def = message_def['signals'][signal_name]
            
            # NaN 또는 무한대 값 검사
            if isinstance(value, (int, float)):
                if np.isnan(value) or np.isinf(value):
                    logger.warning(f"잘못된 신호 값 - {signal_name}: {value}")
                    advanced_msg.status = MessageStatus.ERROR
                    advanced_msg.error_message = f"Invalid signal value: {signal_name}"
                    break
    
    def _execute_callbacks(self, advanced_msg: AdvancedCanMessage):
        """등록된 콜백 함수들 실행"""
        callbacks = self.message_callbacks.get(advanced_msg.message_id, [])
        for callback in callbacks:
            try:
                callback(advanced_msg)
            except Exception as e:
                logger.error(f"콜백 실행 오류: {e}")
    
    def _update_statistics(self):
        """통계 정보 업데이트"""
        total = self.stats['total_messages']
        if total > 0:
            self.stats['success_rate'] = (self.stats['valid_messages'] / total) * 100
            self.stats['error_rate'] = (self.stats['invalid_messages'] / total) * 100
        
        # 평균 처리 시간 계산
        if self.processing_times:
            self.stats['average_processing_time'] = np.mean(list(self.processing_times))
    
    def _update_frequency_monitoring(self):
        """주파수 모니터링 업데이트"""
        if self.config['frequency_monitoring']:
            current_time = time.time()
            if current_time - self.last_frequency_reset >= 1.0:
                self.stats['messages_per_second'] = sum(self.message_frequency.values())
                self.message_frequency.clear()
                self.last_frequency_reset = current_time
    
    def register_callback(self, message_id: int, callback: Callable[[AdvancedCanMessage], None]):
        """메시지 콜백 등록"""
        self.message_callbacks[message_id].append(callback)
        logger.info(f"콜백 등록 - Message ID: {message_id}")
    
    def unregister_callback(self, message_id: int, callback: Callable[[AdvancedCanMessage], None]):
        """메시지 콜백 해제"""
        if callback in self.message_callbacks[message_id]:
            self.message_callbacks[message_id].remove(callback)
            logger.info(f"콜백 해제 - Message ID: {message_id}")
    
    def get_message_history(self, message_id: Optional[int] = None, limit: int = 100) -> List[AdvancedCanMessage]:
        """메시지 히스토리 조회"""
        if message_id is None:
            return list(self.processed_messages)[-limit:]
        else:
            return [msg for msg in self.processed_messages if msg.message_id == message_id][-limit:]
    
    def get_signal_history(self, signal_name: str, limit: int = 100) -> List[Tuple[float, Any]]:
        """신호 히스토리 조회"""
        history = []
        for msg in self.processed_messages:
            if signal_name in msg.signals:
                history.append((msg.timestamp, msg.signals[signal_name]))
        return history[-limit:]
    
    def get_statistics(self) -> Dict:
        """통계 정보 반환"""
        return self.stats.copy()
    
    def get_message_definitions(self) -> Dict:
        """메시지 정의 반환"""
        return self.message_definitions.copy()
    
    def get_signal_definitions(self) -> Dict:
        """신호 정의 반환"""
        return self.signal_definitions.copy()
    
    def shutdown(self):
        """프로세서 종료"""
        self.running = False
        if self.processing_thread:
            self.processing_thread.join(timeout=1)
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=1)
        logger.info("TSMaster CAN 프로세서 종료")


# 사용 예시
if __name__ == "__main__":
    # TSMaster 스타일 프로세서 테스트
    processor = TSMasterCanProcessor("candb_ex.dbc")
    
    # 콜백 등록 예시
    def radar_callback(message: AdvancedCanMessage):
        print(f"레이더 데이터 수신: {message.message_name}, 신호: {message.signals}")
    
    processor.register_callback(200, radar_callback)
    
    # 테스트 메시지 처리
    test_msg = can.Message(arbitration_id=200, data=[0, 100, 0, 50, 0, 20, 0, 10], is_extended_id=False)
    result = processor.process_message(test_msg)
    
    print(f"처리 결과: {result.status}, 신호: {result.signals}")
    print(f"통계: {processor.get_statistics()}")
    
    processor.shutdown()
