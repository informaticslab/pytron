from construct import *
import socket
import sys
from _thread import *
from binascii import hexlify
from time import sleep

HOST = '192.168.1.73'       # ip of tv
PORT = 1515

mdc_format = Struct(
    "fields" / RawCopy(Struct(
        "header" / Const(Int8ub, 0xAA),
        "cmd" / Int8ub,
        "id" / Const(Int8ub, 0x01),
        "msg_length" / Int8ub,
        "msg_data" / Int8ub,
    )),
    "checksum" / Checksum(Bytes(1), lambda data: (sum(bytes(data)[1:]) % 256).to_bytes(1, byteorder='big'), this.fields.data),
)

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
print('Socket created')

# Bind socket to local host and port
try:
    s.bind((HOST, PORT))
except socket.error as msg:
    print ('Bind failed. Error Code : ' + str(msg[0]) + ' Message ' + msg[1])
    sys.exit()

print ('Socket bind complete')

# Start listening on socket
s.listen(10)
print ('Socket now listening')


# Function for handling connections. This will be used to create threads
def client_thread(conn):

    # infinite loop so that function do not terminate and thread do not end.
    while True:

        # Receiving from client
        data = conn.recv(1024)
        reply = data
        if not data:
            break

        print("Received packet = {}".format(hexlify(data)))
        print("Checksum = {}".format(hexlify((sum(bytes(data)[1:-1])).to_bytes(1, byteorder='big'))))


        print("Parsed message = {}".format(mdc_format.parse(data)))

        conn.sendall(reply)

    # came out of loop
    conn.close()


# now keep talking with the client
while 1:
    # wait to accept a connection - blocking call
    conn, addr = s.accept()
    print ('Connected with ' + addr[0] + ':' + str(addr[1]))

    # start new thread takes 1st argument as a function name to be run, second is the tuple of arguments to the function.
    start_new_thread(client_thread, (conn,))

s.close()


