#!/usr/local/bin/python
"""
----------------------------------------------------------------------------
AROWSEND v 2.0.0 - Unidirectional Data Transfer Protocol AROWBftp
----------------------------------------------------------------------------

For transferring a file, data stream  or directory tree across a unidirectional link
network diode using  TCP.
Parts Copyright Somerdata Ltd 2015
usage: see AROWSend.py -h
Based on the following copyrighted works -  
BlindFTP

Copyright Philippe Lagadec 2005-2008
Auteurs:
- Philippe Lagadec (PL) - philippe.lagadec(a)laposte.net
- Laurent Villemin (LV) - laurent.villemin(a)laposte.net
                          laurent.villemin(a)dga.defense.gouv.fr

Parts of this software are governed by the CeCILL license under French law and
# abiding by the rules of distribution of free software.  You can  use,
# modify and/or redistribute the software under the terms of the CeCILL
# license as circulated by CEA, CNRS and INRIA at the following URL
# "http://www.cecill.info".
#
# A copy of the CeCILL license is also provided in these attached files:
# Licence_CeCILL_V2-en.html and Licence_CeCILL_V2-fr.html
#
# As a counterpart to the access to the source code and  rights to copy,
# modify and redistribute granted by the license, users are provided only
# with a limited warranty  and the software's author, the holder of the
# economic rights, and the successive licensors have only limited
# liability.
#
# In this respect, the user's attention is drawn to the risks associated
# with loading,  using,  modifying and/or developing or reproducing the
# software by the user in light of its specific status of free software,
# that may mean  that it is complicated to manipulate,  and  that  also
# therefore means  that it is reserved for developers  and  experienced
# professionals having in-depth computer knowledge. Users are therefore
# encouraged to load and test the software's suitability as regards their
# requirements in conditions enabling the security of their systems and/or
# data to be ensured and,  more generally, to use and operate it in the
# same conditions as regards security.
#
# The fact that you are presently reading this means that you have had
# knowledge of the CeCILL license and that you accept its terms.

"""
"""
This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
     any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
#------------------------------------------------------------------------------
#V2.0.0 refactored for Python 3 - removed console printing module as python 3 supports unicode
#V1.3.1 Added multicast,single file send
#V1.3.0 Re-factored code, corrected bug when sending very many files,added more
#break events to abort
#added folder levels option to reduce memory usage, improve speed of scanning
#V1.2.1 Added scan end packet and removed restriction when tcp streaming is
#connected, added logging info
#changed loop code so individual files are sent [MinFileRedundancy] times and
#changed default to 1, removed old UDP code
#corrected shutdown to close threads, crc on the fly, added logging handlers
#re-organised folders for tidyness, added code to support PyInstaller
#V1.1.2 Corrected deletion code - strict now deletes files on the receive
#target immediately
#V1.1.1 corrected startup so cmd line takes precedence
#V1.1.0 Added internal statistics http server, ini file for settings storage
#V1.0.3 Cleaner thread exit - Changed threading to add stop events and hold
#terminal window open until user entry
# moved wait pause to send files thread, corrected xfl reset code
# added ini configuration file
#8/2/2013-changed to fully threading, including socket management,added stream
#packet handling, priority queueing,
#                   removed redundant code
#24/09/2012 - Release V1.0.1
#28/08/2012 - Somerdata Release V1.0.0
# 3/09/2012 - Correction to delete file code
# 20/09/2012 -changed recv to thread, added blocking to decode thread,
# corrected high cpu use from heartbeat thread
#------------------------------------------------------------------------------
type="3202"
__version__ ="2.0.0"
#=== IMPORTS ==================================================================
import sys,shutil
import socket
import struct
import time
import os
import os.path
import tempfile
import logging
import logging.handlers
import traceback
import gc
import binascii
import threading
import errno
import queue
from configparser import SafeConfigParser
from collections import  deque
import ipaddress

# Dedicated Windows modules
if sys.platform == 'win32':
    try:
        import win32api
        import win32process
        import winsound
        #import CRC32# python
        
    except:
        raise ImportError(u"the pywin32 module is not installed: " + u"see http://sourceforge.net/projects/pywin32")

#else:
    #from AROWC import CRC32 #cython
        
try:
    from path import path
except:
    raise ImportError(u"the path module is not installed:" + u" see http://www.jorendorff.com/articles/python/path/" + u" or http://pypi.python.org/pypi/path.py/ (if first URL is down)")

try:#use the c version if possible
    #from lxml import etree as ET

    import xml.etree.cElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET

# XFL - Python module to create and compare file lists in XML
try:
    import xfl
except:
    raise ImportError(u"the XFL module or one of its submodules  is not installed or damaged:")
# plx - portability layer extension
try:
    from plx import str_lat1, print_console
except:
    raise ImportError(u"the plx module is not installed:")

# internal modules
from OptionParser_doc import *
#import Console
import DispProgress
import socketserver 
from sendstatsserver import StatsServer

#=== CONSTANTS ===============================================================
AROW_APP = 'AROWSend'
AROW_VER = ':V2.0.0'
#UDP_TYPE=False
SCRIPT_NAME = os.path.basename(__file__)    # script filename
MARKER1 = 0xB6
MARKER2 = 0x3A
MARKER3 = 0x07
ConfigFile = 'AROWSend.ini'
RunningFile = 'bftp_run.ini'
Freq = 1000
Dur = 100
# this number is the buffer size that should be returned from a socket recv
# call and is experimental
# It depends on the os and receiving hardware.  too low creates a large
# overhead, too high slows processing
#somewhere between 16000 and 500000 probably, power of 2 probably
RX_BUF_LEN = 65536
            

# Network Packet Max size
if sys.platform == 'darwin':
    # With MacOSX exception 'Message too long' if size is too long (Packet
    # size)
    FRAME_SIZE = 1500
else:
    #if UDP_TYPE:
        #FRAME_SIZE = 65500
    #else:
    FRAME_SIZE = 32768

MODE_DEBUG = False   # check if debug() messages are displayed
MODE_VERBOSE = False
TEMP_ROOT = u"temp"    # Tempfile root
MAX_FILE_LENGTH = 1024  # Max length for the filename field
HB_DELAY = 5 # Default time between two Heartbeats (secs)

# This is the limit on receive when data will not be entered into the queue any
# more.
#Raising the limit can lead to high de-queuing times
#lowering leads to data corruption if data arrives faster than can be processed
#MAX_QUEUE_LEN =500000000
# in mode strict synchro retention duration
# a file disappears/deletes from the low-side window is deleted from the high
# side after this delay
#OFFLINEDELAY = 86400*7 # 86400 seconds in 1 day (7 days)
#OFFLINEDELAY = 1
IgnoreExtensions = ('.part', '.tmp', '.ut', '.dlm') #  Extensions of temp files which are never sent (temp files)

# Header fields of BFTP data (format v5) :
# check help of module struct for the codes
# - fields 1-3 frame marker 3 bytes BBB
# - field 4 frame padding size uchar B
# - field 5 frame length uint32 I
# - field 6 data size in file frame: uint32=I
# - field 7 session number: uint32=I
# - field 8 offset, position of data in the file: Long Long =Q
# - field 9 number of frames in the session: uint32=I
# - field 10 file frame number: uint32=I
# - field 11 number of frames in the file: uint32=I
# - field 12 file date/time (in seconds since epoch): uint32=I
# - field 13 length of file (in octets): Long Long=Q
# - field 14 File checksum CRC32: Int32=I (unsigned)
# - field 15 packet type: short=H
# - field 16 file name length (+path): short=H
# (following the file name, then the data)
# packed for maximum efficiency on 32-bit boundary systems
#NB. the meaning of fields 7-16 can change with packet type -see individual packet send code
HEADER_FORMAT = "4B 3I Q 4I Q I 2H"
# Correction bug 557 : size of format differs according to OS
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
# size : Win32 (56) ; Linux (56) ; MacOSX PPC (52)
LEGACY_PAD = False #invoke for AROW fw before V1.2
# Types of packets:
FILE_PACKET = 5  # File
INFO_PACKET = int(2)
DIRECTORY_PACKET = 1  # Directory (not yet used)
HEARTBEAT_PACKET = 10 # HeartBeat
SCANEND_PACKET = 11 # indicates completion of scan
DELETEFile_PACKET = 16 # File Delete
TCP_STREAM_PACKET = 20
UDP_STREAM_PACKET = 21
MC_STREAM_PACKET = 22
# Manifest of XFL attributes
ATTR_CRC = "c"                         # File CRC
ATTR_NBSEND = "NS"                    # Number sent
ATTR_LASTVIEW = "LV"                # Last View Date
ATTR_LASTSEND = "LS"                # Last Send Date
ATTR_NAME = "n"
#ATTR_CRC = "crc" # File CRC
#ATTR_NBSEND = "NbSend" # Number sent
#ATTR_LASTVIEW = "LastView" # Last View Date
#ATTR_LASTSEND = "LastSend" # Last Send Date

#=== Values to be processed within the .ini file ========================
# number of times 1 file will be sent (unless modified)
#MinFileRedundancy = 1

#=== GLOBAL VARIABLES =======================================================

#
# options parameters
global options
options = None
global isFileRx# bool used to signal that files are being received and heartbeat checking
               # should be suspended
isFileRx = False
global isTxing#bool used to signal that files are being transmitted and heartbeats should be
              #suspended
isTxing = False 
#global isTCPConnected
#isTCPConnected = False
global MinFileRedundancy
MinFileRedundancy = 1 

#
strEvent = threading.Event()
sendEvent = threading.Event()

# for stats measurement:
stats = None
strTCPQueue = deque()# the queue used for stream packet management
strUDPQueue = deque()
prQueue = queue.PriorityQueue()
PRIORITY_ONE = 1
PRIORITY_TWO = 2
PRIORITY_THREE = 3
PRIORITY_FOUR = 4
#------------------------------------------------------------------------------
# Helper defs
#-------------
# str_adjust : Adjust string to a dedicated length adding space or cutting
# string
#-------------------
def str_adjust(string, length=79):
    """adjust the string to obtain exactly the length indicated
    by truncating or filling with spaces."""
    l = len(string)
    if l > length:
        return string[0:length]
    else:
        return string + " " * (length - l)
#------------------------------------------------------------------------------
# DEBUG : Display debug messages if MODE_DEBUG is True
#-------------------
def debug_print(text):
    "to post a message if MODE_DEBUG = True"

    if MODE_DEBUG:
        print_console("DEBUG:" + text)
def test_connection():
    """ Used to test connection on startup or restart.Returns -1 if no socket available"""
    s = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    try:
        print (u" Checking %s Port %d " % (HOST,PORT))
        s.settimeout(1)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR,1)
        s.connect((HOST,PORT))
        s.getsockname()
        s.shutdown(1)
        s.close()
        del s
        time.sleep(0.1)
    except Exception as e:
        if s:
            s.close()
        print (u"Error: No connection %s" % (e))
        AROWLogger.error(u"TestConnection failed %s" % (e))
        return(-1)    

#------------------------------------------------------------------------------
# EXIT_HELP : Display Help in case of error
#-------------------
def exit_help():
    "Display a help message in case of error."

    # display the docstring (in the beginning of this file) that contains the
    # help.
    print (__doc__)
    sys.exit(1)


#------------------------------------------------------------------------------
# MTIME2STR : Convert date as a string
#-------------------
def mtime2str(file_date):
    "Convert a file date to string for display."
    localtime = time.localtime(file_date)
    return time.strftime('%d/%m/%Y %H:%M:%S', localtime)

def timepart2str(file_date):
    "Convert a file date to string for display."
    localtime = time.localtime(file_date)
    return time.strftime(' %H:%M:%S', localtime)

#------------------------------------------------------------------------------
# TCPStrmPkt
#-------------------
class TCPStrmPkt:
    """ A class to manage streaming sources. A TCP server allows for connection from a tcp source 
     and provides frame formatting to AROWBftp standard . Frames are queued for transmission, and an event flag
     raised to signal the frame transmission thread."""
        
    def __init__(self,port):
        self.sp_TCPport = port
        pass
    
    class ThSocketServer(socketserver.ThreadingMixIn,socketserver.TCPServer):
        daemon_threads = True
        allow_reuse_address = True
        #pass
    
    def th_send_str_pkt(self):
   
        """ thread to send stream packet """
        
        streampacket = threading.Thread(None,self.th_setup_tcp_srvr)
        streampacket.setDaemon(True)
        streampacket.start()
        
    
    def th_setup_tcp_srvr(self):
        """ for external connection, clients attach via the port number (only one) """
        
        server_address = ('localhost',self.sp_TCPport)
        """
       use a standard TCP server to server connecting clients
        """
        try:
            server = self.ThSocketServer(server_address,self.RequestHandler)
            server.allow_reuse_address = True
            ip,port = server.server_address
            print(u"TCP Serving on: " + str(ip) + ":" + str(port))
            skserver = threading.Thread(target=server.serve_forever)
            skserver.name = "TCPStream"
            skserver.setDaemon(True)
            skserver.start()
            return server
            
        except Exception as e:
            print( e)
        
    class RequestHandler(socketserver.BaseRequestHandler):
        """ Class to handle client requests on connection to the tcp server"""
        
        #For diagnostic purposes, initial values are filled with appropriate
        #sized fields
        sp_frame_num = 0
        sp_pad_size = 0
        sp_frame_length = 0
        sp_data_size = 0
        sp_sessionnum = 11111111
        sp_offset = 22222222222222
        sp_session_numframes = 33333333
        sp_numframe = 44444444
        sp_delay = HB_DELAY
        sp_timeout = time.time() + 1.25 * (sp_delay) 
        sp_filesize = 66666666
        sp_checksum = 0
        sp_packettype = TCP_STREAM_PACKET
        sp_filename_length = 77
        sp_file_num_frames = 0    
        
        def handle(self):
            #global isTCPConnected
            try:
                #isTCPConnected = True
                while True:
                    data = self.request.recv(4096)
                    if data:# data is accumulated until a threshold is reached - needs a timeout to flush
                        self.send_streampacket(data)
                        #Console.Print_temp("TCP "+str(sent),NL=False)
                    else:
                        self.request.close() #called when client disconnects
                        break
            except Exception as e:
                print (e)
            
        def send_streampacket(self, message=None):
            """ Create and enqueue  a stream frame """
            if message == None:
                return#nothing to send
            self.sp_data_size = len(message)
            # pad for 4 byte alignment.  NB this is for legacy AROW, not needed
            # for revisions from Feb2013
            if LEGACY_PAD:
                pad_size = 4 - (self.sp_data_size) % 4
                if pad_size == 4:
                    pad_size = 0
                if pad_size == 1:
                    padding = " "
                elif pad_size == 2:
                    padding = "  "
                elif pad_size == 3:
                    padding = "   "
                elif pad_size == 0:
                    padding = "" 
                self.sp_frame_length = len(message) + pad_size
            else:
                pad_size = 0
                padding = ""
                self.sp_frame_length = len(message)
            debug_print("sending Frame..")
            self.sp_frame_num +=1
            try:        
            # start packing the header:include place holders for unused fields
                header = struct.pack(HEADER_FORMAT,
                    MARKER1,
                    MARKER2,
                    MARKER3,
                    pad_size,
                    self.sp_frame_length,
                    self.sp_data_size,
                    self.server.server_address[1],#tcp stream port source
                #self.sp_sessionnum,
                    self.sp_offset,
                    self.sp_session_numframes,
                    self.sp_frame_num,
                    HB_DELAY,#self.sp_delay,
                    int(time.time()),#self.sp_timeout, (frame timestamp)
                    self.sp_filesize,
                    self.sp_checksum,
                    self.sp_packettype,
                    self.sp_filename_length)
            
                packet = header + message + padding.encode('utf-8')
            except Exception as e:
                print(e)
                return
            strEvent.set()
            prQueue.put(((PRIORITY_ONE,self.sp_frame_num),packet),False)
            sendEvent.set()#signal the transmission thread
            strEvent.clear()
            return len(packet)
            #if sys.platform == 'win32':
                #winsound.Beep(1200,Dur) #comfort beep
            
class MCStrmPkt:
    """ A class to handle multicast streams"""
    def __init__(self,port,group,ttl):
        #For diagnostic purposes, initial values are filled with appropriate
        #sized fields
            self.sp_pad_size = 0
            self.sp_frame_length = 0
            self.sp_data_size = 0
            self.sp_sessionnum = 99999999
            MCStrmPkt.sp_MCTtl = ttl
            #self.sp_offset=8888888888888888
            self.sp_session_numframes = 77777777
            self.sp_numframe = 66666666
            self.sp_frame_num = 0
            self.sp_delay = HB_DELAY
            self.sp_timeout = int(time.time() + 1.25 * (self.sp_delay)) 
            self.sp_filesize = 44444444
            self.sp_checksum = 0
            self.sp_packettype = MC_STREAM_PACKET
            self.sp_filename_length = 33
        
            self.sp_file_num_frames = 0
            global a
            a = 0
            MCStrmPkt.framecount = 0
            self.sp_MCPort = port
            self.sp_MCGroup = group
            
    def th_setup_mc_srvr(self):
        """ for external connection, clients attach via the port number (only one) """
        #server_address=('localhost',self.sp_MCPort)
        server_address = ('',self.sp_MCPort)
        """
       use a standard UDP server to server connecting clients
        """
        try:
            #MCAST_GRP = '224.1.1.1'
            #MCAST_PORT = 5007
            server = socketserver.UDPServer(server_address,self.RequestHandler)
            #server=self.ThSocketServer(server_address,self.RequestHandler)#
            #use this to launch one thread per request
            server.max_packet_size = 65536
            #server.socket.bind((self.sp_MCGroup, self.sp_MCPort))
            mreq = struct.pack('4sl', socket.inet_aton(self.sp_MCGroup), socket.INADDR_ANY)
            server.socket.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
            server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR,1)
            #server.allow_reuse_address=True
            skserver = threading.Thread(target=server.serve_forever)
            skserver.name = "MCServer"
            #if MODE_VERBOSE:
            msg = "Multicast Server running on port level %d" % (self.sp_MCPort)
            #printLock.acquire()
            #Console.Print_temp(msg,NL=True)
            #printLock.release()
            print(msg,)
            sys.stdout.flush()
            AROWLogger.info(msg)
            
            skserver.setDaemon(True)
            skserver.start()
            return server
            
        except Exception as e:
            print (e)
            
    class RequestHandler(socketserver.BaseRequestHandler):
        """ Class to handle client requests on connection to the udp server"""
        def handle(self):
            
            try:
                data = self.request[0]
                if data:#
                    #Console.Print_temp("MC "+str(len(data)),NL=False)
                    self.send_streampacket(data)
                else:
                    self.request.close() #called when client disconnects
            except Exception as e:
                print (e)
        
        def send_streampacket(self, message=None):
            """ Create and enqueue  a stream frame """
            if message == None:
                return#nothing to send
            sp_data_size = len(message)
            # pad for 4 byte alignment.  NB this is for legacy AROW, not needed
            # for revisions from Feb2013
            if LEGACY_PAD == True:
                pad_size = 4 - (sp_data_size) % 4
             
                if pad_size == 4:
                    pad_size = 0
                if pad_size == 1:
                    padding = " "
                elif pad_size == 2:
                    padding = "  "
                elif pad_size == 3:
                    padding = "   "
                elif pad_size == 0:
                    padding = "" 
                sp_frame_length = len(message) + pad_size
            
            else:
                pad_size = 0
                padding = ""
                sp_frame_length = len(message)
            debug_print(u"sending Frame..")
            MCStrmPkt.framecount +=1
            
            # start packing the header:include place holders for unused fields
            header = struct.pack(HEADER_FORMAT,
                MARKER1,
                MARKER2,
                MARKER3,
                pad_size,
                sp_frame_length,
                sp_data_size,
                self.server.server_address[1],     #UDP stream port number,
                MCStrmPkt.sp_MCTtl,#self.sp_offset,
                33333333,#self.sp_session_numframes,
                MCStrmPkt.framecount,#self.sp_frame_num,
                HB_DELAY,#self.sp_delay,
                int(time.time()),#self.sp_timeout, (frame timestamp)
                66666666, #self.sp_filesize,
                0,#self.sp_checksum,
                MC_STREAM_PACKET,#self.sp_packettype,
                77,#self.sp_filename_length
                )
            packet = header + message + padding.encode('utf-8')
            prQueue.put(((PRIORITY_ONE,MCStrmPkt.framecount),packet),False)
            sendEvent.set()#signal the transmission thread
                
#------------------------------------------------------------------------------
# UDPStrmPkt
#-------------------
class UDPStrmPkt:
    """ A class to manage streaming sources. A UDP server allows for connection from a udp source 
     and provides frame formatting to AROWBftp standard . Frames are queued for transmission, and an event flag
     raised to signal the frame transmission thread."""
    framecount = 0
    
    
    def __init__(self,port):
        #For diagnostic purposes, initial values are filled with appropriate
        #sized fields
            self.sp_pad_size = 0
            self.sp_frame_length = 0
            self.sp_data_size = 0
            self.sp_sessionnum = 99999999
            self.sp_offset = 8888888888888888
            self.sp_session_numframes = 77777777
            self.sp_numframe = 66666666
            self.sp_frame_num = 0
            self.sp_delay = HB_DELAY
            self.sp_timeout = time.time() + 1.25 * (self.sp_delay) 
            self.sp_filesize = 44444444
            self.sp_checksum = 0
            self.sp_packettype = UDP_STREAM_PACKET
            self.sp_filename_length = 33
        
            self.sp_file_num_frames = 0
            global a
            a = 0
            UDPStrmPkt.framecount = 0
            self.sp_UDPPort = port
            
        
               
    #class ThSocketServer(socketserver.ThreadingMixIn,socketserver.UDPServer):
        #pass
        
    def th_setup_udp_srvr(self):
        """ for external connection, clients attach via the port number (only one) """
        server_address = ('localhost',self.sp_UDPPort)
        """
       use a standard UDP server to server connecting clients
        """
        try:
            server = socketserver.UDPServer(server_address,self.RequestHandler)
            #server=self.ThSocketServer(server_address,self.RequestHandler)#
            #use this to launch one thread per request
            server.max_packet_size = 65536
            #server.request_queue_size=100
            #server.allow_reuse_address=True
            skserver = threading.Thread(target=server.serve_forever)
            skserver.name = "UDPServer"
            skserver.setDaemon(True)
            skserver.start()
            return server
            
        except Exception as e:
            print (e)
        
    class RequestHandler(socketserver.BaseRequestHandler):
        """ Class to handle client requests on connection to the udp server"""
        def handle(self):
            
            try:
                data = self.request[0]
                if data:#
                    #print("UDP in " + str(len(data)))
                    debug_print("UDP in" + str(len(data)))
                    #Console.Print_temp("UDP " + str(len(data)),NL=False)
                    self.send_streampacket(data)
                else:
                    self.request.close() #called when client disconnects
            except Exception as e:
                print (e)
            
        def send_streampacket(self, message=None):
            """ Create and enqueue  a stream frame """
            if message == None:
                return#nothing to send
            sp_data_size = len(message)
            # pad for 4 byte alignment.  NB this is for legacy AROW, not needed
            # for revisions from Feb2013
            if LEGACY_PAD == True:
                pad_size = 4 - (sp_data_size) % 4
             
                if pad_size == 4:
                    pad_size = 0
                if pad_size == 1:
                    padding = " "
                elif pad_size == 2:
                    padding = "  "
                elif pad_size == 3:
                    padding = "   "
                elif pad_size == 0:
                    padding = "" 
                sp_frame_length = len(message) + pad_size
            
            else:
                pad_size = 0
                padding = ""
                sp_frame_length = len(message)
            debug_print("sending Frame..")
            UDPStrmPkt.framecount +=1
            try:
            # start packing the header:include place holders for unused fields
                header = struct.pack(HEADER_FORMAT,
                    MARKER1,
                    MARKER2,
                    MARKER3,
                    pad_size,
                    sp_frame_length,
                    sp_data_size,
                    self.server.server_address[1],     #UDP stream port number,
                    22222222222222,#self.sp_offset,
                    33333333,#self.sp_session_numframes,
                    UDPStrmPkt.framecount,#self.sp_frame_num,
                    HB_DELAY,#self.sp_delay,
                    int(time.time()),#self.sp_timeout, (frame timestamp)
                    66666666, #self.sp_filesize,
                    0,#self.sp_checksum,
                    UDP_STREAM_PACKET,#self.sp_packettype,
                    77,#self.sp_filename_length
                    )
                packet = header + message + padding.encode('utf-8')
            except Exception as e:
                print(e)
                return
            prQueue.put(((PRIORITY_ONE,UDPStrmPkt.framecount),packet),False)
            sendEvent.set()#signal the transmission thread
            
                        
            #if sys.platform == 'win32':
                #winsound.Beep(1200,Dur) #comfort beep
#-------------------------------------------------------------------------------------------
# HeartBeat - dependent on packet class
#---------------
class HeartBeat:
    """ Generate  HeartBeat BFTP frame

        A session is a heartbeat sequence.
        A heartbeat is a simple frame with a timestamp (Session Id + sequence
        number) to identify if the link (physical and logical) is up or down

        The session Id will identify a restart
        The sequence number will identify lost frame

        Because time synchronisation between transmission/receiving computer isn't guaranteed,
        timestamp can't be checked in absolute terms.
        """
    
    def __init__(self):
        # local variables
        self.hb_pad_size= 0
        self.hb_frame_length = 0
        self.hb_data_size = 0
        self.hb_sessionnum = 0
        self.hb_offset = options.depth
        self.hb_session_numframes = 0
        self.hb_numframe = 0
        self.hb_file_num_frames = 1
        self.hb_delay = HB_DELAY
        self.hb_filesize = 0
        self.hb_checksum = 0
        self.hb_packettype = HEARTBEAT_PACKET
        self.hb_filename_length = 0
        #self.hb_timeout=time.time()+(self.hb_delay)
        self.hb_timeout = int(time.time() + 1.25 * (self.hb_delay)) 
        self.hb_filedate = 0
        
    def newsession(self):
        """ initiate values for a new session """
        self.hb_sessionnum = int(time.time())
        self.hb_numframe = 0
        return(self.hb_sessionnum, self.hb_numframe)

    def incsession(self):
        """ increment values in a existing session """
        self.hb_numframe+=1
        self.hb_timeout = int(time.time() + (self.hb_delay))
        self.hb_filedate = time.time()
        #print mtime2str(self.hb_timeout)
        return(self.hb_numframe, self.hb_timeout)

    def print_heartbeat(self):
        """ Print internal values of heartbeat """            #self.sock.setblocking(0)

        #print ("----- Current HeartBeart -----")
        #print ("Session ID : %d " %self.hb_sessionnum)
        msg = u" Seq             : %d :%s \r" % (self.hb_numframe,self.todaytime2str(self.hb_filedate))
        #stdout.write("\rSeq : %d " %self.hb_numframe)
        #stdout.flush()
        print(msg)
        #Console.Print_temp(msg, NL=False)
        sys.stdout.flush()
        #print ("\r Seq : %d " %self.hb_numframe)
        #print ("Delay : %d " %self.hb_delay)
        #print ("Current Session : %s " %mtime2str(self.hb_sessionnum))
        #print ("Next Timeout : %s " %mtime2str(self.hb_timeout))
        #print ("----- ------------------ -----")

    

    def send_heartbeat(self, message=None, num_session=None, frame_num=None):
        """ Send a heartbeat frame """
        # a HeartBeat is a short frame giving a timestamp which can be verified
        # at the receiver
        # give a session number to trace high-side stimulus from the low-side
        # num frame permits tracing iterations within a session
        # for
        # static assignment for testing and qualification of the mod
        
        if File_sendStop.is_set():
            return
        if num_session == None:
            num_session = self.hb_sessionnum
        if frame_num == None:
            frame_num = self.hb_numframe
        if message == None:
            #adjust length to create packet divisible by 4 for alignment
            message = "HeartBeat   "
        self.hb_data_size = len(message)
        debug_print("sending HB...")
        self.hb_frame_length = len(message)
        # start packing the header:
        try:
            header = struct.pack(HEADER_FORMAT,
                MARKER1,
                MARKER2,
                MARKER3,
                self.hb_pad_size,
                self.hb_frame_length,
                self.hb_data_size,
                self.hb_sessionnum,
                self.hb_offset,
                self.hb_session_numframes,
                frame_num,
                self.hb_delay,
                self.hb_timeout,
                self.hb_filesize,
                self.hb_checksum,
                self.hb_packettype,
                self.hb_filename_length)
        except struct.error as e:
            print(e)
            return
        frame = header + message.encode('utf-8') #68 bytes
        #print("HB: "+str(len(frame)))
        prQueue.put(((PRIORITY_FOUR,1),frame),False)#enqueue frame at low priority
        sendEvent.set()# signal transmission thread
        self.print_heartbeat()
            
    def send_loopHeartbeat(self,HB_Stop):

        """A loop to send heartbeat sequence every hb_delay seconds"""
        self.newsession()
        while (not HB_Stop.is_set()):
            self.send_heartbeat()
            self.incsession()
            time.sleep(self.hb_delay)
               

    def th_send_loop_heartbeat(self, HB_Stop):
        """ thread to send heartbeat """
        Sendheartbeat = threading.Thread(None, self.send_loopHeartbeat, args=(HB_Stop,))
        Sendheartbeat.name = "Heartbeat"
        Sendheartbeat.daemon = True
        Sendheartbeat.start()

    def todaytime2str(self,file_date):
        localtime = time.localtime(file_date)
        return time.strftime(' %H:%M:%S',localtime)
    
#------------------------------------------------------------------------------
# RateLimiter
#-------------------
class RateLimiter:
    "to control the flow of send data."

    def __init__(self, flowrate):
        """class contructor RateLimiter.

        flow : max flow allowed in Kbps."""
        # flow in Kbps converted to octets/s
        self.max_flow = flowrate * 1000 / 8
        debug_print(u"RateLimiter: flow_max = %d octets/s" % self.max_flow)
        # store the send time
        self.strt_time = time.time()
        # number octets already transferred
        self.octets_sent = 0

    def start_time(self):
        "to (re)start flow measurement."
        self.strt_time = time.time()
        #self.strt_time = time.clock()
        self.octets_sent = 0 

    def inc_data_count(self, octets):
        "increment octet sent counter."
        self.octets_sent += octets
        #return self.octets_sent

    def total_time(self):
        "get total measurement time."
        #if (time.time() - self.strt_time) == 0:
            #print (time.strftime("%H:%M:%S",time.localtime(time.time())),time.strftime("%H:%M:%S",time.localtime(self.strt_time)))
        return(time.time() - self.strt_time)
        
    def flow_rate(self):
        "get the average flow rate in octets/s."
        total_time = self.total_time()
        if total_time == 0: 
            return options.flowrate / 8 * 1000 #0 # to stop divide by zero
        flow_rate = self.octets_sent / total_time
        #flow_rate = self.octets_sent*1.0 / total_time
        return flow_rate

    def flow_rate_limiter(self):
        "add a pause in sending to limit the flow to the maximum."
        # add short breaks while the flow is too high:
        while self.flow_rate() > self.max_flow:
            #print "limit %d %d"%(self.flow_rate(), self.max_flow)
            time.sleep(0.0001)#100uS we hope
        

#------------------------------------------------------------------------------
class Th_SendSocket(threading.Thread):
    """ A class to send frames prioritised. This is a client of the AROW server (low side)"""
    def __init__(self,address):
        self.isTxConnected = False
        if address == None:
            self.address = ((HOST,PORT))
        else:
            self.address = address
        self.sendSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.sendSock.connect(self.address)
            
        except Exception as e:
            print (u'Send Socket not available %s' % (e))
            AROWLogger.error(u'Send Socket not available %s' % (e))
            return(None)
        self.isTxConnected = True
        
    def get_tx_connect(self):
        return self.isTxConnected, self.sendSock.getsockname()
        
    
    def send_container(self):
        """wait in a loop for frame ready events to be triggered. Send all items enqueued, in priority order """
        strttime = time.time()
        statlen = 0
        period = 5
        stats.add_rate(statlen)
        while(not File_sendStop.is_set()):
        #while True:
            if sendEvent.wait(period + 1) == True:# wait 5 sec, otherwise update rate stat to 0, this should be same as
                                                  # statsserver update period
                if self.isTxConnected:
                    try:
                        while prQueue.qsize() > 0:
                            intvltime = time.time() - strttime
                            temp=(prQueue.get()[1])
                            statlen+=self.sendSock.send(temp)# count bytes
                            #statlen+=self.sendSock.send(prQueue.get()[1])# count bytes
                            if intvltime >= period:# if more than 5 sec elapsed, update stats
                                statsend = statlen #assign to prevent altering during rate update
                                stats.add_rate(statsend)# send bytes sent to stats (rate conversion done later)
                                strttime = time.time()
                                statlen = 0
                        sendEvent.clear()# reset the event flag
                            #if sys.platform == 'win32':
                            #winsound.Beep(Freq,Dur)#comfort beep, disable in
                            #release

                    except socket.error as se:
                        if se[0] == errno.EPIPE:
                            msg = u"AROW Server disconnected"
                            print (msg)
                            AROWLogger.error(msg)
                            self.isTxConnected = False 
                            File_sendStop.set()
                    except Exception as e:
                        print(u"sendContainer: packet failed %s" % (e))
                        AROWLogger.error(u"sendContainer: packet failed %s" % (e))
                        self.isTxConnected = False
                        File_sendStop.set()
                        break
                else:
                    time.sleep(10)# wait for connection
            else:
                stats.add_rate(0)
             
    def th_send_container(self):
        """ thread to send container of frames """
        SendCont = threading.Thread(None, self.send_container, None)
        SendCont.name = "SendCont"
        SendCont.daemon = True
        SendCont.start()             
    
    def close(self):
        self.sendSock.close()  
#------------------------------------------------------------------------------
class SendOneFile(threading.Thread):
    
    def __init__(self,spath,filetosend,options):
        threading.Thread.__init__(self)
        self.refpath = spath
        self.filetosend = filetosend
        self.options = options
    
    def run(self):
        
        """Send a single file and exit"""
        #rate_limiter=0
        AROWLogger.info(u'Sending file "%s"' % str_lat1(self.filetosend, errors='replace'))
        rate_limiter = RateLimiter(self.options.flowrate)
        self.send_object(self.filetosend, os.path.split(self.filetosend)[1], rate_limiter,None) 
                    
        pass
        return                
    
    def send_object(self,send_file, dest_file, rate_limit=None, session_num=None, session_num_frames=None):
        """To enqueue send a file framed in UDP/TCP BFTP.

        send_file : local filename for the source (local disk)
        dest_file   : path relative to file in the destination directory
        rate_limit : to limit the link rate
        session_num    : session number
        session_num_frames : frame counter
        """
        if prQueue.qsize() == 0:
            self.ObjectCount = 0
        self.send_file = send_file
        offset = 0
        #dest_file_len=len(dest_file)

        #msg = "Sending file %s..." % self.send_file
        #Console.Print_temp(msg,NL=True)
        #AROWLogger.info(msg)
        if session_num == None:
            session_num = int(time.time())
        
        
        session_num_frames = 0
        if sys.platform == 'win32':
            # correct accented characters under Windows
            file_name_dest = (dest_file.encode('utf_8','strict'))
        else:
            # otherwise carry on
            file_name_dest = str(dest_file)
        name_length = len(file_name_dest)
               
        if MODE_DEBUG:
            debug_print("session number         = %d" % session_num)
            debug_print("session frame number  = %d" % session_num_frames)
            debug_print("file destination = %s" % dest_file)
            debug_print("name_length = %d" % name_length)
        if name_length > MAX_FILE_LENGTH:
            raise ValueError
        if self.send_file.isfile():
            file_size = self.send_file.getsize()
            file_date = self.send_file.getmtime()
            debug_print("file_size = %d" % file_size)
            debug_print("file_date = %s" % mtime2str(file_date))
            """
            # calculate  CRC32 before sending file
            if crc==None:
                crc32=CRC32.CalcCRC(self.send_file,File_sendStop)
            else:
                crc32=crcrate_limiter = RateLimiter(self.options.flowrate)
            """
            #calculate crc while file is being sent
            crc32 = 0
        print("crc = 0x%x" % crc32)
        #debugprint("crc = 0x%x" % crc32)
        # size remaining for data in a normal frame
        max_data_size = FRAME_SIZE - HEADER_SIZE - name_length
        #align to 4 byte boundary - not necessary with AROW from Feb 2013
        pad_size = max_data_size % 4#rate_limiter = RateLimiter(self.options.flowrate) add extra bytes
        #pad_size=4-max_data_size%4# add extra bytes
        if pad_size == 4:
            pad_size = 0
    
        max_data_size = max_data_size - pad_size            
        debug_print(u"max_data_size = %d" % max_data_size)
        nb_frames = (file_size + max_data_size - 1) / max_data_size
        if nb_frames == 0:
            # if the file is empty, still necessary to send a packet
            nb_frames = 1
        debug_print(u"number of frames = %d" % nb_frames)
        still_to_send = file_size
        try:
            f = open(self.send_file, 'rb')
            if rate_limit == None:
                # if no rate limit specified, use default:
                rate_limit = RateLimiter(self.options.flowrate)
            rate_limit.start_time()#reset time and octets sent
            for frame_num in range(0, nb_frames):
                # inject a pause to limit the flow rate
                rate_limit.flow_rate_limiter()
                if LEGACY_PAD == True:
                    if still_to_send > max_data_size:
                        data_size = max_data_size
                    else:
                        data_size = still_to_send
                        pad_size = 4 - (data_size + name_length) % 4
                        #pad_size=(data_size+name_length)%4
                        if pad_size == 4:
                            pad_size = 0
                    if pad_size == 1:
                        padding = " "
                    elif pad_size == 2:
                        padding = "  "
                    elif pad_size == 3:
                        padding = "   "
                    elif pad_size == 0:
                        padding = "" 
                else:
                    if still_to_send > max_data_size:
                        data_size = max_data_size
                    else:
                        data_size = still_to_send
                    pad_size = 0
                    padding = ""   
                still_to_send -= data_size
                offset = f.tell()
                """
                # calculate  CRC32 before sending file
                data = f.read(data_size)
                frame_length=name_rate_limiter = RateLimiter(self.options.flowrate)length+len(data)+len(padding)
                """
                #calculate crc while file is being sent
                dataBuf = bytearray(data_size)
                dataRead = f.readinto(dataBuf)
                crc32 = binascii.crc32(dataBuf, crc32)
                frame_length = name_length + dataRead + len(padding)
                # start with packet header:
                header = struct.pack(HEADER_FORMAT,
                    MARKER1,
                    MARKER2,
                    MARKER3,
                    pad_size,#
                    frame_length,
                    data_size,
                    session_num,
                    offset,
                    session_num_frames,
                    frame_num,
                    nb_frames,
                    file_date,
                    file_size,
                    crc32,
                    FILE_PACKET,
                    name_length)
                #calculate crc while file is being sent
                frame = header + file_name_dest.encode('utf-8') + dataBuf[:dataRead] + padding.encode('utf-8')
                #print( "frame crc"+str(crc32))
                try:
                    self.ObjectCount+=1
                    prQueue.put(((PRIORITY_TWO,self.ObjectCount),frame),True)# ordered by priority, then time so packets stay in sequence
                    #prQueue.put(((PRIORITY_TWO,(name_length+frame_num)),frame),True)
                    sendEvent.set()
                    if File_sendStop.is_set():
                        return -1
                    
                except Exception as e:
                    print (e)
                session_num_frames += 1
                rate_limit.inc_data_count(len(frame))
                #debugprint(u"average flow = %d" % rate_limit.flow_rate())
                percentage = 100 * (frame_num + 1) / nb_frames
                # display percentage: comma suppresses carriage return
                if not percentage % 10:
                    #Console.Print_temp(("%d%%\r" % percentage),NL=False)
                    print ("%d%%\r" % percentage,)
                # force display update
                #sys.stdout.flush()
            if MODE_DEBUG:
                print("transfer in %.4f seconds - flow rate %d Kbps" % (rate_limit.total_time(), rate_limit.flow_rate() * 8 / 1000))
                #Console.Print_temp("transfer in %.4f seconds - flow rate %d Kbps" % (rate_limit.total_time(), rate_limit.flow_rate() * 8 / 1000))
            #calculate crc while file is being sent - update the reference tree
            
            #self.DRef.dict[os.path.join(*(dest_file.split(os.path.sep)[2:]))].set(ATTR_CRC,
            #str(crc32))
            #self.DRef.dict[dest_file].set(ATTR_CRC, str(crc32))
            #stats.add_rate(rate_limit.flow_rate()*8/1000)
            isTxing = False
        except IOError as e:
            msg = u"Opening file %s... %s" % (self.send_file,e.errno)
            print ("Error : " + msg)
            AROWLogger.error(msg)
            session_num_frames = -1
            isTxing = False
        print( "final crc"+str(crc32))
        return crc32
        #return session_num_frames
    
    def send_info_message(self,infomsg,msgtype,ipno):
        #msgtypes indicate formatting - xml, mime etc, plus special case of
        #start(100) and close(101)
        #ipno is the source ip identifier as long
        if msgtype == None:
            msgtype = 0
        msg = infomsg[:16384] if len(infomsg) > 16384 else infomsg
        debug_print(u"sending Info msg...")
        frame_length = len(msg)
        # start packing the header:
        try:
            header = struct.pack(HEADER_FORMAT,
                MARKER1,
                MARKER2,
                MARKER3,
                0,
                frame_length,
                0,
                msgtype,
                ipno,
                0,
                0,
                0,
                time.time(),
                0,
                0,
                INFO_PACKET,
                0)
        except Exception as e:
            print(e)
            return
        frame = header + msg.encode('utf-8') 
        #print len(frame)
        prQueue.put(((PRIORITY_FOUR,1),frame))#enqueue frame at low priority
        sendEvent.set()# signal transmission thread
          # pad for 4 byte alignment.  NB this is for legacy AROW, not needed for hw revisions from Feb2013


#the threading version of send
class SendFiles(threading.Thread):
    """Class to organise files to be sent, breaking into frames, tagging with crc,
     checking for changes etc. This is expanded in V1.3 to introduce levelling of folders. This
     creates directory trees for each folder level to a dpeth set by the user. Each folder
     tree consumes RAM, for a whole tree this can be very large when the tree is very large (>10GB)
     Breaking up the tree into sub-trees reduces the memory used and speeds up the first file transmission.
     It also allows individual folder reconstruction from the receive side. For large trees, a good
     folder depth is between 2 & 4 """
    def __init__(self,spath,basepath,options,DRef,XFLFile,File_sendStop,timeoutEvent,tempfile):
        self.index = 0
        self.options = options
        self.DRef = DRef
        self.XFLFileName = XFLFile
        threading.Thread.__init__(self)
        self.refpathlist = spath
        self.directory = spath[0][0]
        self.basepath = basepath
        self.loopsend = RateLimiter(self.options.flowrate)
        self.isAllFilesSent = False#flag to show redundancy loop count has been reached
        self.ObjectCount = 0
        self.FilesToSend = deque()
        self.displayType = DispProgress.DisplayType()
        self.DScan = xfl.DirTree("",File_sendStop)# an instance of the DirTree class
        self.LoopCount = 0
        self.FileLessRedundancy = 0
        self.DirCount = 0
        self.sessRoot = ""
        self.FilesSent = 0
        self.tempsession=tempfile
            
 
    def run(self):
        """
        Synchronise a tree by sending all the files at regular intervals- ignores very recent files and any in extension list and empty directories.
        Uses two trees and compares for all differences - same, additions, deletions and changed
        """
        #rate_limiter=0
        self.send_info_message(hostname, 100, ipno)
                        
        sessionFile = self.XFLFileName
        while(not File_sendStop.is_set()):
            self.DirCount = 0
            self.FilesSent = 0
            session_start = int(time.time()) #seconds since epoch
            timeoutEvent.clear()
            AROWLogger.info(u'Synchronising  directory "%s"' % self.basepath)
           
            #AROWLogger.info(u'Synchronising  directory "%s"' % str_lat1(self.basepath, errors='replace'))
            # use the global RateLimiter object for all transfers:
            rate_limiter = RateLimiter(self.options.flowrate)
            self.send_info_message(hostname, 102, ipno)  
            global MinFileRedundancy,deleteDelay#,isTCPConnected
            # TODO : Distinguish between the treatment of local/ remote tree
            if (0):
                print(u"local tree structure")
                #  use with_directory to detect transmission need
            else:
                
                
                #     Loop 1 : Analyse and prioritise files
                self.isAllFilesSent = False
                # setup display progress cyclical pattern
                
                self.displayType.StartIte()
                #"""
                fileet = ET.Element('dt')
                fileet.set('depth', str(options.depth))
                if options.manifest or (options.manifest_start and  self.LoopCount > 0):
                    self.sessRoot,ext = os.path.splitext(sessionFile)
                    fileet.set('n', os.path.split(sessionFile)[0])
                else:
                    self.sessRoot,ext=os.path.splitext(self.tempsession)
                    fileet.set('n', os.path.split(self.tempsession)[0])

                #fileet.set('n', os.path.split(sessionFile)[0])
                if options.manifest:
                    if path(sessionFile).isfile():
                        self.DRef.read_file(sessionFile)
                if options.manifest_start and self.LoopCount > 0:
                    if path(sessionFile).isfile():
                        self.DRef.read_file(sessionFile)
                
                # to compare the list from disk to the list from the sync file
                scanpathlist = self.DScan.dir_walk(target,followlinks=True,depth=options.depth)
                if self.refpathlist != scanpathlist:
                    """
                    for reffile in self.refpathlist:
                        if reffile not in scanpathlist:
                            #print reffile
                            self.refpathlist.remove(reffile)
                     """  
                    self.scan_and_compare(ext,rate_limiter,session_start,fileet,scanpathlist)
                    self.refpathlist = scanpathlist
                else:
                    self.scan_and_compare(ext,rate_limiter,session_start,fileet,self.refpathlist)
                #debugprint("All files already sent")
                if options.manifest or options.manifest_start:
                    tree = ET.ElementTree(fileet)
                    tree.write(sessionFile)# write out the list of all temp/sync files
                self.LoopCount+=1
                if options.manifest:#send the sync files
                    sesslist = self.DScan.read_file(sessionFile)
                    for member in sesslist:
                        f = os.path.join("arowsync",os.path.split(member)[1])
                        self.send_object(member,f , rate_limiter,session_num=session_start) 
                                    
                    self.send_object(sessionFile, os.path.join("arowsync",os.path.split(sessionFile)[1]), rate_limiter,session_num=session_start) 
                        
                if options.pause > 0:
                    self.wait_in_loop(session_start)# the wait for each loop
                else:
                    File_sendStop.set()
        debug_print("End Loop send")
        
        #raise KeyboardInterrupt()
    
    def scan_and_compare(self,ext,rate_limiter,session_start,fileet, pathlist):
        #pathlist=pathlist[::-1]# reverse list
        while (not(self.isAllFilesSent) or (self.DirCount < len(pathlist))):
        #"""
        #while (not(self.isAllFilesSent)) :
            if File_sendStop.is_set():
                break
            self.directory = pathlist[self.DirCount][0]# get the directory name for this iteration
            dirlevel = pathlist[self.DirCount][1]# and the directory level
            self.XFLFileName = self.sessRoot + '_' + str(self.DirCount) + ext # create the session file to index the iteration files
            try: #read the recovery xml file for this iteration, it may have changed
                self.DRef.read_file(self.XFLFileName)
            except:# there may not be a recovery file so default to reading from the disk
                self.DRef.read_disk(pathlist[self.DirCount],options.depth, working.AffChar)
                
            if MODE_VERBOSE:
                msg = "%s - Scanning tree %s level %d" % (mtime2str(time.time()),self.directory,dirlevel)
                print(msg,)
                #Console.Print_temp(msg,NL=True)
                sys.stdout.flush()
                AROWLogger.info(msg)
            
            
            self.DScan = xfl.DirTree("",File_sendStop)# a new instance of the DirTree class to hold the disk scan results
            if MODE_DEBUG:
                self.DScan.read_disk(self.directory, xfl.callback_dir_print)
            else:#from the second loop or if we are using the synchro file, scan the disk to
                 #create the comparison tree
                if self.LoopCount != 0 or (self.XFLFileName.find("AROWsynchro") != -1):
                    
                    self.DScan.read_disk(pathlist[self.DirCount],options.depth, working.AffChar)
                else:# to speed up the first scan, we know the ref and scan are the same
                    self.DScan = self.DRef
                if MODE_DEBUG:
                    msg = "%s - Comparing trees" % mtime2str(time.time())
                    print(msg,)
                    #Console.Print_temp(msg,NL=True)
                    AROWLogger.info(msg)
                #DScan.read_disk(directory)
            debug_print("%s - Analyse tree structure" % mtime2str(time.time()))
            if self.directory == self.basepath:# the path to scan need to match the level of the folder in the structure
                relpath = ""
            else:
                relpath = os.path.relpath(self.directory, self.basepath)
            # compare the DRef and DScan trees, update the dictionaries
            same, different, only1, only2 = xfl.compare_DT(self.DScan, self.DRef,self.LoopCount,relpath)
            self.process_deleted_files(only2,relpath)
            self.process_new_files(only1,relpath)
            self.process_modified_files(different)
            self.process_identical_files(same)
            t1 = threading.Thread(target=self.setup_recovery_file_attribs,name="DrefFileThrd")
            t1.start()
            #self.setupRecoveryFileAttribs()
            
            #FileToSend=[]
            self.create_file_list(same,only1,different,dirlevel)
            same.clear(),only1.clear(),different.clear()#,only2.clear()
            only2 = []
            #Console.Print_temp("%s - Priority to previously unsent files\n"
            #%mtime2str(time.time()))
            sys.stdout.flush()
            #FileToSend = sortDictBy(FileToSend, "iteration")#removed for use
            #with deque
            print((u"Number of files to synchronise : %d" % len(self.FilesToSend)),)
            #Console.Print_temp((u"Number of files to synchronise : %d" % len(self.FilesToSend)),NL=False)
            debug_print(u"Number of file to synchronise : %d" % len(self.FilesToSend))
            #if len(self.FilesToSend)==0:
                #self.isAllFilesSent=True
            self.loopsend = RateLimiter(self.options.flowrate)
            self.loopsend.start_time()
            print(u"%s - Sending data " % mtime2str(time.time()),)
            #Console.Print_temp(u"%s - Sending data " % mtime2str(time.time()),NL=False)
            sys.stdout.flush()
            folderdepth = options.depth
            self.send_queued_files(rate_limiter,session_start,dirlevel)
            self.DScan.dict.clear()
            #self.FilesToSend.clear()
            t1.join()
            self.write_backup_file()# this has to finish before the next scan starts
            #"""
            #update the session file list
            #sessionFileList.append(self.XFLFile)
            self.DirCount+=1
            #update the xml session tree
            head,tail = os.path.split(self.XFLFileName)
            e = ET.SubElement(fileet,"file")
            e.text = str(tail)   
            
            #"""
                    
    
    def process_new_files(self,only1,relpath):
        if only1:
            msg = u"%s - Processing %d New items\n " % (mtime2str(time.time()),len(only1))
            print(msg,)
            #Console.Print_temp(msg,NL=False)
            #sys.stdout.flush()
            debug_print(u"\n========== New  ========== ")
        RefreshDictNeeded = False
        for f in sorted(only1):
            if(File_sendStop.is_set() == False):
                self.displayType.AffChar()
                debug_print("N  " + f)
                parent, myfile = f.splitpath()
                index = 0
                if parent == relpath:
                #if parent == '':
                    ET.SubElement(self.DRef.et, self.DScan.dict[f].tag)
                    index = len(self.DRef.et) - 1
                    if (self.DScan.dict[f].tag == xfl.TAG_FILE):
                        RefreshDictNeeded = True
                        for attr in (xfl.ATTR_NAME, xfl.ATTR_MTIME, xfl.ATTR_SIZE):
                            self.DRef.et[index].set(attr, self.DScan.dict[f].get(attr))
                        for attr in (ATTR_LASTSEND, ATTR_CRC, ATTR_NBSEND):
                            self.DRef.et[index].set(attr, str(0))
                        self.DRef.et[index].set(ATTR_LASTVIEW, self.DScan.et.get(xfl.ATTR_TIME))
                    else:
                        self.DRef.et[index].set(xfl.ATTR_NAME, self.DScan.dict[f].get(xfl.ATTR_NAME))
                else:
                    ET.SubElement(self.DRef.dict[parent], self.DScan.dict[f].tag)
                    index = len(self.DRef.dict[parent]) - 1
                    if (self.DScan.dict[f].tag == xfl.TAG_FILE):
                        RefreshDictNeeded = True
                        for attr in (xfl.ATTR_NAME, xfl.ATTR_MTIME, xfl.ATTR_SIZE):
                            self.DRef.dict[parent][index].set(attr, self.DScan.dict[f].get(attr))
                        for attr in (ATTR_LASTSEND, ATTR_CRC, ATTR_NBSEND):
                            self.DRef.dict[parent][index].set(attr, str(0))
                        self.DRef.dict[parent][index].set(ATTR_LASTVIEW, (self.DScan.et.get(xfl.ATTR_TIME)))
                    else:
                        self.DRef.dict[parent][index].set(xfl.ATTR_NAME, self.DScan.dict[f].get(xfl.ATTR_NAME))
                # Dictionary reconstruction to insert elements
                if (self.DScan.dict[f].tag == xfl.TAG_DIR):
                    self.DRef.pathdict(relpath)
                    #RefreshDict=False
        # Dictionary reconstruction if only adding files
        if RefreshDictNeeded:
            self.DRef.pathdict(relpath)
     
    def process_deleted_files(self,only2,relpath):
        if only2:
            msg = u"%s - Processing %d Deleted items\n" % (mtime2str(time.time()),len(only2))
            print(msg,)
            #Console.Print_temp(msg,NL=False)
            #sys.stdout.flush()
            debug_print(u"\n========== Deleted ========== ")
        for f in sorted(only2, reverse=True):#traverse the list backwards to delete files before directories
            debug_print("S  " + f)
            self.displayType.AffChar()
            DeletionNeeded = False
            parent, myfile = f.splitpath()#get directory and file name
            if(self.DRef.dict[f].tag == 'l'):#is this a level?
                try:
                    if os.path.exists(f):
                        if os.listdir(f) == []:
                            pass
                        else:
                            continue
                    else:
                        pass
                        
                except:
                    pass
                DeletionNeeded = True# empty directory
                if self.options.synchro_tree_strict:
                    self.send_delete_file_message(f)
                
            if(self.DRef.dict[f].tag == xfl.TAG_DIR):#is this a directory?
                # Check the presence of children (dir / file)
                if not(bool(self.DRef.dict[f].getchildren())):
                    DeletionNeeded = True# empty directory
                    if self.options.synchro_tree_strict:
                        self.send_delete_file_message(f)
                    
            if(self.DRef.dict[f].tag == xfl.TAG_FILE):#is this a file?
                LastView = self.DRef.dict[f].get(ATTR_LASTVIEW)# get the last file time
                NbSend = int(self.DRef.dict[f].get(ATTR_NBSEND))# how many times has it been sent?
                if LastView == None:
                    LastView = 0# catch for no time stamp
                # if missing after X days ; remove
                if (time.time() - (float(LastView) + OffLineDelay)) > 0:
                    if (NbSend == None): NbSend = -1 #catch number of sends
                    #if (NbSend == None): NbSend=-10 #catch number of sends
                    else:
                        if (NbSend >= 0):
                            NbSend = -1
                    for attr in (ATTR_LASTSEND, ATTR_CRC):
                        self.DRef.dict[f].set(attr, str(0))
                    if self.options.synchro_tree_strict:
                        self.send_delete_file_message(f)
                    NbSend-=1
                    if NbSend > -1:
                    #if NbSend > -10:
                        self.DRef.dict[f].set(ATTR_NBSEND, str(NbSend))
                    else:
                        DeletionNeeded = True
            if DeletionNeeded:
                #print "deleting %s "%f
                debug_print(u"****** |Removing")
                if parent == relpath: #'':
                    self.DRef.et.remove(self.DRef.dict[f])# remove from the refe element tree
                else:
                    #self.DRef.et.remove(self.DRef.dict[f])
                    self.DRef.dict[parent].remove(self.DRef.dict[f])
                #self.DRef.pathdict(relpath)
    
    def process_modified_files(self,different):
        if different:
            msg = u"%s - Processing %d Modified items\n" % (mtime2str(time.time()),len(different))
            print(msg)
            #Console.Print_temp(msg,NL=False)
            debug_print(u"\n========== Modified  ========== ")
        for f in (different):
            self.displayType.AffChar()
            debug_print("D  " + f)
            if (self.DScan.dict[f].tag == xfl.TAG_FILE):
                # update data
                for attr in (xfl.ATTR_MTIME, xfl.ATTR_SIZE):
                    self.DRef.dict[f].set(attr, str(self.DScan.dict[f].get(attr)))
                for attr in (ATTR_LASTSEND, ATTR_CRC, ATTR_NBSEND):
                    self.DRef.dict[f].set(attr, str(0))
                self.DRef.dict[f].set(ATTR_LASTVIEW, self.DScan.et.get(xfl.ATTR_TIME))
            
    def process_identical_files(self,same):
        if same:
            msg = u"%s - Processing %d matched items\n" % (mtime2str(time.time()),len(same))
            print(msg)
            #Console.Print_temp(msg,NL=False)
            sys.stdout.flush()
            debug_print(u"\n========== Matched  ========== ")
        for f in (same):
            if(File_sendStop.is_set() == False):
                self.displayType.AffChar()
                debug_print("I  " + f)
                if (self.DScan.dict[f].tag == xfl.TAG_FILE):
                    try:
                        if self.DRef.dict[f].get(ATTR_LASTVIEW) == None:#set attribs to inital values
                            for attr in (ATTR_LASTSEND, ATTR_CRC, ATTR_NBSEND):
                                self.DRef.dict[f].set(attr, str(0))
                        self.DRef.dict[f].set(ATTR_LASTVIEW, self.DScan.et.get(xfl.ATTR_TIME))
                    except KeyError:
                        pass #the entry in the tree may not exist ( damaged recovery file?)

    def setup_recovery_file_attribs(self):
        if MODE_VERBOSE:
            msg = "u%s - setting attributes in Recovery File %s\n" % (mtime2str(time.time()),self.XFLFileName)
            print(msg)
            #Console.Print_temp(msg)
        self.DRef.et.set(xfl.ATTR_TIME, str(time.time()))#set the recovery file timestamp
        if self.XFLFileName == "AROWsynchro.xml":
            if os.path.isfile(self.XFLFileName):
                try:
                    os.rename(self.XFLFileName,XFLFileBak)# then create a backup of the old xml file
                except Exception as e:
                    try:
                        AROWLogger.error(e)
                        os.remove(XFLFileBak)# on windows, can't rename an existing file so remove it first
                        os.rename(self.XFLFileName,XFLFileBak)
                    except:
                        pass # if the file is locked elsewhere then continue without change
        
                try:
                    self.DRef.write_file(self.XFLFileName)
                except Exception as e :
                    print(str(e))#maybe the path is inaccessible
    def create_file_list(self,same,only1,different,dirlevel):    
        if MODE_VERBOSE:
            msg = u"%s -  %d files selected for filtering\n" % (mtime2str(time.time()),(len(same) + len(only1) + len(different)))
            debug_print(msg)
            print(msg)
            #Console.Print_temp(msg,NL=False)
            sys.stdout.flush()
        for f in (only1):
            self.filter_files(f,dirlevel)
        for f in (different):
            self.filter_files(f,dirlevel)
        for f in (same):
            self.filter_files(f,dirlevel)
                
    def filter_files(self,f,dirlevel):
        if(File_sendStop.is_set() == False):
            self.displayType.AffChar()
            if str(f).find("arowsync/AROWsynchro") == 0:
                return
            
            root,extension = os.path.splitext(os.path.basename(f))
            if not(extension in IgnoreExtensions) and (self.DScan.dict[f].tag == xfl.TAG_FILE):# only send files, not directories
                # Ignore very recent files (< 60 seconds ago)(risk of taking a largefile currently being transferred in)
                 # and files already delivered
                try:
                    if abs(float(self.DRef.dict[f].get(xfl.ATTR_MTIME)) - float(self.DRef.dict[f].get(ATTR_LASTVIEW))) > 60 and int(self.DRef.dict[f].get(ATTR_NBSEND)) < MinFileRedundancy:
                        myfile = {'iteration':int(self.DRef.dict[f].get(ATTR_NBSEND)), 'file':f}
                        self.FilesToSend.append(myfile)
                    debug_print(" +-- " + f)
                except KeyError:
                    pass# the entry in the tree may not exist ( damaged recovery file?)
   
    def send_queued_files(self, rate_limiter,session_start,dirlevel):
        """manages queue of files to be sent from directory scan """
        LastFileSendMax = False
        ToSend = len(self.FilesToSend)
        #head,tail=os.path.split(self.directory)
        #a,b=os.path.split(head)
        # bail if the total loop time > the permitted transmit time and there
        # are no more files- why?
        while LastFileSendMax == False:
            if(File_sendStop.is_set() == False): 
                if MODE_DEBUG:
                    msg = u"Left to send %d of %d" % (len(self.FilesToSend),ToSend)
                    print(msg,)
                    #Console.Print_temp(msg,NL=True)
                if len(self.FilesToSend) != 0:
                    try:
                        item = self.FilesToSend.popleft()
                        #item=FileToSend.pop(0)
                        f = item['file']
                        i = item['iteration']
                        debug_print(u"Iteration:* %d *" % i)
                        # when using multi-folders to send , path names need
                        # manipulating because we need to send the full
                        # path but store the folder/file from the next level down
                        fullfilepath = os.path.join(self.basepath,f)
                        # Correction Bug error if file was already removed.
                        if fullfilepath.isfile():
                        #File stability/integrity check : check date and size
                        #compared to reference
                        #   discard file from list if it is different
                        # todo?  : don't check stability/integrity for small files
                        # or synchro files
                        
                            s_table = (fullfilepath.getmtime() == float(self.DRef.dict[f].get(xfl.ATTR_MTIME)) and \
                                fullfilepath.getsize() == int(self.DRef.dict[f].get(xfl.ATTR_SIZE)))
                            if not s_table:
                                self.DRef.dict[f].set(ATTR_CRC,'0')
                                self.DRef.dict[f].set(ATTR_NBSEND,'0')
                            if (s_table or fullfilepath.getsize() < 1024 or (str(f).find("AROWsynchro" != 0))):
                            #if s_table:
                                #to compute crc before sending the file
                                #if self.DRef.dict[f].get(ATTR_CRC)=='0':
                                    #current_CRC=str(CRC32.CalcCRC(fullfilepath,File_sendStop))#
                                    #interruptible using event
                                    #self.DRef.dict[f].set(ATTR_CRC, current_CRC)
                                try:
                                    if File_sendStop.is_set():
                                        msg = u"Stop signal received - file transfer interrupted"
                                        AROWLogger.error(msg)
                                        print(msg,)
                                        #Console.Print_temp(msg,NL=True)
                                        return
                                    #print fullfilepath
                                    crc = self.send_object(fullfilepath, f, rate_limiter,session_num=session_start)
                                    if crc != -1:
                                        """
                                    if (self.sendObject(fullfilepath, f, rate_limiter, session_num=session_start,crc=int(self.DRef.dict[f].get(ATTR_CRC))) != -1):
                                        # add the last sent file time to the manifest file 
                                        self.DRef.dict[f].set(ATTR_LASTSEND, str(time.time()))
                                        #set the number of times this file has been sent
                                        self.DRef.dict[f].set(ATTR_NBSEND, str(int(self.DRef.dict[f].get(ATTR_NBSEND)) + 1))
                                        """
                                        # add the last sent file time to the
                                        # manifest file
                                        self.DRef.dict[f].set(ATTR_LASTSEND, str(time.time()))
                                        #set the number of times this file has been
                                        #sent
                                        self.DRef.dict[f].set(ATTR_NBSEND, str(int(self.DRef.dict[f].get(ATTR_NBSEND)) + 1))
                                        self.DRef.dict[f].set(ATTR_CRC, str(crc))
                                    
                                        self.FilesSent+=1
                                    else:
                                        return        
                                except Exception as e:
                                    print (e)
                                    raise
                            else:
                                msg = u"File check failed - out"
                                debug_print(msg)
                                AROWLogger.error(msg)
                            # must reset reference data ?
                            # files not sent will be retransmitted later
                            
                        # end of integrity check
                    except Exception as e:#maybe the file doesn't exist
                            pass
            # List empty : nothing to transmit
                else:
                    # no files to send, can exit loop 2
                    LastFileSendMax = True
                    #if not self.isAllFilesSent:
                    #self.LoopCount+=1
                    self.isAllFilesSent = True
                    self.FilesToSend.clear()    
            else:
                #forced break, just set everything to done and leave
                LastFileSendMax = True
                self.isAllFilesSent = True
                continue
                
    def write_backup_file(self):
        if MODE_VERBOSE:
            msg = u"%s - Writing Backup recovery file... %s \n" % (mtime2str(time.time()),self.XFLFileName)
            print(msg,)
            #Console.Print_temp(msg,NL=True)
            AROWLogger.info(msg)
        #Console.Print_temp("%s - Backup recovery file \n"
        #%mtime2str(time.time()))
        self.DRef.et.set(xfl.ATTR_TIME, str(time.time()))
        if self.XFLFileName == "AROWsynchro.xml" :
            if os.path.isfile(self.XFLFileName):
                try:
                    os.rename(self.XFLFileName,XFLFileBak)
                except:#windows
                    os.remove(XFLFileBak)
                    os.rename(self.XFLFileName,XFLFileBak)
        try:
            if not(os.path.isdir(os.path.split(self.XFLFileName)[0])):
                os.makedirs(os.path.split(self.XFLFileName)[0])
            self.DRef.write_file(self.XFLFileName)
        except Exception as e:
            pass
    def wait_in_loop(self,session_start):
        waiting = options.pause # wait from end of last scan
        if waiting > 0:
            NextScanTime = int(time.time() + waiting)
            #NextScanTime = time.time() + waiting
            self.send_scan_end_message(self.FilesSent,NextScanTime,session_start)
            msg = "%d File(s) sent %s Next scan in %d seconds at %s " % (self.FilesSent,mtime2str(time.time()),waiting,timepart2str(NextScanTime))
            print(msg,)
            #Console.Print_temp(msg, NL=True)
            AROWLogger.info(msg)
            gc.collect()
            #print("self.DRef.dict[f].get(ATTR_LASTVIEW)%s - Waiting %d secs
            #before new scan" %(mtime2str(time.time()),waiting))
            timeoutEvent.wait(waiting)# delay can be interrupted for resetting or shutdown to exit thread
            if options.pause > waiting:# pause may have been changed while waiting and could be longer
                waiting = options.pause - File_send.loopsend.total_time()
                print("%s - Waiting %d secs before new scan" % (mtime2str(time.time()),waiting),)
                #Console.Print_temp("%s - Waiting %d secs before new scan" % (mtime2str(time.time()),waiting),NL=True)
                timeoutEvent.wait(waiting)    

    def send_object(self,send_file, dest_file, rate_limit=None, session_num=None,
        session_num_frames=None):
        """To enqueue send a file framed in UDP/TCP BFTP.

        send_file : local filename for the source (local disk)
        dest_file   : path relative to file in the destination directory
        rate_limit : to limit the link rate
        session_num    : session number
        session_num_frames : frame counter
        """
        if prQueue.qsize() == 0:
            self.ObjectCount = 0
        self.send_file_name = send_file
        offset = 0
        #dest_file_len=len(dest_file)

        #msg = "Sending file %s..." % self.send_file
        #Console.Print_temp(msg,NL=True)
        #AROWLogger.info(msg)
        if session_num == None:
            session_num = int(time.time())
        
        
        session_num_frames = 0
        #if sys.platform == 'win32':
            # correct accented characters under Windows
      #      file_name_dest = (dest_file.encode('utf_8','strict'))
        #else:
            # otherwise carry on
        #file_name_dest = str(dest_file)
        file_name_dest = dest_file.encode('utf-8')
        name_length = len(file_name_dest)
               
        if MODE_DEBUG:
            debug_print(u"session number         = %d" % session_num)
            debug_print(u"session frame number  = %d" % session_num_frames)
            debug_print(u"file destination = %s" % dest_file)
            debug_print(u"name_length = %d" % name_length)
        if name_length > MAX_FILE_LENGTH:
            raise ValueError
        if os.path.isfile(self.send_file_name):
        #if self.send_file.isfile():
            file_size = os.path.getsize(self.send_file_name)
            #file_size = self.send_file_name.getsize()
            file_date = os.path.getmtime(self.send_file_name)
            debug_print(u"file_size = %d" % file_size)
            debug_print(u"file_date = %s" % mtime2str(file_date))
            """
            # calculate  CRC32 before sending file
            if crc==None:
                crc32=CRC32.CalcCRC(self.send_file,File_sendStop)
            else:
                crc32=crc
            """
            #calculate crc while file is being sent
            crc32 = 0
        debug_print(u"crc = 0x%x" % crc32)
        # size remaining for data in a normal frame
        max_data_size = FRAME_SIZE - HEADER_SIZE - name_length
        #align to 4 byte boundary - not necessary with AROW from Feb 2013
        pad_size = max_data_size % 4# add extra bytes
        #pad_size=4-max_data_size%4# add extra bytes
        if pad_size == 4:
            pad_size = 0
    
        max_data_size = max_data_size - pad_size            
        debug_print(u"max_data_size = %d" % max_data_size)
        nb_frames = int((file_size + max_data_size - 1) / max_data_size)
        if nb_frames == 0:
            # if the file is empty, still necessary to send a packet
            nb_frames = 1
        debug_print(u"number of frames = %d" % nb_frames)
        still_to_send = file_size
        try:
            f = open(self.send_file_name, 'rb')
            if rate_limit == None:
                # if no rate limit specified, use default:
                rate_limit = RateLimiter(self.options.flowrate)
            rate_limit.start_time()#reset time and octets sent
            for frame_num in range(0, nb_frames):
                # inject a pause to limit the flow rate
                rate_limit.flow_rate_limiter()
                if LEGACY_PAD == True:
                    if still_to_send > max_data_size:
                        data_size = max_data_size
                    else:
                        data_size = still_to_send
                        pad_size = 4 - (data_size + name_length) % 4
                        #pad_size=(data_size+name_length)%4
                        if pad_size == 4:
                            pad_size = 0
                    if pad_size == 1:
                        padding = " "
                    elif pad_size == 2:
                        padding = "  "
                    elif pad_size == 3:
                        padding = "   "
                    elif pad_size == 0:
                        padding = "" 
                else:
                    if still_to_send > max_data_size:
                        data_size = max_data_size
                    else:
                        data_size = still_to_send
                    pad_size = 0
                    padding = ""
                padding=padding.encode('utf-8')
                still_to_send -= data_size
                offset = f.tell()
                """
                # calculate  CRC32 before sending file
                data = f.read(data_size)
                frame_length=name_length+len(data)+len(padding)
                """
                #calculate crc while file is being sent
                dataBuf = bytearray(data_size)
                dataRead = f.readinto(dataBuf)
                crc32 = binascii.crc32(dataBuf, crc32)
                frame_length = name_length + dataRead + len(padding)
                try:
                    # start with packet header:
                    header = struct.pack(HEADER_FORMAT,
                        MARKER1, #byte
                        MARKER2, #byte
                        MARKER3, #byte
                        pad_size,# byte
                        frame_length, #unsigned int
                        data_size, # unsigned int
                        session_num, #unsigned int
                        offset,#unsigned long long
                        session_num_frames,#unsigned int
                        frame_num,#unsigned int
                        nb_frames,#unsigned int
                        file_date,#unsigned int
                        file_size,#unsigned long long
                        crc32,#uint
                        FILE_PACKET,#unsigned short
                        name_length)#unsigned short
                except Exception as e:
                    print(e)
                #calculate crc while file is being sent
                try:
                    #frame = str(header.hex()) + file_name_dest + str(dataBuf[:dataRead]) + padding
                    #print("Filename bytes "+str(file_name_dest))
                    # convert all to bytearray
                    #frame =header+file_name_dest.encode('utf-8')+dataBuf[:dataRead] + padding.encode('utf-8')
                    frame = header + file_name_dest + dataBuf[:dataRead] + padding
                except Exception as e:
                    print(e)
                    """
                # calculate  CRC32 before sending file
                frame = header + file_name_dest + data+padding
                """
                #print( "frame crc "+str(crc32))
                #print( "frame count "+str(self.ObjectCount))
                try:
                    self.ObjectCount+=1
                    prQueue.put(((PRIORITY_TWO,self.ObjectCount),frame),True)# ordered by priority, then object number so packets stay in sequence, blocks until free slot
                    sendEvent.set()
                    if File_sendStop.is_set():
                        return -1
                    
                except Exception as e:
                    print (e)
                session_num_frames += 1
                rate_limit.inc_data_count(len(frame))
                #debugprint("average flow = %d" % rate_limit.flow_rate())
                percentage = 100 * (frame_num + 1) / nb_frames
                # display percentage: comma suppresses carriage return
                if not percentage % 10:
                    #Console.Print_temp((u"%d%%\r" % percentage),NL=False)
                    print (u"%d%%\r" % percentage)
                # force display update
                #sys.stdout.flush()
            if MODE_DEBUG:
                print(u"transfer in %.4f seconds - flow rate %d Kbps" % (rate_limit.total_time(), rate_limit.flow_rate() * 8 / 1000))
                #Console.Print_temp(u"transfer in %.4f seconds - flow rate %d Kbps" % (rate_limit.total_time(), rate_limit.flow_rate() * 8 / 1000))
            #calculate crc while file is being sent - update the reference tree
            
            #self.DRef.dict[os.path.join(*(dest_file.split(os.path.sep)[2:]))].set(ATTR_CRC,
            #str(crc32))
            #self.DRef.dict[dest_file].set(ATTR_CRC, str(crc32))
            #stats.add_rate(rate_limit.flow_rate()*8/1000)
            isTxing = False
        except IOError as e:
            msg = u"Opening file %s... %s" % (self.send_file_name,e.errno)
            print(u"Error : " + msg)
            AROWLogger.error(msg)
            session_num_frames = -1
            isTxing = False
        #print( "final crc "+str(crc32))
        return crc32
        #return session_num_frames

    def send_delete_file_message(self,delfile):
        """ Send a message to delete the high-side file
        """
        # must add Dref elements (size/date) to ensure receive order ?
        debug_print(u"Sending DeleteFileMessage...")
        if sys.platform == 'win32':
            # under Windows correct accent-containing files
            file_name = delfile.encode('utf_8','strict')
        else:
            # otherwise seems ok
            file_name = str(delfile)
        size = len(file_name)
        if LEGACY_PAD == True:
            # pad for 4 byte alignment.  NB this is for legacy AROW, not needed
            # for revisions from Feb2013
            pad_size = 4 - (size) % 4
             
            if pad_size == 4:
                pad_size = 0
            if pad_size == 1:
                padding = " "
            elif pad_size == 2:
                padding = "  "
            elif pad_size == 3:
                padding = "   "
            elif pad_size == 0:
                padding = "" 
        else:
            pad_size = 0
            padding = ""
        padding=padding.encode('utf-8')
        # start packing the header:
        header = struct.pack(HEADER_FORMAT,
            MARKER1,
            MARKER2,
            MARKER3,
            pad_size,
            size + pad_size,
            0,
            0,
            0,
            1,
            1,
            0,
            0,
            size,
            0,
            DELETEFile_PACKET,
            len(file_name))
        try:
            frame = header + file_name+padding
        except Exception as e:
            print(e)
            
        if MODE_DEBUG:
            msg = (u"deleting ", file_name)
            print(msg)
            #Console.Print_temp(msg,NL=False)
        try:
            prQueue.put(((PRIORITY_THREE,1),frame),False)
            sendEvent.set()
        except Exception as e:
            print ("Delete error: "+e)

    def send_scan_end_message(self,FilesSent,NextScanTime,session_num):
        message = u"ScanEnd "
        debug_print(u"sending ScanEnd...")
        frame_length = len(message)
        # start packing the header:
        try:
            header = struct.pack(HEADER_FORMAT,
                MARKER1,
                MARKER2,
                MARKER3,
                0,
                frame_length,
                0,
                session_num,
                options.depth,
                FilesSent,
                MinFileRedundancy,
                0,
                NextScanTime,
                0,
                0,
                SCANEND_PACKET,
                0)
        except Exception as e:
            print(e)
            return
        frame = header + message.encode('utf-8')  #
        #frame = str(header.hex()) + message #68 bytes
        #print ("Header: "+ str(len(str(header.hex()))))
    
        print ("Scan Message: "+ str(len(frame)))
        try:
            prQueue.put(((PRIORITY_FOUR,1),frame),False)#enqueue frame at low priority
        except Exception as e:
            print("Scan Message error: "+e)
        sendEvent.set()# signal transmission thread
    
    def send_info_message(self,infomsg,msgtype,ipno):
        #msgtypes indicate formatting - xml, mime etc, plus special case of
        #start(100) and close(101)
        #ipno is the source ip identifier as long
        if msgtype == None:
            msgtype = 0
        msg = infomsg[:16384] if len(infomsg) > 16384 else infomsg
        debug_print(u"sending Info msg...")
        frame_length = int(len(msg))
        v=int(ipaddress.IPv4Address("0."+ __version__))
        # start packing the header:
        try:
            header = struct.pack(HEADER_FORMAT,
                MARKER1,
                MARKER2,
                MARKER3,
                0,
                frame_length,
                v,
                msgtype,
                ipno,
                0,
                0,
                0,
                int(time.time()),
                0,
                0,
                INFO_PACKET,
                0)
        except Exception as e:
            print("SendInfoStruct :"+e)
            return
        frame = header + msg.encode('utf-8')
        #print len(frame)
        try:
            prQueue.put(((PRIORITY_FOUR,0),frame),False)#enqueue frame at low priority
            #prQueue.put((PRIORITY_FOUR,frame))#enqueue frame at low priority
        except Exception as e:
            print(e)
        sendEvent.set()# signal transmission thread
          # pad for 4 byte alignment.  NB this is for legacy AROW, not needed
                                 # for revisions from Feb2013

             
           
            
