__all__ = [
    "ServiceMonitor",
]

from misc import Power
import osTimer


class MonitorInterface(object):
    def start(self):
        """start"""

    def stop(self):
        """stop"""

    def status(self):
        """status"""


class ServiceMonitor(MonitorInterface):
    THRESHOLD = 3

    def __init__(self, service):
        self.service = service
        self.__failed_count = 0
        self.__level = 0
        self.__timer = None
        self.__ping_count = 0
        self.__exception_handlers = {}
        self.service.signal.connect(self.ping_handler, sender=0xFE)

    def set_level(self, level):
        if self.__level != level:
            self.__level = level

    def __timer_handle(self, *args):
        """定时器调度"""
        if self.__ping_count:
            self.__failed_count += 1
        self.__ping_count = self.__ping_count + 1
        self.service.signal.send(0xFE)
        if self.__failed_count:
            self.__failed_handle()

    def set_exception_handlers(self, handler):
        if handler is not None:
            self.__exception_handlers = handler

    def __failed_handle(self):
        """失败处理"""
        try:
            for k, v in self.__exception_handlers.items():
                if k == "reboot":
                    if v.get("failCount") == self.__failed_count:
                        # 关机
                        Power.powerDown()
                elif k == "stop":
                    if v.get("failCount") == self.__failed_count:
                        # 停止服务
                        self.stop()
                else:
                    continue
        except Exception as e:
            print(e)

    def ping_handler(self, *args, **kwargs):
        self.__ping_count = 0

    def start(self):
        if self.__level != self.THRESHOLD:
            self.service.start()
            if self.__timer is None:
                self.__timer = osTimer()
                self.__timer.start(15000, 1, self.__timer_handle)
            return self.status()

    def status(self):
        return self.service.status()

    def clear(self):
        self.__failed_count = 0
        self.__level = 0
        if self.__timer is not None:
            self.__timer.stop()
            self.__timer.delete()
            self.__timer = None
        self.__ping_count = 0

    def stop(self):
        if self.__level != self.THRESHOLD:
            self.service.stop()
            self.clear()
            return self.status

    def __call__(self, *args, **kwargs):
        return self.service
