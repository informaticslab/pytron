from kivy.app import App, Widget
from kivy.uix.gridlayout import GridLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.slider import Slider
from construct import *
from kivy.logger import Logger
import socket
import sys
from binascii import hexlify
import struct
from time import sleep

dst_ip = '192.168.0.10'       # ip of tv
dst_port = 1515

mdc_format = Struct(
    "fields" / RawCopy(Struct(
        "header" / Const(Int8ub, 0xAA),
        "cmd" / Int8ub,
        "id" / Const(Int8ub, 0x01),
        "msg_length" / Int8ub,
        "msg_data" / Int8ub,
    )),
    "checksum" / Checksum(Bytes(1), lambda data: sum(bytearray(data)[1:]) % 256, this.fields.data),
)


def send_mdc_msg(msg):

    return
    # create socket
    #print('# Creating socket')
    #print("Sending MDC Msg {}".format(hexlify(msg)))

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    except socket.error:
        print('Failed to create socket')
        sys.exit()

    sock.connect((dst_ip, dst_port))

    try:
        sock.sendall(msg)
    except socket.error:
        print('Send failed')
        sys.exit()


    # Receive data
    #print('# Receive data from server')
    reply = sock.recv(1024)
    #print(reply)

    sock.close()

class TvControlScreen(GridLayout):

    def __init__(self, **kwargs):
        super(TvControlScreen, self).__init__(**kwargs)
        self.cols = 4
        self.add_widget(Label(text='Power'))

        self.btnPowerOn = Button(text='On', font_size=28)
        self.btnPowerOn.bind(on_press=btn_power_on_touched)
        self.add_widget(self.btnPowerOn)

        self.btnPowerOff = Button(text='Off', font_size=28)
        self.add_widget(self.btnPowerOff)
        self.btnPowerOff.bind(on_press=btn_power_off_touched)

        self.add_widget(Label(text=''))

        self.add_widget(Label(text='HDMI Sources'))
        self.btnSourceHdmi1 = Button(text='HDMI 1', font_size=28)
        self.add_widget(self.btnSourceHdmi1)

        self.btnSourceHdmi2 = Button(text='HDMI 2', font_size=28)
        self.add_widget(self.btnSourceHdmi2)

        self.btnSourceHdmi3 = Button(text='HDMI 3', font_size=28)
        self.add_widget(self.btnSourceHdmi3)

        self.add_widget(Label(text='Display Port Sources'))

        self.btnSourceDp1 = Button(text='DP 1', font_size=28)
        self.add_widget(self.btnSourceDp1)

        self.btnSourceDp2 = Button(text='DP 2', font_size=28)
        self.add_widget(self.btnSourceDp2)

        self.btnSourceDp3 = Button(text='DP 3', font_size=28)
        self.add_widget(self.btnSourceDp3)


class PowerLayout(Widget):
    def __init__(self, **kwargs):
        super(PowerLayout, self).__init__(**kwargs)

    def btn_power_on_touched(instance):
        data = mdc_format.build(dict(fields=dict(value=dict(cmd=0x11, msg_length=0x01, msg_data=0x01))))
        print("Sending Power On packet = {}".format(hexlify(data)))
        send_mdc_msg(data)

    def btn_power_off_touched(instance):
        data = mdc_format.build(dict(fields=dict(value=dict(cmd=0x11, msg_length=0x01, msg_data=0x00))))
        print("Sending Power Off packet = {}".format(hexlify(data)))
        send_mdc_msg(data)


class VolumeSlider(Slider):
    def __init__(self, **kwargs):
        kwargs['min'] = 0
        kwargs['max'] = 100
        kwargs['value'] = 25
        super(VolumeSlider, self).__init__(**kwargs)


class VolumeLayout(Widget):
    def __init__(self, **kwargs):
        super(VolumeLayout, self).__init__(**kwargs)

    def set_volume(self, instance, value):
        vol = int(value)
        data = mdc_format.build(dict(fields=dict(value=dict(cmd=0x12, msg_length=0x01, msg_data=vol))))
        send_mdc_msg(data)
        sleep(0.2)
        #Logger.debug('Setting volume to {}'.format(value))


class HdmiLayout(Widget):
    def __init__(self, **kwargs):
        super(HdmiLayout, self).__init__(**kwargs)

    def btn_source_hdmi1_touched(instance):
        data = mdc_format.build(dict(fields=dict(value=dict(cmd=0x14, msg_length=0x01, msg_data=0x21))))
        print("Sending Source HDMI 1 packet = {}".format(hexlify(data)))
        send_mdc_msg(data)

    def btn_source_hdmi2_touched(instance):
        data = mdc_format.build(dict(fields=dict(value=dict(cmd=0x14, msg_length=0x01, msg_data=0x23))))
        print("Sending Source HDMI 2 packet = {}".format(hexlify(data)))
        send_mdc_msg(data)


class DisplayPortLayout(Widget):
    def __init__(self, **kwargs):
        super(DisplayPortLayout, self).__init__(**kwargs)


class HeaderLayout(Widget):
    def __init__(self, **kwargs):
        super(HeaderLayout, self).__init__(**kwargs)

class RootContainer(BoxLayout):
    def __init__(self, **kwargs):
        super(RootContainer, self).__init__(**kwargs)


class PyTronApp(App):

    def build(self):
        return RootContainer()


def init():
    data = mdc_format.build(dict(fields=dict(value=dict(cmd=0x12, msg_length=0x01, msg_data=25))))
    send_mdc_msg(data)

    sleep(0.2)

if __name__ == '__main__':
    init()
    PyTronApp().run()
