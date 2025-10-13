# Windows CAN Interface 프로젝트

Ubuntu에서 개발된 virtual CAN 프로젝트를 Windows 환경에서 실제 USB CAN 인터페이스를 사용하도록 포팅한 프로젝트입니다.

## 주요 기능

- **실제 USB CAN 인터페이스 지원**: PEAK PCAN-USB, Vector, IXXAT 등 다양한 CAN 인터페이스 지원
- **레이더 데이터 실시간 처리**: CAN 메시지에서 레이더 객체 데이터를 추출하여 직접 변수로 활용
- **GUI 인터페이스**: PyQt5 기반의 사용자 친화적인 인터페이스
- **데이터 로깅**: CAN 메시지를 CSV 파일로 저장
- **실시간 모니터링**: 레이더 객체의 거리, 각도, 속도 등을 실시간으로 표시

## 파일 구조

```
can_interface/
├── can_interface.py      # 메인 CAN 수신 프로그램 (GUI)
├── send_can.py          # CAN 송신 프로그램 (테스트용)
├── radar_data.py        # 레이더 데이터 관리 클래스
├── radar_example.py     # 레이더 데이터 활용 예제
├── test_can.py          # CAN 인터페이스 테스트 프로그램
├── candb_ex.dbc         # CAN 데이터베이스 파일
├── requirements.txt     # Python 패키지 의존성
├── WINDOWS_SETUP.md     # Windows 설치 가이드
├── LICENSE              # 라이선스 파일
├── logs/                # CAN 로그 파일 저장 디렉토리
│   └── *.csv           # CAN 메시지 로그 파일들
└── README.md           # 이 파일
```

## 빠른 시작

### 1. 환경 설정

#### conda 사용 (권장)
```bash
# conda 가상환경 생성
conda create -n can_env python=3.9

# 가상환경 활성화
conda activate can_env

# 필요한 패키지 설치
conda install pyqt pandas numpy
pip install python-can cantools
```

#### venv 사용
```bash
# Python 가상환경 생성
python -m venv can_env

# 가상환경 활성화 (Windows)
can_env\Scripts\activate

# 필요한 패키지 설치
pip install -r requirements.txt
```

### 2. CAN 인터페이스 연결
1. USB CAN 인터페이스를 컴퓨터에 연결
2. 해당 제조사의 드라이버 설치
3. 프로그램 실행 후 "Connect CAN" 버튼 클릭

### 3. 프로그램 실행
```bash
# CAN 수신 프로그램 실행 (메인 프로그램)
python can_interface.py

# CAN 송신 프로그램 실행 (테스트용)
python send_can.py

# 레이더 데이터 활용 예제 실행
python radar_example.py

# CAN 인터페이스 테스트 실행
python test_can.py
```

## 레이더 데이터 활용

### 기본 사용법
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
    print(f"거리: {object_1.distance}m")
    print(f"각도: {object_1.angle}도")
```

### 고급 활용
```python
# 거리 범위 내 객체들
nearby_objects = radar_manager.get_objects_in_range(0, 50)  # 0-50m

# 각도 범위 내 객체들
front_objects = radar_manager.get_objects_in_angle_range(-30, 30)  # 정면 ±30도

# 속도 범위 내 객체들
fast_objects = radar_manager.get_objects_by_velocity(10, 50)  # 10-50 m/s
```

## 지원되는 CAN 인터페이스

- **PEAK PCAN-USB**: PEAK-System의 USB CAN 인터페이스
- **Vector CANoe/CANalyzer**: Vector의 CAN 분석 도구
- **IXXAT USB-to-CAN**: IXXAT의 USB CAN 인터페이스
- **SocketCAN**: Linux 호환 인터페이스
- **Virtual CAN**: 테스트용 가상 인터페이스

## 레이더 데이터 구조

각 레이더 객체는 다음 정보를 포함합니다:

- **Object ID**: 객체 식별자 (1-10)
- **Distance**: 거리 (미터) - 자동 계산
- **Angle**: 각도 (도) - 자동 계산
- **Relative Position X/Y**: 상대 위치 (미터)
- **Relative Velocity X**: 상대 속도 (m/s)
- **Relative Acceleration X**: 상대 가속도 (m/s²)
- **Timestamp**: 타임스탬프

## CAN 메시지 구조

프로젝트는 다음 CAN 메시지 ID를 사용합니다:

- **100**: 차량 상태 (속도, 스티어링 각도)
- **101**: 차량 가속도 (횡가속도)
- **102**: 차선 정보
- **200-209**: 레이더 객체 데이터 (10개 객체)

## 설치 및 설정

자세한 설치 방법은 [WINDOWS_SETUP.md](WINDOWS_SETUP.md) 파일을 참조하세요.

## 6. 로깅 기능

- "Log Start" 버튼으로 데이터 로깅 시작
- "Log End" 버튼으로 로깅 종료 및 CSV 파일 저장
- 파일명 형식: `YYYYMMDD_HHMMSS_can_log.csv`
- 로그 파일은 `logs/` 디렉토리에 자동 저장

## 7. 문제 해결

### 일반적인 문제들

1. **CAN 인터페이스 연결 실패**
   - USB CAN 인터페이스가 올바르게 연결되었는지 확인
   - 해당 제조사의 드라이버가 설치되었는지 확인

2. **Python 패키지 설치 오류**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

3. **PyQt5 관련 오류**
   ```bash
   pip uninstall PyQt5
   pip install PyQt5==5.15.9
   ```

4. **dataclasses 모듈 오류**
   ```bash
   pip install dataclasses
   ```

## 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다.

## 기여하기

버그 리포트나 기능 제안은 GitHub Issues를 통해 제출해 주세요.

## 변경 사항

### v2.0 (Windows 포팅)
- Ubuntu virtual CAN에서 Windows USB CAN 인터페이스로 변경
- 레이더 데이터 관리 클래스 추가
- GUI 인터페이스 개선
- 다양한 CAN 인터페이스 지원

### v1.0 (Ubuntu)
- Virtual CAN 기반 구현
- 기본 CAN 메시지 수신/송신 기능
