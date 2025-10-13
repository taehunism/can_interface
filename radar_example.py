"""
레이더 데이터를 직접 변수로 활용하는 예제
Windows CAN 인터페이스에서 레이더 데이터를 실시간으로 처리하는 방법을 보여줍니다.
"""

import time
import sys
from radar_data import RadarDataManager, RadarObject


def radar_data_example():
    """레이더 데이터 활용 예제"""
    print("=== 레이더 데이터 활용 예제 ===")
    
    # RadarDataManager 인스턴스 생성
    radar_manager = RadarDataManager()
    
    # 시뮬레이션 데이터 생성 (실제로는 CAN에서 받아옴)
    print("시뮬레이션 레이더 데이터 생성...")
    
    # 5개의 레이더 객체 데이터 시뮬레이션
    for i in range(1, 6):
        import random
        
        # 랜덤 데이터 생성
        rel_pos_x = random.uniform(-100, 100)
        rel_pos_y = random.uniform(-50, 50)
        rel_vel_x = random.uniform(-20, 20)
        rel_acc_x = random.uniform(-5, 5)
        
        # 레이더 객체 업데이트
        radar_manager.update_object(
            object_id=i,
            rel_pos_x=rel_pos_x,
            rel_pos_y=rel_pos_y,
            rel_vel_x=rel_vel_x,
            rel_acc_x=rel_acc_x,
            timestamp=time.time()
        )
    
    print("\n=== 레이더 데이터 분석 ===")
    
    # 1. 가장 가까운 객체 정보
    print(f"가장 가까운 객체 거리: {radar_manager.closest_distance:.2f}m")
    if radar_manager.closest_object:
        print(f"가장 가까운 객체 ID: {radar_manager.closest_object.object_id}")
        print(f"가장 가까운 객체 각도: {radar_manager.closest_object.angle:.1f}도")
    
    # 2. 객체 개수
    print(f"총 객체 개수: {radar_manager.object_count}")
    
    # 3. 모든 객체 정보 출력
    print("\n=== 모든 레이더 객체 정보 ===")
    all_objects = radar_manager.get_all_objects()
    for obj in all_objects:
        print(f"객체 {obj.object_id}: 거리={obj.distance:.2f}m, "
              f"각도={obj.angle:.1f}도, "
              f"속도={obj.rel_vel_x:.2f}m/s")
    
    # 4. 거리 범위별 객체 필터링
    print("\n=== 거리 범위별 객체 필터링 ===")
    close_objects = radar_manager.get_objects_in_range(0, 30)  # 0-30m
    print(f"30m 이내 객체 수: {len(close_objects)}")
    
    far_objects = radar_manager.get_objects_in_range(30, 100)  # 30-100m
    print(f"30-100m 범위 객체 수: {len(far_objects)}")
    
    # 5. 각도 범위별 객체 필터링
    print("\n=== 각도 범위별 객체 필터링 ===")
    front_objects = radar_manager.get_objects_in_angle_range(-30, 30)  # 정면 ±30도
    print(f"정면 ±30도 범위 객체 수: {len(front_objects)}")
    
    side_objects = radar_manager.get_objects_in_angle_range(30, 150)  # 측면
    print(f"측면 객체 수: {len(side_objects)}")
    
    # 6. 속도 범위별 객체 필터링
    print("\n=== 속도 범위별 객체 필터링 ===")
    fast_objects = radar_manager.get_objects_by_velocity(10, 50)  # 10-50 m/s
    print(f"빠른 객체 수 (10-50 m/s): {len(fast_objects)}")
    
    slow_objects = radar_manager.get_objects_by_velocity(-10, 10)  # -10-10 m/s
    print(f"느린 객체 수 (-10-10 m/s): {len(slow_objects)}")
    
    # 7. 요약 정보
    print("\n=== 레이더 데이터 요약 ===")
    summary = radar_manager.get_summary()
    for key, value in summary.items():
        print(f"{key}: {value}")


