from kivy.app import App, Widget
from kivy.uix.gridlayout import GridLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.slider import Slider
from kivy.properties import ListProperty
from construct import *
from kivy.logger import Logger
import socket
import sys
from binascii import hexlify
import struct
from time import sleep

dst_ip = '192.168.0.10'       # ip of tv
dst_port = 1515

init_power = 0
init_source = 0x21
init_volume = 25

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

mdc_status_request = Struct(
    "fields" / RawCopy(Struct(
        "header" / Const(Int8ub, 0xAA),
        "cmd" / Const(Int8ub, 0x00),
        "id" / Const(Int8ub, 0x01),
        "msg_length" / Const(Int8ub, 0x00),
    )),
    "checksum" / Checksum(Bytes(1), lambda data: sum(bytearray(data)[1:]) % 256, this.fields.data),
)
mdc_status_response = Struct(
    "fields" / RawCopy(Struct(
        "header" / Const(Int8ub, 0xAA),
        "cmd" / Int8ub,
        "id" / Const(Int8ub, 0x01),
        "msg_length" / Int8ub,
        "ack_nack" / Int8ub,
        "rcmd" /Int8ub,
        "power" / Int8ub,
        "volume" / Int8ub,
        "mute" / Int8ub,
        "input" / Int8ub,
        "aspect" / Int8ub,
        "ntime" / Int8ub,
        "ftime" / Int8ub,
    )),
    "checksum" / Checksum(Bytes(1), lambda data: (sum(bytes(data)[1:]) % 256).to_bytes(1, byteorder='big'), this.fields.data),
)


def send_mdc_msg(msg):

    # create socket
    print('# Creating socket')
    print("Sending MDC Msg {}".format(hexlify(msg)))

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
    print('# Receive data from TV')
    #reply = sock.recv(1024)
    #print(reply)

    sock.close()


def get_tv_status():
    global init_power, init_source, init_volume

    data = mdc_status_request.build(dict(fields=dict(value=dict())))
    print("Sending Status Request packet = {}".format(hexlify(data)))

    # create socket
    print('# Creating socket')
    print("Sending MDC Msg {}".format(hexlify(data)))

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    except socket.error:
        print('Failed to create socket')
        sys.exit()

    sock.connect((dst_ip, dst_port))

    try:
        sock.sendall(data)
    except socket.error:
        print('Send failed')
        sys.exit()

    # Receiving from client
    data = sock.recv(1024)

    print("Received packet = {}".format(hexlify(data)))
    #print("Checksum = {}".format(hexlify((sum(bytearray(data)[1:-1])).to_bytes(1, byteorder='big'))))

    resp = mdc_status_response.parse(data)
    print("Parsed message = {}".format(resp))
    print("ACK/NACK = {}".format(resp.fields.value.ack_nack))

    init_power = resp.fields.value.power
    init_source = resp.fields.value.input
    init_volume = resp.fields.value.volume


    # came out of loop
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


class VolumeSlider(Slider):
    def __init__(self, **kwargs):
        kwargs['min'] = 0
        kwargs['max'] = 100
        kwargs['value'] = 25
        super(VolumeSlider, self).__init__(**kwargs)


class VolumeLayout(Widget):
    def __init__(self, **kwargs):
        super(VolumeLayout, self).__init__(**kwargs)


class HdmiLayout(Widget):
    def __init__(self, **kwargs):
        super(HdmiLayout, self).__init__(**kwargs)


class RootContainer(FloatLayout):
    def __init__(self, **kwargs):
        super(RootContainer, self).__init__(**kwargs)
        if init_power == 0:
            self.ids.powerOff.state = 'down'
        else:
            self.ids.powerOn.state = 'down'

        if init_source == 0x21 or init_source == 0x22:
            self.ids.hdmi1.state = 'down'
        elif init_source == 0x23 or init_source == 0x24:
            self.ids.hdmi2.state = 'down'
        else:
            self.ids.hdmi1.state = 'normal'
            self.ids.hdmi2.state = 'normal'

        self.ids.volume.value = init_volume

    def btn_power_on_touched(self):
        data = mdc_format.build(dict(fields=dict(value=dict(cmd=0x11, msg_length=0x01, msg_data=0x01))))
        print("Sending Power On packet = {}".format(hexlify(data)))
        self.ids.powerOn.state = 'down'
        send_mdc_msg(data)

    def btn_power_off_touched(self):
        data = mdc_format.build(dict(fields=dict(value=dict(cmd=0x11, msg_length=0x01, msg_data=0x00))))
        print("Sending Power Off packet = {}".format(hexlify(data)))
        self.ids.powerOff.state = 'down'
        send_mdc_msg(data)

    def btn_source_hdmi1_touched(self):
        data = mdc_format.build(dict(fields=dict(value=dict(cmd=0x14, msg_length=0x01, msg_data=0x21))))
        print("Sending Source HDMI 1 packet = {}".format(hexlify(data)))
        self.ids.hdmi1.state = 'down'
        send_mdc_msg(data)

    def btn_source_hdmi2_touched(self):
        data = mdc_format.build(dict(fields=dict(value=dict(cmd=0x14, msg_length=0x01, msg_data=0x23))))
        print("Sending Source HDMI 2 packet = {}".format(hexlify(data)))
        self.ids.hdmi2.state = 'down'
        send_mdc_msg(data)

    def set_volume(self, instance, value):
        print("Volume value = {}".format(value))
        vol = int(value)
        data = mdc_format.build(dict(fields=dict(value=dict(cmd=0x12, msg_length=0x01, msg_data=vol))))
        print("Sending Volume packet = {}".format(hexlify(data)))
        send_mdc_msg(data)
        sleep(0.2)
        #Logger.debug('Setting volume to {}'.format(value))


class PyTronApp(App):

    def build(self):
        return RootContainer()


def init():
    get_tv_status()
    sleep(0.2)

if __name__ == '__main__':
    init()
    PyTronApp().run()
