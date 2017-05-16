import socket
import threading
import queue
from construct import Struct, RawCopy, Const, Int8ub, Checksum, Bytes, core, this
import time

from binascii import hexlify

DEST_IP = '192.168.0.10'       # ip of tv
DEST_PORT = 1515

SIM_IP = 'localhost'       # ip of tv
SIM_PORT = 1515
USE_SIM = False

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


POWER_ON_MESSAGE = mdc_format.build(dict(fields=dict(value=dict(cmd=0x11, msg_length=0x01, msg_data=0x01))))
POWER_OFF_MESSAGE = mdc_format.build(dict(fields=dict(value=dict(cmd=0x11, msg_length=0x01, msg_data=0x00))))
HDMI1_INPUT_MESSAGE = mdc_format.build(dict(fields=dict(value=dict(cmd=0x14, msg_length=0x01, msg_data=0x21))))
HDMI2_INPUT_MESSAGE = mdc_format.build(dict(fields=dict(value=dict(cmd=0x14, msg_length=0x01, msg_data=0x23))))


def queue_power_on_cmd(cmd_q):
    cmd_q.put(POWER_ON_MESSAGE)


def queue_power_off_cmd(cmd_q):
    cmd_q.put(POWER_OFF_MESSAGE)


def queue_hmdi1_cmd(cmd_q):
    cmd_q.put(HDMI1_INPUT_MESSAGE)


def queue_hmdi2_cmd(cmd_q):
    cmd_q.put(HDMI2_INPUT_MESSAGE)


def queue_volume_cmd(cmd_q, vol):
    cmd_q.put(mdc_format.build(dict(fields=dict(value=dict(cmd=0x12, msg_length=0x01, msg_data=vol)))))


class ClientReply(object):
    """ A reply from the client thread.
        Each reply type has its associated data:

        ERROR:      The error string
        SUCCESS:    Depends on the command - for RECEIVE it's the received
                    data string, for others None.
    """
    ERROR, SUCCESS = range(2)

    def __init__(self, type, data=None):
        self.type = type
        self.data = data


class MdcCommandThread(threading.Thread):
    """ Implements the threading.Thread interface (start, join, etc.) and
        can be controlled via the cmd_q Queue attribute. Replies are
        placed in the reply_q Queue attribute.
    """

    def __init__(self, cmd_q=None):
        super(MdcCommandThread, self).__init__()
        self.cmd_q = cmd_q
        self.alive = threading.Event()
        self.alive.set()
        self.socket = None

        if USE_SIM:
            self.ip = SIM_IP
            self.port = SIM_PORT
        else:
            self.ip = DEST_IP
            self.port = DEST_PORT

    def run(self):

        while self.alive.isSet():

            try:
                cmd_data = self.cmd_q.get(True, 0.05)
                try:

                    self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    self.socket.settimeout(4)
                    self.socket.connect((self.ip, self.port))
                    self.socket.sendall(cmd_data)
                    data = self.socket.recv(1024)
                except socket.error:
                    continue
                except socket.timeout:
                    continue
                finally:
                    self.socket.close()

            except queue.Empty:
                continue

        # came out of loop
        self.socket.close()

    def join(self, timeout=None):
        self.alive.clear()
        threading.Thread.join(self, timeout)



class MdcStatusThread(threading.Thread):
    """ Implements the threading.Thread interface (start, join, etc.) and
        can be controlled via the cmd_q Queue attribute. Replies are
        placed in the reply_q Queue attribute.
    """

    def __init__(self, status_q=None):
        super(MdcStatusThread, self).__init__()
        self.status_q = status_q
        self.alive = threading.Event()
        self.alive.set()
        self.socket = None
        self.mdc_status_request = mdc_status_request.build(dict(fields=dict(value=dict())))

        if USE_SIM:
            self.ip = SIM_IP
            self.port = SIM_PORT
        else:
            self.ip = DEST_IP
            self.port = DEST_PORT

    def run(self):

        while self.alive.isSet():

            # sleep every second
            time.sleep(1)

            try:
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.socket.settimeout(4)
            except socket.error:
                print('Pytron: Failed to create socket for MDC TV status message')
                sys.exit()

            try:
                self.socket.connect((self.ip, self.port ))
                self.socket.sendall(self.mdc_status_request)
            except socket.timeout:
                self.status_q.put((-1, -1, -1))
                continue
            except socket.error:
                self.status_q.put((-1, -1, -1))
                continue

            # Receiving from client
            try:
                data = self.socket.recv(1024)

                # print("Checksum = {}".format(hexlify((sum(bytearray(data)[1:-1])).to_bytes(1, byteorder='big'))))

            except socket.error:
                self.status_q.put((-1, -1, -1))
                continue

            try:
                resp = mdc_status_response.parse(data)

            except core.FieldError:
                self.status_q.put((-1, -1, -1))
                continue

                #print("Pytron: Parsed message = {}".format(resp))
                #print("Pytron: ACK/NACK = {}".format(resp.fields.value.ack_nack))

            self.status_q.put((resp.fields.value.power, resp.fields.value.input, resp.fields.value.volume))


        # came out of loop
        self.socket.close()

    def join(self, timeout=None):
        self.alive.clear()
        threading.Thread.join(self, timeout)


def main(args):
    # Create a single input and a single output queue for all threads.
    status_q = queue.Queue()
    cmd_q = queue.Queue()

    # Create the comms thread
    status_thread = MdcStatusThread(status_q=status_q)
    status_thread.start()

    # Now get 100 results
    count = 100
    while count > 0:
        try:
            # Blocking 'get' from a Queue.
            result = status_q.get(True, 0.1)
            print("Power = {}, Input = {}, Volume = {}, Time = {}".format(result[0], hex(result[1]), result[2], time.strftime("%H:%M:%S")))
            count -= 1
        except queue.Empty:
            continue

    # Ask threads to die and wait for them to do it
    status_thread.join()


if __name__ == '__main__':
    import sys
    main(sys.argv[1:])