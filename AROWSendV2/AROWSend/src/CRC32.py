'''
Created on 27 Apr 2015
CRC32.py python version - change imports in AROWSend.py to use
@author: somerdata
'''
import binascii
import io
import DispProgress
try:
    from plx import print_console
except:
    raise ImportError( u'the plx module is not installed:'\
        +u' see http://www.decalage.info/en/python/plx')

MODE_DEBUG = False

#------------------------------------------------------------------------------
# CalcCRC
#-------------------
def calc_crc(mfile, CRCStop):
    """Calculate CRC32 for the file."""

    debug_print(u'Calculate CRC32 for "%s"...' % mfile)
    MonAff=DispProgress.DisplayType()
    MonAff.StartIte()
    sequence=" Calculate CRC32 " + mfile
    MonAff.NewString(sequence, truncate=True)
    updateCount=0
    
    try:
        f = io.open(mfile, 'rb')
        buf = f.read(16384)
        # start CRC32 calculation:
        crc32 = binascii.crc32(buf)
        while len(buf) != 0 :
            if CRCStop.is_set():
                crc32=0
                break
            buf = f.read(16384)
            # CRC32:
            crc32 = binascii.crc32(buf, crc32)
            updateCount+=1
            if updateCount>=100:
                MonAff.AffLigneBlink()
                updateCount=0
        f.close()
        debug_print(u"CRC32 = %08X" % crc32)
    except IOError:
            #print ("Error : CRC32 Opening impossible for: %s" %file)
            crc32=0
    return(crc32)

#------------------------------------------------------------------------------
def debug_print(text):
    "to post a message if MODE_DEBUG = True"

    if MODE_DEBUG:
        print_console (u"DEBUG:" + text)