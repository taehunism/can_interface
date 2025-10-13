import sys
from PyQt5 import QtWidgets, QtCore, QtGui
import can
import cantools
import threading
import pandas as pd
import time
from radar_data import RadarDataManager, RadarObject


class CanDataViewer(QtWidgets.QWidget):
    def __init__(self, dbc_path):
        super().__init__()

        self.setWindowTitle("TAEHUNISM - Windows CAN Interface")
        self.resize(1000, 700)

        self.db = cantools.database.load_file(dbc_path)

        self.messages = []
        self.delta_t_mode = False

        self.logging_active = False
        self.logged_rows = []
        self.current_data = {}

        self.receive_active = False

        self.start_time = None
        self.last_timestamp = None
        self.last_logged_time = None
        
        # 레이더 데이터 관리자 초기화
        self.radar_manager = RadarDataManager()
        
        # CAN 인터페이스 설정
        self.can_interface = None
        self.can_channel = None
        
        # 더미 데이터 전송 관련
        self.dummy_data_active = False
        self.dummy_data_thread = None
        self.dummy_simulation_active = False
        self.dummy_simulation_thread = None

        # UI 버튼 생성
        self.btn_start = QtWidgets.QPushButton("Start", self)
        self.btn_stop = QtWidgets.QPushButton("Stop", self)
        self.btn_delta_t = QtWidgets.QPushButton("Period", self)
        self.btn_log = QtWidgets.QPushButton("Log Start", self)
        self.btn_log_end = QtWidgets.QPushButton("Log End", self)
        self.btn_connect = QtWidgets.QPushButton("Connect CAN", self)
        self.btn_disconnect = QtWidgets.QPushButton("Disconnect CAN", self)

        btn_font = QtGui.QFont("Arial", 11, QtGui.QFont.Bold)
        for btn in (self.btn_start, self.btn_stop, self.btn_delta_t, self.btn_log, 
                   self.btn_log_end, self.btn_connect, self.btn_disconnect):
            btn.setFont(btn_font)
            btn.setFixedHeight(40)

        self.btn_stop.setEnabled(False)
        self.btn_log.setEnabled(True)  # Log Start는 사용 가능
        self.btn_log_end.setEnabled(False)  # Log End는 초기 비활성
        self.btn_disconnect.setEnabled(False)  # Disconnect는 초기 비활성

        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.setSpacing(20)
        btn_layout.addWidget(self.btn_connect)
        btn_layout.addWidget(self.btn_disconnect)
        btn_layout.addWidget(self.btn_start)
        btn_layout.addWidget(self.btn_stop)
        btn_layout.addWidget(self.btn_delta_t)
        btn_layout.addWidget(self.btn_log)
        btn_layout.addWidget(self.btn_log_end)

        # 메인 테이블
        self.table = QtWidgets.QTableWidget(self)
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(['Timestamp', 'Message', 'Signal', 'Value'])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("alternate-background-color: #ffffff; background-color: #ffffff;")
        
        # 레이더 데이터 표시 테이블
        self.radar_table = QtWidgets.QTableWidget(self)
        self.radar_table.setColumnCount(6)
        self.radar_table.setHorizontalHeaderLabels(['Object ID', 'Distance (m)', 'Angle (deg)', 'Rel Pos X', 'Rel Pos Y', 'Rel Vel X'])
        self.radar_table.horizontalHeader().setStretchLastSection(True)
        self.radar_table.setAlternatingRowColors(True)
        self.radar_table.setMaximumHeight(200)
        
        # 레이더 데이터 라벨
        self.radar_label = QtWidgets.QLabel("Radar Objects:")
        self.radar_label.setFont(QtGui.QFont("Arial", 12, QtGui.QFont.Bold))
        
        # 레이더 요약 정보 라벨
        self.radar_summary = QtWidgets.QLabel("No radar data")
        self.radar_summary.setFont(QtGui.QFont("Arial", 10))

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.addLayout(btn_layout)
        main_layout.addWidget(self.table)
        main_layout.addWidget(self.radar_label)
        main_layout.addWidget(self.radar_table)
        main_layout.addWidget(self.radar_summary)

        # 버튼 이벤트 연결
        self.btn_connect.clicked.connect(self.connect_can)
        self.btn_disconnect.clicked.connect(self.disconnect_can)
        self.btn_start.clicked.connect(self.start_receiving)
        self.btn_stop.clicked.connect(self.stop_receiving)
        self.btn_delta_t.clicked.connect(self.toggle_delta_t)
        self.btn_log.clicked.connect(self.start_logging)
        self.btn_log_end.clicked.connect(self.end_logging)

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.refresh_table)
        self.timer.start(500)

    def connect_can(self):
        """CAN 인터페이스 연결"""
        try:
            # Windows에서 사용 가능한 CAN 인터페이스들 시도
            interfaces_to_try = [
                ('pcan', 'PCAN_USBBUS1'),  # PEAK PCAN-USB
                ('vector', '0'),           # Vector CANoe/CANalyzer
                ('ixxat', '0'),            # IXXAT USB-to-CAN
                ('socketcan', 'can0'),     # SocketCAN (Linux 호환)
                ('virtual', 'vcan0'),      # Virtual CAN (테스트용)
            ]
            
            connected = False
            for interface, channel in interfaces_to_try:
                try:
                    self.can_interface = can.interface.Bus(
                        channel=channel, 
                        interface=interface,
                        bitrate=500000  # 500kbps
                    )
                    self.can_channel = channel
                    connected = True
                    print(f"CAN 인터페이스 연결 성공: {interface} - {channel}")
                    
                    # Virtual CAN으로 연결된 경우 더미 데이터 전송 시작
                    if interface == 'virtual':
                        print("Virtual CAN으로 연결됨. 더미 데이터 전송을 시작합니다.")
                        self.start_dummy_data_transmission()
                    
                    break
                except Exception as e:
                    print(f"CAN 인터페이스 연결 실패: {interface} - {channel}, 오류: {e}")
                    continue
            
            if not connected:
                print("사용 가능한 CAN 인터페이스를 찾을 수 없습니다.")
                print("Virtual CAN으로 연결을 시도합니다...")
                
                # Virtual CAN으로 강제 연결 시도
                try:
                    # 사용 가능한 virtual 채널 확인
                    configs = can.interface.detect_available_configs()
                    virtual_configs = [c for c in configs if c.get('interface') == 'virtual']
                    
                    if virtual_configs:
                        channel = virtual_configs[0]['channel']
                        print(f"Virtual CAN 채널 사용: {channel}")
                    else:
                        channel = 'channel-0'
                        print(f"기본 Virtual CAN 채널 사용: {channel}")
                    
                    self.can_interface = can.interface.Bus(
                        channel=channel, 
                        interface='virtual',
                        bitrate=500000
                    )
                    self.can_channel = channel
                    connected = True
                    print("Virtual CAN 연결 성공. 더미 데이터 전송을 시작합니다.")
                    self.start_dummy_data_transmission()
                except Exception as e:
                    print(f"Virtual CAN 연결도 실패: {e}")
                    print("사용 가능한 인터페이스:")
                    try:
                        configs = can.interface.detect_available_configs()
                        for config in configs:
                            print(f"  - {config}")
                    except:
                        print("  - 인터페이스 정보를 가져올 수 없습니다.")
                    return
            
            self.btn_connect.setEnabled(False)
            self.btn_disconnect.setEnabled(True)
            self.btn_start.setEnabled(True)
            
        except Exception as e:
            print(f"CAN 연결 중 오류 발생: {e}")

    def disconnect_can(self):
        """CAN 인터페이스 연결 해제"""
        try:
            # 더미 데이터 전송 및 시뮬레이션 중지
            if self.dummy_data_active:
                self.stop_dummy_data_transmission()
            if self.dummy_simulation_active:
                self.stop_dummy_data_simulation()
            
            if self.can_interface:
                self.can_interface.shutdown()
                self.can_interface = None
                self.can_channel = None
                print("CAN 인터페이스 연결 해제됨")
            
            self.btn_connect.setEnabled(True)
            self.btn_disconnect.setEnabled(False)
            self.btn_start.setEnabled(False)
            self.btn_stop.setEnabled(False)
            
            if self.receive_active:
                self.stop_receiving()
                
        except Exception as e:
            print(f"CAN 연결 해제 중 오류 발생: {e}")

    def start_dummy_data_transmission(self):
        """더미 데이터 전송 시작"""
        if not self.dummy_data_active:
            self.dummy_data_active = True
            self.dummy_data_thread = threading.Thread(target=self._dummy_data_worker, daemon=True)
            self.dummy_data_thread.start()
            print("더미 데이터 전송이 시작되었습니다.")
            
            # 더미 데이터를 직접 처리하도록 시뮬레이션
            self.start_dummy_data_simulation()

    def stop_dummy_data_transmission(self):
        """더미 데이터 전송 중지"""
        self.dummy_data_active = False
        if self.dummy_data_thread:
            self.dummy_data_thread.join(timeout=1)
        
        # 더미 시뮬레이션도 중지
        self.stop_dummy_data_simulation()
        print("더미 데이터 전송이 중지되었습니다.")

    def start_dummy_data_simulation(self):
        """더미 데이터 시뮬레이션 시작 (직접 처리)"""
        if not self.dummy_simulation_active:
            self.dummy_simulation_active = True
            self.dummy_simulation_thread = threading.Thread(target=self._dummy_simulation_worker, daemon=True)
            self.dummy_simulation_thread.start()
            print("더미 데이터 시뮬레이션이 시작되었습니다.")

    def stop_dummy_data_simulation(self):
        """더미 데이터 시뮬레이션 중지"""
        self.dummy_simulation_active = False
        if self.dummy_simulation_thread:
            self.dummy_simulation_thread.join(timeout=1)
        print("더미 데이터 시뮬레이션이 중지되었습니다.")

    def _dummy_simulation_worker(self):
        """더미 데이터 시뮬레이션 워커 (직접 처리)"""
        import random
        
        print("더미 데이터 시뮬레이션 워커 시작")
        
        while self.dummy_simulation_active:
            try:
                # 현재 시간
                current_time = time.time()
                
                # 100 메시지 - 차량 속도 및 스티어링 앵글
                speed = random.uniform(0, 250)
                steering = random.uniform(-7800, 7800)
                
                # 가상 CAN 메시지 생성
                msg_100 = can.Message(
                    arbitration_id=100,
                    data=self._create_vehicle_status_data(speed, steering),
                    is_extended_id=False,
                    timestamp=current_time
                )
                self.add_can_message(msg_100)
                
                # 101 메시지 - 횡가속도
                lat_accel = random.uniform(-10, 10)
                msg_101 = can.Message(
                    arbitration_id=101,
                    data=self._create_accel_data(lat_accel),
                    is_extended_id=False,
                    timestamp=current_time
                )
                self.add_can_message(msg_101)
                
                # 102 메시지 - 차선정보
                lane_data = [random.randint(0, 1) for _ in range(4)]
                msg_102 = can.Message(
                    arbitration_id=102,
                    data=self._create_lane_data(lane_data),
                    is_extended_id=False,
                    timestamp=current_time
                )
                self.add_can_message(msg_102)
                
                # 200~209 메시지 - 10개 레이더 객체
                for i in range(200, 210):
                    rel_pos_x = random.uniform(-100, 100)
                    rel_pos_y = random.uniform(-50, 50)
                    rel_vel_x = random.uniform(-20, 20)
                    rel_acc_x = random.uniform(-5, 5)
                    
                    msg_radar = can.Message(
                        arbitration_id=i,
                        data=self._create_radar_data(rel_pos_x, rel_pos_y, rel_vel_x, rel_acc_x),
                        is_extended_id=False,
                        timestamp=current_time
                    )
                    self.add_can_message(msg_radar)
                
                print(f"더미 데이터 시뮬레이션 완료: {current_time:.3f}")
                time.sleep(0.1)  # 100ms 간격
                
            except Exception as e:
                print(f"더미 시뮬레이션 오류: {e}")
                time.sleep(1)

    def _create_vehicle_status_data(self, speed, steering):
        """차량 상태 데이터 생성"""
        speed_raw = self._to_int16(speed, 0.01)
        steering_raw = self._to_int16(steering, 0.1)
        return speed_raw.to_bytes(2, 'little', signed=True) + steering_raw.to_bytes(2, 'little', signed=True) + bytes(4)

    def _create_accel_data(self, lat_accel):
        """가속도 데이터 생성"""
        lat_accel_raw = int(lat_accel / 0.001)
        return lat_accel_raw.to_bytes(2, 'little', signed=True) + bytes(6)

    def _create_lane_data(self, lane_data):
        """차선 데이터 생성"""
        return bytes(lane_data) + bytes(4)

    def _create_radar_data(self, rel_pos_x, rel_pos_y, rel_vel_x, rel_acc_x):
        """레이더 데이터 생성"""
        x_raw = self._to_raw(rel_pos_x)
        y_raw = self._to_raw(rel_pos_y)
        vel_raw = self._to_raw(rel_vel_x)
        acc_raw = self._to_raw(rel_acc_x)
        
        return (x_raw.to_bytes(2, 'little') +
                y_raw.to_bytes(2, 'little') +
                vel_raw.to_bytes(2, 'little') +
                acc_raw.to_bytes(2, 'little'))

    def _dummy_data_worker(self):
        """더미 데이터 전송 워커 스레드"""
        import random
        
        print("더미 데이터 전송 워커 시작")
        
        while self.dummy_data_active and self.can_interface:
            try:
                # 100 메시지 - 차량 속도 및 스티어링 앵글
                speed = random.uniform(0, 250)
                steering = random.uniform(-7800, 7800)
                
                speed_raw = self._to_int16(speed, 0.01)
                steering_raw = self._to_int16(steering, 0.1)
                
                data_100 = speed_raw.to_bytes(2, 'little', signed=True) + steering_raw.to_bytes(2, 'little', signed=True) + bytes(4)
                msg_100 = can.Message(arbitration_id=100, data=data_100, is_extended_id=False)
                self.can_interface.send(msg_100)
                print(f"전송: ID=100, Speed={speed:.1f}, Steering={steering:.1f}")
                
                # 101 메시지 - 횡가속도
                lat_accel = random.uniform(-10, 10)
                lat_accel_raw = int(lat_accel / 0.001)
                data_101 = lat_accel_raw.to_bytes(2, 'little', signed=True) + bytes(6)
                msg_101 = can.Message(arbitration_id=101, data=data_101, is_extended_id=False)
                self.can_interface.send(msg_101)
                
                # 102 메시지 - 차선정보
                lane_c0 = random.randint(0, 1)
                lane_c1 = random.randint(0, 1)
                lane_c2 = random.randint(0, 1)
                lane_c3 = random.randint(0, 1)
                data_102 = bytes([lane_c0, lane_c1, lane_c2, lane_c3]) + bytes(4)
                msg_102 = can.Message(arbitration_id=102, data=data_102, is_extended_id=False)
                self.can_interface.send(msg_102)
                
                # 200~209 메시지 - 10개 레이더 객체
                for i in range(200, 210):
                    rel_pos_x = random.uniform(-100, 100)
                    rel_pos_y = random.uniform(-50, 50)
                    rel_vel_x = random.uniform(-20, 20)
                    rel_acc_x = random.uniform(-5, 5)
                    
                    x_raw = self._to_raw(rel_pos_x)
                    y_raw = self._to_raw(rel_pos_y)
                    vel_raw = self._to_raw(rel_vel_x)
                    acc_raw = self._to_raw(rel_acc_x)
                    
                    data = (x_raw.to_bytes(2, 'little') +
                           y_raw.to_bytes(2, 'little') +
                           vel_raw.to_bytes(2, 'little') +
                           acc_raw.to_bytes(2, 'little'))
                    
                    msg_radar = can.Message(arbitration_id=i, data=data, is_extended_id=False)
                    self.can_interface.send(msg_radar)
                
                print(f"레이더 데이터 전송 완료 (ID 200-209)")
                time.sleep(0.1)  # 100ms 간격
                
            except Exception as e:
                print(f"더미 데이터 전송 오류: {e}")
                time.sleep(1)

    def _to_int16(self, val, scale):
        """값을 16비트 정수로 변환"""
        raw = int(val / scale)
        if raw < -32768:
            raw = -32768
        elif raw > 32767:
            raw = 32767
        return raw

    def _to_raw(self, val, scale=0.1, offset=0):
        """값을 raw 데이터로 변환"""
        raw = int((val - offset) / scale)
        if raw < 0:
            raw = (1 << 16) + raw
        return raw

    def start_receiving(self):
        if not self.can_interface:
            print("CAN 인터페이스가 연결되지 않았습니다. 먼저 CAN을 연결하세요.")
            return
            
        if not self.receive_active:
            self.receive_active = True
            self.start_time = QtCore.QDateTime.currentDateTime()
            self.last_logged_time = None
            self.current_data = {}
            self.last_timestamp = None
            print("CAN 메시지 수신 시작")
            self.btn_start.setEnabled(False)
            self.btn_stop.setEnabled(True)

    def stop_receiving(self):
        if self.receive_active:
            self.receive_active = False
            print("CAN 메시지 수신 중지")
            self.btn_start.setEnabled(True)
            self.btn_stop.setEnabled(False)

    def toggle_delta_t(self):
        self.delta_t_mode = not self.delta_t_mode
        if self.delta_t_mode:
            self.last_timestamp = QtCore.QDateTime.currentDateTime()
            self.btn_delta_t.setText("Timestamp")  # 모드 켰을 때 버튼명 변경
        else:
            self.btn_delta_t.setText("Period")  # 모드 껐을 때 버튼명 변경
        print(f"Data Period 모드: {self.delta_t_mode}")
        self.refresh_table()

    def start_logging(self):
        if not self.receive_active:
            print("CAN 수신 먼저 시작하세요.")
            return
        if self.logging_active:
            print("이미 로깅 중입니다.")
            return
        self.logging_active = True
        self.logged_rows = []
        self.current_data = {}
        self.last_logged_time = None
        # Log Start 누르면 버튼 비활성화, Log End 활성화
        self.btn_log.setEnabled(False)
        self.btn_log_end.setEnabled(True)
        print("로깅 시작")

    def end_logging(self):
        if not self.logging_active:
            print("로깅 중이 아닙니다.")
            return

        # 마지막 데이터 반영
        if self.current_data and (not self.logged_rows or self.logged_rows[-1] != self.current_data):
            self.logged_rows.append(self.current_data.copy())

        self.logging_active = False

        # Log End 누르면 버튼 비활성화, Log Start 활성화
        self.btn_log_end.setEnabled(False)
        self.btn_log.setEnabled(True)

        if not self.logged_rows:
            print("저장할 로깅 데이터가 없습니다.")
            return

        try:
            df = pd.DataFrame(self.logged_rows)
            # 비어있는 행 없애기 (모든 값이 NaN 또는 빈 문자열인 행 제거)
            if len(df) > 1:
            #     df.iloc[0] = 0  # 숫자형인 경우 0, 문자형으로 입력하려면 '0'
                df = df.drop(df.index[0])
            # df.dropna(how='all', inplace=True)
            # df = df.loc[~(df== '').all(axis=1)]
            
            filename = QtCore.QDateTime.currentDateTime().toString("yyyyMMdd_hhmmss") + "_can_log.csv"
            df.to_csv(filename, index=False)
            print(f"로깅 종료. 파일 저장됨: {filename}")

        except Exception as e:
            print(f"CSV 저장 중 오류 발생: {e}")

    def add_can_message(self, msg):
        if not self.receive_active:
            return

        try:
            message = self.db.get_message_by_frame_id(msg.arbitration_id)
            signals = message.decode(msg.data)
            current_time = QtCore.QDateTime.currentDateTime()

            if self.start_time is not None:
                elapsed_ms = self.start_time.msecsTo(current_time)
                elapsed_sec = elapsed_ms / 1000.0
                timestamp_seconds_str = f"{elapsed_sec:.3f}"
            else:
                timestamp_seconds_str = "0.000"

            if self.delta_t_mode:
                if self.last_timestamp is None:
                    delta_ms = 0
                else:
                    delta_ms = self.last_timestamp.msecsTo(current_time)
                display_time = f"{delta_ms / 1000.0:.3f}"
                self.last_timestamp = current_time
            else:
                display_time = timestamp_seconds_str

            for sig_name, val in signals.items():
                self.messages.append((display_time, message.name, sig_name, val))

            # 레이더 데이터 처리 (ID 200-209)
            if 200 <= msg.arbitration_id <= 209:
                self._process_radar_data(msg.arbitration_id, signals, elapsed_sec)

            if self.logging_active:
                if self.last_logged_time is None or elapsed_sec > self.last_logged_time:
                    self.last_logged_time = elapsed_sec
                    new_row = self.current_data.copy()
                    new_row['Timestamp'] = timestamp_seconds_str
                    self.logged_rows.append(new_row)

                for sig_name, val in signals.items():
                    self.current_data[sig_name] = val

            if len(self.messages) > 1000:
                self.messages = self.messages[-1000:]

        except Exception as e:
            print(f"디코딩 실패 (ID:{msg.arbitration_id}): {e}")

    def _process_radar_data(self, msg_id, signals, timestamp):
        """레이더 데이터 처리 및 RadarDataManager 업데이트"""
        try:
            # 메시지 ID에서 객체 번호 추출 (200-209 -> 1-10)
            object_id = msg_id - 199
            
            # 신호 이름에서 데이터 추출
            rel_pos_x = signals.get(f'RelPosX{object_id}', 0)
            rel_pos_y = signals.get(f'RelPosY{object_id}', 0)
            rel_vel_x = signals.get(f'RelVelX{object_id}', 0)
            rel_acc_x = signals.get(f'RelAccX{object_id}', 0)
            
            # RadarDataManager에 데이터 업데이트
            self.radar_manager.update_object(
                object_id=object_id,
                rel_pos_x=rel_pos_x,
                rel_pos_y=rel_pos_y,
                rel_vel_x=rel_vel_x,
                rel_acc_x=rel_acc_x,
                timestamp=timestamp
            )
            
        except Exception as e:
            print(f"레이더 데이터 처리 실패 (ID:{msg_id}): {e}")

    def refresh_table(self):
        try:
            # 메인 테이블 업데이트
            display = self.messages[-100:]
            self.table.setRowCount(len(display))
            for row, (time, msg, sig, val) in enumerate(display):
                self.table.setItem(row, 0, QtWidgets.QTableWidgetItem(time))
                self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(msg))
                self.table.setItem(row, 2, QtWidgets.QTableWidgetItem(sig))
                self.table.setItem(row, 3, QtWidgets.QTableWidgetItem(str(val)))
            
            # 레이더 테이블 업데이트
            self._update_radar_table()
            
            # 오래된 레이더 객체 정리
            self.radar_manager.clear_old_objects(max_age=2.0)
            
        except KeyboardInterrupt:
            print("사용자에 의한 인터럽트 발생 - 안전하게 종료합니다.")
            QtWidgets.qApp.quit()

    def _update_radar_table(self):
        """레이더 데이터 테이블 업데이트"""
        try:
            radar_objects = self.radar_manager.get_all_objects()
            self.radar_table.setRowCount(len(radar_objects))
            
            for row, obj in enumerate(radar_objects):
                self.radar_table.setItem(row, 0, QtWidgets.QTableWidgetItem(str(obj.object_id)))
                self.radar_table.setItem(row, 1, QtWidgets.QTableWidgetItem(f"{obj.distance:.2f}"))
                self.radar_table.setItem(row, 2, QtWidgets.QTableWidgetItem(f"{obj.angle:.1f}"))
                self.radar_table.setItem(row, 3, QtWidgets.QTableWidgetItem(f"{obj.rel_pos_x:.2f}"))
                self.radar_table.setItem(row, 4, QtWidgets.QTableWidgetItem(f"{obj.rel_pos_y:.2f}"))
                self.radar_table.setItem(row, 5, QtWidgets.QTableWidgetItem(f"{obj.rel_vel_x:.2f}"))
            
            # 요약 정보 업데이트
            summary = self.radar_manager.get_summary()
            summary_text = (f"Objects: {summary['object_count']}, "
                          f"Closest: {summary['closest_distance']:.2f}m, "
                          f"Last Update: {summary['last_update_time']:.1f}s")
            self.radar_summary.setText(summary_text)
            
        except Exception as e:
            print(f"레이더 테이블 업데이트 실패: {e}")


def can_listener(viewer):
    """CAN 메시지 수신 스레드"""
    while True:
        try:
            if viewer.can_interface and viewer.receive_active:
                msg = viewer.can_interface.recv(timeout=1)
                if msg is not None:
                    viewer.add_can_message(msg)
            else:
                time.sleep(0.1)
        except Exception as e:
            print(f"CAN 수신 오류: {e}")
            time.sleep(1)


def main():
    app = QtWidgets.QApplication(sys.argv)
    viewer = CanDataViewer("candb_ex.dbc")
    viewer.show()

    # CAN 수신 스레드 시작
    listen_thread = threading.Thread(target=can_listener, args=(viewer,), daemon=True)
    listen_thread.start()

    try:
        sys.exit(app.exec_())
    except KeyboardInterrupt:
        print("프로그램이 Ctrl+C로 종료되었습니다.")
        if viewer.can_interface:
            viewer.disconnect_can()
        if viewer.dummy_data_active:
            viewer.stop_dummy_data_transmission()



if __name__ == "__main__":
    main()
