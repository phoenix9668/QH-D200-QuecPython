from machine import UART
from machine import Pin
from umqtt import MQTTClient
from misc import Power
import dataCall
import cellLocator
import _thread
import utime
import log
import net
import checkNet
import sim
import ustruct
import ujson

Work_Led = Pin(Pin.GPIO12, Pin.OUT, Pin.PULL_DISABLE, 1)

PROJECT_NAME = "QuecPython_EC600U"
PROJECT_VERSION = "1.0.0"
# 用户需要配置的APN信息，根据实际情况修改
usrConfig = {'apn': 'smgftyz.grevpdn.zj', 'username': '', 'password': ''}

checknet = checkNet.CheckNetwork(PROJECT_NAME, PROJECT_VERSION)
TaskEnable = True  # 调用disconnect后会通过该状态回收线程资源
do_device_address = 0xFE
humiture_device_address = 0x01
msg_id = 0
state = 0
mqtt_sub_msg = {}

log.basicConfig(level=log.DEBUG)
app_log = log.getLogger("app_log")


def watch_dog_task():
    while True:
        if Work_Led.read():
            Work_Led.write(0)
        else:
            Work_Led.write(1)
        utime.sleep(10)


class MqttClient():
    # 说明：reconn该参数用于控制使用或关闭umqtt内部的重连机制，默认为True，使用内部重连机制。
    # 如需测试或使用外部重连机制可参考此示例代码，测试前需将reconn=False,否则默认会使用内部重连机制！
    def __init__(self, clientid, server, port, user=None, password=None, keepalive=0, ssl=False, ssl_params={},
                 reconn=True):
        self.__clientid = clientid
        self.__pw = password
        self.__server = server
        self.__port = port
        self.__uasename = user
        self.__keepalive = keepalive
        self.__ssl = ssl
        self.__ssl_params = ssl_params
        self.topic = None
        self.qos = None
        # 网络状态标志
        self.__nw_flag = True
        # 创建互斥锁
        self.mp_lock = _thread.allocate_lock()
        # 创建类的时候初始化出mqtt对象
        self.client = MQTTClient(self.__clientid, self.__server, self.__port, self.__uasename, self.__pw,
                                 keepalive=self.__keepalive, ssl=self.__ssl, ssl_params=self.__ssl_params,
                                 reconn=reconn)

    def connect(self):
        self.client.connect(clean_session=False)
        # 注册网络回调函数，网络状态发生变化时触发
        flag = dataCall.setCallback(self.nw_cb)
        if flag != 0:
            # 回调注册失败
            raise Exception("Network callback registration failed")

    def set_callback(self, sub_cb):
        self.client.set_callback(sub_cb)

    def error_register_cb(self, func):
        self.client.error_register_cb(func)

    def subscribe(self, topic, qos=0):
        self.topic = topic  # 保存topic ，多个topic可使用list保存
        self.qos = qos  # 保存qos
        self.client.subscribe(topic, qos)

    def publish(self, topic, msg, qos=0):
        self.client.publish(topic, msg, qos)

    def disconnect(self):
        global TaskEnable
        # 关闭wait_msg的监听线程
        TaskEnable = False
        # 关闭之前的连接，释放资源
        self.client.disconnect()

    def reconnect(self):
        # 判断锁是否已经被获取
        if self.mp_lock.locked():
            return
        self.mp_lock.acquire()
        # 重新连接前关闭之前的连接，释放资源(注意区别disconnect方法，close只释放socket资源，disconnect包含mqtt线程等资源)
        self.client.close()
        # 重新建立mqtt连接
        while True:
            net_sta = net.getState()  # 获取网络注册信息
            if net_sta != -1 and net_sta[1][0] == 1:
                call_state = dataCall.getInfo(1, 0)  # 获取拨号信息
                if (call_state != -1) and (call_state[2][0] == 1):
                    try:
                        # 网络正常，重新连接mqtt
                        self.connect()
                    except Exception as e:
                        # 重连mqtt失败, 5s继续尝试下一次
                        self.client.close()
                        utime.sleep(5)
                        continue
                else:
                    # 网络未恢复，等待恢复
                    utime.sleep(10)
                    continue
                # 重新连接mqtt成功，订阅Topic
                try:
                    # 多个topic采用list保存，遍历list重新订阅
                    if self.topic is not None:
                        self.client.subscribe(self.topic, self.qos)
                    self.mp_lock.release()
                except:
                    # 订阅失败，重新执行重连逻辑
                    self.client.close()
                    utime.sleep(5)
                    continue
            else:
                utime.sleep(5)
                continue
            break  # 结束循环
        # 退出重连
        return True

    def nw_cb(self, args):
        nw_sta = args[1]
        if nw_sta == 1:
            # 网络连接
            app_log.info("*** network connected! ***")
            self.__nw_flag = True
        else:
            # 网络断线
            app_log.info("*** network not connected! ***")
            self.__nw_flag = False

    def __listen(self):
        while True:
            try:
                if not TaskEnable:
                    break
                self.client.wait_msg()
            except OSError as e:
                # 判断网络是否断线
                if not self.__nw_flag:
                    # 网络断线等待恢复进行重连
                    self.reconnect()
                # 在socket状态异常情况下进行重连
                elif self.client.get_mqttsta() != 0 and TaskEnable:
                    self.reconnect()
                else:
                    # 这里可选择使用raise主动抛出异常或者返回-1
                    return -1

    def loop_forever(self):
        _thread.start_new_thread(self.__listen, ())


