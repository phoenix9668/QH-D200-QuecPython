# import uos
# uos.chdir('/usr/')
from machine import UART
from machine import Pin
from umqtt import MQTTClient
import cellLocator
import _thread
import utime
import log
import checkNet
import sim
import ustruct
import ujson

Work_Led = Pin(Pin.GPIO12, Pin.OUT, Pin.PULL_DISABLE, 1)

PROJECT_NAME = "QuecPython_EC600U"
PROJECT_VERSION = "1.0.0"

checknet = checkNet.CheckNetwork(PROJECT_NAME, PROJECT_VERSION)
device_address = 0xFE
msg_id = 0

log.basicConfig(level=log.INFO)
app_log = log.getLogger("app_log")


def watch_dog_task():
    while True:
        if Work_Led.read():
            Work_Led.write(0)
        else:
            Work_Led.write(1)
        utime.sleep(10)


class Uart2(object):
    def __init__(self, no=UART.UART2, bate=115200, data_bits=8, parity=0, stop_bits=1, flow_control=0):
        self.uart = UART(no, bate, data_bits, parity, stop_bits, flow_control)
        self.uart.control_485(UART.GPIO28, 0)
        self.uart.set_callback(self.callback)
        self.modbus_rtu = None

    def set_modbus_rtu_instance(self, modbus_rtu_instance):
        self.modbus_rtu = modbus_rtu_instance

    def callback(self, para):
        app_log.info("call para:{}".format(para))
        if (0 == para[0]):
            self.uartRead(para[2])

    def uartWrite(self, msg):
        app_log.info("Write msg:{}".format(msg))
        self.uart.write(msg)

    def uartRead(self, len):
        msg = self.uart.read(len)
        hex_msg = [hex(x) for x in msg]
        app_log.info("Read msg: {}".format(hex_msg))
        if self.modbus_rtu:
            self.modbus_rtu.handle_response(msg)


class ModbusRTU:
    def __init__(self, device_address):
        self.device_address = device_address
        self.relay1_status = 0
        self.relay2_status = 0
        self.relay3_status = 0
        self.relay4_status = 0
        self.relay5_status = 0
        self.relay6_status = 0
        self.relay7_status = 0
        self.relay8_status = 0

    def calculate_crc(self, data):
        crc = 0xFFFF
        for pos in data:
            crc ^= pos
            for _ in range(8):
                if crc & 0x0001:
                    crc >>= 1
                    crc ^= 0xA001
                else:
                    crc >>= 1
        return crc

    def reverse_crc(self, crc):
        return ((crc & 0xFF) << 8) | ((crc >> 8) & 0xFF)

    def build_message(self, function_code, coil_address, value):
        # 构建 Modbus 请求消息
        message = ustruct.pack(
            '>BBHH', self.device_address, function_code, coil_address, value)
        # 计算 CRC 校验码
        crc = self.calculate_crc(message)
        crc_bytes = ustruct.pack('<H', crc)
        return message + crc_bytes

    def send_message(self, message, timeout=1000):
        uart_inst.uartWrite(message)
        utime.sleep_ms(100)  # 等待响应的时间，可以根据需要调整

    def handle_response(self, data):
        if len(data) < 6:
            app_log.error("Invalid response length")
            return
        elif len(data) == 8:
            address, function_code, coil_address, value, crc_received = ustruct.unpack(
                '>BBHHH', data)
        elif len(data) == 6:
            address, function_code, bytes_num, value, crc_received = ustruct.unpack(
                '>BBBBH', data)
        crc_calculated = self.calculate_crc(data[:-2])
        crc_calculated_swapped = self.reverse_crc(crc_calculated)
        if crc_received != crc_calculated_swapped:
            app_log.error("CRC mismatch: received=0x{:04X}, calculated=0x{:04X}".format(
                crc_received, crc_calculated))
        elif function_code == 0x05:
            app_log.info("Relay control successful: coil_address=0x{:04X}, value=0x{:04X}".format(
                coil_address, value))
        elif function_code == 0x81:
            app_log.error("Relay query status failure: bytes_num=0x{:02X}, value=0x{:02X}".format(
                bytes_num, value))
        elif function_code == 0x01:
            app_log.info("Relay query status successful: bytes_num=0x{:02X}, value=0x{:02X}".format(
                bytes_num, value))
            self.relay1_status = (value & 0x01)
            self.relay2_status = (value & 0x02) >> 1
            self.relay3_status = (value & 0x04) >> 2
            self.relay4_status = (value & 0x08) >> 3
            self.relay5_status = (value & 0x10) >> 4
            self.relay6_status = (value & 0x20) >> 5
            self.relay7_status = (value & 0x40) >> 6
            self.relay8_status = (value & 0x80) >> 7
            app_log.info("Relay 1 Status: {}".format(self.relay1_status))
            app_log.info("Relay 2 Status: {}".format(self.relay2_status))
            app_log.info("Relay 3 Status: {}".format(self.relay3_status))
            app_log.info("Relay 4 Status: {}".format(self.relay4_status))
            app_log.info("Relay 5 Status: {}".format(self.relay5_status))
            app_log.info("Relay 6 Status: {}".format(self.relay6_status))
            app_log.info("Relay 7 Status: {}".format(self.relay7_status))
            app_log.info("Relay 8 Status: {}".format(self.relay8_status))

    def control_relay(self, relay_number, state):
        coil_address = relay_number - 1
        value = 0xFF00 if state else 0x0000
        message = self.build_message(0x05, coil_address, value)
        self.send_message(message)

    def query_relay_status(self):
        message = self.build_message(0x01, 0x0000, 0x0008)
        self.send_message(message)


