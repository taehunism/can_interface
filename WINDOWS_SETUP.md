# Windows CAN Interface 설치 가이드

이 가이드는 Ubuntu에서 개발된 virtual CAN 프로젝트를 Windows 환경에서 실제 USB CAN 인터페이스를 사용하도록 설정하는 방법을 설명합니다.

## 1. 시스템 요구사항

- Windows 10/11 (64비트 권장)
- Python 3.8 이상
- USB CAN 인터페이스 하드웨어 (PEAK PCAN-USB, Vector, IXXAT 등)

## 2. Python 환경 설정

### 2.1 Python 설치
1. [Python 공식 웹사이트](https://www.python.org/downloads/)에서 Python 3.8 이상 다운로드
2. 설치 시 "Add Python to PATH" 옵션 체크
3. pip 업그레이드: `python -m pip install --upgrade pip`

### 2.2 가상환경 생성 (권장)

#### 방법 1: conda 사용 (권장)
```bash
# conda 가상환경 생성
conda create -n can_env python=3.9

# 가상환경 활성화
conda activate can_env

# 가상환경 비활성화 (필요시)
conda deactivate
```

#### 방법 2: venv 사용
```bash
# 가상환경 생성
python -m venv can_env

# 가상환경 활성화 (Windows)
can_env\Scripts\activate

# 가상환경 비활성화 (필요시)
deactivate
```

### 2.3 필요한 패키지 설치

#### conda 사용시
```bash
# conda로 설치 가능한 패키지들
conda install pyqt pandas numpy

# pip로 추가 패키지 설치
pip install python-can cantools
```

#### venv 사용시
```bash
pip install -r requirements.txt
```

## 3. CAN 인터페이스 하드웨어 설정

### 3.1 PEAK PCAN-USB 사용시
1. [PEAK-System 웹사이트](https://www.peak-system.com/)에서 PCAN-Basic API 다운로드
2. PCAN-Basic API 설치
3. USB CAN 인터페이스를 컴퓨터에 연결
4. 장치 관리자에서 "PCAN-USB" 장치가 정상 인식되는지 확인

### 3.2 Vector CANoe/CANalyzer 사용시
1. Vector CANoe 또는 CANalyzer 설치
2. Vector 드라이버 설치
3. USB CAN 인터페이스 연결 및 설정

### 3.3 IXXAT USB-to-CAN 사용시
1. IXXAT 웹사이트에서 드라이버 다운로드
2. IXXAT 드라이버 설치
3. USB CAN 인터페이스 연결

## 4. 프로젝트 실행

### 4.1 CAN 수신 프로그램 실행
```bash
python can_interface.py
```

### 4.2 CAN 송신 프로그램 실행 (테스트용)
```bash
python send_can.py
```

## 5. 사용 방법

### 5.1 CAN 수신 프로그램 사용법
1. 프로그램 실행
2. "Connect CAN" 버튼 클릭하여 CAN 인터페이스 연결
3. "Start" 버튼 클릭하여 CAN 메시지 수신 시작
4. 레이더 데이터는 하단 테이블에서 확인 가능

### 5.2 레이더 데이터 활용
프로그램에서 레이더 데이터를 직접 변수로 활용하려면:

```python
from radar_data import RadarDataManager

# RadarDataManager 인스턴스 생성
radar_manager = RadarDataManager()

# 가장 가까운 객체 거리
closest_distance = radar_manager.closest_distance

# 객체 개수
object_count = radar_manager.object_count

# 특정 ID의 객체 정보
object_1 = radar_manager.get_object_by_id(1)
if object_1:
    print(f"객체 1 거리: {object_1.distance}m")
    print(f"객체 1 각도: {object_1.angle}도")

# 거리 범위 내 객체들
nearby_objects = radar_manager.get_objects_in_range(0, 50)  # 0-50m 범위

# 모든 유효한 객체들
all_objects = radar_manager.get_all_objects()
```

## 6. 문제 해결

### 6.1 CAN 인터페이스 연결 실패
- USB CAN 인터페이스가 올바르게 연결되었는지 확인
- 해당 제조사의 드라이버가 설치되었는지 확인
- 장치 관리자에서 장치가 정상 인식되는지 확인

### 6.2 Python 패키지 설치 오류
```bash
# pip 업그레이드
python -m pip install --upgrade pip

# 개별 패키지 설치
pip install PyQt5
pip install python-can
pip install cantools
pip install pandas
pip install numpy
```

### 6.3 PyQt5 관련 오류
```bash
# PyQt5 재설치
pip uninstall PyQt5
pip install PyQt5==5.15.9
```

## 7. 지원되는 CAN 인터페이스

이 프로그램은 다음 CAN 인터페이스를 지원합니다:
- PEAK PCAN-USB
- Vector CANoe/CANalyzer
- IXXAT USB-to-CAN
- SocketCAN (Linux 호환)
- Virtual CAN (테스트용)

## 8. 레이더 데이터 구조

레이더 데이터는 다음 정보를 포함합니다:
- Object ID: 객체 식별자 (1-10)
- Distance: 거리 (미터)
- Angle: 각도 (도)
- Relative Position X/Y: 상대 위치 (미터)
- Relative Velocity X: 상대 속도 (m/s)
- Relative Acceleration X: 상대 가속도 (m/s²)

## 9. 로깅 기능

- "Log Start" 버튼으로 데이터 로깅 시작
- "Log End" 버튼으로 로깅 종료 및 CSV 파일 저장
- 파일명 형식: `YYYYMMDD_HHMMSS_can_log.csv`

## 10. 주의사항

- CAN 인터페이스 연결 전에 하드웨어 드라이버가 설치되어 있어야 합니다
- 실제 CAN 네트워크에 연결할 때는 네트워크 설정을 확인하세요
- 레이더 데이터는 실시간으로 업데이트되며, 2초 이상 업데이트되지 않은 객체는 자동으로 제거됩니다
