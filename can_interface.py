import sys
from PyQt5 import QtWidgets, QtCore, QtGui
import can
import cantools
import threading
import pandas as pd


class CanDataViewer(QtWidgets.QWidget):
    def __init__(self, dbc_path):
        super().__init__()

        self.setWindowTitle("TAEHUNISM")
        self.resize(800, 600)

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

        # UI 버튼 생성
        self.btn_start = QtWidgets.QPushButton("Start", self)
        self.btn_stop = QtWidgets.QPushButton("Stop", self)
        self.btn_delta_t = QtWidgets.QPushButton("Period", self)
        self.btn_log = QtWidgets.QPushButton("Log Start", self)
        self.btn_log_end = QtWidgets.QPushButton("Log End", self)

        btn_font = QtGui.QFont("Arial", 11, QtGui.QFont.Bold)
        for btn in (self.btn_start, self.btn_stop, self.btn_delta_t, self.btn_log, self.btn_log_end):
            btn.setFont(btn_font)
            btn.setFixedHeight(40)

        self.btn_stop.setEnabled(False)
        self.btn_log.setEnabled(True)  # Log Start는 사용 가능
        self.btn_log_end.setEnabled(False)  # Log End는 초기 비활성

        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.setSpacing(20)
        btn_layout.addWidget(self.btn_start)
        btn_layout.addWidget(self.btn_stop)
        btn_layout.addWidget(self.btn_delta_t)
        btn_layout.addWidget(self.btn_log)
        btn_layout.addWidget(self.btn_log_end)

        self.table = QtWidgets.QTableWidget(self)
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(['Timestamp', 'Message', 'Signal', 'Value'])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("alternate-background-color: #ffffff; background-color: #ffffff;")

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.addLayout(btn_layout)
        main_layout.addWidget(self.table)

        # 버튼 이벤트 연결
        self.btn_start.clicked.connect(self.start_receiving)
        self.btn_stop.clicked.connect(self.stop_receiving)
        self.btn_delta_t.clicked.connect(self.toggle_delta_t)
        self.btn_log.clicked.connect(self.start_logging)
        self.btn_log_end.clicked.connect(self.end_logging)

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.refresh_table)
        self.timer.start(500)

    def start_receiving(self):
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

    def refresh_table(self):
        try:
            display = self.messages[-100:]
            self.table.setRowCount(len(display))
            for row, (time, msg, sig, val) in enumerate(display):
                self.table.setItem(row, 0, QtWidgets.QTableWidgetItem(time))
                self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(msg))
                self.table.setItem(row, 2, QtWidgets.QTableWidgetItem(sig))
                self.table.setItem(row, 3, QtWidgets.QTableWidgetItem(str(val)))
        except KeyboardInterrupt:
            print("사용자에 의한 인터럽트 발생 - 안전하게 종료합니다.")
            QtWidgets.qApp.quit()


def can_listener(bus, viewer):
    while True:
        msg = bus.recv(timeout=1)
        if msg is not None:
            viewer.add_can_message(msg)


def main():
    app = QtWidgets.QApplication(sys.argv)
    viewer = CanDataViewer("candb_ex.dbc")
    viewer.show()

    bus = can.interface.Bus(channel='vcan0', interface='socketcan')

    listen_thread = threading.Thread(target=can_listener, args=(bus, viewer), daemon=True)
    listen_thread.start()

    try:
        sys.exit(app.exec_())
    except KeyboardInterrupt:
        print("프로그램이 Ctrl+C로 종료되었습니다.")
        # 필요한 종료 정리 코드 추가 가능



if __name__ == "__main__":
    main()
