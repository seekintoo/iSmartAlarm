#!/usr/bin/env python2
 
import sys
import time
from rflib import *
from binascii import hexlify, unhexlify

#These values will be most likely incorrect for your environment and target radio. Change them accordingly.

def ConfigureD(d, freq):
    d.setModeIDLE()
    d.setMdmModulation(MOD_GFSK)
    d.setFreq(freq)
    d.setMdmDeviatn(19042.969)
    d.setMdmChanBW(101562.5)
    d.setMdmDRate(38383.5)
#    d.setMdmChanSpc(199951.172)
    d.setMdmChanSpc(51000)
    d.setMdmSyncWord(0xd391)
    d.setMdmSyncMode(SYNCM_CARRIER)
    d.setEnablePktCRC(1)
    d.setEnablePktDataWhitening(0)
    d.setEnablePktAppendStatus(0)
#    d.makePktFLEN(0xff)
    d.makePktVLEN()
    d.printRadioConfig()

def main():

        try:
            if len(sys.argv) != 2:
                print "Usage   : %s 908000000" % sys.argv[0]
                sys.exit(0)

	    d = RfCat()
	    ConfigureD(d, long(sys.argv[1]))
	    d.setModeRX() 

	    while True:
		pkt   = d.RFrecv(timeout=120000)
		frame = hexlify(pkt[0])
                print "[rfcat recv] : '%s'\n" % (frame)

        except KeyboardInterrupt, e:
            print("W: interrupt received, proceeding")
            print e

        finally:
	    d.setModeIDLE()
	    sys.exit(0)

if __name__ == '__main__':
    main()
    RfCat().setModeIDLE()
    sys.exit(0)
