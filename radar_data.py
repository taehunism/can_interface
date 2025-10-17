"""
레이더 데이터 객체를 관리하는 클래스
Windows CAN 인터페이스에서 레이더 데이터를 직접 변수로 활용할 수 있도록 함
"""

import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class RadarObject:
    """단일 레이더 객체의 데이터를 저장하는 클래스"""
    object_id: int
    rel_pos_x: float  # 상대 위치 X (미터)
    rel_pos_y: float  # 상대 위치 Y (미터)
    rel_vel_x: float  # 상대 속도 X (m/s)
    rel_acc_x: float  # 상대 가속도 X (m/s²)
    timestamp: float  # 타임스탬프
    distance: float = 0.0   # 거리 (미터) - 계산된 값
    angle: float = 0.0      # 각도 (도) - 계산된 값
    
    def __post_init__(self):
        """거리와 각도를 자동 계산"""
        self.distance = (self.rel_pos_x**2 + self.rel_pos_y**2)**0.5
        self.angle = self._calculate_angle()
    
    def _calculate_angle(self) -> float:
        """각도 계산 (라디안을 도로 변환)"""
        import math
        if self.rel_pos_x == 0 and self.rel_pos_y == 0:
            return 0.0
        return math.degrees(math.atan2(self.rel_pos_y, self.rel_pos_x))
    
    def is_valid(self) -> bool:
        """객체 데이터가 유효한지 확인"""
        return (self.distance > 0 and 
                abs(self.rel_pos_x) <= 1000 and 
                abs(self.rel_pos_y) <= 1000)


class RadarDataManager:
    """레이더 데이터를 관리하고 직접 변수로 활용할 수 있게 하는 클래스"""
    
    def __init__(self, max_objects: int = 10):
        self.max_objects = max_objects
        self.radar_objects: Dict[int, RadarObject] = {}
        self.object_history: List[RadarObject] = []
        self.max_history = 1000
        
        # 직접 접근 가능한 변수들
        self.closest_object: Optional[RadarObject] = None
        self.closest_distance: float = float('inf')
        self.object_count: int = 0
        self.last_update_time: float = 0.0
        
    def update_object(self, object_id: int, rel_pos_x: float, rel_pos_y: float, 
                     rel_vel_x: float, rel_acc_x: float, timestamp: float = None) -> None:
        """레이더 객체 데이터 업데이트"""
        if timestamp is None:
            timestamp = time.time()
            
        # 새로운 객체 생성
        radar_obj = RadarObject(
            object_id=object_id,
            rel_pos_x=rel_pos_x,
            rel_pos_y=rel_pos_y,
            rel_vel_x=rel_vel_x,
            rel_acc_x=rel_acc_x,
            timestamp=timestamp
        )
        
        # 유효성 검사
        if not radar_obj.is_valid():
            return
            
        # 객체 저장
        self.radar_objects[object_id] = radar_obj
        self.object_history.append(radar_obj)
        
        # 히스토리 크기 제한
        if len(self.object_history) > self.max_history:
            self.object_history = self.object_history[-self.max_history:]
        
        # 직접 변수 업데이트
        self._update_direct_variables()
        self.last_update_time = timestamp
    
    def _update_direct_variables(self) -> None:
        """직접 접근 가능한 변수들을 업데이트"""
        if not self.radar_objects:
            self.closest_object = None
            self.closest_distance = float('inf')
            self.object_count = 0
            return
            
        # 가장 가까운 객체 찾기
        self.closest_object = min(self.radar_objects.values(), 
                                key=lambda obj: obj.distance)
        self.closest_distance = self.closest_object.distance
        self.object_count = len(self.radar_objects)
    
    def get_object_by_id(self, object_id: int) -> Optional[RadarObject]:
        """ID로 특정 객체 가져오기"""
        return self.radar_objects.get(object_id)
    
    def get_objects_in_range(self, min_distance: float, max_distance: float) -> List[RadarObject]:
        """거리 범위 내의 객체들 반환"""
        return [obj for obj in self.radar_objects.values() 
                if min_distance <= obj.distance <= max_distance]
    
    def get_objects_in_angle_range(self, min_angle: float, max_angle: float) -> List[RadarObject]:
        """각도 범위 내의 객체들 반환"""
        return [obj for obj in self.radar_objects.values() 
                if min_angle <= obj.angle <= max_angle]
    
    def get_objects_by_velocity(self, min_vel: float, max_vel: float) -> List[RadarObject]:
        """속도 범위 내의 객체들 반환"""
        return [obj for obj in self.radar_objects.values() 
                if min_vel <= obj.rel_vel_x <= max_vel]
    
    def clear_old_objects(self, max_age: float = 1.0) -> None:
        """오래된 객체들 제거 (초 단위)"""
        current_time = time.time()
        to_remove = []
        
        for obj_id, obj in self.radar_objects.items():
            if current_time - obj.timestamp > max_age:
                to_remove.append(obj_id)
        
        for obj_id in to_remove:
            del self.radar_objects[obj_id]
        
        if to_remove:
            self._update_direct_variables()
    
    def get_summary(self) -> Dict:
        """현재 상태 요약 반환"""
        return {
            'object_count': self.object_count,
            'closest_distance': self.closest_distance,
            'closest_object_id': self.closest_object.object_id if self.closest_object else None,
            'last_update_time': self.last_update_time,
            'valid_objects': [obj.object_id for obj in self.radar_objects.values() if obj.is_valid()]
        }
    
    def get_all_objects(self) -> List[RadarObject]:
        """모든 유효한 객체들 반환"""
        return [obj for obj in self.radar_objects.values() if obj.is_valid()]


# 사용 예시를 위한 헬퍼 함수들
def create_radar_manager() -> RadarDataManager:
    """RadarDataManager 인스턴스 생성"""
    return RadarDataManager()

def get_radar_data_variables(radar_manager: RadarDataManager) -> Dict:
    """레이더 데이터를 직접 변수로 활용할 수 있는 딕셔너리 반환"""
    return {
        'closest_distance': radar_manager.closest_distance,
        'object_count': radar_manager.object_count,
        'closest_object': radar_manager.closest_object,
        'all_objects': radar_manager.get_all_objects(),
        'summary': radar_manager.get_summary()
    }
