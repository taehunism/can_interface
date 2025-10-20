import sys
from PyQt5 import QtWidgets, QtCore, QtGui
import can
import cantools
import threading
import pandas as pd
import time
from radar_data import RadarDataManager, RadarObject
from tsmaster_can_processor import TSMasterCanProcessor, AdvancedCanMessage, MessageStatus


class CanDataViewer(QtWidgets.QWidget):
    def __init__(self, dbc_path):
        super().__init__()

        self.setWindowTitle("TAEHUNISM - Windows CAN Interface")
        self.resize(1000, 700)

        # 채널별 프로세서
        self.tsmaster_processor_ch1 = TSMasterCanProcessor(dbc_path)
        self.tsmaster_processor_ch2 = TSMasterCanProcessor(dbc_path)
        self.db = self.tsmaster_processor_ch1.db  # 기본 참조

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
        
        # CAN 인터페이스 설정 (듀얼 채널)
        self.can_interface_ch1 = None
        self.can_interface_ch2 = None
        self.can_channel_ch1 = None
        self.can_channel_ch2 = None
        
        # 더미 데이터 시뮬레이션 관련
        self.dummy_simulation_active = False
        self.dummy_simulation_thread = None
        
        # 통계 정보
        self.stats_label = None
        
        # 정렬 상태
        self.sort_by_name = False
        self.sort_reverse = False
        
        # 필터링 상태
        self.filter_active = False
        self.filter_message = ""
        self.filter_signal = ""

        # 표시 행수 및 내부 버퍼 제한
        self.display_limit = 1000
        self.max_messages = 20000
        # 고정 표시 상태
        self.pinned_rows = {"CH1": {}, "CH2": {}}  # {(msg_name, sig): (timestamp, value, unit)}
        # 채널별 마지막 수신 시간 모니터링
        self.last_rx_time = {"CH1": 0.0, "CH2": 0.0}
        # 실시간 처리용: 최신값 저장소와 사용자 핸들러들
        self.latest_values = {}  # key: (channel, signal_name) -> (value, timestamp)
        self.processing_handlers = []  # list of (filter_fn, handler)

        # UI 버튼 생성
        self.btn_start = QtWidgets.QPushButton("Start", self)
        self.btn_stop = QtWidgets.QPushButton("Stop", self)
        self.btn_delta_t = QtWidgets.QPushButton("Period", self)
        self.btn_log = QtWidgets.QPushButton("Log Start", self)
        self.btn_log_end = QtWidgets.QPushButton("Log End", self)
        self.btn_connect_ch1 = QtWidgets.QPushButton("Connect CH1", self)
        self.btn_disconnect_ch1 = QtWidgets.QPushButton("Disconnect CH1", self)
        self.btn_connect_ch2 = QtWidgets.QPushButton("Connect CH2", self)
        self.btn_disconnect_ch2 = QtWidgets.QPushButton("Disconnect CH2", self)
        self.btn_sort = QtWidgets.QPushButton("Sort by Name", self)
        self.btn_reverse = QtWidgets.QPushButton("Reverse", self)
        self.btn_filter = QtWidgets.QPushButton("Filter", self)
        self.btn_load_dbc_ch1 = QtWidgets.QPushButton("Load DBC CH1", self)
        self.btn_load_dbc_ch2 = QtWidgets.QPushButton("Load DBC CH2", self)
        self.chk_defaults = QtWidgets.QCheckBox("Defaults on decode error", self)
        self.chk_defaults.setChecked(False)
        self.chk_collapse = QtWidgets.QCheckBox("Collapse duplicates", self)
        self.chk_collapse.setChecked(True)
        self.view_channel = QtWidgets.QComboBox(self)
        self.view_channel.addItems(["All", "CH1", "CH2"])
        self.chk_pin = QtWidgets.QCheckBox("Pin messages", self)
        self.chk_pin.setChecked(False)

        btn_font = QtGui.QFont("Arial", 11, QtGui.QFont.Bold)
        for btn in (self.btn_start, self.btn_stop, self.btn_delta_t, self.btn_log, 
                   self.btn_log_end, self.btn_connect_ch1, self.btn_disconnect_ch1, self.btn_connect_ch2, self.btn_disconnect_ch2, self.btn_sort, self.btn_reverse, self.btn_filter, self.btn_load_dbc_ch1, self.btn_load_dbc_ch2):
            btn.setFont(btn_font)
            btn.setFixedHeight(40)

        self.btn_stop.setEnabled(False)
        self.btn_log.setEnabled(True)  # Log Start는 사용 가능
        self.btn_log_end.setEnabled(False)  # Log End는 초기 비활성
        self.btn_disconnect_ch1.setEnabled(False)
        self.btn_disconnect_ch2.setEnabled(False)

        # 버튼 2줄 구성
        btn_layout_top = QtWidgets.QHBoxLayout()
        btn_layout_top.setSpacing(20)
        btn_layout_top.addWidget(self.btn_connect_ch1)
        btn_layout_top.addWidget(self.btn_disconnect_ch1)
        btn_layout_top.addWidget(self.btn_connect_ch2)
        btn_layout_top.addWidget(self.btn_disconnect_ch2)
        btn_layout_top.addWidget(self.btn_start)
        btn_layout_top.addWidget(self.btn_stop)
        btn_layout_top.addWidget(self.btn_delta_t)
        btn_layout_top.addWidget(self.btn_sort)
        btn_layout_top.addWidget(self.btn_reverse)

        btn_layout_bottom = QtWidgets.QHBoxLayout()
        btn_layout_bottom.setSpacing(20)
        btn_layout_bottom.addWidget(self.btn_log)
        btn_layout_bottom.addWidget(self.btn_log_end)
        btn_layout_bottom.addWidget(self.btn_filter)
        btn_layout_bottom.addWidget(self.btn_load_dbc_ch1)
        btn_layout_bottom.addWidget(self.btn_load_dbc_ch2)
        btn_layout_bottom.addWidget(self.chk_defaults)
        btn_layout_bottom.addWidget(self.chk_collapse)
        btn_layout_bottom.addWidget(QtWidgets.QLabel("View:"))
        btn_layout_bottom.addWidget(self.view_channel)
        btn_layout_bottom.addWidget(self.chk_pin)

        # 표시 행수 컨트롤 (둘째 줄)
        rows_label = QtWidgets.QLabel("Rows:")
        self.row_limit_spin = QtWidgets.QSpinBox(self)
        self.row_limit_spin.setRange(100, 50000)
        self.row_limit_spin.setSingleStep(100)
        self.row_limit_spin.setValue(self.display_limit)
        self.row_limit_spin.valueChanged.connect(self.on_row_limit_changed)
        btn_layout_bottom.addWidget(rows_label)
        btn_layout_bottom.addWidget(self.row_limit_spin)

        # 메인 테이블
        self.table = QtWidgets.QTableWidget(self)
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(['Timestamp', 'Channel', 'Message', 'Signal', 'Value', 'Unit'])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("alternate-background-color: #ffffff; background-color: #ffffff;")
        
        # 레이더 UI 숨김 플래그 (요청에 따라 화면에서 제거)
        self.show_radar = False
        
        # CAN 처리 통계 라벨
        self.stats_label = QtWidgets.QLabel("CAN Statistics: No data")
        self.stats_label.setFont(QtGui.QFont("Arial", 9))
        self.stats_label.setStyleSheet("color: blue;")

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.addLayout(btn_layout_top)
        main_layout.addLayout(btn_layout_bottom)
        main_layout.addWidget(self.table)
        if self.show_radar:
            main_layout.addWidget(self.radar_label)
            main_layout.addWidget(self.radar_table)
            main_layout.addWidget(self.radar_summary)
        main_layout.addWidget(self.stats_label)

        # 버튼 이벤트 연결
        self.btn_connect_ch1.clicked.connect(lambda: self.connect_can(channel_index=1))
        self.btn_disconnect_ch1.clicked.connect(lambda: self.disconnect_can(channel_index=1))
        self.btn_connect_ch2.clicked.connect(lambda: self.connect_can(channel_index=2))
        self.btn_disconnect_ch2.clicked.connect(lambda: self.disconnect_can(channel_index=2))
        self.btn_start.clicked.connect(self.start_receiving)
        self.btn_stop.clicked.connect(self.stop_receiving)
        self.btn_delta_t.clicked.connect(self.toggle_delta_t)
        self.btn_log.clicked.connect(self.start_logging)
        self.btn_log_end.clicked.connect(self.end_logging)
        self.btn_sort.clicked.connect(self.toggle_sort)
        self.btn_reverse.clicked.connect(self.toggle_reverse)
        self.btn_filter.clicked.connect(self.show_filter_dialog)
        self.btn_load_dbc_ch1.clicked.connect(lambda: self.load_dbc_dialog(channel_index=1))
        self.btn_load_dbc_ch2.clicked.connect(lambda: self.load_dbc_dialog(channel_index=2))
        self.chk_defaults.stateChanged.connect(self.on_toggle_defaults)
        self.chk_collapse.stateChanged.connect(lambda _: self.refresh_table())

        self.view_channel.currentIndexChanged.connect(lambda _: self.refresh_table())
        self.chk_pin.stateChanged.connect(lambda _: self.initialize_pinned_rows())

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.refresh_table)
        self.timer.start(500)

        # 추가: CIPV 파이프라인 초기화 (FR_RDR_CIPV/FR_RDR_OBJ_XXX 사용 시)
        # 위치: __init__ 마지막 타이머 시작 직후
        self.setup_cipv_pipeline()

    def connect_can(self, channel_index=1):
        """CAN 인터페이스 연결"""
        try:
            # Windows에서 사용 가능한 CAN/CAN FD 인터페이스들 시도
            interfaces_to_try = [
                # CAN FD 지원 인터페이스들
                ('vector', '3', True),            # Vector CANoe/CANalyzer (CAN FD 지원)
                ('ixxat', '0', True),             # IXXAT USB-to-CAN (CAN FD 지원)
                ('socketcan', 'can0', True),      # SocketCAN (CAN FD 지원)
                # 일반 CAN 인터페이스들
                ('pcan', 'PCAN_USBBUS1', False),  # PEAK PCAN-USB (CAN만)
                ('vector', '0', False),           # Vector CANoe/CANalyzer (CAN만)
                ('ixxat', '0', False),            # IXXAT USB-to-CAN (CAN만)
                ('socketcan', 'can0', False),     # SocketCAN (CAN만)
                ('virtual', 'vcan0', False),      # Virtual CAN (테스트용)
            ]

            interfaces_to_try2 = [
                # CAN FD 지원 인터페이스들
                ('vector', '2', True),            # Vector CANoe/CANalyzer (CAN FD 지원)
                ('ixxat', '0', True),             # IXXAT USB-to-CAN (CAN FD 지원)
                ('socketcan', 'can0', True),      # SocketCAN (CAN FD 지원)
                # 일반 CAN 인터페이스들
                ('pcan', 'PCAN_USBBUS1', False),  # PEAK PCAN-USB (CAN만)
                ('vector', '0', False),           # Vector CANoe/CANalyzer (CAN만)
                ('ixxat', '0', False),            # IXXAT USB-to-CAN (CAN만)
                ('socketcan', 'can0', False),     # SocketCAN (CAN만)
                ('virtual', 'vcan0', False),      # Virtual CAN (테스트용)
            ]
            
            connected = False
            # 채널별 우선 후보 구성 (요청: CH1=vector 3, CH2=vector 2)
            preferred = []
            if channel_index == 1:
                preferred = [('vector', '3', True), ('vector', '3', False)]
            else:
                preferred = [('vector', '2', True), ('vector', '2', False)]

            # 1차 목록 시도 후 실패 시 2차 목록도 시도
            candidates = preferred + interfaces_to_try + []
            try:
                candidates += interfaces_to_try2
            except NameError:
                pass

            for interface, channel, is_can_fd in candidates:
                try:
                    if is_can_fd:
                        # CAN FD 연결 시도
                        bus = can.interface.Bus(
                            channel=channel, 
                            interface=interface,
                            bitrate=500000,  # 데이터 비트레이트 500kbps
                            fd=True,         # CAN FD 활성화
                            data_bitrate=2000000  # 데이터 비트레이트 2Mbps
                        )
                        if channel_index == 1:
                            self.can_interface_ch1 = bus
                            self.can_channel_ch1 = channel
                        else:
                            self.can_interface_ch2 = bus
                            self.can_channel_ch2 = channel
                        connected = True
                        print(f"CH{channel_index} CAN FD 연결 성공: {interface} - {channel}")
                    else:
                        # 일반 CAN 연결 시도
                        bus = can.interface.Bus(
                            channel=channel, 
                            interface=interface,
                            bitrate=500000  # 500kbps
                        )
                        if channel_index == 1:
                            self.can_interface_ch1 = bus
                            self.can_channel_ch1 = channel
                        else:
                            self.can_interface_ch2 = bus
                            self.can_channel_ch2 = channel
                        connected = True
                        print(f"CH{channel_index} CAN 연결 성공: {interface} - {channel}")
                    
                    # Virtual CAN으로 연결된 경우 더미 데이터 시뮬레이션 시작
                    if interface == 'virtual' and channel_index == 1:
                        print("CH1 Virtual CAN으로 연결됨. 더미 데이터 시뮬레이션을 시작합니다.")
                        self.start_dummy_data_simulation()
                    
                    break
                except Exception as e:
                    print(f"CAN 인터페이스 연결 실패: {interface} - {channel} (CAN FD: {is_can_fd}), 오류: {e}")
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
                    
                    bus = can.interface.Bus(
                        channel=channel, 
                        interface='virtual',
                        bitrate=500000
                    )
                    if channel_index == 1:
                        self.can_interface_ch1 = bus
                        self.can_channel_ch1 = channel
                    else:
                        self.can_interface_ch2 = bus
                        self.can_channel_ch2 = channel
                    connected = True
                    print(f"CH{channel_index} Virtual CAN 연결 성공.")
                    if channel_index == 1:
                        self.start_dummy_data_simulation()
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
            
            if channel_index == 1:
                self.btn_connect_ch1.setEnabled(False)
                self.btn_disconnect_ch1.setEnabled(True)
            else:
                self.btn_connect_ch2.setEnabled(False)
                self.btn_disconnect_ch2.setEnabled(True)
            self.btn_start.setEnabled(True)
            
        except Exception as e:
            print(f"CAN 연결 중 오류 발생: {e}")

    def disconnect_can(self, channel_index=1):
        """CAN 인터페이스 연결 해제"""
        try:
            # 더미 데이터 시뮬레이션 중지
            if self.dummy_simulation_active:
                self.stop_dummy_data_simulation()
            
            if channel_index == 1:
                if self.can_interface_ch1:
                    self.can_interface_ch1.shutdown()
                    self.can_interface_ch1 = None
                    self.can_channel_ch1 = None
                    print("CH1 연결 해제됨")
            else:
                if self.can_interface_ch2:
                    self.can_interface_ch2.shutdown()
                    self.can_interface_ch2 = None
                    self.can_channel_ch2 = None
                    print("CH2 연결 해제됨")
            
            if channel_index == 1:
                self.btn_connect_ch1.setEnabled(True)
                self.btn_disconnect_ch1.setEnabled(False)
            else:
                self.btn_connect_ch2.setEnabled(True)
                self.btn_disconnect_ch2.setEnabled(False)
            self.btn_start.setEnabled(False)
            self.btn_stop.setEnabled(False)
            
            if self.receive_active:
                self.stop_receiving()
                
        except Exception as e:
            print(f"CAN 연결 해제 중 오류 발생: {e}")


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
        """차량 상태 데이터 생성 (8바이트)"""
        speed_raw = self._to_int16(speed, 0.01)
        steering_raw = self._to_int16(steering, 0.1)
        # 8바이트 데이터: speed(2) + steering(2) + padding(4)
        return speed_raw.to_bytes(2, 'little', signed=True) + steering_raw.to_bytes(2, 'little', signed=True) + bytes(4)

    def _create_accel_data(self, lat_accel):
        """가속도 데이터 생성 (8바이트)"""
        lat_accel_raw = int(lat_accel / 0.001)
        # 8바이트 데이터: lat_accel(2) + padding(6)
        return lat_accel_raw.to_bytes(2, 'little', signed=True) + bytes(6)

    def _create_lane_data(self, lane_data):
        """차선 데이터 생성 (8바이트)"""
        # 8바이트 데이터: lane_data(4) + padding(4)
        return bytes(lane_data) + bytes(4)

    def _create_radar_data(self, rel_pos_x, rel_pos_y, rel_vel_x, rel_acc_x):
        """레이더 데이터 생성 (8바이트)"""
        x_raw = self._to_raw(rel_pos_x)
        y_raw = self._to_raw(rel_pos_y)
        vel_raw = self._to_raw(rel_vel_x)
        acc_raw = self._to_raw(rel_acc_x)
        
        # 8바이트 데이터: x(2) + y(2) + vel(2) + acc(2)
        return (x_raw.to_bytes(2, 'little') +
                y_raw.to_bytes(2, 'little') +
                vel_raw.to_bytes(2, 'little') +
                acc_raw.to_bytes(2, 'little'))


    def start_receiving(self):
        if not (self.can_interface_ch1 or self.can_interface_ch2):
            print("CAN 인터페이스가 연결되지 않았습니다. CH1/CH2 중 하나 이상을 먼저 연결하세요.")
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

    def toggle_sort(self):
        """정렬 모드 토글"""
        self.sort_by_name = not self.sort_by_name
        if self.sort_by_name:
            self.btn_sort.setText("Sort by Time")
            self.btn_sort.setStyleSheet("background-color: #4CAF50; color: white;")
        else:
            self.btn_sort.setText("Sort by Name")
            self.btn_sort.setStyleSheet("")
        
        # 테이블 새로고침
        self.refresh_table()

    def toggle_reverse(self):
        """역순 정렬 토글"""
        self.sort_reverse = not self.sort_reverse
        if self.sort_reverse:
            self.btn_reverse.setText("Normal")
            self.btn_reverse.setStyleSheet("background-color: #FF9800; color: white;")
        else:
            self.btn_reverse.setText("Reverse")
            self.btn_reverse.setStyleSheet("")
        
        # 테이블 새로고침
        self.refresh_table()

    def initialize_pinned_rows(self):
        """DBC 로드 상태를 기반으로 채널별 고정 표시 행을 미리 구성"""
        self.pinned_rows = {"CH1": {}, "CH2": {}}
        if not self.chk_pin.isChecked():
            return
        mapping = {
            "CH1": self.tsmaster_processor_ch1,
            "CH2": self.tsmaster_processor_ch2,
        }
        for ch, processor in mapping.items():
            try:
                defs = processor.get_message_definitions()
                for msg_def in defs.values():
                    msg_name = msg_def['message'].name
                    for sig_name, sig_def in msg_def['signals'].items():
                        unit = getattr(sig_def, 'unit', '') or ''
                        self.pinned_rows[ch][(msg_name, sig_name)] = ("", None, unit)
            except Exception:
                continue
        self.refresh_table()

    # 추가 메서드: CIPV 기반 RDR to CAM Projection
    def setup_cipv_pipeline(self):
        # 1) 아래 이름들을 DBC에 맞게 교체하세요
        CIPV_MSG_NAME = "A_ADAS_DRV_01_10ms"      # CIPV 정보 메시지명
        CIPV_SIGNAL_NAME = "ADAS_DRV_ICCCIPVFrRdrIDVal"          # CIPV 객체 번호 신호명
        # CIPV_SIGNAL_NAME = "ADAS_DRV_EMCIPVFrRdrIDVal"          # CIPV 객체 번호 신호명

        OBJ_BASE_NAME = "A_FR_RDR_Obj"       # 객체 메시지 접두어 (패턴 A)
        OBJ_NAME_FORMAT = lambda obj_id: f"{OBJ_BASE_NAME}_{int(obj_id)}"  # 예: FR_RDR_OBJ_3
        OBJ_HAS_ID_SIGNAL = False           # 패턴 B(단일 메시지에 ObjectID 신호 존재)면 True
        OBJ_ID_SIGNAL_NAME = "ObjectID"    # 패턴 B에서 객체 번호 신호명

        # 동적으로 신호 이름을 생성하는 함수
        def get_pos_signals(obj_id):
            """CIPV 객체 ID에 해당하는 위치 신호 이름들을 반환"""
            if obj_id is None:
                return None, None
            # 01, 02, 03... 형태로 포맷팅 (2자리, 앞에 0 패딩)
            id_str = f"{int(obj_id):02d}"
            return f"FR_RDR_Obj_RelPosX{id_str}Val", f"FR_RDR_Obj_RelPosY{id_str}Val"

        # 상태
        self.cipv_id = {"CH1": None, "CH2": None}
        self.cipv_pos = {
            "CH1": {"x": None, "y": None, "ts": None},
            "CH2": {"x": None, "y": None, "ts": None},
        }
        
        # 실시간 projection을 위한 데이터 저장소 (다른 파이썬 파일에서 접근 가능)
        self.cipv_projection_data = {
            "CH1": {"x": None, "y": None, "obj_id": None, "timestamp": None, "valid": False},
            "CH2": {"x": None, "y": None, "obj_id": None, "timestamp": None, "valid": False}
        }

        def cipv_filter(ch, msg_name, sig_name, value, ts):
            return msg_name == CIPV_MSG_NAME and sig_name == CIPV_SIGNAL_NAME

        def cipv_handler(ch, msg_name, sig_name, value, ts):
            try:
                self.cipv_id[ch] = int(value) + 1 # CIPV 객체 아이디는 0부터 시작함
            except Exception:
                self.cipv_id[ch] = None

        def obj_filter(ch, msg_name, sig_name, value, ts):
            obj_id = self.cipv_id.get(ch)
            if obj_id is None:
                return False
            
            # 동적으로 신호 이름 생성
            pos_x_signal, pos_y_signal = get_pos_signals(obj_id)
            if pos_x_signal is None or pos_y_signal is None:
                return False
                
            if not OBJ_HAS_ID_SIGNAL:
                return msg_name == OBJ_NAME_FORMAT(obj_id) and sig_name in (pos_x_signal, pos_y_signal)
            if sig_name not in (pos_x_signal, pos_y_signal):
                return False
            latest_obj_id = self.latest_values.get((ch, OBJ_ID_SIGNAL_NAME), (None, None))[0]
            return latest_obj_id == obj_id

        def obj_handler(ch, msg_name, sig_name, value, ts):
            obj_id = self.cipv_id.get(ch)
            if obj_id is None:
                return
                
            # 동적으로 신호 이름 생성
            pos_x_signal, pos_y_signal = get_pos_signals(obj_id)
            if pos_x_signal is None or pos_y_signal is None:
                return
                
            pos = self.cipv_pos[ch]
            if sig_name == pos_x_signal:
                pos["x"] = value
            elif sig_name == pos_y_signal:
                pos["y"] = value
            pos["ts"] = ts
            
            # x, y 데이터가 모두 있을 때 projection 데이터 업데이트
            if pos["x"] is not None and pos["y"] is not None:
                # 실시간 projection을 위한 데이터 저장 (다른 파이썬 파일에서 접근 가능)
                self.cipv_projection_data[ch].update({
                    "x": pos["x"],
                    "y": pos["y"], 
                    "obj_id": self.cipv_id[ch],
                    "timestamp": ts,
                    "valid": True
                })
                
                # 디버깅용 출력 (필요시 주석 해제)
                # print(f"[{ch}] CIPV#{self.cipv_id[ch]} X={pos['x']:.2f} Y={pos['y']:.2f}")
                
                # 여기서 카메라 projection 처리 함수 호출 가능
                # self.process_camera_projection(ch, pos["x"], pos["y"], self.cipv_id[ch])

        # 등록
        self.register_processing_handler(cipv_filter, cipv_handler)
        self.register_processing_handler(obj_filter, obj_handler)

    def get_cipv_projection_data(self, channel="CH1"):
        """다른 파이썬 파일에서 CIPV projection 데이터에 접근하기 위한 메서드"""
        return self.cipv_projection_data.get(channel, {
            "x": None, "y": None, "obj_id": None, "timestamp": None, "valid": False
        })
    
    def get_all_cipv_projection_data(self):
        """모든 채널의 CIPV projection 데이터 반환"""
        return self.cipv_projection_data.copy()
    
    def is_cipv_data_valid(self, channel="CH1"):
        """특정 채널의 CIPV 데이터가 유효한지 확인"""
        data = self.cipv_projection_data.get(channel, {})
        return data.get("valid", False)

    # ========= 데이터 처리 API =========
    def register_processing_handler(self, filter_fn, handler):
        """실시간 처리 핸들러 등록
        filter_fn(ch, msg_name, sig_name, value, timestamp)->bool 가 True면 handler 호출
        handler(ch, msg_name, sig_name, value, timestamp) 시그니처로 호출됨
        """
        self.processing_handlers.append((filter_fn, handler))

    def unregister_processing_handler(self, handler):
        self.processing_handlers = [(f, h) for (f, h) in self.processing_handlers if h is not handler]

    def _run_processing_handlers(self, ch, msg_name, sig_name, value, timestamp):
        for f, h in list(self.processing_handlers):
            try:
                if f(ch, msg_name, sig_name, value, timestamp):
                    h(ch, msg_name, sig_name, value, timestamp)
            except Exception as e:
                print(f"Processing handler error: {e}")

    def sort_messages(self, messages):
        """메시지 정렬"""
        if self.sort_by_name:
            # 메시지 이름으로 정렬 (신호 이름도 고려)
            return sorted(messages, key=lambda x: (x[2], x[3]), reverse=self.sort_reverse)
        else:
            # 시간순 정렬 (기본)
            if self.sort_reverse:
                return list(reversed(messages))
            return messages

    def filter_messages(self, messages):
        """메시지 필터링"""
        if not self.filter_active:
            return messages
        
        filtered = []
        for row in messages:
            time, ch, msg, sig, val, unit = row
            # 메시지 이름 필터링
            if self.filter_message and self.filter_message.lower() not in msg.lower():
                continue
            # 신호 이름 필터링
            if self.filter_signal and self.filter_signal.lower() not in sig.lower():
                continue
            filtered.append((time, ch, msg, sig, val, unit))
        
        return filtered

    def show_filter_dialog(self):
        """필터 설정 다이얼로그 표시"""
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("메시지 필터 설정")
        dialog.setModal(True)
        dialog.resize(400, 200)
        
        layout = QtWidgets.QVBoxLayout(dialog)
        
        # 메시지 이름 필터
        msg_layout = QtWidgets.QHBoxLayout()
        msg_layout.addWidget(QtWidgets.QLabel("메시지 이름:"))
        msg_edit = QtWidgets.QLineEdit(self.filter_message)
        msg_edit.setPlaceholderText("예: VehicleStatus, RadarObj1")
        msg_layout.addWidget(msg_edit)
        layout.addLayout(msg_layout)
        
        # 신호 이름 필터
        sig_layout = QtWidgets.QHBoxLayout()
        sig_layout.addWidget(QtWidgets.QLabel("신호 이름:"))
        sig_edit = QtWidgets.QLineEdit(self.filter_signal)
        sig_edit.setPlaceholderText("예: VehicleSpeed, RelPosX1")
        sig_layout.addWidget(sig_edit)
        layout.addLayout(sig_layout)
        
        # 버튼들
        btn_layout = QtWidgets.QHBoxLayout()
        
        apply_btn = QtWidgets.QPushButton("적용")
        clear_btn = QtWidgets.QPushButton("필터 해제")
        cancel_btn = QtWidgets.QPushButton("취소")
        
        apply_btn.clicked.connect(lambda: self.apply_filter(msg_edit.text(), sig_edit.text(), dialog))
        clear_btn.clicked.connect(lambda: self.clear_filter(dialog))
        cancel_btn.clicked.connect(dialog.reject)
        
        btn_layout.addWidget(apply_btn)
        btn_layout.addWidget(clear_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)
        
        dialog.exec_()

    def on_row_limit_changed(self, value):
        """표시 행수 변경 콜백"""
        self.display_limit = int(value)
        self.refresh_table()

    def load_dbc_dialog(self, channel_index=1):
        """DBC 파일 선택 및 재로드"""
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select DBC file", "", "DBC Files (*.dbc);;All Files (*)")
        if path:
            processor = self.tsmaster_processor_ch1 if channel_index == 1 else self.tsmaster_processor_ch2
            ok = processor.reload_dbc(path)
            if ok:
                print(f"CH{channel_index} DBC reloaded: {path}")
                self.initialize_pinned_rows()
            else:
                print(f"CH{channel_index} DBC reload failed: {path}")

    def on_toggle_defaults(self, state):
        """디코딩 실패 시 기본값 사용 토글"""
        self.tsmaster_processor_ch1.config['use_default_on_decode_error'] = bool(state)
        self.tsmaster_processor_ch2.config['use_default_on_decode_error'] = bool(state)

    def apply_filter(self, message_filter, signal_filter, dialog):
        """필터 적용"""
        self.filter_message = message_filter.strip()
        self.filter_signal = signal_filter.strip()
        self.filter_active = bool(self.filter_message or self.filter_signal)
        
        if self.filter_active:
            self.btn_filter.setText("Filter ON")
            self.btn_filter.setStyleSheet("background-color: #2196F3; color: white;")
        else:
            self.btn_filter.setText("Filter")
            self.btn_filter.setStyleSheet("")
        
        dialog.accept()
        self.refresh_table()

    def clear_filter(self, dialog):
        """필터 해제"""
        self.filter_message = ""
        self.filter_signal = ""
        self.filter_active = False
        self.btn_filter.setText("Filter")
        self.btn_filter.setStyleSheet("")
        
        dialog.accept()
        self.refresh_table()

    def add_can_message(self, msg, channel_label="CH1"):
        if not self.receive_active:
            return

        try:
            # TSMaster 스타일 고급 CAN 데이터 처리기 사용
            processor = self.tsmaster_processor_ch1 if channel_label == "CH1" else self.tsmaster_processor_ch2
            advanced_msg = processor.process_message(msg)
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

            # 채널 마지막 수신 시간 기록
            try:
                self.last_rx_time[channel_label] = time.time()
            except Exception:
                pass

            # 메시지 상태에 따른 처리
            if advanced_msg.status == MessageStatus.VALID:
                for sig_name, val in advanced_msg.signals.items():
                    # 단위 조회
                    unit = ""
                    try:
                        message_def = processor.get_message_definitions().get(advanced_msg.message_id)
                        if message_def:
                            sig_def = message_def['signals'].get(sig_name)
                            if sig_def is not None and getattr(sig_def, 'unit', None):
                                unit = sig_def.unit or ""
                    except Exception:
                        unit = ""
                    self.messages.append((display_time, channel_label, advanced_msg.message_name, sig_name, val, unit))
                    # 핀 모드일 때 상태 업데이트
                    if self.chk_pin.isChecked():
                        key = (advanced_msg.message_name, sig_name)
                        self.pinned_rows[channel_label][key] = (display_time, val, unit)
                    # 최신값 저장 및 사용자 핸들러 호출
                    ts_float = time.time()
                    self.latest_values[(channel_label, sig_name)] = (val, ts_float)
                    self._run_processing_handlers(channel_label, advanced_msg.message_name, sig_name, val, ts_float)

                # 레이더 데이터 처리 (ID 200-209)
                if 200 <= advanced_msg.message_id <= 209:
                    self._process_radar_data(advanced_msg.message_id, advanced_msg.signals, elapsed_sec)

                if self.logging_active:
                    if self.last_logged_time is None or elapsed_sec > self.last_logged_time:
                        self.last_logged_time = elapsed_sec
                        new_row = self.current_data.copy()
                        new_row['Timestamp'] = timestamp_seconds_str
                        self.logged_rows.append(new_row)

                    for sig_name, val in advanced_msg.signals.items():
                        self.current_data[sig_name] = val
            else:
                # 유효하지 않은 메시지도 표시 (상세한 오류 정보 포함)
                status_info = f"{advanced_msg.status.value.upper()}"
                error_info = f"{status_info}: {advanced_msg.error_message}" if advanced_msg.error_message else status_info
                self.messages.append((display_time, channel_label, advanced_msg.message_name, error_info, 
                                    f"DLC:{advanced_msg.dlc}, Retry:{advanced_msg.retry_count}", ""))
                
                if advanced_msg.status != MessageStatus.VALID:
                    print(f"CAN 메시지 처리 실패 - ID: {advanced_msg.message_id}, "
                          f"상태: {advanced_msg.status.value}, 오류: {advanced_msg.error_message}")

            # 내부 메시지 보존 개수 제한
            if len(self.messages) > self.max_messages:
                self.messages = self.messages[-self.max_messages:]

        except Exception as e:
            print(f"CAN 메시지 처리 중 예외 발생 (ID:{msg.arbitration_id}): {e}")

    def _process_radar_data(self, msg_id, signals, timestamp):
        """레이더 데이터 처리 및 RadarDataManager 업데이트"""
        try:
            if not self.show_radar:
                return
            # 메시지 ID에서 객체 번호 추출 (200-209 -> 1-10)
            object_id = msg_id - 199
            
            # 신호 이름에서 데이터 추출
            rel_pos_x = signals.get(f'RelPosX{object_id}')
            rel_pos_y = signals.get(f'RelPosY{object_id}')
            rel_vel_x = signals.get(f'RelVelX{object_id}')
            rel_acc_x = signals.get(f'RelAccX{object_id}')

            # 폴백: 이름이 다른 경우 숫자형 4개 값을 순서대로 매핑
            if any(v is None for v in (rel_pos_x, rel_pos_y, rel_vel_x, rel_acc_x)):
                numeric_values = [v for v in signals.values() if isinstance(v, (int, float))]
                if len(numeric_values) >= 4:
                    rel_pos_x = numeric_values[0] if rel_pos_x is None else rel_pos_x
                    rel_pos_y = numeric_values[1] if rel_pos_y is None else rel_pos_y
                    rel_vel_x = numeric_values[2] if rel_vel_x is None else rel_vel_x
                    rel_acc_x = numeric_values[3] if rel_acc_x is None else rel_acc_x
                # 부족하면 0으로
                rel_pos_x = 0 if rel_pos_x is None else rel_pos_x
                rel_pos_y = 0 if rel_pos_y is None else rel_pos_y
                rel_vel_x = 0 if rel_vel_x is None else rel_vel_x
                rel_acc_x = 0 if rel_acc_x is None else rel_acc_x
            
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
            if self.chk_pin.isChecked():
                # 고정 표시: DBC에 있는 메시지/신호를 기준으로 채널별 최신값을 표시
                display = []
                channels = ["CH1", "CH2"] if self.view_channel.currentText() == "All" else [self.view_channel.currentText()]
                for ch in channels:
                    for (msg, sig), (ts, val, unit) in self.pinned_rows[ch].items():
                        display.append((ts, ch, msg, sig, val, unit))
            else:
                # 메인 테이블 업데이트 (필터링 및 정렬 적용)
                display = self.messages[-self.display_limit:]
                display = self.filter_messages(display)
                # 채널 뷰 필터
                view = self.view_channel.currentText()
                if view in ("CH1", "CH2"):
                    display = [row for row in display if row[1] == view]
                if self.chk_collapse.isChecked():
                    # (Message, Signal) 별 최신 값만 유지
                    latest_by_key = {}
                    for time, ch, msg, sig, val, unit in display:
                        latest_by_key[(ch, msg, sig, unit)] = (time, ch, msg, sig, val, unit)
                    display = list(latest_by_key.values())
                display = self.sort_messages(display)
            self.table.setRowCount(len(display))
            for row, (time, ch, msg, sig, val, unit) in enumerate(display):
                self.table.setItem(row, 0, QtWidgets.QTableWidgetItem(time))
                self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(ch))
                self.table.setItem(row, 2, QtWidgets.QTableWidgetItem(msg))
                self.table.setItem(row, 3, QtWidgets.QTableWidgetItem(sig))
                self.table.setItem(row, 4, QtWidgets.QTableWidgetItem(str(val)))
                self.table.setItem(row, 5, QtWidgets.QTableWidgetItem(unit))
            
            # 레이더 테이블 업데이트 (비활성)
            if self.show_radar:
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
            
            # TSMaster 스타일 통계 업데이트
            # 간단히 CH1 통계 표시 (핀 모드/뷰와 무관)
            stats = self.tsmaster_processor_ch1.get_statistics()
            stats_text = (f"TSMaster CAN Stats - Total: {stats['total_messages']}, "
                         f"Valid: {stats['valid_messages']}, "
                         f"Errors: {stats['invalid_messages']}, "
                         f"DLC Mismatch: {stats['dlc_mismatches']}, "
                         f"Success Rate: {stats.get('success_rate', 0):.1f}%, "
                         f"Avg Time: {stats.get('average_processing_time', 0)*1000:.2f}ms")
            self.stats_label.setText(stats_text)
            
        except Exception as e:
            print(f"레이더 테이블 업데이트 실패: {e}")


