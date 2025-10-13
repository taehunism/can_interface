#!/usr/bin/env python3
"""
CAN 인터페이스 테스트 프로그램
"""

import can
import time
import threading

def test_can_interface():
    """CAN 인터페이스 테스트"""
    print("=== CAN 인터페이스 테스트 ===")
    
    # 사용 가능한 인터페이스 확인
    try:
        configs = can.interface.detect_available_configs()
        print("사용 가능한 CAN 인터페이스:")
        for config in configs:
            print(f"  - {config}")
    except Exception as e:
        print(f"인터페이스 확인 오류: {e}")
        return
    
    # Virtual CAN 연결 시도
    try:
        print("\nVirtual CAN 연결 시도...")
        virtual_configs = [c for c in configs if c.get('interface') == 'virtual']
        
        if virtual_configs:
            channel = virtual_configs[0]['channel']
            print(f"Virtual CAN 채널 사용: {channel}")
        else:
            channel = 'channel-0'
            print(f"기본 Virtual CAN 채널 사용: {channel}")
        
        bus = can.interface.Bus(
            channel=channel,
            interface='virtual',
            bitrate=500000
        )
        print("Virtual CAN 연결 성공!")
        
        # 메시지 전송 테스트
        print("\n메시지 전송 테스트...")
        for i in range(5):
            msg = can.Message(
                arbitration_id=100 + i,
                data=[i, i+1, i+2, i+3, i+4, i+5, i+6, i+7],
                is_extended_id=False
            )
            bus.send(msg)
            print(f"전송: ID={100+i}, Data={[i, i+1, i+2, i+3, i+4, i+5, i+6, i+7]}")
            time.sleep(0.1)
        
        # 메시지 수신 테스트
        print("\n메시지 수신 테스트...")
        received_count = 0
        start_time = time.time()
        
        while received_count < 5 and (time.time() - start_time) < 5:
            msg = bus.recv(timeout=1)
            if msg:
                print(f"수신: ID={msg.arbitration_id}, Data={list(msg.data)}")
                received_count += 1
        
        print(f"수신된 메시지: {received_count}개")
        
        bus.shutdown()
        print("CAN 인터페이스 테스트 완료!")
        
    except Exception as e:
        print(f"CAN 인터페이스 테스트 실패: {e}")

if __name__ == "__main__":
    test_can_interface()
