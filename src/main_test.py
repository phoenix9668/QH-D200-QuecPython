import time
from machine import Pin

# 初始化 Work 灯对应的引脚
LED_Work = Pin(Pin.GPIO12, Pin.OUT, Pin.PULL_DISABLE, 1)
msg_id = 0
time.sleep(10)
print('Start')
while True:
    # 读取引脚状态并取反
    if LED_Work.read():
        LED_Work.write(0)
    else:
        LED_Work.write(1)
    # 休眠 0.2 秒
    time.sleep(1)
    msg_id = msg_id + 1
    print('msg_id:{}'.format(msg_id))
