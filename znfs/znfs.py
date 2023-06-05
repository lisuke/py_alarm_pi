#!/usr/bin/env python

# Reference:

import os
import sys
import time
import logging

from PIL import ImageFont
from datetime import datetime
from luma.core.interface.serial import i2c
from luma.core.render import canvas
from luma.oled.device import ssd1306

try:
    import psutil
except ImportError:
    print("The psutil library was not found. Run 'sudo -H pip install psutil' to install it.")
    sys.exit()

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)-15s - %(message)s'
)
logging.getLogger("PIL").setLevel(logging.ERROR)


class Fan(object):

    def __init__(self) -> None:
        import smbus

        self._bus = smbus.SMBus(1)

        self._addr = 0x0d
        self._fan_reg = 0x08

    def start(self) -> None:
        self._bus.write_byte_data(self._addr, self._fan_reg, 0x01)
        self._bus.write_byte_data(self._addr, self._fan_reg, 0x01)

    def stop(self) -> None:
        self._bus.write_byte_data(self._addr, self._fan_reg, 0x00)
        self._bus.write_byte_data(self._addr, self._fan_reg, 0x00)

    # Singleton
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(Fan, cls).__new__(cls, *args, **kwargs)

        return cls._instance


def create_fan() -> Fan:
    return Fan()


def create_screen():
    serial = i2c(port=1, address=0x3C)
    screen = ssd1306(serial, width=128, height=32, rotate=2)

    return screen


def beautiful_bytes(n):
    """
    >>> beautiful_bytes(10000)
    '9K'
    >>> beautiful_bytes(100001221)
    '95M'
    """
    symbols = ('K', 'M', 'G', 'T', 'P', 'E', 'Z', 'Y')
    prefix = {}
    for i, s in enumerate(symbols):
        prefix[s] = 1 << (i + 1) * 10
    for s in reversed(symbols):
        if n >= prefix[s]:
            value = int(float(n) / prefix[s])
            return '%s%s' % (value, s)

    return f"{n}B"


def temp_usage(context):
    # temp
    temp_file = open("/sys/class/thermal/thermal_zone0/temp")
    tmp = temp_file.read()
    temp_file.close()
    temp = float(tmp) / 1000

    # fan
    fan = context['fan']
    fan_temp = context['fan_temp']

    if temp > fan_temp[1]:
        fan.start()
    elif temp < fan_temp[0]:
        fan.stop()

    return "temp:%.2f°C " % (temp)


def uptime_usage():
    # uptime
    uptime = datetime.now() - datetime.fromtimestamp(psutil.boot_time())

    return "up:%s " % (str(uptime).split('.')[0])


def cpu_usage():
    # cpu
    cpu_percent = psutil.cpu_percent()
    return "CPU: %.1f%% " % (cpu_percent)


def mem_usage():
    total = str(round(psutil.virtual_memory().total /
                (1024.0 * 1024.0 * 1024.0), 2))
    memory = float(psutil.virtual_memory().total -
                   psutil.virtual_memory().free) / float(psutil.virtual_memory().total)

    return u"MEM: %.1f%% " % (float(memory*100))


def network(iface, context):
    cur_stat = psutil.net_io_counters()

    if "old_stat" not in context["network"].keys():
        context["network"]["old_stat"] = cur_stat
        return ""

    old_stat = context["network"]["old_stat"]

    cur_s = (cur_stat.bytes_sent - old_stat.bytes_sent) / context["delay"]
    cur_r = (cur_stat.bytes_recv - old_stat.bytes_recv) / context["delay"]

    context["network"]["old_stat"] = cur_stat

    return "%s: Tx%s, Rx%s " % (iface, beautiful_bytes(cur_s), beautiful_bytes(cur_r))


def display(context={}):
    screen = context['screen']

    with canvas(screen) as draw:
        draw.rectangle(screen.bounding_box, outline="white", fill="black")

        index = context['index']
        if index % 2 == 0:
            draw.text((2, 2), cpu_usage() + temp_usage(context=context),
                      font=context['font'], fill="white")
        else:
            draw.text((2, 2), mem_usage() + uptime_usage(),
                      font=context['font'], fill="white")

        draw.text((2, 14), network('end0', context=context),
                  font=context['font'], fill="white")

    context['index'] += 1
    time.sleep(context["delay"])


def main():
    context = {
        "fan": create_fan(),
        "fan_temp": [45, 50],
        "screen": create_screen(),
        "font": ImageFont.truetype('NotoSansCJK-Regular.ttc', 10, encoding="unic"),
        "network": {},
        "delay": 1,
        "index": 1
    }

    while True:
        display(context=context)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