def cell_location_task():
    global msg_id
    while True:
        utime.sleep(86400)
        cell_location = cellLocator.getLocation(
            "www.queclocator.com", 80, "qa6qTK91597826z6", 8, 1)
        msg_id += 1
        mqtt_client.publish(property_publish_topic.encode(
            'utf-8'), msg_cellLocator.format
            (msg_id, cell_location[0], cell_location[1], cell_location[2]).encode('utf-8'))


def sim_task():
    global msg_id
    while True:
        sim_imsi = sim.getImsi()
        sim_iccid = sim.getIccid()
        msg_id += 1
        mqtt_client.publish(property_publish_topic.encode(
            'utf-8'), msg_sim.format(msg_id, sim_imsi, sim_iccid).encode('utf-8'))
        utime.sleep(7200)


def mqtt_sub_cb(topic, msg):
    app_log.info("Subscribe Recv: Topic={},Msg={}".format(
        topic, msg))
    # app_log.info("Subscribe Recv: Topic={},Msg={}".format(
    #     topic.decode(), msg.decode()))
    # msg_dict = ujson.loads(msg.get("msg").decode())
    # app_log.info(msg_dict)


def mqtt_err_cb(err):
    app_log.error("thread err:%s" % err)
    if err == "reconnect_start":
        app_log.error("start reconnect")
    elif err == "reconnect_success":
        app_log.error("success reconnect")
    else:
        app_log.error("reconnect FAIL")


