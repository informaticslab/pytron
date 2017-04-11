import os
import string


BASE = "/sys/class/backlight/rpi_backlight/"

ON = 0
OFF = 1

def power(state):
    if state in (ON,OFF):
        _power = open(os.path.join(BASE,"bl_power"), "w")
        _power.write(str(state))
        _power.close()
        return
    raise TypeError("Invalid power state")


def brightness(value):
    if value > 0 and value < 256:
        _brightness = open(os.path.join(BASE,"brightness"), "w")
        _brightness.write(str(value))
        _brightness.close()
        return
    raise TypeError("Brightness should be between 0 and 255")

if __name__ == '__main__':
    power(ON)
    brightness(255)


