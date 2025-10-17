#!/usr/bin/env python3
"""
CAN FD 데이터 처리 테스트 스크립트
최대 64바이트까지의 CAN FD 메시지를 생성하여 처리 테스트
"""

import can
import time
from tsmaster_can_processor import TSMasterCanProcessor

def test_can_fd():
    """CAN FD 데이터 처리 테스트"""
    print("=== CAN FD 데이터 처리 테스트 시작 ===")
    
    # TSMaster 프로세서 초기화
    processor = TSMasterCanProcessor("candb_ex.dbc")
    
    # CAN FD DLC 매핑 테스트
    print("\n--- CAN FD DLC 매핑 테스트 ---")
    can_fd_dlc_mapping = {
        0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 7, 8: 8,
        9: 9, 10: 10, 11: 11, 12: 12, 13: 13, 14: 14, 15: 15,
        16: 20, 17: 24, 18: 32, 19: 48, 20: 64
    }
    
    for dlc, expected_bytes in can_fd_dlc_mapping.items():
        print(f"DLC {dlc:2d} -> {expected_bytes:2d} 바이트")
    
    # 테스트용 CAN FD 메시지 생성
    test_messages = []
    
    # 1. 일반 CAN 메시지 (8바이트)
    msg_8byte = can.Message(arbitration_id=100, data=bytes(range(8)), is_extended_id=False)
    test_messages.append(("일반 CAN (8바이트)", msg_8byte, 8))
    
    # 2. CAN FD 메시지들 (다양한 길이)
    test_lengths = [12, 16, 20, 24, 32, 48, 64]
    
    for length in test_lengths:
        # 100번 ID로 테스트 (8바이트 예상)
        data = bytes(range(length))
        msg = can.Message(arbitration_id=100, data=data, is_extended_id=False)
        test_messages.append((f"CAN FD {length}바이트", msg, length))
        
        # 200번 ID로 테스트 (8바이트 예상)
        msg_radar = can.Message(arbitration_id=200, data=data, is_extended_id=False)
        test_messages.append((f"레이더 CAN FD {length}바이트", msg_radar, length))
    
    # 3. 극한 길이 테스트
    msg_65byte = can.Message(arbitration_id=100, data=bytes(range(65)), is_extended_id=False)
    test_messages.append(("극한 길이 (65바이트)", msg_65byte, 65))
    
    # 각 메시지 처리 테스트
    success_count = 0
    total_count = len(test_messages)
    
    print(f"\n--- CAN FD 메시지 처리 테스트 ---")
    print(f"총 테스트 메시지: {total_count}개")
    
    for test_name, msg, original_length in test_messages:
        print(f"\n--- {test_name} 테스트 ---")
        print(f"원본 데이터 길이: {original_length} 바이트")
        
        try:
            # 메시지 처리
            result = processor.process_message(msg)
            
            print(f"처리 결과: {result.status.value}")
            print(f"최종 DLC: {result.dlc}")
            print(f"최종 데이터 길이: {len(result.raw_data)} 바이트")
            print(f"디코딩된 신호 수: {len(result.signals)}")
            
            if result.signals:
                print("디코딩된 신호들:")
                for sig_name, value in result.signals.items():
                    print(f"  {sig_name}: {value}")
            
            if result.status.value == "valid":
                success_count += 1
                print("[SUCCESS] 디코딩 성공!")
            else:
                print(f"[FAIL] 디코딩 실패: {result.error_message}")
                
        except Exception as e:
            print(f"[ERROR] 처리 중 오류 발생: {e}")
    
    # 결과 요약
    print(f"\n=== 테스트 결과 요약 ===")
    print(f"총 테스트: {total_count}")
    print(f"성공: {success_count}")
    print(f"실패: {total_count - success_count}")
    print(f"성공률: {success_count/total_count*100:.1f}%")
    
    # 통계 정보
    stats = processor.get_statistics()
    print(f"\n=== 처리 통계 ===")
    print(f"총 메시지: {stats['total_messages']}")
    print(f"유효 메시지: {stats['valid_messages']}")
    print(f"무효 메시지: {stats['invalid_messages']}")
    print(f"DLC 불일치: {stats['dlc_mismatches']}")
    print(f"디코딩 오류: {stats.get('decoding_errors', 0)}")
    
    processor.shutdown()
    print("\n=== CAN FD 테스트 완료 ===")

def test_can_fd_dlc_conversion():
    """CAN FD DLC 변환 테스트"""
    print("\n=== CAN FD DLC 변환 테스트 ===")
    
    processor = TSMasterCanProcessor("candb_ex.dbc")
    
    test_cases = [
        (0, 0), (1, 1), (8, 8), (15, 15),
        (16, 20), (17, 24), (18, 32), (19, 48), (20, 64),
        (25, 20), (30, 20), (40, 20), (50, 20), (64, 20)
    ]
    
    for byte_count, expected_dlc in test_cases:
        actual_dlc = processor._bytes_to_can_fd_dlc(byte_count)
        status = "OK" if actual_dlc == expected_dlc else "NG"
        print(f"{status} {byte_count:2d} 바이트 -> DLC {actual_dlc:2d} (예상: {expected_dlc:2d})")
    
    processor.shutdown()

if __name__ == "__main__":
    test_can_fd()
    test_can_fd_dlc_conversion()