#------------------------------------------------------------------------------
# CalcCRC
#-------------------
#------------------------------------------------------------------------------
# SortDictBy
#-----------------
def sort_dict_by(nslist, key):
    """
    sort dictionary by a field
    """
    nslist = map(lambda x, key=key: (x[key], x), nslist)
    nslist.sort()
    return map(lambda key_x:key_x[1], nslist)
#    return map(lambda (key,x): x, nslist)
#---------------------------------------------------------------------------------------------------------------
class Stats:
    """class for calculating transfer stats"""
    def __init__(self):
        maxdeq = StatsServer.SECPERIODS
        self.statsqueue = deque(maxlen=maxdeq)
        self.outstatsminqueue = deque(maxlen=StatsServer.MINPERIODS)
        self.outstatshourqueue = deque(maxlen=StatsServer.HOURPERIODS)
        self.outCountMin = 0
        self.outCountHour = 0
        self.outRateHour = 0
        self.outRateMin = 0
        self.HTTPPort = options.port_Stats

    def add_rate(self,rate):
        self.statsqueue.appendleft(rate)
        self.outRateMin+=rate
        self.outCountMin+=1
        if self.outCountMin > 11:
            self.outstatsminqueue.appendleft(self.outRateMin / self.outCountMin)
            self.outRateHour += self.outRateMin / self.outCountMin
            self.outRateMin = self.outCountMin = 0
            self.outCountHour+=1
            if self.outCountHour > 59:
                self.outstatshourqueue.appendleft(self.outRateHour / self.outCountHour)
                self.outRateHour = 0
                self.outCountHour = 0
    def get_setup(self):
        return options
    def get_heartbeat(self):
        return HB_send
        
