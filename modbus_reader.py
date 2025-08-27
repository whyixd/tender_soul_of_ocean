import logging.handlers
from pymodbus.client import ModbusSerialClient
from pymodbus import FramerType, ModbusException

from serial_device_finder import find_usb_serial_device
import logging
import time

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
            framer=FramerType.RTU,
            baudrate=9600,
            timeout=3,
            retries=5,
            bytesize=8,
            parity="N",
            stopbits=1,
        )
        self.connection = self.client.connect()

    def read_sensor_data(self):
        if not self.client.connected:
            self.client.connect()
        if self.client.connected:
            try:
                time.sleep(0.5)
                res = self.client.read_holding_registers(address=500, count=2, slave=1)
                if res.isError():
                    modbus_logger.error("Modbus 讀取失敗")
                    return [0, 0, 0, "unknown"]
                wind_speed = res.registers[0] / 10.0
                wind_level = res.registers[1]
                time.sleep(0.5)
                res2 = self.client.read_holding_registers(address=502, count=2, slave=1)
                if res2.isError():
                    modbus_logger.error("Modbus 讀取失敗")
                    return [0, 0, 0, "unknown"]
                wind_direction = self.get_wind_direction(res2.registers[0])
                wind_angle = res2.registers[1]
                # wind_level = 0
                # wind_direction = "unknown"
                # wind_angle = 0
                time.sleep(0.5)  # 請求之間增加延遲
                res3 = self.client.read_holding_registers(address=504, count=2, slave=1)
                humidity = res3.registers[0] / 10.0
                temperature = res3.registers[1] / 10.0
                if res3.isError():
                    modbus_logger.error("Modbus 讀取失敗")
                    return [0, 0, 0, "unknown"]
                modbus_logger.info(
                    f"風速: {wind_speed} m/s, 風級: {wind_level}, 風向角度: {wind_angle}, 風向: {wind_direction}, 濕度: {humidity}%, 溫度: {temperature}°C"
                )
                return [
                    wind_speed,
                    wind_level,
                    wind_angle,
                    wind_direction,
                    humidity,
                    temperature,
                ]
            except ModbusException as e:
                modbus_logger.error(f"讀取 Modbus 失敗: {e}")
                return [0, 0, 0, "unknown"]
            except Exception as e:
                modbus_logger.error(f"發生錯誤: {e}")
                return [0, 0, 0, "unknown"]

        return None

    def get_wind_direction(self, wind_direction):
        """根據風向數值轉換成風向文字"""
        if wind_direction == 0:
            return "N"
        elif wind_direction == 1:
            return "NE"
        elif wind_direction == 2:
            return "E"
        elif wind_direction == 3:
            return "SE"
        elif wind_direction == 4:
            return "S"
        elif wind_direction == 5:
            return "SW"
        elif wind_direction == 6:
            return "W"
        elif wind_direction == 7:
            return "NW"
        else:
            return "unknown"

    # def get_wind_direction(self, angle):
    #     """根據角度轉換成風向文字"""
    #     directions = [
    #         "北",
    #         "北北東",
    #         "東北",
    #         "東北東",
    #         "東",
    #         "東南東",
    #         "東南",
    #         "南南東",
    #         "南",
    #         "南南西",
    #         "西南",
    #         "西南西",
    #         "西",
    #         "西北西",
    #         "西北",
    #         "北北西",
    #         "北",
    #     ]
    #     index = round(angle / 22.5) % 16
    #     return directions[index]

    def close(self):
        self.client.close()

# if __name__ == "__main__":
#     com_port = find_usb_serial_device(vid="0403", pid="6001")
#     if com_port is None:
#         modbus_logger.warning("找不到 風速計 設備")
#     else:
#         modbus_logger.info(f"找到 風速計 設備: {com_port}")
#     modbus = ModbusReader(com_port=com_port)


#     def continuous_read():
#         import time

#         while True:
#             modbus.read_sensor_data()
#             time.sleep(3)


#     continuous_read()


#     modbus.close()