def real_time_radar_monitoring():
    """실시간 레이더 모니터링 예제"""
    print("\n=== 실시간 레이더 모니터링 예제 ===")
    print("Ctrl+C로 종료하세요.")
    
    radar_manager = RadarDataManager()
    
    try:
        while True:
            # 실제로는 여기서 CAN 메시지를 받아서 처리
            # 시뮬레이션을 위해 랜덤 데이터 생성
            import random
            
            # 기존 객체들 업데이트 (일부만)
            for i in range(1, 4):
                if random.random() > 0.3:  # 70% 확률로 업데이트
                    rel_pos_x = random.uniform(-100, 100)
                    rel_pos_y = random.uniform(-50, 50)
                    rel_vel_x = random.uniform(-20, 20)
                    rel_acc_x = random.uniform(-5, 5)
                    
                    radar_manager.update_object(
                        object_id=i,
                        rel_pos_x=rel_pos_x,
                        rel_pos_y=rel_pos_y,
                        rel_vel_x=rel_vel_x,
                        rel_acc_x=rel_acc_x,
                        timestamp=time.time()
                    )
            
            # 오래된 객체 정리
            radar_manager.clear_old_objects(max_age=1.0)
            
            # 현재 상태 출력
            print(f"\r객체 수: {radar_manager.object_count}, "
                  f"가장 가까운 거리: {radar_manager.closest_distance:.2f}m", end="")
            
            time.sleep(0.5)
            
    except KeyboardInterrupt:
        print("\n모니터링 종료")


def custom_radar_analysis():
    """사용자 정의 레이더 분석 예제"""
    print("\n=== 사용자 정의 레이더 분석 예제 ===")
    
    radar_manager = RadarDataManager()
    
    # 테스트 데이터 생성
    test_objects = [
        (1, 25.5, 10.2, 15.0, 2.0),  # ID, X, Y, Vel, Acc
        (2, 45.0, -20.0, -5.0, -1.0),
        (3, 80.0, 30.0, 25.0, 3.0),
        (4, 15.0, 5.0, 8.0, 0.5),
        (5, 60.0, -15.0, 12.0, 1.5),
    ]
    
    for obj_id, x, y, vel, acc in test_objects:
        radar_manager.update_object(obj_id, x, y, vel, acc, time.time())
    
    # 사용자 정의 분석 함수들
    def find_dangerous_objects(radar_manager, min_distance=20, max_speed=30):
        """위험한 객체 찾기 (가까우면서 빠른 객체)"""
        dangerous = []
        for obj in radar_manager.get_all_objects():
            if obj.distance <= min_distance and abs(obj.rel_vel_x) >= max_speed:
                dangerous.append(obj)
        return dangerous
    
    def find_lane_changing_objects(radar_manager, min_lateral_speed=5):
        """차선 변경 객체 찾기 (측면 속도가 큰 객체)"""
        lane_changing = []
        for obj in radar_manager.get_all_objects():
            # 측면 속도 계산 (Y 방향 속도)
            lateral_speed = abs(obj.rel_vel_x * 0.1)  # 간단한 근사
            if lateral_speed >= min_lateral_speed:
                lane_changing.append(obj)
        return lane_changing
    
    # 분석 실행
    print("위험한 객체 (20m 이내, 30m/s 이상):")
    dangerous = find_dangerous_objects(radar_manager)
    for obj in dangerous:
        print(f"  객체 {obj.object_id}: 거리={obj.distance:.1f}m, 속도={obj.rel_vel_x:.1f}m/s")
    
    print("\n차선 변경 가능한 객체:")
    lane_changing = find_lane_changing_objects(radar_manager)
    for obj in lane_changing:
        print(f"  객체 {obj.object_id}: 거리={obj.distance:.1f}m, 각도={obj.angle:.1f}도")


if __name__ == "__main__":
    print("레이더 데이터 활용 예제 프로그램")
    print("=" * 50)
    
    # 기본 예제 실행
    radar_data_example()
    
    # 사용자 정의 분석 예제 실행
    custom_radar_analysis()
    
    # 실시간 모니터링 예제 (선택사항)
    print("\n실시간 모니터링을 시작하시겠습니까? (y/n): ", end="")
    if input().lower() == 'y':
        real_time_radar_monitoring()
    
    print("\n프로그램 종료")