class Uart2(object):
    def __init__(self, no=UART.UART2, bate=115200, data_bits=8, parity=0, stop_bits=1, flow_control=0):
        self.uart = UART(no, bate, data_bits, parity, stop_bits, flow_control)
        self.uart.control_485(UART.GPIO28, 0)
        self.uart.set_callback(self.callback)
        self.modbus_rtu = None

    def set_modbus_rtu_instance(self, modbus_rtu_instance):
        self.modbus_rtu = modbus_rtu_instance

    def callback(self, para):
        app_log.debug("call para:{}".format(para))
        if (0 == para[0]):
            self.uartRead(para[2])

    def uartWrite(self, msg):
        hex_msg = [hex(x) for x in msg]
        app_log.debug("Write msg:{}".format(hex_msg))
        self.uart.write(msg)

    def uartRead(self, len):
        msg = self.uart.read(len)
        hex_msg = [hex(x) for x in msg]
        app_log.debug("Read msg: {}".format(hex_msg))
        if self.modbus_rtu:
            self.modbus_rtu.handle_response(msg)


class ModbusRTU:
    def __init__(self, do_device_address, humiture_device_address):
        self.do_device_address = do_device_address
        self.humiture_device_address = humiture_device_address
        self.relay1_status = 0
        self.relay2_status = 0
        self.relay3_status = 0
        self.relay4_status = 0
        self.relay5_status = 0
        self.relay6_status = 0
        self.relay7_status = 0
        self.relay8_status = 0
        self.temperature = 0
        self.humidity = 0

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

    def build_message(self, device_address, function_code, coil_address, value):
        # 构建 Modbus 请求消息
        message = ustruct.pack(
            '>BBHH', device_address, function_code, coil_address, value)
        # 计算 CRC 校验码
        crc = self.calculate_crc(message)
        crc_bytes = ustruct.pack('<H', crc)
        app_log.debug("build_message:{}".format(
            ['0x{:02X}'.format(b) for b in (message + crc_bytes)]))
        return message + crc_bytes

    def build_do_all_message(self, function_code, coil_address, coil_number, command_bytes, value):
        # 构建 Modbus 请求消息
        message = ustruct.pack(
            '>BBHHBB', self.do_device_address, function_code, coil_address, coil_number, command_bytes, value)
        # 计算 CRC 校验码
        crc = self.calculate_crc(message)
        crc_bytes = ustruct.pack('<H', crc)
        return message + crc_bytes

    def send_message(self, message, timeout=50):
        uart_inst.uartWrite(message)
        utime.sleep_ms(timeout)  # 等待响应的时间，可以根据需要调整

    def handle_response(self, data):
        global msg_id
        if len(data) < 6:
            app_log.error("Invalid response length")
            return
        elif len(data) == 8:
            address, function_code, coil_address, value, crc_received = ustruct.unpack(
                '>BBHHH', data)
        elif len(data) == 6:
            address, function_code, bytes_num, value, crc_received = ustruct.unpack(
                '>BBBBH', data)
        elif len(data) == 9:
            address, function_code, bytes_num, humidity, temperature, crc_received = ustruct.unpack(
                '>BBBHHH', data)
        else:
            app_log.error("The data is linked together")
            return
        crc_calculated = self.calculate_crc(data[:-2])
        crc_calculated_swapped = self.reverse_crc(crc_calculated)
        if crc_received != crc_calculated_swapped:
            app_log.error("CRC mismatch: received=0x{:04X}, calculated=0x{:04X}".format(
                crc_received, crc_calculated))
        elif function_code == 0x05:
            app_log.info("Relay control successful: coil_address=0x{:04X}, value=0x{:04X}".format(
                coil_address, value))
        elif function_code == 0x0f:
            app_log.info("Relay all control successful: coil_address=0x{:04X}, value=0x{:04X}".format(
                coil_address, value))
        elif function_code == 0x82:
            app_log.error("Relay all control failure: coil_address=0x{:04X}, value=0x{:04X}".format(
                coil_address, value))
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
            app_log.debug("Relay 1 Status: {}".format(self.relay1_status))
            app_log.debug("Relay 2 Status: {}".format(self.relay2_status))
            app_log.debug("Relay 3 Status: {}".format(self.relay3_status))
            app_log.debug("Relay 4 Status: {}".format(self.relay4_status))
            app_log.debug("Relay 5 Status: {}".format(self.relay5_status))
            app_log.debug("Relay 6 Status: {}".format(self.relay6_status))
            app_log.debug("Relay 7 Status: {}".format(self.relay7_status))
            app_log.debug("Relay 8 Status: {}".format(self.relay8_status))
            msg_id += 1
            mqtt_client.publish(property_publish_topic.encode(
                'utf-8'), msg_all_status.format(msg_id, modbus_rtu.relay1_status, modbus_rtu.relay2_status,
                                                modbus_rtu.relay3_status, modbus_rtu.relay4_status,
                                                modbus_rtu.relay5_status, modbus_rtu.relay6_status,
                                                modbus_rtu.relay7_status, modbus_rtu.relay8_status).encode('utf-8'))
        elif function_code == 0x81:
            app_log.error("Relay query status failure: bytes_num=0x{:02X}, value=0x{:02X}".format(
                bytes_num, value))
        elif function_code == 0x03:
            app_log.info("Humiture query successful: bytes_num=0x{:02X}, humidity=0x{:04X}, temperature=0x{:04X}".format(
                bytes_num, humidity, temperature))
            if humidity == 0x0000 or temperature == 0x0000:
                app_log.error("Humiture query failure: bytes_num=0x{:02X}, humidity=0x{:04X}, temperature=0x{:04X}".format(
                    bytes_num, humidity, temperature))
            else:
                self.humidity = humidity / 10
                self.temperature = temperature / 10
                app_log.debug("humidity: {}".format(self.humidity))
                app_log.debug("temperature: {}".format(self.temperature))
                msg_id += 1
                mqtt_client.publish(property_publish_topic.encode(
                    'utf-8'), msg_temperature_humidity.format(msg_id, modbus_rtu.temperature, modbus_rtu.humidity).encode('utf-8'))

    def control_single_relay(self, relay_number, state):
        coil_address = relay_number - 1
        value = 0xFF00 if state else 0x0000
        message = self.build_message(
            self.do_device_address, 0x05, coil_address, value)
        self.send_message(message)

    def control_all_relay(self, state):
        value = 0xFF if state else 0x00
        message = self.build_do_all_message(0x0f, 0x0000, 0x0008, 0x01, value)
        self.send_message(message)

    def query_relay_status(self):
        message = self.build_message(
            self.do_device_address, 0x01, 0x0000, 0x0008)
        self.send_message(message)

    def query_humiture_status(self):
        message = self.build_message(
            self.humiture_device_address, 0x03, 0x0000, 0x0002)
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


