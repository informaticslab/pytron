from kivy.app import App, Widget
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.slider import Slider
from kivy.uix.modalview import ModalView
from kivy.uix.button import Button
from kivy.logger import Logger
from kivy.clock import Clock
from kivy.core.window import Window

import datetime
import queue
from mdc_comms_thread import MdcStatusThread, MdcCommandThread,\
    queue_volume_cmd, queue_power_on_cmd, queue_power_off_cmd, queue_hmdi1_cmd, queue_hmdi2_cmd


DEST_IP = '192.168.0.10'       # ip of tv
DEST_PORT = 1515

SIM_IP = 'localhost'       # ip of tv
SIM_PORT = 1515
USE_SIM = False

init_power = 0
init_source = 0x21
init_volume = 25
set_volume = 25
inactive_secs = 0

CMD_SETTLE_SECS = 10
POWER_SAVE_SECS = 240

NIGHTLY_POWER_OFF_HOUR = 19
NIGHTLY_POWER_OFF_MINUTE = 00

mdc_cmd_q = None
mdc_status_q = None
mdc_cmd_thread = None
mdc_status_thread = None

# comms_thread = None

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
    global inactive_secs, mdc_cmd_q

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
        Window.size = (800, 480)

    def btn_power_on_touched(self):
        self.clear_inactive_secs()
        self.ids.powerOn.state = 'down'
        queue_power_on_cmd(mdc_cmd_q)

    def btn_power_off_touched(self):
        self.clear_inactive_secs()
        self.ids.powerOff.state = 'down'
        queue_power_off_cmd(mdc_cmd_q)

    def btn_source_hdmi1_touched(self):
        self.clear_inactive_secs()
        self.ids.hdmi1.state = 'down'
        queue_hmdi1_cmd(mdc_cmd_q)

    def btn_source_hdmi2_touched(self):
        self.clear_inactive_secs()
        self.ids.hdmi2.state = 'down'
        queue_hmdi2_cmd(mdc_cmd_q)

    def set_volume(self, instance, value):
        global set_volume
        self.clear_inactive_secs()
        set_volume = int(value)
        #queue_volume_cmd(mdc_cmd_q, set_volume)


    @staticmethod
    def clear_inactive_secs():
        global inactive_secs
        inactive_secs = 0


class PytronApp(App):
    def __init__(self, **kwargs):
        super(PytronApp,  self).__init__(**kwargs)
        self.last_volume = 0
        self.powerSaveModalView = None
        self.displayNotRespondingView = None
        self.content = None
        self.savingPower = False
        self.powerSaveModeSecs = 0
        self.backlightOn = True

    def build(self):
        # call my_callback every 3/4 of a second
        Clock.schedule_interval(self.send_volume_update, 0.75)
        Clock.schedule_interval(self.pi_screen_saver, 1.0)
        Clock.schedule_interval(self.nightly_power_off_tv, 50.0)
        Clock.schedule_interval(self.update_time, 1.0)
        Clock.schedule_interval(self.update_tv_status, 1.0)
        # Create the comms thread

        return RootContainer()

    def update_time(self, dt):
        self.root.ids.label_time.text = str(datetime.datetime.now().strftime("%a, %B %d, %I:%M:%S %p"))

    def send_volume_update(self, dt):
        global set_volume

        if set_volume != self.last_volume:
            queue_volume_cmd(mdc_cmd_q, set_volume)
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
                if USE_SIM is False:
                    with open('/sys/class/backlight/rpi_backlight/bl_power', 'w') as f:
                        f.write("1")

    def nightly_power_off_tv(self, dt):
        now = datetime.datetime.now()

        # turn TV power off at 7pm
        if now.hour == NIGHTLY_POWER_OFF_HOUR and now.minute == NIGHTLY_POWER_OFF_MINUTE:
            queue_power_off_cmd(mdc_cmd_q)

    def update_tv_status(self, dt):
        if inactive_secs < CMD_SETTLE_SECS:
            return
        if self.savingPower is True:
            return

        if mdc_status_q.empty():
            return

        while not mdc_status_q.empty():
            display_status = mdc_status_q.get()

        power = display_status[0]
        source = display_status[1]
        volume = display_status[2]

        if power == -1:
            self.root.ids.powerOn.state = 'normal'
            self.root.ids.powerOff.state = 'normal'
            self.root.ids.hdmi2.state = 'normal'
            self.root.ids.hdmi2.state = 'normal'
            self.root.ids.volume.value = 0
            if self.displayNotRespondingView is None:
                self.show_display_not_responding(dt)

        else:
            if self.displayNotRespondingView:
                self.displayNotRespondingView.dismiss()
                self.displayNotRespondingView = None

            if power == 0:
                self.root.ids.powerOff.state = 'down'
                self.root.ids.powerOn.state = 'normal'

            else:
                self.root.ids.powerOn.state = 'down'
                self.root.ids.powerOff.state = 'normal'

            if source == 0x21 or source == 0x22:
                self.root.ids.hdmi1.state = 'down'
                self.root.ids.hdmi2.state = 'normal'

            elif source == 0x23 or source == 0x24:
                self.root.ids.hdmi2.state = 'down'
                self.root.ids.hdmi1.state = 'normal'

            else:
                self.root.ids.hdmi1.state = 'normal'
                self.root.ids.hdmi2.state = 'normal'

            self.root.ids.volume.value = volume

    def show_display_not_responding(self, dt):
        self.content = Button(text='Waiting for TV to respond...', font_size='28sp')
        self.displayNotRespondingView = ModalView(size_hint=(None, None), size=(400, 200), auto_dismiss=False)
        self.displayNotRespondingView.add_widget(self.content)

        # open the view
        self.displayNotRespondingView.open()

    def dismiss_power_save_modal(self, dt):
        global inactive_secs

        inactive_secs = 0
        if self.powerSaveModalView:
            self.powerSaveModalView.dismiss()
        self.powerSaveModalView = None
        self.savingPower = False
        self.backlightOn = True
        self.powerSaveModeSecs = 0
        if USE_SIM is False:
            with open('/sys/class/backlight/rpi_backlight/bl_power', 'w') as f:
                f.write("0")

        Logger.info("Pytron: Got into dismiss_power_save_modal")
        return


def main(args):
    global mdc_cmd_q, mdc_status_q

    # Create a single input and a single output queue for all threads.
    mdc_status_q = queue.Queue()
    mdc_cmd_q = queue.Queue()

    # Create the comms threads
    command_thread = MdcCommandThread(cmd_q=mdc_cmd_q)
    command_thread.start()

    status_thread = MdcStatusThread(status_q=mdc_status_q)
    status_thread.start()

    Logger.info("Pytron: Initializing application....")
    PytronApp().run()

if __name__ == '__main__':
    import sys
    main(sys.argv[1:])