if __name__ == '__main__':
    utime.sleep(5)
    stagecode, subcode = checknet.wait_network_connected(30)
    if stagecode == 3 and subcode == 1:
        app_log.info('Network connection successful!')

        uart_inst = Uart2()
        modbus_rtu = ModbusRTU(device_address=device_address)
        uart_inst.set_modbus_rtu_instance(modbus_rtu)

        _thread.start_new_thread(watch_dog_task, ())

        msg_cellLocator = """{{
                        "id": "{0}",
                        "version": "1.0",
                        "params": {{
                            "CellLocator": {{
                                "Longitude": {{
                                    "value": {1}
                                }},
                                "Latitude": {{
                                    "value": {2}
                                }},
                                "Accuracy": {{
                                "value": {3}
                                }}
                            }}
                        }},
                        "method": "thing.event.property.post"
                    }}"""

        msg_sim = """{{
                    "id": "{0}",
                    "version": "1.0",
                    "params": {{
                        "IMSI": {{
                            "value": "{1}"
                        }},
                        "ICCID": {{
                            "value": "{2}"
                        }}
                    }},
                    "method": "thing.event.property.post"
                }}"""

        msg_netStatus = """{{
                                        "id": "{0}",
                                        "version": "1.0",
                                        "params": {{
                                            "NetStatus": {{
                                                "StageCode": {{
                                                    "value": "{1}"
                                                }},
                                                "SubCode": {{
                                                    "value": "{2}"
                                                }}
                                            }}
                                        }},
                                        "method": "thing.event.property.post"
                                    }}"""

        msg_temperature_humidity = """{{
                                "id": "{0}",
                                "version": "1.0",
                                "params": {{
                                    "temperature": {{
                                        "value": {1}
                                    }},
                                    "humidity": {{
                                        "value": {2}
                                    }}
                                }},
                                "method": "thing.event.property.post"
                             }}"""

        msg_do_status = """{{
                                "id": "{0}",
                                "version": "1.0",
                                "params": {{
                                    "NO1": {{
                                        "value": {1}
                                    }},
                                    "NO2": {{
                                        "value": {2}
                                    }},
                                    "NO3": {{
                                        "value": {3}
                                    }},
                                    "NO4": {{
                                        "value": {4}    
                                    }},
                                    "NO5": {{
                                        "value": {5}
                                    }},
                                    "NO6": {{
                                        "value": {6}
                                    }},
                                    "NO7": {{
                                        "value": {7}
                                    }},
                                    "NO8": {{
                                        "value": {8}
                                    }}
                                }},
                                "method": "thing.event.property.post"
                             }}"""

        ProductKey = "he2myN7xfqd"  # 产品标识
        DeviceName = "QH-D200-485-001"  # 设备名称

        property_subscribe_topic = "/sys" + "/" + ProductKey + "/" + \
            DeviceName + "/" + "thing/service/property/set"
        property_publish_topic = "/sys" + "/" + ProductKey + "/" + \
            DeviceName + "/" + "thing/event/property/post"

        # 创建一个mqtt实例
        mqtt_client = MQTTClient(client_id="he2myN7xfqd.QH-D200-485-001|securemode=2,signmethod=hmacsha256,timestamp=1718692037263|",
                                 server="iot-06z00dcnrlb8g5r.mqtt.iothub.aliyuncs.com",
                                 port=1883, user="QH-D200-485-001&he2myN7xfqd",
                                 password="4c079c7ae6cb2801dfe6fb1e69433d4887f7584a659bf5d0bb37740f29625cef",
                                 keepalive=60, reconn=True)
        # 设置消息回调
        mqtt_client.set_callback(mqtt_sub_cb)
        mqtt_client.error_register_cb(mqtt_err_cb)
        # 建立连接
        try:
            mqtt_client.connect(clean_session=False)
        except Exception as e:
            app_log.error('e=%s' % e)

        # 订阅主题
        app_log.info(
            "Connected to aliyun, subscribed to: {}".format(property_subscribe_topic))
        mqtt_client.subscribe(property_subscribe_topic.encode('utf-8'), qos=0)

        msg_id += 1
        mqtt_client.publish(property_publish_topic.encode(
            'utf-8'), msg_netStatus.format(msg_id, stagecode, subcode).encode('utf-8'))

        _thread.start_new_thread(cell_location_task, ())
        _thread.start_new_thread(sim_task, ())

        while True:
            mqtt_client.wait_msg()
            modbus_rtu.control_relay(1, True)
            utime.sleep(1)
            modbus_rtu.control_relay(2, True)
            utime.sleep(1)
            modbus_rtu.control_relay(3, True)
            utime.sleep(1)
            modbus_rtu.control_relay(4, True)
            utime.sleep(1)
            modbus_rtu.control_relay(5, True)
            utime.sleep(1)
            modbus_rtu.control_relay(6, True)
            utime.sleep(1)
            modbus_rtu.control_relay(7, True)
            utime.sleep(1)
            modbus_rtu.control_relay(8, True)
            modbus_rtu.query_relay_status()
            msg_id += 1
            mqtt_client.publish(property_publish_topic.encode(
                'utf-8'), msg_do_status.format(msg_id, modbus_rtu.relay1_status, modbus_rtu.relay2_status,
                                               modbus_rtu.relay3_status, modbus_rtu.relay4_status,
                                               modbus_rtu.relay5_status, modbus_rtu.relay6_status,
                                               modbus_rtu.relay7_status, modbus_rtu.relay8_status).encode('utf-8'))
            utime.sleep(60)
            modbus_rtu.control_relay(1, False)
            utime.sleep(1)
            modbus_rtu.control_relay(2, False)
            utime.sleep(1)
            modbus_rtu.control_relay(3, False)
            utime.sleep(1)
            modbus_rtu.control_relay(4, False)
            utime.sleep(1)
            modbus_rtu.control_relay(5, False)
            utime.sleep(1)
            modbus_rtu.control_relay(6, False)
            utime.sleep(1)
            modbus_rtu.control_relay(7, False)
            utime.sleep(1)
            modbus_rtu.control_relay(8, False)
            modbus_rtu.query_relay_status()
            msg_id += 1
            mqtt_client.publish(property_publish_topic.encode(
                'utf-8'), msg_do_status.format(msg_id, modbus_rtu.relay1_status, modbus_rtu.relay2_status,
                                               modbus_rtu.relay3_status, modbus_rtu.relay4_status,
                                               modbus_rtu.relay5_status, modbus_rtu.relay6_status,
                                               modbus_rtu.relay7_status, modbus_rtu.relay8_status).encode('utf-8'))
            utime.sleep(60)
            # for i in range(10):
            #     write_msg = "Hello count={}".format(i)
            #     uart_inst.uartWrite(write_msg)
            #     utime.sleep(10)
            #     # 发布消息
            #     msg_id += 1
            #     app_log.info("Publish Send: Topic={},Msg={}".format(
            #         property_publish_topic, msg_temperature_humidity.format(msg_id, 12, 23)))
            #     mqtt_client.publish(property_publish_topic.encode(
            #         'utf-8'), msg_temperature_humidity.format(msg_id, 12, 23).encode('utf-8'))
    else:
        app_log.error('Network connection failed! stagecode = {}, subcode = {}'.format(
            stagecode, subcode))
