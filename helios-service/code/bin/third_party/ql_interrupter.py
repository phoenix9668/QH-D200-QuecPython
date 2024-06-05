import osTimer, sys_bus, utime
from machine import Pin, ExtInt
import _thread

"""
ExInt阻断器
    enable
    disable
"""


class ExIntInterrupter(object):
    def __init__(self, gpio, trige_mode=ExtInt.IRQ_RISING, pull_mode=ExtInt.PULL_DISABLE, callback=None):
        self.__ext = ExtInt(gpio, trige_mode, pull_mode, callback)

    def enable(self):
        return self.__ext.enable()

    def disable(self):
        return self.__ext.disable()

    def start(self):
        return self.enable()

    def stop(self):
        return self.disable()


"""
Pin阻断器
    write
    read
"""


class PinInterrupter(object):

    def __init__(self, gpio, trige_mode=Pin.OUT, pull_mode=Pin.PULL_DISABLE, mode=0):
        self.gpio = Pin(gpio, trige_mode, pull_mode, mode)

    def write(self, value):
        self.gpio.write(value)

    def read(self):
        return self.gpio.read()

    def blinker(self, keep_time):
        self.write(1)
        utime.sleep(keep_time)
        self.write(0)

    def __blinker(self, count, keep_time):
        while count > 0:
            self.blinker(keep_time)

    def freq_blinker(self, freq, keep_time):
        return _thread.start_new_thread(self.__blinker, (freq, keep_time))


"""
具有BUS功能的ExInt阻断器
    publish
"""


class BusInterrupter(object):

    def register_callback(self, callback):
        if callback is not None:
            sys_bus.subscribe(self.topic, callback)

    def default_callback(self, *args, **kwargs):
        self.publish(*args, **kwargs)

    def publish(self, *args, **kwargs):
        sys_bus.publish(self.topic, kwargs)


class BusExIntInterrupter(ExIntInterrupter, BusInterrupter):
    def __init__(self, topic, gpio, trige_mode=ExtInt.IRQ_RISING, pull_mode=ExtInt.PULL_DISABLE):
        self.topic = topic
        super().__init__(gpio, trige_mode, pull_mode, self.default_callback)

    def default_callback(self, *args, **kwargs):
        self.publish(**dict(gpio=args[0][0], pressure=args[0][1]))


"""
定时器阻断器
    start
    stop
"""


class TimerInterrupter(object):
    def __init__(self, keep_time, callback, period=1):
        """

        @param period: 周期
        @param callback: 回调
        @param loop: 1 循环 0 是一次
        """
        self.__timer = osTimer()
        self.__keep_time = keep_time
        self.__callback = callback
        self.__period = period

    def start(self):
        self.__timer.start(self.__keep_time, self.__period, self.__callback)

    def stop(self):
        self.__timer.stop()


"""
看门狗
    继承于BusExInt 具有bus和ExInt的能力
    组合了
        定时器阻断器
        Pin阻断器
"""


class WatchDog(object):
    TOPIC = "WDT_KICK_TOPIC"

    def __init__(self, gpio, mode, keep_time, done_pin=None, trige_mode=ExtInt.IRQ_RISING,
                 pull_mode=ExtInt.PULL_DISABLE):
        self.timer_inter = TimerInterrupter(keep_time, self.__process)
        self.pin_inter = PinInterrupter(gpio, mode=mode)
        if done_pin is not None:
            self.bus_ext = BusExIntInterrupter(self.TOPIC, done_pin, trige_mode=trige_mode, pull_mode=pull_mode)
            self.bus_ext.enable()

    def start(self):
        self.timer_inter.start()

    def stop(self):
        self.timer_inter.stop()

    def __process(self, *args, **kwargs):
        self.pin_inter.blinker(1)
        kwargs.update(dict(msg=self.TOPIC + "_FEED"))
        sys_bus.publish(self.TOPIC + "_FEED", kwargs)


"""
ExInt处理器 
    继承于BusExInt 具有bus和ExInt的能力
"""


class ExIntProcess(BusExIntInterrupter):
    TOPIC = "GPIO{}_EXINT"

    def __init__(self, pin, trige_mode=Pin.OUT, pull_mode=Pin.PULL_DISABLE):
        super().__init__(self.TOPIC.format(pin), pin, trige_mode, pull_mode)


if __name__ == '__main__':
    def pin_interrupt_callback(topic, message):
        print("pin_interrupt_callback, topic: {}, message: {}".format(topic, message))


    def ext_interrupt_callback(topic, message):
        print("ext_interrupt_callback, topic: {}, message: {}".format(topic, message))


    def kick_feed_interrupt_callback(topic, message):
        print("kick_feed_interrupt_callback, topic: {}, message: {}".format(topic, message))


    # 订阅gpio的中断
    sys_bus.subscribe("GPIO18_EXINT", pin_interrupt_callback)

    # 订阅WDT_KICK_TOPIC订阅喂狗中断的回调
    sys_bus.subscribe("WDT_KICK_TOPIC", ext_interrupt_callback)

    # 订阅喂狗的回调, 每次喂狗都会触发次订阅的回调
    sys_bus.subscribe("WDT_KICK_TOPIC_FEED", kick_feed_interrupt_callback)
    # 初始化狗
    wd = WatchDog(Pin.GPIO15, 1, 20000, Pin.GPIO8)
    # 开启喂狗
    wd.start()

    # 初始化中断的处理器
    ep = ExIntProcess(Pin.GPIO5)
    # 开启中断
    ep.start()