#------------------------------------------------------------------------------
# Analyse Config File
#---------------------
def analyse_conf(config):
    """analyse/initialise paramters
    (helper module ConfigParser)"""
    class initvalues:
        address = 0
        port_TCP = 0
        port_UDP = 0
        port_TCPStr = 0
        flowrate = 0
        pause = 0
        redundancy = 0
        loop = 0 
        debug = False
        sending_file = False
        synchro_tree = False
        synchro_tree_strict = False
        manifest = False
        temp_path = ""
        
        def __repr__(self):# override to allow printing of instance members
            return (u"Addr %s,Port %s,UDP %s, TCP %s,Flow %s,Pause %s,Redundancy %s,Loop %s,Recovery %s") % (self.address,self.port_TCP,self.port_UDP,self.port_TCPStr,self.flowrate,self.pause,self.redundancy, self.loop,self.manifest)
    init1 = initvalues()
    
    args = {}
    if not config.read(ConfigFile):
        AROWLogger.error(u" Unable to load intialisation file - Missing or Wrong Path?")
        return (None,None)
    config.sections()
    if config.has_option("AROWSend", 'Options'):
        try:
            init1.address = config.get('SendAddress','ip')
            init1.port_TCP = config.getint('SendAddress','port')
            init1.port_UDP = config.getint('SendAddress','UDPPort')
            init1.port_TCPStr = config.getint('SendAddress','TCPStrPort')
            init1.flowrate = config.getint('SendParams','flowrate')
            init1.pause = config.getint('SendParams','pause')
            init1.redundancy = config.getint('SendParams','redundancy')
            init1.loop = config.getboolean('SendModes','loop')
            init1.sending_file = config.getboolean('SendModes','single')
            init1.synchro_tree = config.getboolean('SendModes','synchro')
            init1.synchro_tree_strict = config.getboolean('SendModes','synchrostrict')
            init1.manifest = config.getboolean('SendModes','manifest')
            init1.temp_path = config.get('TemporaryPath','tmp_path')
            init1.depth = config.getint('ScanDepth','Depth')
            args[0] = config.get('SourcePath','folder')
            return init1,args
        except:
            AROWLogger.error(" Unknown parameters in initialisation file, using Command Arguments")
            return (None,None)
    else:
        AROWLogger.error(" Unable to read initialisation file - Empty?")
        return None,None
    


