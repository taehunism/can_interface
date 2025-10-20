"""
카메라 projection을 위한 예제 파일
CAN 인터페이스에서 받은 레이더 데이터를 카메라 픽셀 좌표계로 변환
"""

import cv2
import numpy as np
import time
from can_interface import CanDataViewer

class CameraProjectionProcessor:
    def __init__(self, can_viewer):
        """
        Args:
            can_viewer: CanDataViewer 인스턴스
        """
        self.can_viewer = can_viewer
        
        # 카메라 내부 파라미터 (실제 카메라에 맞게 조정 필요)
        # 일반적인 카메라 해상도: 640x480 또는 1280x720
        self.camera_matrix = np.array([
            [800, 0, 320],      # fx, 0, cx (640x480 기준)
            [0, 800, 240],      # 0, fy, cy
            [0, 0, 1]           # 0, 0, 1
        ])
        
        # 카메라 해상도 (픽셀)
        self.image_width = 640
        self.image_height = 480
        
        # 카메라-레이더 외부 파라미터 (실제 설치에 맞게 조정 필요)
        self.rotation_matrix = np.eye(3)  # 회전 행렬
        self.translation_vector = np.array([0, 0, 0])  # 이동 벡터
        
    def radar_to_camera_coords(self, radar_x, radar_y):
        """
        레이더 좌표를 카메라 픽셀 좌표로 변환
        수식: u = (f_x * X_r) / Z_r + c_x, v = (f_y * Y_r) / Z_r + c_y
        
        Args:
            radar_x: 레이더 상대위치 X (X_rel)
            radar_y: 레이더 상대위치 Y (Y_rel)
        Returns:
            u, v: 카메라 픽셀 좌표
        """
        # 1. 레이더 상대위치 데이터
        X_rel = radar_x
        Y_rel = radar_y
        
        # 2. 외부 파라미터 적용 (레이더 -> 카메라)
        # X_r = R * X_rel + T
        # Y_r = R * Y_rel + T
        radar_point = np.array([X_rel, Y_rel, 0])  # Z=0으로 가정
        camera_3d = self.rotation_matrix @ radar_point + self.translation_vector
        
        X_r = camera_3d[0]  # 카메라 좌표계 X
        Y_r = camera_3d[1]  # 카메라 좌표계 Y
        Z_r = camera_3d[2]  # 카메라 좌표계 Z
        
        # Z_r이 0에 가까우면 피타고라스로 계산
        if abs(Z_r) < 1e-6:
            Z_r = np.sqrt(X_rel**2 + Y_rel**2)
        
        # 3. 내부 파라미터로 픽셀 좌표 계산
        # u = (f_x * X_r) / Z_r + c_x
        # v = (f_y * Y_r) / Z_r + c_y
        f_x = self.camera_matrix[0, 0]  # fx
        f_y = self.camera_matrix[1, 1]  # fy
        c_x = self.camera_matrix[0, 2]  # cx
        c_y = self.camera_matrix[1, 2]  # cy
        
        u = (f_x * X_r) / Z_r + c_x
        v = (f_y * Y_r) / Z_r + c_y
        
        # 픽셀 좌표가 이미지 범위 내에 있는지 확인
        u = max(0, min(int(u), self.image_width - 1))
        v = max(0, min(int(v), self.image_height - 1))
        
        return u, v
    
    def draw_point_on_camera(self, pixel_x, pixel_y, obj_id, image=None):
        """
        카메라 이미지에 객체 점 그리기
        Args:
            pixel_x, pixel_y: 픽셀 좌표
            obj_id: 객체 ID
            image: OpenCV 이미지 (None이면 새로 생성)
        Returns:
            image: 점이 그려진 이미지
        """
        if image is None:
            # 빈 이미지 생성 (검은 배경)
            image = np.zeros((self.image_height, self.image_width, 3), dtype=np.uint8)
        
        # 객체 ID에 따라 다른 색상 사용
        colors = [
            (0, 255, 0),    # 녹색
            (255, 0, 0),    # 파란색
            (0, 0, 255),    # 빨간색
            (255, 255, 0),  # 청록색
            (255, 0, 255),  # 자홍색
            (0, 255, 255),  # 노란색
        ]
        color = colors[obj_id % len(colors)]
        
        # 원 그리기 (중심점)
        cv2.circle(image, (pixel_x, pixel_y), 5, color, -1)
        
        # 객체 ID 텍스트 표시
        cv2.putText(image, f"ID:{obj_id}", 
                   (pixel_x + 10, pixel_y - 10), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        
        return image
    
    def process_realtime_projection(self):
        """실시간 projection 처리"""
        while True:
            try:
                # CH1에서 CIPV 데이터 가져오기
                cipv_data = self.can_viewer.get_cipv_projection_data("CH1")
                
                if cipv_data["valid"]:
                    radar_x = cipv_data["x"]
                    radar_y = cipv_data["y"]
                    obj_id = cipv_data["obj_id"]
                    timestamp = cipv_data["timestamp"]
                    
                    # 카메라 픽셀 좌표로 변환
                    pixel_x, pixel_y = self.radar_to_camera_coords(radar_x, radar_y)
                    
                    # Z_r 계산 (피타고라스)
                    Z_r = np.sqrt(radar_x**2 + radar_y**2)
                    
                    print(f"객체 ID: {obj_id}")
                    print(f"  레이더 좌표: X_rel={radar_x:.2f}m, Y_rel={radar_y:.2f}m")
                    print(f"  거리: Z_r={Z_r:.2f}m")
                    print(f"  카메라 픽셀: u={pixel_x}, v={pixel_y}")
                    print(f"  시간: {timestamp:.3f}s")
                    print("-" * 50)
                    
                    # 실제 카메라 이미지에 점 그리기
                    image = self.draw_point_on_camera(pixel_x, pixel_y, obj_id)
                    
                    # 이미지 표시 (실시간 확인용)
                    cv2.imshow("Radar to Camera Projection", image)
                    cv2.waitKey(1)  # 1ms 대기 (실시간 표시)
                
                time.sleep(0.01)  # 10ms 간격으로 체크
                
            except KeyboardInterrupt:
                print("Projection 처리 중단")
                break
            except Exception as e:
                print(f"Projection 처리 오류: {e}")
                time.sleep(0.1)
        
        # OpenCV 창 정리
        cv2.destroyAllWindows()

def main():
    """메인 실행 함수"""
    # CAN 인터페이스 초기화
    can_viewer = CanDataViewer("sensor_data_20250915.dbc")
    
    # Projection 프로세서 초기화
    projection_processor = CameraProjectionProcessor(can_viewer)
    
    # 실시간 projection 처리 시작
    projection_processor.process_realtime_projection()

if __name__ == "__main__":
    main()
