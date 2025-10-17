#!/usr/bin/env python3
"""
DLC 불일치 처리 테스트 스크립트
다양한 DLC 길이의 CAN 메시지를 생성하여 강력한 디코딩이 작동하는지 테스트
"""

import can
import time
from tsmaster_can_processor import TSMasterCanProcessor

def test_dlc_mismatch():
    """DLC 불일치 처리 테스트"""
    print("=== DLC 불일치 처리 테스트 시작 ===")
    
    # TSMaster 프로세서 초기화
    processor = TSMasterCanProcessor("candb_ex.dbc")
    
    # 테스트용 CAN 메시지 생성
    test_messages = []
    
    # 1. 정상 길이 메시지 (8바이트)
    msg_normal = can.Message(arbitration_id=100, data=bytes([0x10, 0x20, 0x30, 0x40, 0x50, 0x60, 0x70, 0x80]), is_extended_id=False)
    test_messages.append(("정상 길이 (8바이트)", msg_normal))
    
    # 2. 짧은 메시지 (4바이트)
    msg_short = can.Message(arbitration_id=100, data=bytes([0x10, 0x20, 0x30, 0x40]), is_extended_id=False)
    test_messages.append(("짧은 메시지 (4바이트)", msg_short))
    
    # 3. 긴 메시지 (12바이트)
    msg_long = can.Message(arbitration_id=100, data=bytes([0x10, 0x20, 0x30, 0x40, 0x50, 0x60, 0x70, 0x80, 0x90, 0xA0, 0xB0, 0xC0]), is_extended_id=False)
    test_messages.append(("긴 메시지 (12바이트)", msg_long))
    
    # 4. 빈 메시지 (0바이트)
    msg_empty = can.Message(arbitration_id=100, data=bytes(), is_extended_id=False)
    test_messages.append(("빈 메시지 (0바이트)", msg_empty))
    
    # 5. 레이더 메시지 테스트 (다양한 길이)
    for i in range(200, 203):  # ID 200, 201, 202
        # 짧은 레이더 메시지 (4바이트)
        msg_radar_short = can.Message(arbitration_id=i, data=bytes([0x10, 0x20, 0x30, 0x40]), is_extended_id=False)
        test_messages.append((f"레이더 메시지 {i} (4바이트)", msg_radar_short))
        
        # 긴 레이더 메시지 (12바이트)
        msg_radar_long = can.Message(arbitration_id=i, data=bytes([0x10, 0x20, 0x30, 0x40, 0x50, 0x60, 0x70, 0x80, 0x90, 0xA0, 0xB0, 0xC0]), is_extended_id=False)
        test_messages.append((f"레이더 메시지 {i} (12바이트)", msg_radar_long))
    
    # 각 메시지 처리 테스트
    success_count = 0
    total_count = len(test_messages)
    
    for test_name, msg in test_messages:
        print(f"\n--- {test_name} 테스트 ---")
        print(f"원본 데이터 길이: {len(msg.data)} 바이트")
        
        try:
            # 메시지 처리
            result = processor.process_message(msg)
            
            print(f"처리 결과: {result.status.value}")
            print(f"최종 DLC: {result.dlc}")
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
    print("\n=== 테스트 완료 ===")

if __name__ == "__main__":
    test_dlc_mismatch()
