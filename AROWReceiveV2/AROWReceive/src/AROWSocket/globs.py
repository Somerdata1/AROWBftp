'''
Created on 21 Apr 2015

@author: somerdata
'''
import time

import struct

# Header fields of BFTP data (format v5) :
    # check help of module struct for the codes
    # - frame marker 3 bytes BBB
    # - frame padding size uchar B
    # - frame length uint32 I
    # - data size in file frame: uint32=I
    # - session number: uint32=I
    # - offset, position of data in the file: Long Long =Q
    # - number of frames in the session: uint32=I
    # - file frame number: uint32=I
    # - number of frames in the file: uint32=I
    # - file date/time (in seconds since epoch): uint32=I
    # - length of file  (in octets): Long Long=Q
    # - File checksum CRC32: int32=i (signed)
    # - packet type: uchar=B
    # - file name length (+path): ucharsrc=B
    # (following the file name, then the data)

    # packed for maximum efficiency on 32-bit boundary systems
HEADER_FORMAT = "BBBBIIIQIIIIQiHH"
   # Correction bug 557 : size of format differs according to OS
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)

        # size : Win32 (54) ; Linux (54) ; MacOSX PPC (50)
        
UDP_TYPE=False
