from kivy.app import App, Widget
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.slider import Slider
from kivy.uix.modalview import ModalView
from kivy.uix.button import Button
from kivy.logger import Logger
from kivy.clock import Clock
from construct import *
import socket
import sys
import argparse
from binascii import hexlify
from time import sleep
import datetime


dst_ip = '192.168.0.10'       # ip of tv
dst_port = 1515

sim_ip = '192.168.1.73'       # ip of tv
sim_port = 1515
USE_SIM = False

init_power = 0
init_source = 0x21
init_volume = 25
set_volume = 25

inactive_secs = 0

POWER_SAVE_SECS = 240
NIGHTLY_POWER_OFF_HOUR = 19
NIGHTLY_POWER_OFF_MINUTE = 00

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
    Logger.debug("Pytron: Creating socket for Samsung TV MDC protocol")
    Logger.debug("Pytron: Sending MDC Msg {}".format(hexlify(msg)))

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)

    except socket.error:
        Logger.error('Pytron: Failed to create socket')
        sys.exit()

    if USE_SIM:
        sock.connect((sim_ip, sim_port))
    else:
        sock.connect((dst_ip, dst_port))

    try:
        sock.sendall(msg)
    except socket.error:
        Logger.critical('Pytron: Send MDC message failed')
        sys.exit()


    # Receive data
    Logger.debug('Pytron: Received MDC message from from TV')
    #reply = sock.recv(1024)
    #print(reply)

    sock.close()


def get_tv_status():
    global init_power, init_source, init_volume

    data = mdc_status_request.build(dict(fields=dict(value=dict())))
    Logger.info("Pytron: Sending Status Request packet = {}".format(hexlify(data)))

    # create socket
    Logger.debug('Pytron: Creating socket for Samsung MDC TV Status message')
    Logger.debug("Pytron: Sending MDC Status request {}".format(hexlify(data)))

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(15)

    except socket.error:
        Logger.critical('Pytron: Failed to create socket for MDC TV status message')
        sys.exit()

    if USE_SIM:
        sock.connect((sim_ip, sim_port))
    else:
        sock.connect((dst_ip, dst_port))

    try:
        sock.sendall(data)
        Logger.info("Pytron: Sent packet = {}".format(hexlify(data)))
    except socket.error:
        Logger.critical('Pytron: Send failed')

    # Receiving from client
    try:
        data = sock.recv(1024)

        Logger.info("Pytron: Received packet = {}".format(hexlify(data)))
        #print("Checksum = {}".format(hexlify((sum(bytearray(data)[1:-1])).to_bytes(1, byteorder='big'))))

        resp = mdc_status_response.parse(data)
        Logger.debug("Pytron: Parsed message = {}".format(resp))
        Logger.debug("Pytron: ACK/NACK = {}".format(resp.fields.value.ack_nack))

        init_power = resp.fields.value.power
        init_source = resp.fields.value.input
        init_volume = resp.fields.value.volume

    except socket.error:
        Logger.critical('Pytron: socket receive failed in get_tv_status()')
        sys.exit()

    # came out of loop
    sock.close()


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
    global inactive_secs

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
        self.clear_inactive_secs()
        data = mdc_format.build(dict(fields=dict(value=dict(cmd=0x11, msg_length=0x01, msg_data=0x01))))
        Logger.info("Pytron: Sending Power On packet = {}".format(hexlify(data)))
        self.ids.powerOn.state = 'down'
        send_mdc_msg(data)

    def btn_power_off_touched(self):
        self.clear_inactive_secs()
        data = mdc_format.build(dict(fields=dict(value=dict(cmd=0x11, msg_length=0x01, msg_data=0x00))))
        Logger.info("Pytron: Sending Power Off packet = {}".format(hexlify(data)))
        self.ids.powerOff.state = 'down'
        send_mdc_msg(data)

    def btn_source_hdmi1_touched(self):
        self.clear_inactive_secs()
        data = mdc_format.build(dict(fields=dict(value=dict(cmd=0x14, msg_length=0x01, msg_data=0x21))))
        Logger.info("Pytron: Sending Source HDMI 1 packet = {}".format(hexlify(data)))
        self.ids.hdmi1.state = 'down'
        send_mdc_msg(data)

    def btn_source_hdmi2_touched(self):
        self.clear_inactive_secs()
        data = mdc_format.build(dict(fields=dict(value=dict(cmd=0x14, msg_length=0x01, msg_data=0x23))))
        Logger.info("Pytron: Sending Source HDMI 2 packet = {}".format(hexlify(data)))
        self.ids.hdmi2.state = 'down'
        send_mdc_msg(data)

    def set_volume(self, instance, value):
        global set_volume

        self.clear_inactive_secs()
        Logger.info("Pytron: Volume value = {}".format(set_volume))
        set_volume = int(value)

    def clear_inactive_secs(self):
        global inactive_secs
        inactive_secs = 0