#------------------------------------------------------------------------------
# Save Config trace File
#---------------------
def save_conf_trace(options,args):
    """to backup current parameters"""
    cfgfile = open(ConfigFile,'w')
    config = SafeConfigParser() #must all be strings
    
    # add the settings to the structure of the file, and lets write it out...
    config.add_section('AROWSend')
    config.set('AROWSend','Options',"")
    config.add_section('SendAddress')
    config.set('SendAddress','IP',str(options.address))
    config.set('SendAddress','Port', str(options.port_TCP))
    config.set('SendAddress','UDPPort', str(options.port_UDP))
    config.set('SendAddress','TCPStrPort', str(options.port_TCPStr))
    config.set('SendAddress','MCGroup',str(options.MCGroup))
    config.set('SendAddress','MulticastStrPort', str(options.port_MCStr))
    config.set('SendAddress','MulticastTTL', str(options.MCTtl))
    config.add_section('SendParams')
    config.set('SendParams','FlowRate',str(options.flowrate))
    config.set('SendParams','Pause',str(options.pause))
    config.set('SendParams','Redundancy',str(options.redundancy))
    config.add_section('SendModes')
    config.set('SendModes','Loop',str(options.loop))
    config.set('SendModes','Single',str(options.sending_file))
    config.set('SendModes','Synchro',str(options.synchro_tree))
    config.set('SendModes','SynchroStrict',str(options.synchro_tree_strict))
    config.set('SendModes','Manifest',str(options.manifest))
    config.add_section('SourcePath')
    config.set('SourcePath','Folder',args[0])
    config.set('SourcePath','TmpPath',str(options.temp_path))
    config.set('SourcePath','Depth',str(options.depth))
    config.write(cfgfile)
    cfgfile.close()