def can_listener_channel(viewer, channel_label):
    """채널별 CAN 메시지 수신 스레드 (작은 타임아웃으로 블로킹 수신)"""
    while True:
        try:
            if not viewer.receive_active:
                time.sleep(0.1)
                continue
            bus = viewer.can_interface_ch1 if channel_label == "CH1" else viewer.can_interface_ch2
            if not bus:
                time.sleep(0.1)
                continue
            msg = bus.recv(timeout=0.02)  # 20ms 블로킹
            if msg is not None:
                viewer.add_can_message(msg, channel_label=channel_label)
        except Exception as e:
            print(f"CAN 수신 오류({channel_label}): {e}")
            time.sleep(0.2)


def main():
    app = QtWidgets.QApplication(sys.argv)
    viewer = CanDataViewer("sensor_data_20250915.dbc")
    viewer.show()

    # CAN 수신 스레드 시작 (채널별)
    listen_thread_ch1 = threading.Thread(target=can_listener_channel, args=(viewer, "CH1"), daemon=True)
    listen_thread_ch2 = threading.Thread(target=can_listener_channel, args=(viewer, "CH2"), daemon=True)
    listen_thread_ch1.start()
    listen_thread_ch2.start()

    try:
        sys.exit(app.exec_())
    except KeyboardInterrupt:
        print("프로그램이 Ctrl+C로 종료되었습니다.")
        viewer.disconnect_can(channel_index=1)
        viewer.disconnect_can(channel_index=2)



if __name__ == "__main__":
    main()
