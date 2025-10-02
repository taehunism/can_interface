import can
import random
import time

def random_int16(min_val, max_val):
    # 16비트 부호 있는 범위 내 정수 변환 함수
    val = random.uniform(min_val, max_val)
    return int(val * 10)  # 스케일 0.1 적용 가정
def to_int16(val, scale):
    raw = int(val / scale)
    if raw < -32768:
        raw = -32768
    elif raw > 32767:
        raw = 32767
    return raw
def main():
    bus = can.interface.Bus(channel='vcan0', interface='socketcan')

    while True:
        # 100 메시지 - 차량 속도 및 스티어링 앵글
        speed = random.uniform(0, 250)
        steering = random.uniform(-7800, 7800)

        
        speed_raw = to_int16(speed, 0.01)
        steering_raw = to_int16(steering, 0.1)

        data_100 = speed_raw.to_bytes(2, 'little', signed=True) + steering_raw.to_bytes(2, 'little', signed=True) + bytes(4)

        msg_100 = can.Message(arbitration_id=100, data=data_100, is_extended_id=False)
        bus.send(msg_100)

        # 101 메시지 - 횡가속도
        lat_accel = random.uniform(-10, 10)
        lat_accel_raw = int((lat_accel) / 0.001)
        data_101 = lat_accel_raw.to_bytes(2, 'little', signed=True) + bytes(6)
        msg_101 = can.Message(arbitration_id=101, data=data_101, is_extended_id=False)
        bus.send(msg_101)

        # 102 메시지 - 차선정보 c0,c1,c2,c3 (0 또는 1)
        lane_c0 = random.randint(0, 1)
        lane_c1 = random.randint(0, 1)
        lane_c2 = random.randint(0, 1)
        lane_c3 = random.randint(0, 1)
        data_102 = bytes([lane_c0, lane_c1, lane_c2, lane_c3]) + bytes(4)
        msg_102 = can.Message(arbitration_id=102, data=data_102, is_extended_id=False)
        bus.send(msg_102)

        # 200~209 메시지 - 10개 레이더 객체
        for i in range(200, 210):
            rel_pos_x = random.uniform(-1000, 1000)
            rel_pos_y = random.uniform(-1000, 1000)
            rel_vel_x = random.uniform(-100, 100)
            rel_acc_x = random.uniform(-50, 50)

            def to_raw(val, scale=0.1, offset=0):
                raw = int((val - offset) / scale)
                # 16비트 signed 저장용
                if raw < 0:
                    raw = (1 << 16) + raw
                return raw

            x_raw = to_raw(rel_pos_x)
            y_raw = to_raw(rel_pos_y)
            vel_raw = to_raw(rel_vel_x)
            acc_raw = to_raw(rel_acc_x)

            data = (x_raw.to_bytes(2, 'little') +
                    y_raw.to_bytes(2, 'little') +
                    vel_raw.to_bytes(2, 'little') +
                    acc_raw.to_bytes(2, 'little'))

            msg_radar = can.Message(arbitration_id=i, data=data, is_extended_id=False)
            bus.send(msg_radar)

        time.sleep(0.1)

if __name__ == "__main__":
    main()