#------------------------------------------------------------------------------
# analyse_options
#---------------------
def analyse_options():
    """analyse command line  options .
    (helper module optparse)"""
    global MinFileRedundancy
    #config = ConfigParser.RawConfigParser(allow_no_value=True)
    config = SafeConfigParser(allow_no_value=True)
        
    # create optparse.OptionParser object , giving as string
    # "usage" the docstring at the beginning of the file:
    parser = OptionParser_doc(usage="%prog [options] <fi directory>")
    parser.doc = __doc__

    # adds possible options:
    parser.add_option("-a", dest="address", default="localhost", \
        help=u"Diode Low-side Address: IP address or machine name")
    parser.add_option("-b", "--loop", action="store_true", dest="loop",\
        default=True, help=u"Send files in a loop")
    parser.add_option("-c", "--manifest", action="store_true", dest="manifest",\
        default=False, help=u"Create manifest file")# send a manifest file
    parser.add_option("-C", "--Manifest", action="store_true", dest="manifest_start",\
        default=False, help=u"Create manifest file but send files on start ")# send a manifest file
    parser.add_option("-d", "--debug", action="store_true", dest="debug",\
        default=False, help=u"Debug Mode")
    parser.add_option("-e", "--send", action="store_true", dest="sending_file",\
        default=False, help=u"Send  file")
    parser.add_option("-g","--temp",dest="temp_path",\
        help= u"temporary folder path")    
    parser.add_option("-i","--ttl", dest="MCTtl",\
        help=u"Multicast TTL", type="int", default=1)
    parser.add_option("-j","--depth", dest="depth",\
        help=u"Depth of scan (range 1 to 5 )", type="int", default=2)
    parser.add_option("-l", dest="flowrate",\
        help=u"Rate limit (Kbps)", type="int", default=100000)
    parser.add_option("-m", dest="MCGroup", default="224.1.1.1", \
        help=u"Multicast Address Group to Join: IP address ")
    parser.add_option("-n", dest="port_MCStr",\
        help=u"Multicast Stream Port ", type="int", default=5001)
    parser.add_option("-o","--delay", dest="offline_delay",\
        help=u"Delay between deletion and transmission of deletion (seconds)", type="int", default=7 * 86400)
    parser.add_option("-p", dest="port_TCP",\
        help="Destination  Port ", type="int", default=9876)
    parser.add_option("-P", dest="pause",\
        help="Pause between 2 loops (in seconds)", type="int", default=300)
    parser.add_option("-R","--redundancy",dest="redundancy",default=1,type="int",\
        help=u"Redundancy,Set the number of times files are re-transmitted(1-10)")
    parser.add_option("-s", "--synchro", action="store_true", dest=u"synchro_tree",\
        default=False, help=u"Synchronise the tree")
    parser.add_option("-S", "--Synchro", action="store_true", dest=u"synchro_tree_strict",\
        default=False, help=u"Sync send and receive folders-auto file deletion")
    parser.add_option("-t", dest="port_TCPStr",\
        help=u"TCP Stream  Port ", type="int", default=10003)
    parser.add_option("-u","--udp", dest="port_UDP",\
        help=u"UDP Stream  Port ", type="int", default=8002)
    parser.add_option("-v", "--verbose", action="store_true", dest="verbose",\
        default=False, help="verbose mode")
    parser.add_option("-w", "--http",dest="port_Stats",\
        help=u"Stats Http  Port ", type="int", default=8081)
    # command line arguments override stored arguments from ini file
    if not sys.argv[1:]:
        (options,args) = analyse_conf(config)# use the ini file
        if not options :#no command line, no ini file
            print (u"Using defaults")
            (options,args) = parser.parse_args(sys.argv[1:])
            if not args:
                args = ['TestSend']
    else: # parse command line options:
        (options, args) = parser.parse_args(sys.argv[1:])
    # check that there is at least 1 action:
    nb_actions = 0
    if options.sending_file: nb_actions+=1
    if options.synchro_tree: nb_actions+=1
    if options.synchro_tree_strict:nb_actions+=1
    if nb_actions < 1:
        parser.error(u"You must specify at least one action. (%s -h for complete help)" % SCRIPT_NAME)
    if len(args) != 1:
        parser.error(u"You must specify exactly one file/directory. (%s -h for complete help)" % SCRIPT_NAME)
    if options.depth < 1 or options.depth > 5:
        #options.depth=parser.defaults['depth']
        parser.error(u"Depth option out of range(1-5) )")
    if options.redundancy < 1 or options.redundancy > 10:
        #options.depth=parser.defaults['redundancy']
        parser.error(u"Redundancy option out of range (1-10)  )")
        
    MinFileRedundancy = options.redundancy#DRef.read_disk(target, working.AffChar)
    save_conf_trace(options,args) # save the current setup to an ini file
    return (options, args)


