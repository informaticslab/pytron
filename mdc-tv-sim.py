from construct import *
import socket
import sys
from _thread import *
from binascii import hexlify
from time import gmtime, strftime

HOST = 'localhost'       # ip of tv
PORT = 1515

curr_power = 1
curr_input = 0x21
curr_volume = 10

mdc_cmd = Struct(
    "fields" / RawCopy(Struct(
        "header" / Const(Int8ub, 0xAA),
        "cmd" / Int8ub,
        "id" / Const(Int8ub, 0x01),
    )),
)

mdc_status_request = Struct(
    "fields" / RawCopy(Struct(
        "header" / Const(Int8ub, 0xAA),
        "cmd" / Int8ub,
        "id" / Const(Int8ub, 0x01),
        "msg_length" / Int8ub,
        "msg_data" / Int8ub,
    )),
    "checksum" / Checksum(Bytes(1), lambda data: (sum(bytes(data)[1:]) % 256).to_bytes(1, byteorder='big'), this.fields.data),
)

mdc_power_request = Struct(
    "fields" / RawCopy(Struct(
        "header" / Const(Int8ub, 0xAA),
        "cmd" / Int8ub,
        "id" / Const(Int8ub, 0x01),
        "msg_length" / Int8ub,
        "power" / Int8ub,
    )),
    "checksum" / Checksum(Bytes(1), lambda data: (sum(bytes(data)[1:]) % 256).to_bytes(1, byteorder='big'), this.fields.data),
)

mdc_volume_request = Struct(
    "fields" / RawCopy(Struct(
        "header" / Const(Int8ub, 0xAA),
        "cmd" / Int8ub,
        "id" / Const(Int8ub, 0x01),
        "msg_length" / Int8ub,
        "volume" / Int8ub,
    )),
    "checksum" / Checksum(Bytes(1), lambda data: (sum(bytes(data)[1:]) % 256).to_bytes(1, byteorder='big'), this.fields.data),
)

mdc_input_request = Struct(
    "fields" / RawCopy(Struct(
        "header" / Const(Int8ub, 0xAA),
        "cmd" / Int8ub,
        "id" / Const(Int8ub, 0x01),
        "msg_length" / Int8ub,
        "input" / Int8ub,
    )),
    "checksum" / Checksum(Bytes(1), lambda data: (sum(bytes(data)[1:]) % 256).to_bytes(1, byteorder='big'), this.fields.data),
)

mdc_status_response = Struct(
    "fields" / RawCopy(Struct(
        "header" / Const(Int8ub, 0xAA),
        "cmd" / Const(Int8ub, 0xFF),
        "id" / Const(Int8ub, 0x01),
        "msg_length" / Const(Int8ub, 0x09),
        "ack_nack" / Const(Int8ub, 0x41),
        "rcmd" / Const(Int8ub, 0x00),
        "power" / Int8ub,
        "volume" / Int8ub,
        "mute" / Const(Int8ub, 0x00),
        "input" / Int8ub,
        "aspect" / Const(Int8ub, 0x00),
        "ntime" / Const(Int8ub, 0x00),
        "ftime" / Const(Int8ub, 0x00),
    )),
    "checksum" / Checksum(Bytes(1), lambda data: sum(bytearray(data)[1:]) % 256, this.fields.data),
)

mdc_volume_response = Struct(
    "fields" / RawCopy(Struct(
        "header" / Const(Int8ub, 0xAA),
        "cmd" / Const(Int8ub, 0xFF),
        "id" / Const(Int8ub, 0x01),
        "msg_length" / Const(Int8ub, 0x03),
        "ack_nack" / Const(Int8ub, 0x41),
        "rcmd" / Const(Int8ub, 0x12),
        "volume" / Int8ub,
    )),
    "checksum" / Checksum(Bytes(1), lambda data: sum(bytearray(data)[1:]) % 256, this.fields.data),
)

