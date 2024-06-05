from usr.bin.components.abstract_service import AbstractService
from usr.utils.service_utils import Singleton
from usr.utils.resolver import TimeResolver
from usr.bin.components.monitor import ServiceMonitor
from machine import UART
import uos, ujson

LOGGER = "LOG"


class LOG_LV:
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class AbstractLogOutputUtil(object):
    def open(self):
        pass

    def output(self, message, **kwargs):
        pass

    def close(self):
        pass

    def __call__(self, message, **kwargs):
        self.output(message, **kwargs)


@Singleton
class UartLogOutputUtil(AbstractLogOutputUtil):
    def __init__(self, UARTn=UART.UART2):
        self.uart = UART(UARTn, 115200, 8, 0, 1, 0)

    def output(self, message, **kwargs):
        self.uart.write(message)


@Singleton
class PrintLogOutputUtil(AbstractLogOutputUtil):
    def output(self, message, **kwargs):
        print(message.log_format)


@Singleton
class MqttLogOutputUtil(AbstractLogOutputUtil):

    def __init__(self):
        super().__init__()

    def output(self, message, **kwargs):
        pass


class AliCloudLogOutPut(AbstractLogOutputUtil):
    def __init__(self, server):
        self.server = server
        self.topic = "/sys/{}/{}/thing/log/post".format(self.server.productKey, self.server.DeviceName)
        self.id = 0
        super().__init__()

    def get_id(self):
        if self.id > 999999:
            self.id = 0
        self.id += 1

    def output(self, message, **kwargs):
        content = {
            "utcTime": "T".join(message.time.split(" ")[:-1]) + "+0800",
            "logLevel": message.level,
            "module": message.tag,
            "code": message.level,
            "logContent": message.content
        }
        if message.level == "ERROR":
            content["traceContext"] = message.content
        reply = {
            "id": str(self.get_id()),
            "version": "1.0",
            "sys": {
                "ack": 0
            },
            "params": [content],
            "method": "thing.log.post"
        }
        self.server.publish(self.topic, ujson.dumps(reply))


@Singleton
class ConsoleLogOutputUtil(AbstractLogOutputUtil):
    def __init__(self):
        super().__init__()

    def output(self, message, **kwargs):
        pass


@Singleton
class FileLogOutputUtil(AbstractLogOutputUtil):
    def __init__(self):
        super().__init__()
        self.file_name = "log.txt"
        self.abs_path = "/usr/log/"
        self.content = []
        self.f = None

    def open(self):
        if "log" not in uos.listdir("/usr"):
            uos.mkdir(self.abs_path)
        self.f = open(self.abs_path + self.file_name, "w+")

    def output(self, message, **kwargs):
        self.open()
        if len(self.content) > 10:
            self.close()

    def close(self):
        self.f.close()
        self.f = None


class AbstractFormatUtil(object):
    def __init__(self):
        self.time = ""
        self.tag = ""
        self.level = ""
        self.content = ""
        self.log_format = ""

    def format(self, *args, **kwargs):
        pass


class LogFormatUtil(AbstractFormatUtil):

    @classmethod
    def format(cls, *args, **kwargs):
        self = LogFormatUtil()
        self.time = args[0]
        self.tag = args[1]
        self.level = args[2]
        self.content = args[3]
        self.log_format = "{} {} [{}] - {}\n".format(self.time, self.tag, self.level, self.content)
        return self


class LogServiceMonitor(ServiceMonitor):

    @staticmethod
    def create_monitor(config=None):
        log_service = LogService()
        if config is not None:
            level = config.get('level')
            log_service.set_level(level)
        lsm = LogServiceMonitor(log_service)
        if config is not None:
            lsm.set_exception_handlers(config.get('exceptionHandlers', None))
        return lsm


@Singleton
class LogService(AbstractService):
    """
        default log is async queue
        you can set
    """

    def __init__(self):
        super().__init__(LOGGER)
        self.__reporter = [PrintLogOutputUtil(), ]
        self.__tr = TimeResolver()
        self.format_util = LogFormatUtil()
        self.__level_map = {
            LOG_LV.DEBUG: 0,
            LOG_LV.INFO: 1,
            LOG_LV.WARNING: 2,
            LOG_LV.ERROR: 3,
            LOG_LV.CRITICAL: 4
        }
        self.low_level = 0

    def __set_report(self, report):
        if isinstance(report, AbstractLogOutputUtil):
            self.__reporter.append(report)

    def set_output(self, out_obj):
        if isinstance(out_obj, AbstractLogOutputUtil):
            self.__set_report(out_obj)
        else:
            self.log_send(self.name, LOG_LV.ERROR, '"{}" is not extend AbstractLogOutputUtil'.format(out_obj))
            raise Exception('"{}" is not extend AbstractLogOutputUtil'.format(out_obj))

    def set_level(self, level):
        if level in self.__level_map:
            self.low_level = self.__level_map[level]
        else:
            self.low_level = 0

    def log_send(self, sign, level, msg, mode=1):
        """send log deal"""
        if self.mode is not None:
            mode = self.mode
        if self.__level_map[level] >= self.low_level:
            if mode:
                self.send_msg_async(message=self.format_msg(sign, level, msg))
            else:
                self.send_msg_sync(message=self.format_msg(sign, level, msg))

    def format_msg(self, sign, level, msg):
        """
            format msg
            year-month-day hour-minute-second  weekday service [level] - message
        """
        return self.format_util.format(self.__tr.resolver(), sign, level, msg)

    def output_msg(self, *args, **kwargs):
        msg = "message"
        em = kwargs.get(msg, False)
        if em:
            for repoter in self.__reporter:
                repoter.output(em[msg])

    def prepare_before_stop(self):
        for repoter in self.__reporter:
            repoter.close()

    def prepare_before_start(self):
        self.signal.connect(self.output_msg, sender="anonymous")
        for repoter in self.__reporter:
            repoter.open()


class LogAdapter(object):
    """
        log adapter mode
        mode used : adapter proxy single LogService

    """

    def __init__(self, name, enable=1):
        self.log_service = LogService()
        self.name = name
        self.enable = enable
        self.mode = 1
        self.tag = None

    def get_tag(self):
        if self.tag is None:
            return self.name
        else:
            return self.tag

    def critical(self, msg):
        if self.enable:
            self.log_service.log_send(self.name, LOG_LV.CRITICAL, msg, self.mode)

    def debug(self, msg):
        if self.enable:
            self.log_service.log_send(self.name, LOG_LV.DEBUG, msg, self.mode)

    def info(self, msg):
        if self.enable:
            self.log_service.log_send(self.name, LOG_LV.INFO, msg, self.mode)

    def warning(self, msg):
        if self.enable:
            self.log_service.log_send(self.name, LOG_LV.WARNING, msg, self.mode)

    def error(self, msg):
        if self.enable:
            self.log_service.log_send(self.name, LOG_LV.ERROR, msg, self.mode)


if __name__ == '__main__':
    net_ser = LogAdapter("Net")
    ls = LogService()
    ls.start()
    net_ser.debug("111")