def cleanup():
        save_conf_trace(options,args)
        
        _remove_tmp_files()
        msg = AROW_APP + u" Finished"
        AROWLogger.info(msg)
        print(msg,)
        #Console.Print_temp(msg, NL=True)
        input(u"Press return to end...")
        try:
            sys.stdin.close()
        except:
            pass
        raise SystemExit(0)
    
def _remove_tmp_files():
    for tmpfile in path(tempfile.tempdir).files():
        if tmpfile.find("BFTP_") != -1:
            try:
                os.remove(tmpfile)
            except:
                if MODE_VERBOSE:
                    print (u"Failed to remove old temp files from directory %s" % tempfile.tempdir)

def setup_logger():
    LOG_FILENAME = AROW_APP + '.log'
    logformat = '%(asctime)s %(levelname)-8s %(message)s'
    datefmt = '%d/%m/%Y %H:%M:%S'
    AROWLogger = logging.getLogger('AROWLog')# use this to propagate instances across submodule classes
    AROWLogger.setLevel(logging.DEBUG)
    rothandler = logging.handlers.RotatingFileHandler(LOG_FILENAME,mode='a',maxBytes=1E6,backupCount=3)
    rothandler.setLevel(logging.DEBUG)
    formatter = logging.Formatter(logformat,datefmt)
    rothandler.setFormatter(formatter)
    AROWLogger.addHandler(rothandler)
    return AROWLogger


