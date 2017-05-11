import socket
import struct
import threading
import queue
import logging
from construct import *
from binascii import hexlify

DEST_IP = '192.168.0.10'       # ip of tv
DEST_PORT = 1515

SIM_IP = 'localhost'       # ip of tv
SIM_PORT = 1515
USE_SIM = True

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


class MdcCommsThread(threading.Thread):
    """ Implements the threading.Thread interface (start, join, etc.) and
        can be controlled via the cmd_q Queue attribute. Replies are
        placed in the reply_q Queue attribute.
    """
    def __init__(self, result_q=None):
        super(MdcCommsThread, self).__init__()
        self.result_q = result_q
        self.alive = threading.Event()
        self.alive.set()
        self.socket = None
        self.mdc_request = mdc_status_request.build(dict(fields=dict(value=dict())))

    def run(self):
        while self.alive.isSet():
            try:
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.socket.settimeout(15)

            except socket.error:
                logging.critical('Pytron: Failed to create socket for MDC TV status message')
                sys.exit()

            if USE_SIM:
                self.socket.connect((SIM_IP, SIM_PORT))
            else:
                self.socket.connect((DEST_IP, DEST_PORT))

            try:
                self.socket.sendall(data)
                logging.info("Pytron: Sent packet = {}".format(hexlify(data)))
            except socket.error:
                logging.critical('Pytron: Send failed')

            # Receiving from client
            try:
                data = self.socket.recv(1024)

                logging.info("Pytron: Received packet = {}".format(hexlify(data)))
                # print("Checksum = {}".format(hexlify((sum(bytearray(data)[1:-1])).to_bytes(1, byteorder='big'))))

                resp = mdc_status_response.parse(data)
                logging.debug("Pytron: Parsed message = {}".format(resp))
                logging.debug("Pytron: ACK/NACK = {}".format(resp.fields.value.ack_nack))

                init_power = resp.fields.value.power
                init_source = resp.fields.value.input
                init_volume = resp.fields.value.volume

            except socket.error:
                logging.critical('Pytron: socket receive failed in get_tv_status()')

            # came out of loop
            self.socket.close()

    def join(self, timeout=None):
        self.alive.clear()
        threading.Thread.join(self, timeout)

    def get_status(self):


    def _error_reply(self, errstr):
        return ClientReply(ClientReply.ERROR, errstr)

    def _success_reply(self, data=None):
        return ClientReply(ClientReply.SUCCESS, data)

def main(args):
    # Create a single input and a single output queue for all threads.
    status_result_q = queue.Queue()

    # Create the "thread pool"
    pool = [WorkerThread(dir_q=dir_q, result_q=result_q) for i in range(4)]

    # Start all threads
    for thread in pool:
        thread.start()

    # Give the workers some work to do
    work_count = 0
    for dir in args:
        if os.path.exists(dir):
            work_count += 1
            dir_q.put(dir)

    print 'Assigned %s dirs to workers' % work_count

    # Now get all the results
    while work_count > 0:
        # Blocking 'get' from a Queue.
        result = result_q.get()
        print 'From thread %s: %s files found in dir %s' % (
            result[0], len(result[2]), result[1])
        work_count -= 1

    # Ask threads to die and wait for them to do it
    for thread in pool:
        thread.join()


if __name__ == '__main__':
    import sys
    main(sys.argv[1:])