def power_restart():
    while True:
        utime.sleep(14400)
        Power.powerRestart()


def humiture_task():
    while True:
        utime.sleep(600)
        modbus_rtu.query_humiture_status()


def mqtt_sub_cb(topic, msg):
    global state, mqtt_sub_msg
    app_log.info("Subscribe Recv: Topic={},Msg={}".format(
        topic.decode(), msg.decode()))
    mqtt_sub_msg = ujson.loads(msg.decode())
    state = 1
    app_log.debug(mqtt_sub_msg['params'])


def process_relay_logic():
    global state, msg_id, mqtt_sub_msg

    if 'code' in mqtt_sub_msg:
        if mqtt_sub_msg['code'] == 200:
            app_log.debug('post_reply, code is 200')
            state = 0
            mqtt_sub_msg = {}
            return

    if 'method' not in mqtt_sub_msg:
        app_log.error('method is missing')
    elif not mqtt_sub_msg['method']:
        app_log.error('method is empty')
    elif 'thing.service.query_humiture' in mqtt_sub_msg['method']:
        modbus_rtu.query_humiture_status()
        state = 0
        mqtt_sub_msg = {}
        return

    if 'params' not in mqtt_sub_msg:
        app_log.error('params is missing')
    elif not mqtt_sub_msg['params']:
        app_log.error('params is empty')
    elif 'ALLNO' in mqtt_sub_msg['params']:
        if mqtt_sub_msg['params']['ALLNO'] == 1:
            modbus_rtu.control_all_relay(True)
        else:
            modbus_rtu.control_all_relay(False)
    else:
        for key, value in mqtt_sub_msg['params'].items():
            if value == 1:
                if key == 'NO1':
                    modbus_rtu.control_single_relay(1, True)
                elif key == 'NO2':
                    modbus_rtu.control_single_relay(2, True)
                elif key == 'NO3':
                    modbus_rtu.control_single_relay(3, True)
                elif key == 'NO4':
                    modbus_rtu.control_single_relay(4, True)
                elif key == 'NO5':
                    modbus_rtu.control_single_relay(5, True)
                elif key == 'NO6':
                    modbus_rtu.control_single_relay(6, True)
                elif key == 'NO7':
                    modbus_rtu.control_single_relay(7, True)
                elif key == 'NO8':
                    modbus_rtu.control_single_relay(8, True)
            else:
                if key == 'NO1':
                    modbus_rtu.control_single_relay(1, False)
                elif key == 'NO2':
                    modbus_rtu.control_single_relay(2, False)
                elif key == 'NO3':
                    modbus_rtu.control_single_relay(3, False)
                elif key == 'NO4':
                    modbus_rtu.control_single_relay(4, False)
                elif key == 'NO5':
                    modbus_rtu.control_single_relay(5, False)
                elif key == 'NO6':
                    modbus_rtu.control_single_relay(6, False)
                elif key == 'NO7':
                    modbus_rtu.control_single_relay(7, False)
                elif key == 'NO8':
                    modbus_rtu.control_single_relay(8, False)

    modbus_rtu.query_relay_status()
    state = 0
    mqtt_sub_msg = {}