mdc_power_response = Struct(
    "fields" / RawCopy(Struct(
        "header" / Const(Int8ub, 0xAA),
        "cmd" / Const(Int8ub, 0xFF),
        "id" / Const(Int8ub, 0x01),
        "msg_length" / Const(Int8ub, 0x03),
        "ack_nack" / Const(Int8ub, 0x41),
        "rcmd" / Const(Int8ub, 0x11),
        "power" / Int8ub,
    )),
    "checksum" / Checksum(Bytes(1), lambda data: sum(bytearray(data)[1:]) % 256, this.fields.data),
)

mdc_input_response = Struct(
    "fields" / RawCopy(Struct(
        "header" / Const(Int8ub, 0xAA),
        "cmd" / Const(Int8ub, 0xFF),
        "id" / Const(Int8ub, 0x01),
        "msg_length" / Const(Int8ub, 0x03),
        "ack_nack" / Const(Int8ub, 0x41),
        "rcmd" / Const(Int8ub, 0x14),
        "input" / Int8ub,
    )),
    "checksum" / Checksum(Bytes(1), lambda data: sum(bytearray(data)[1:]) % 256, this.fields.data),
)



#     "checksum" / Checksum(Bytes(1), lambda data: (sum(bytes(data)[1:]) % 256).to_bytes(1, byteorder='big'), this.fields.data),

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
print('Socket created')

# Bind socket to local host and port
try:
    s.bind((HOST, PORT))
except socket.error as msg:
    print ('Bind failed. Error Code : ' + str(msg[0]) + ' Message ' + msg[1])
    sys.exit()

print('Socket bind complete')

# Start listening on socket
s.listen(10)
print('Socket now listening')


# Function for handling connections. This will be used to create threads
def client_thread(conn):

    global curr_power, curr_input, curr_volume

    # infinite loop so that function do not terminate and thread do not end.
    while True:

        # Receiving from client
        data = conn.recv(1024)
        if not data:
            break

        req_time = strftime("%H:%M:%S", gmtime())
        # print("{}, received packet = {}".format(strftime("%H:%M:%S", gmtime()), hexlify(data)))
        #print("Checksum = {}".format(hexlify((sum(bytes(data)[1:-1])).to_bytes(1, byteorder='big'))))
        request = mdc_cmd.parse(data)
        #print("Parsed message = {}".format(request))

        if request.fields.value.cmd == 0x00:
            print("Status requested at {}".format(req_time))
            reply = mdc_status_response.build(dict(fields=dict(value=dict(power=curr_power, volume=curr_volume, input=curr_input))))
        elif request.fields.value.cmd == 0x12:
            req = mdc_volume_request.parse(data)
            curr_volume = req.fields.value.volume
            print("Volume set to {} at {}".format(curr_volume, req_time))
            reply = mdc_volume_response.build(dict(fields=dict(value=dict(volume=curr_volume))))
        elif request.fields.value.cmd == 0x14:
            req = mdc_input_request.parse(data)
            curr_input = req.fields.value.input
            print("Input set to {} at {}".format(hex(curr_input), req_time))
            reply = mdc_input_response.build(dict(fields=dict(value=dict(input=curr_input))))
        elif request.fields.value.cmd == 0x11:
            req = mdc_power_request.parse(data)
            curr_power = req.fields.value.power
            print("Power set to {} at {}".format(curr_power, req_time))
            reply = mdc_power_response.build(dict(fields=dict(value=dict(power=curr_power))))
        else:
            reply = request

        conn.sendall(bytearray(reply))

    # came out of loop
    conn.close()


# now keep talking with the client
while 1:
    # wait to accept a connection - blocking call
    conn, addr = s.accept()
    #print ('Connected with ' + addr[0] + ':' + str(addr[1]))

    # start new thread takes 1st argument as a function name to be run, second is the tuple of arguments to the function.
    start_new_thread(client_thread, (conn,))

s.close()