#
#==============================================================================
# MAIN PROGRAM
#=====================
if __name__ == '__main__':
    
    def close_threads():
        HB_Stop.set()# stop heartbeat
        if MCStrInst != None:
            MCStrInst.shutdown()#shutdown the UDP handler
        if UDPStrInst != None:
            UDPStrInst.shutdown()#shutdown the UDP handler
        if TCPStrInst != None:
            TCPStrInst.shutdown()#shutdown the TCP handler
        if StatsServerInst != None:
            StatsServerInst.shutdown() #shutdown the stats
    
    def close_early():
        close_threads()
        SendSock.close()#close the socket
        cleanup()
        
        
    hostname = socket.gethostname()
    msg = u"  <AROWSend>  Copyright (C) 2019  Somerdata Ltd \n \
     This program comes with ABSOLUTELY NO WARRANTY;\n\
     This is free software, and you are welcome to redistribute it under certain conditions\n\
     See Licence distributed with this software"
    print( msg)
    #(hostname,alias,ipaddr)=socket.gethostbyname_ex(socket.getfqdn())
    os.stat_float_times(False)
    AROWLogger = setup_logger()
    
    AROWLogger.info(u"Starting " + AROW_APP + ": " + AROW_VER + " on " + hostname)
    print (AROW_APP + AROW_VER)
    (options, args) = analyse_options()
    target = os.path.basename(args[0])
    #target = path(args[0])
    HOST = options.address
    PORT = options.port_TCP
    MODE_DEBUG = options.debug
    MODE_VERBOSE = options.verbose
    AROWLogger.info(str(options))
    #print options
    print (u"Tree source: ",target)
    if options.temp_path == None:
        print (u'Temp Path: System')
    else:
        print (u'Temp Path:', options.temp_path)
    print (u"Data Port:" ,options.address, options.port_TCP)
    print (u'TCP Stream:' , options.port_TCPStr)
    print (u'UDP Stream:' ,options.port_UDP)
    print (u'Multicast receiving from:' ,u"Address:",options.MCGroup,u"Port:", options.port_MCStr,u"TTL:",options.MCTtl)
    print (u"Statistics port:", options.port_Stats)
    print (u"Options:" ,u"Strict sync:",options.synchro_tree_strict,u"Use recovery file:",options.manifest,u"Debug:",options.debug,u"Verbose:",options.verbose)
    print (u"Delay to notify deletions (seconds):",options.offline_delay)
    print (u"Scan depth:",options.depth)# the number of folder levels to scan
    print (u"Flow control (kbps):",options.flowrate)
    if options.temp_path:
        tempfile.tempdir = options.temp_path # set this to a fast diskstore location for speed
    else:
        tempfile.tempdir = tempfile.gettempdir()
    _remove_tmp_files()
                
    HB_send = HeartBeat()# establish hb before stats is running
    stats = Stats()
    statsserver = StatsServer(stats)
    try:
        StatsServerInst = statsserver.Th_setupStatsServer()
    except Exception as e:
        msg = u" Stats server not running %s port %s" % (e,options.port_Stats)
        AROWLogger.error(msg)
        #printLock.acquire()
        print(msg,)
        #Console.Print_temp(msg,NL=True)
        #printLock.release()
        cleanup()
    if test_connection() != -1:
        #AROW communication socket
        File_sendStop = threading.Event()
        File_sendStop.clear()
        SendSock = Th_SendSocket((HOST,PORT))
        isConnected,TxName = SendSock.get_tx_connect()# try to connect
        SendSock.th_send_container()# set up the sending loop
        AROWLogger.info(hostname + " I/F: " + TxName[0] + " Port: " + str(TxName[1]))
        ipno = int(struct.unpack("!L",socket.inet_aton(TxName[0]))[0])
                  
        # Send heartbeat messages
        HB_Stop = threading.Event()
        HB_send.th_send_loop_heartbeat(HB_Stop)
        # Streaming packet threads
        TCP_send = TCPStrmPkt(port=options.port_TCPStr)
        TCPStrInst = TCP_send.th_setup_tcp_srvr()
        UDP_send = UDPStrmPkt(port=options.port_UDP)
        UDPStrInst = UDP_send.th_setup_udp_srvr()
        MC_send = MCStrmPkt(port=options.port_MCStr,group=options.MCGroup,ttl=options.MCTtl)
        MCStrInst = MC_send.th_setup_mc_srvr()
        shutdely = 10        
        if options.sending_file:
            File_send1 = SendOneFile(target,target,options)
            File_send1.name = "OneFilesend"
            File_send1.start()
            File_send1.join()
            close_threads()
            File_send1.send_info_message(hostname, 101, ipno)# tell the receiver
            msg = u"AROWSend closing now , sending closedown message...." 
            print(msg,)
            #Console.Print_temp(msg,NL=True)
            AROWLogger.info(msg)
            SendSock.close()#close the socket
            cleanup()
            
        elif (options.synchro_tree_strict or options.synchro_tree):
        # Delay before considering an offline file as deleted
            if options.synchro_tree_strict:
                OffLineDelay = 1 # hi side files will be deleted immediately if lo side files deleted
            if options.synchro_tree:
                OffLineDelay = options.offline_delay
            working = DispProgress.DisplayType()#setup the progress characters
            working.StartIte()
            # Tree Reference file synchronise
            msg = u"Reading/constructing initial directory tree... %s" % mtime2str(time.time())
            print(msg, )
            #Console.Print_temp(msg, NL=True)
            AROWLogger.info(msg)
            #we set up to compare the scanned files o against either the
            #recovery file or the disk contents.
            #on start up, there may be no recovery file so the disk needs to be
            #scanned and a'fake' file created.
            TempFile_id = False
            syncpath = os.path.join(target,"arowsync")
            XFLFile = os.path.join(syncpath,"AROWsynchro.xml")
            XFLFileBak = "AROWsynchro.bak"
            # the manifest_start option requires the tempfile and the manifest file to be created. 
            if options.manifest or options.manifest_start:
                try:
                    os.makedirs(syncpath)
                except OSError as e:
                    if e.errno != errno.EEXIST:
                        raise
            else:
                try: # if a manifest option had been chosen previously, remove the directory and its contents to prevent stale manifest
                     shutil.rmtree(syncpath)
                except Exception as e:
                     pass
            try:
                    TempFile_id,TempFile = tempfile.mkstemp(prefix='BFTP_',suffix='.xml')
            except Exception as e:
                    msg = u"No temp path? %s %s " % (e,options.temp_path)
                    print(msg,)
                    #Console.Print_temp(msg,NL=True)
                    AROWLogger.error(msg) 
                    close_early()
    
            DRef = xfl.DirTree(u"",File_sendStop)
            if (TempFile_id):#using the temp file location,create an initial reference tree for comparison
                debug_print(u"Session temp recovery file : %s" % TempFile)
                try:
                    #DRef.read_disk(target, working.AffChar)
                    dirlist = DRef.dir_walk(target,followlinks=True,depth=options.depth)
                except Exception as e:
                    print(u"Unable to read directory tree ",e)
                    close_early()
                #if options.manifest_start:# the first time just scan the directory(s) but set up the manifest file for later
                    #XFLFile = os.path.join(syncpath,"AROWsynchro.xml")
                    #XFLFileBak = "AROWsynchro.bak"
            else:# use the recovery file
                debug_print(u"Reading/creating recovery file : %s" % XFLFile)
                try:
                    dirlist = DRef.read_recovery_file(XFLFile)# try and read from the file
                except Exception as e: # file recovery failed, go to default
                    try:
                        dirlist = DRef.dir_walk(target,followlinks=True,depth=options.depth)
                    except Exception as e:
                        print(str(e),)
                        #Console.Print_temp(str(e), NL=True)
                        AROWLogger.error(str(e))
                    
            if options.loop:
                try:
                    timeoutEvent = threading.Event()
                    # setup to compare the read file with the scanned
                    # information
                    File_send = SendFiles(dirlist,target,options,DRef,XFLFile,File_sendStop,timeoutEvent,TempFile)
                    #File_send=SendFiles(target,options,DRef,XFLFile,File_sendStop,timeoutEvent)
                    File_send.send_info_message(hostname, 100, ipno)  
                    File_send.name = "Filesend"
                    File_send.start()
                    
                except Exception as e:
                    msg = u"Error: sending tree failed."
                    print(msg,)
                    #Console.Print_temp(msg, NL=True)
                    traceback.print_exc()
                    AROWLogger.error(msg)
                #testloop=0
                
                while True:
                    try:
                        time.sleep(1) #just check the keyboard every 1sec
                        #testloop+=1
                        if File_sendStop.isSet():
                        #if testloop >10:
                            raise KeyboardInterrupt
                    except KeyboardInterrupt:# user request shutdown
                        close_threads()
                        File_send.send_info_message(hostname, 101, ipno)# tell the receiver
                        msg = u"AROWSend closing in %d secs, sending closedown message...." % shutdely
                        print(msg,)
                        #Console.Print_temp(msg,NL=True)
                        AROWLogger.info(msg)
                        File_sendStop.set()#stop sending threads
                        timeoutEvent.set()# break the send loop
                        time.sleep(shutdely)
                        SendSock.close()#close the socket
                        break
            else:
                try:
                    File_send = SendFiles(target)
                    File_send.start()
                    
                except:
                    msg = u"Error: sending tree failed."
                    print(msg,)
                    #Console.Print_temp(msg,NL=True)
                    traceback.print_exc()
                    AROWLogger.error(msg)
            if (TempFile_id):
                debug_print(u"Removing temp backup file : %s" % XFLFile)
                os.close(TempFile_id)
                cleanup()
            
    else:
        msg = u"Error: No Socket Connection"# fatal so exit
        print(msg,)
        #Console.Print_temp(msg,NL=True)
        cleanup()