class PytronApp(App):
    def __init__(self, **kwargs):
        super(PytronApp,  self).__init__(**kwargs)
        self.last_volume = 0
        self.powerSaveModalView = None
        self.content = None
        self.savingPower = False
        self.powerSaveModeSecs = 0
        self.backlightOn = True

    def build(self):
        # call my_callback every 3/4 of a second
        Clock.schedule_interval(self.send_mdc_updates, 0.75)
        Clock.schedule_interval(self.pi_screen_saver, 1.0)
        Clock.schedule_interval(self.nightly_power_off_tv, 50.0)
        Clock.schedule_interval(self.update_tv_status, 3.0)


        return RootContainer()

    def send_mdc_updates(self, dt):
        global set_volume

        if set_volume != self.last_volume:
            data = mdc_format.build(dict(fields=dict(value=dict(cmd=0x12, msg_length=0x01, msg_data=set_volume))))
            Logger.info("Pytron: Sending Volume packet = {}".format(hexlify(data)))
            send_mdc_msg(data)
            self.last_volume = set_volume

    def pi_screen_saver(self, dt):
        global inactive_secs
        if inactive_secs > POWER_SAVE_SECS:
            # create content and add it to the view
            if self.powerSaveModalView is None:
                self.content = Button(text='Going into screen saver mode. Touch to dismiss.', font_size='28sp')
                self.powerSaveModalView = ModalView(size_hint=(None, None), size=(800, 480), auto_dismiss=False)
                self.powerSaveModalView.add_widget(self.content)

                # bind the on_press event of the button to the dismiss function
                self.content.bind(on_press=self.dismiss_power_save_modal)

                # open the view
                self.powerSaveModalView.open()
                self.savingPower = True

        else:
            inactive_secs += 1

        if self.savingPower is True:
            if self.powerSaveModeSecs < 10:
                self.powerSaveModeSecs += 1
            elif self.backlightOn is True:
                self.backlightOn = False
                with open('/sys/class/backlight/rpi_backlight/bl_power', 'w') as f:
                    f.write("1")

    def nightly_power_off_tv(self, dt):
        now = datetime.datetime.now()

        # turn TV power off at 7pm
        if now.hour == NIGHTLY_POWER_OFF_HOUR and now.minute == NIGHTLY_POWER_OFF_MINUTE:
            data = mdc_format.build(dict(fields=dict(value=dict(cmd=0x11, msg_length=0x01, msg_data=0x00))))
            Logger.info("Pytron: Sending nightly power off packet = {}".format(hexlify(data)))
            send_mdc_msg(data)

    def update_tv_status(self, dt):
        if self.savingPower is True:
            return

        get_tv_status()
        if init_power == 0:
            self.root.ids.powerOff.state = 'down'
            self.root.ids.powerOn.state = 'normal'

        else:
            self.root.ids.powerOn.state = 'down'
            self.root.ids.powerOff.state = 'normal'

        if init_source == 0x21 or init_source == 0x22:
            self.root.ids.hdmi1.state = 'down'
            self.root.ids.hdmi2.state = 'normal'

        elif init_source == 0x23 or init_source == 0x24:
            self.root.ids.hdmi2.state = 'down'
            self.root.ids.hdmi1.state = 'normal'

        else:
            self.root.ids.hdmi1.state = 'normal'
            self.root.ids.hdmi2.state = 'normal'

        self.root.ids.volume.value = init_volume

    def dismiss_power_save_modal(self, dt):
        global inactive_secs

        inactive_secs = 0
        if self.powerSaveModalView:
            self.powerSaveModalView.dismiss()
        self.powerSaveModalView = None
        self.savingPower = False
        self.backlightOn = True
        self.powerSaveModeSecs = 0
        with open('/sys/class/backlight/rpi_backlight/bl_power', 'w') as f:
            f.write("0")

        Logger.info("Pytron: Got into dismiss_power_save_modal")
        return




def init():
    get_tv_status()
    Logger.info("Pytron: Initializing application....")

if __name__ == '__main__':
    init()
    PytronApp().run()
