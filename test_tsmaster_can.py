#!/usr/bin/env python3
"""
TSMaster 스타일 CAN 데이터 처리 테스트 프로그램
"""

import can
import time
import numpy as np
from tsmaster_can_processor import TSMasterCanProcessor, AdvancedCanMessage, MessageStatus, MessagePriority

def test_tsmaster_processor():
    """TSMaster 스타일 프로세서 테스트"""
    print("=== TSMaster 스타일 CAN 프로세서 테스트 ===")
    
    # 프로세서 초기화
    processor = TSMasterCanProcessor("candb_ex.dbc")
    
    # 콜백 함수 정의
    def radar_callback(message: AdvancedCanMessage):
        print(f"레이더 콜백 - ID: {message.message_id}, 신호: {message.signals}")
    
    def vehicle_callback(message: AdvancedCanMessage):
        print(f"차량 콜백 - ID: {message.message_id}, 신호: {message.signals}")
    
    # 콜백 등록
    processor.register_callback(200, radar_callback)
    processor.register_callback(100, vehicle_callback)
    
    # 테스트 메시지들
    test_messages = [
        # 정상적인 차량 상태 메시지
        can.Message(arbitration_id=100, data=[0x00, 0x64, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00], is_extended_id=False),
        
        # DLC 불일치 메시지 (4바이트)
        can.Message(arbitration_id=100, data=[0x00, 0x64, 0x00, 0x00], is_extended_id=False),
        
        # 레이더 데이터 메시지
        can.Message(arbitration_id=200, data=[0x00, 0x64, 0x00, 0x32, 0x00, 0x14, 0x00, 0x0A], is_extended_id=False),
        
        # 잘못된 메시지 ID
        can.Message(arbitration_id=999, data=[0x01, 0x02, 0x03, 0x04], is_extended_id=False),
        
        # DLC 초과 메시지
        can.Message(arbitration_id=101, data=[0x00, 0x64, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00], is_extended_id=False),
    ]
    
    print("\n=== 메시지 처리 테스트 ===")
    for i, msg in enumerate(test_messages):
        print(f"\n--- 테스트 {i+1} ---")
        print(f"원본: ID={msg.arbitration_id}, DLC={len(msg.data)}")
        
        result = processor.process_message(msg)
        print(f"결과: 상태={result.status.value}, 이름={result.message_name}")
        print(f"우선순위={result.priority.name}, 처리시간={result.processing_time*1000:.2f}ms")
        
        if result.status == MessageStatus.VALID:
            print(f"신호: {result.signals}")
        else:
            print(f"오류: {result.error_message}")
    
    # 통계 정보
    print(f"\n=== 통계 정보 ===")
    stats = processor.get_statistics()
    for key, value in stats.items():
        print(f"{key}: {value}")
    
    # 메시지 히스토리
    print(f"\n=== 메시지 히스토리 ===")
    history = processor.get_message_history(limit=5)
    for msg in history:
        print(f"ID: {msg.message_id}, 상태: {msg.status.value}, 시간: {msg.timestamp:.3f}")
    
    # 신호 히스토리
    print(f"\n=== 신호 히스토리 (VehicleSpeed) ===")
    signal_history = processor.get_signal_history("VehicleSpeed", limit=3)
    for timestamp, value in signal_history:
        print(f"시간: {timestamp:.3f}, 값: {value}")
    
    # 프로세서 종료
    processor.shutdown()
    print("\nTSMaster 프로세서 테스트 완료!")

def test_performance():
    """성능 테스트"""
    print("\n=== 성능 테스트 ===")
    
    processor = TSMasterCanProcessor("candb_ex.dbc")
    
    # 대량 메시지 처리 테스트
    start_time = time.time()
    message_count = 1000
    
    for i in range(message_count):
        # 랜덤 레이더 데이터 생성
        msg_id = 200 + (i % 10)
        data = [i & 0xFF, (i >> 8) & 0xFF, (i*2) & 0xFF, ((i*2) >> 8) & 0xFF,
                (i*3) & 0xFF, ((i*3) >> 8) & 0xFF, (i*4) & 0xFF, ((i*4) >> 8) & 0xFF]
        
        msg = can.Message(arbitration_id=msg_id, data=data, is_extended_id=False)
        processor.process_message(msg)
    
    end_time = time.time()
    processing_time = end_time - start_time
    
    print(f"처리된 메시지: {message_count}")
    print(f"총 처리 시간: {processing_time:.3f}초")
    print(f"초당 처리량: {message_count/processing_time:.0f} msg/s")
    
    # 최종 통계
    stats = processor.get_statistics()
    print(f"성공률: {stats.get('success_rate', 0):.1f}%")
    print(f"평균 처리 시간: {stats.get('average_processing_time', 0)*1000:.2f}ms")
    
    processor.shutdown()

if __name__ == "__main__":
    print("TSMaster 스타일 CAN 데이터 처리 테스트 시작")
    print("=" * 60)
    
    try:
        test_tsmaster_processor()
        test_performance()
        
        print("\n" + "=" * 60)
        print("모든 테스트 완료!")
        
    except Exception as e:
        print(f"테스트 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()
