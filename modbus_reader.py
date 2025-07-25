import logging.handlers
from pymodbus.client import ModbusSerialClient
from serial_device_finder import find_usb_serial_device
import logging

modbus_logger = logging.getLogger("ModbusReader")
modbus_logger.setLevel(logging.DEBUG)
modbus_logger.propagate = False
modbus_stream_handler = logging.StreamHandler()

modbus_rotating_file_handler = logging.handlers.RotatingFileHandler(
    "modbus_reader.log", maxBytes=5 * 1024 * 1024, backupCount=10, encoding="utf-8"
)
modbus_stream_handler.setLevel(logging.DEBUG)
modbus_rotating_file_handler.setLevel(logging.DEBUG)
modbus_formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
)

modbus_stream_handler.setFormatter(modbus_formatter)
modbus_rotating_file_handler.setFormatter(modbus_formatter)
modbus_logger.addHandler(modbus_stream_handler)
modbus_logger.addHandler(modbus_rotating_file_handler)


class ModbusReader:
    def __init__(self, com_port="COM13"):
        self.client = ModbusSerialClient(
            port=com_port,
            baudrate=9600,
            timeout=1,
            bytesize=8,
            parity="N",
            stopbits=1,
        )

    def read_sensor_data(self):
        connection = self.client.connect()

        if connection:
            try:
                res = self.client.read_holding_registers(address=0, count=4, slave=1)
                if res.isError():
                    modbus_logger.error("Modbus 讀取失敗")
                    return [0, 0, 0, "未知"]
                wind_speed = res.registers[0] / 10.0
                wind_level = res.registers[1]
                wind_angle = res.registers[2] / 10
                wind_direction = self.get_wind_direction(wind_angle)
                modbus_logger.info(
                    f"風速: {wind_speed} m/s, 風級: {wind_level}, 風向角度: {wind_angle}, 風向: {wind_direction}"
                )
                return [wind_speed, wind_level, wind_angle, wind_direction]
            except Exception as e:
                modbus_logger.error(f"讀取 Modbus 失敗: {e}")
                return [0, 0, 0, "未知"]

        return None

    def get_wind_direction(self, angle):
        """根據角度轉換成風向文字"""
        directions = [
            "北",
            "北北東",
            "東北",
            "東北東",
            "東",
            "東南東",
            "東南",
            "南南東",
            "南",
            "南南西",
            "西南",
            "西南西",
            "西",
            "西北西",
            "西北",
            "北北西",
            "北",
        ]
        index = round(angle / 22.5) % 16
        return directions[index]

    def close(self):
        self.client.close()


# com_port = find_usb_serial_device(vid="0403", pid="6001")
# if com_port is None:
#     modbus_logger.warning("找不到 風速計 設備")
# else:
#     modbus_logger.info(f"找到 風速計 設備: {com_port}")
# modbus = ModbusReader(com_port=com_port)