if __name__ == '__main__':
    utime.sleep(5)
    pdpCtx = dataCall.getPDPContext(1)
    app_log.info("pdpCtx:{}".format(pdpCtx))
    if pdpCtx != -1:
        if pdpCtx[1] != usrConfig['apn']:
            ret = dataCall.setPDPContext(
                1, 0, usrConfig['apn'], usrConfig['username'], usrConfig['password'], 0)
            if ret == 0:
                app_log.info('APN config success.')
                Power.powerRestart()
            else:
                app_log.info('APN config failed.')
        else:
            app_log.info('APN configured.')
    else:
        app_log.info('get PDP Context failed.')

    checknet.poweron_print_once()
    stagecode, subcode = checknet.wait_network_connected(30)
    if stagecode == 3 and subcode == 1:
        app_log.info('Network connection successful!')

        uart_inst = Uart2()
        modbus_rtu = ModbusRTU(do_device_address=do_device_address,
                               humiture_device_address=humiture_device_address)
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

        msg_all_status = """{{
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

        ProductKey = "k1lpuw8kM8O"  # 产品标识
        # DeviceName = "QH-D200-485-001"  # 设备名称
        # DeviceName = "QH-D200-485-002"  # 设备名称
        # DeviceName = "QH-D200-485-003"  # 设备名称
        # DeviceName = "QH-D200-485-004"  # 设备名称
        # DeviceName = "QH-D200-485-005"  # 设备名称
        DeviceName = "QH-D200-485-006"  # 设备名称

        property_subscribe_topic = "/sys" + "/" + ProductKey + "/" + \
            DeviceName + "/" + "thing/service/property/set"
        property_publish_topic = "/sys" + "/" + ProductKey + "/" + \
            DeviceName + "/" + "thing/event/property/post"

        # 创建一个mqtt实例
        # mqtt_client = MqttClient(clientid="k1lpuw8kM8O.QH-D200-485-001|securemode=2,signmethod=hmacsha256,timestamp=1721809948760|",
        #                          server="iot-06z00i0fhc1e85a.mqtt.iothub.aliyuncs.com",
        #                          port=1883,
        #                          user="QH-D200-485-001&k1lpuw8kM8O",
        #                          password="edf945e46e6fde71febae6843d41b808bdb32d6672983f2142696e40d9148ff5",
        #                          keepalive=60, reconn=False)

        # mqtt_client = MqttClient(clientid="k1lpuw8kM8O.QH-D200-485-002|securemode=2,signmethod=hmacsha256,timestamp=1721980140395|",
        #                          server="iot-06z00i0fhc1e85a.mqtt.iothub.aliyuncs.com",
        #                          port=1883,
        #                          user="QH-D200-485-002&k1lpuw8kM8O",
        #                          password="0f70269947a9b2adbda87ac981fff9bb9ea5f212ae6ff667316199d3774fe369",
        #                          keepalive=60, reconn=False)

        # mqtt_client = MqttClient(clientid="k1lpuw8kM8O.QH-D200-485-003|securemode=2,signmethod=hmacsha256,timestamp=1722934767615|",
        #                          server="iot-06z00i0fhc1e85a.mqtt.iothub.aliyuncs.com",
        #                          port=1883,
        #                          user="QH-D200-485-003&k1lpuw8kM8O",
        #                          password="9516ef6dcb7660e678be2d4d258206efff03f28cb6360fe559f9a0e85fe7802b",
        #                          keepalive=60, reconn=False)

        # mqtt_client = MqttClient(clientid="k1lpuw8kM8O.QH-D200-485-004|securemode=2,signmethod=hmacsha256,timestamp=1722995169908|",
        #                          server="iot-06z00i0fhc1e85a.mqtt.iothub.aliyuncs.com",
        #                          port=1883,
        #                          user="QH-D200-485-004&k1lpuw8kM8O",
        #                          password="9e5225e1c1519140a46c6a47ffa2e7c3096ab158e3660a9728ca3ee0f5969bee",
        #                          keepalive=60, reconn=False)

        # mqtt_client = MqttClient(clientid="k1lpuw8kM8O.QH-D200-485-005|securemode=2,signmethod=hmacsha256,timestamp=1722995243424|",
        #                          server="iot-06z00i0fhc1e85a.mqtt.iothub.aliyuncs.com",
        #                          port=1883,
        #                          user="QH-D200-485-005&k1lpuw8kM8O",
        #                          password="ba0ab4e907be169cfb63e86eb854957b4883df65dcaca702ef6d2fde962790dc",
        #                          keepalive=60, reconn=False)

        mqtt_client = MqttClient(clientid="k1lpuw8kM8O.QH-D200-485-006|securemode=2,signmethod=hmacsha256,timestamp=1722997119995|",
                                 server="iot-06z00i0fhc1e85a.mqtt.iothub.aliyuncs.com",
                                 port=1883,
                                 user="QH-D200-485-006&k1lpuw8kM8O",
                                 password="2fb1b34060a5d8271bb62e7f24899d79f33b4974545ba13b404e4393081aea5c",
                                 keepalive=60, reconn=False)

        def mqtt_err_cb(err):
            app_log.error("thread err:%s" % err)
            mqtt_client.reconnect()  # 可根据异常进行重连

        # 设置消息回调
        mqtt_client.set_callback(mqtt_sub_cb)
        mqtt_client.error_register_cb(mqtt_err_cb)
        # 建立连接
        try:
            mqtt_client.connect()
        except Exception as e:
            app_log.error('e=%s' % e)

        # 订阅主题
        app_log.info(
            "Connected to aliyun, subscribed to: {}".format(property_subscribe_topic))
        mqtt_client.subscribe(property_subscribe_topic.encode('utf-8'), qos=0)

        msg_id += 1
        mqtt_client.publish(property_publish_topic.encode(
            'utf-8'), msg_netStatus.format(msg_id, stagecode, subcode).encode('utf-8'))

        mqtt_client.loop_forever()

        _thread.start_new_thread(cell_location_task, ())
        _thread.start_new_thread(sim_task, ())
        _thread.start_new_thread(humiture_task, ())

        while True:
            if state == 1:
                process_relay_logic()
            utime.sleep_ms(50)
    else:
        app_log.error('Network connection failed! stagecode = {}, subcode = {}'.format(
            stagecode, subcode))
