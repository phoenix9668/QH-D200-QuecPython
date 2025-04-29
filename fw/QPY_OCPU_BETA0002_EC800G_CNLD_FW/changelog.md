## Release History
**[QPY_OCPU_BETA0002_EC800G_CNLD_FW] 2024-10-16**
* ZH
1. 基于control_485新增可选参数打开/关闭485通信方向快速切换
2. 增加quecpython交互口枚举USB-REPL-PORT(MI_20)
3. 修复特定场景下，用户手动拨号，接口返回-1，但是实际拨号成功的问题
4. 修复校准模式下APP启动调用nw的协议栈导致设备死机问题
5. 修复485切换通信方向太慢，导致数据丢失问题
6. 修复uart波特率在4800、9600时485控制脚异常问题
7. 增加NAT模式设置和获取接口

* EN
1. Added optional parameters based on control_485 to turn on/off the fast switching of 485 communication direction
2. Added quecpython interactive port enumeration USB-REPL-PORT (MI_20)
3. Fixed the problem that in certain scenarios, the user dialed manually, the interface returned -1, but the actual dialing was successful
4. Fixed the problem that the device crashed when the APP started calling the nw protocol stack in calibration mode
5. Fixed the problem that the 485 switching communication direction was too slow, resulting in data loss
6. Fixed the abnormal problem of 485 control pin when the uart baud rate was 4800 and 9600
7. Added NAT mode setting and acquisition interface



**[QPY_OCPU_BETA0001_EC800G_CNLD_FW] 2022-10-09**
*Function list
1. uos
2. gc
3. usocket
4. uio
5. ujson
6. utime
7. sys/usys
8. _thread
9. example
10. dataCall
11. sim
12. net
13. checkNet
14. fota
15. misc
16. misc
17. misc
18. modem
19. Pin
20. UART
21. ExtInt
22. RTC
23. I2C
24. SPI
25. WDT
26. osTimer
27. Queue
