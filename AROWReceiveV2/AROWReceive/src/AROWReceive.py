#!/usr/local/bin/python
"""
----------------------------------------------------------------------------
AROWReceive v 2.0.0 - Unidirectional File Transfer Protocol
January 2019
----------------------------------------------------------------------------

For receiving files, data streams, directory trees across a unidirectional link
network diode using  TCP.
Parts Copyright Somerdata Ltd
usage: see AROWReceive.py -h
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
# V2.0.0 refactored for Python 3 , removed console printing as Python 3 has unicode
#v1.3.1  - added multicast server and processing
#V1.3.0 release
#V1.3.0 beta refactoring and compatibility changes with AROWSend V1.3.0 this version
#does not support level-based recovery files
#V1.2.1 major reorganisation moved code to modules
#V1.1.2 Mar 2015 - changed receive code to limit system memory usage and recover
# from overruns, add option to override deletion requests, fixed bug at low data rates
# and with multiple different file sizes ( moved frame length determination)
#V1.1.1 corrected startup so cmd line overrides ini file, speed improvements to decode
#V1.1.0 added simple http server for display of statistics
#V1.0.3 added ini config file
# clean up thread exit
# hold terminal window open until user input
#24/09/2012            -    Release V1.0.1
#28/08/2012            -    Somerdata Release V1.0.0
# 3/09/2012            - Correction to delete file code
# 20/09/2012        -changed recv to thread, added blocking to decode thread,
# corrected high cpu use from heartbeat thread 
#------------------------------------------------------------------------------
type="3201"
__version__="2.0.0"
#=== IMPORTS ==================================================================
def show_exception_and_exit(exc_type, exc_value, tb):
    import traceback
    traceback.print_exception(exc_type, exc_value, tb)
    input("Press key to exit.")
    sys.exit(-1)
#standard python modules
import sys, socket, struct, time,  os.path, tempfile, traceback
sys.excepthook = show_exception_and_exit
import threading
from collections import  deque
import socketserver
from configparser import SafeConfigParser

# internal modules
import TabBits
import  xfl
import logging,logging.handlers
import time

#from AROWSocket.BFTPDecode import Decode
#from BFTPSocket import BFTPSocket#python
#from AROWSocket.BFTPSocket import BFTPSocket#cython
from statsserver import StatsServer #for browser display of stats
from OptionParser_doc import OptionParser_doc

# Dedicated Windows modules
if sys.platform == 'win32':
    try:
        import win32api, win32process, winsound
        
        from BFTPSocket import BFTPSocket#python
    except Exception as e:
       print(e)
        #raise SystemExit( "the pywin32 module is not installed: " +"see http://sourceforge.net/projects/pywin32")

else:
    #from BFTPSocket import BFTPSocket#python
    
    try:
        from AROWSocket.BFTPSocket import BFTPSocket#cython
    except Exception as e:
        
        msg= "BFTPSocket library missing or incorrect, run 'setup.py build_ext --inplace' from the AROWSocket folder"
        print (msg)
        input (" Press any key to acknowledge...")
        #raise SystemExit("AROWReceive ended with error")
        
from AROWSocket.BFTPDecode import Decode

try:
    from path import path
except:
    raise SystemExit("the path module is not installed:"\
        +" see http://www.jorendorff.com/articles/python/path/"\
        +" or http://pypi.python.org/pypi/path.py/ (if first URL is down)")

# plx - portability layer extension TODO: remove this as Unicode is now included
try:
    from plx import str_lat1, print_console
except:
    raise SystemExit('the plx module is not installed:'\
        +' see http://www.decalage.info/en/python/plx')

try:#use the c version if possible
    import xml.etree.cElementTree as ET
except ImportError:
   
    import xml.etree.ElementTree as ET
   

#=== CONSTANTS ===============================================================
AROW_APP = 'AROWReceive'
AROW_VER = ':V2.0.0'

SCRIPT_NAME = os.path.basename(__file__)    # script filename
ConfigFile = 'AROWRecv.ini'
#RunningFile = 'AROW_run.ini'
MODE_DEBUG = True   # check if debug() messages are displayed
TEMP_ROOT = "temp"    # Tempfile root
HB_DELAY = 5 # Default time between two Heartbeats (secs)
# This is the limit on receive when data will not be entered into the queue any more.
#Raising the limit can lead to high de-queuing times
#lowering leads to data corruption if data arrives faster than can be processed
MAX_QUEUE_LEN =60000 #(tuples)#250000000  
# in mode strict synchro retention duration

IgnoreExtensions = ('.part', '.tmp', '.ut', '.dlm') #  Extensions of temp files which are never sent (temp files)
#HEADER_SIZE=BFTPSocket.HEADER_SIZE
# Types of packets:
# Manifest of XFL attributes
ATTR_CRC = "crc"                         # File CRC
ATTR_NBSEND = "NbSend"                    # Number  sent
ATTR_LASTVIEW = "LastView"                # Last View Date
ATTR_LASTSEND = "LastSend"                # Last Send Date



#=== GLOBAL VARIABLES =======================================================
#TODO: get rid of these
global RxSock
RxSock=None
decodeEvent=threading.Event()
# for stats measurement:
stats = None
#RxQueue=Queue()
RxQueue=deque(maxlen=MAX_QUEUE_LEN)#the double ended queue used as a fifo to decouple tcp reception from data processing

#for installer
def resource_path(relative_path):
    """Get absolute path to resource, for PyInstaller """
    try:
        #PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path=sys._MEIPASS
    except:
        basepath =os.path.abspath(".")
    return os.path.join(base_path,relative_path)

#------------------------------------------------------------------------------
# str_adjust : Adjust string to a dedicated length adding space or cutting string
#-------------------
def str_adjust (string, length=79):
    """adjust the string to obtain exactly the length indicated
    by truncating or filling with spaces."""
    l = len(string)
    if l>length:
        return string[0:length]
    else:
        return string + " "*(length-l)
#------------------------------------------------------------------------------
# DEBUG : Display debug messages if MODE_DEBUG is True
#-------------------

def debug(text):
    "to post a message if MODE_DEBUG = True"

    if MODE_DEBUG:
        print_console ("DEBUG:" + text)
#--------------------------------------------------------------------------------------------------------        
def test_connection():
    """ Used to test connection on startup or restart.Returns -1 if no socket available"""
    s=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    try:
        print(u" Checking %s Port %d " %(HOST,PORT))
        #s.setsockopt(socket.SOL_TCP, socket.TCP_NODELAY, 0)
        s.settimeout(1)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR,1)
        #s.settimeout(1)
        s.connect((HOST,PORT))
        s.settimeout(None)
        s.shutdown(1)
        s.close()
        del s
        time.sleep(0.1)# wait a bit so server can respond
    except Exception as e:
        if s:
            s.close()
        print ("No Connection %s" %(e))
        AROWLogger.info("No Connection " +str(e)+ " "+str(HOST))
        return(-1)    
#..............................................................................................

class Th_TCPStreamPktSend(object):
    """Threaded Class to send TCP packets to another client"""
    def __init__(self,TCPport,name,TCPAddr):
        super(Th_TCPStreamPktSend,self).__init__()
        self.sp_TCPport=TCPport
        self.sp_TCPAddr=TCPAddr
        #self.sp_TCPAddr='localhost'
        self.name=name
        self.isTCPStreamSockConnected=False
        self.TCPOutQueue=deque()# a deque for streaming tcp data out
    
    class ThSocketServer(socketserver.ThreadingMixIn,socketserver.TCPServer):
        daemon_threads =True
        allow_reuse_address = True
        #pass
        
    class ThRequestHandler(socketserver.BaseRequestHandler):
        def handle(self):
            #global isTCPStreamSockConnected
            self.server.isTCPStreamSockConnected = True
            if MODE_VERBOSE:
                print("TCP Stream Connected",)
                #Console.Print_temp("TCP Stream Connected", NL=True)
            try:
                count=0
                self.server.TCPOutQueue.clear()
                while True:
                    if len(self.server.TCPOutQueue)>0:
                        #print ('TXLen',str(len(self.server.TCPOutQueue)))
                        if count==0:#TODO: this needs an event to wait on
                            debug_print(u"TCP "+ str(len(self.server.TCPOutQueue)))
                           #Console.Print_temp("TCP "+ str(len(self.server.TCPOutQueue)),NL =False)
                            while len(self.server.TCPOutQueue)>0:
                                self.request.send(self.server.TCPOutQueue.popleft())
                                #count+=1
                    else :
                        time.sleep(0.1)#meander around waiting for a tcp packet
                        count=0#break    
            except Exception as e:
                self.request.close()
                #print (e)
                print (u"TCP Client closed connection ",e)
                self.server.isTCPStreamSockConnected = False# signal decode not to bother sending packets
                  
    
    
    def th_setup_srvr_skt(self, TCP_Run):
        address=(self.sp_TCPAddr,self.sp_TCPport)
        try:
            server=self.ThSocketServer(address,self.ThRequestHandler)
            #server.allow_reuse_address = True
            ip,port=server.server_address
            server.isTCPStreamSockConnected=self.isTCPStreamSockConnected
            server.TCPOutQueue=self.TCPOutQueue
            print (u"TCP Serving on: " + str(ip)+ ":"+ str(port))
            self.name=threading.Thread(None,target=server.serve_forever)
            self.name.name="TCPStream"
            #self.name=threading.Thread(name="TCPStream",target=server.serve_forever)
            self.name.setDaemon(True)
            self.name.start()
            TCP_Run.set()
            return server
            
        except Exception as e:
            print (u'Streaming Server..', e)
            TCP_Run.clear()
            return None
            #isTCPStreamSockConnected = False 
    
    class TH_TCPStreamClient(threading.Thread):
        def __init__(self,address,qu):
            #super(TH_TCPStreamClient,self).__init__(self)
            threading.Thread.__init__(self)
            self.address=address
            self.TCPOutQueue=qu
            TCP_Run.set()
            
            pass
            #super(TH_TCPStreamClient,self).__init__()
            
        
        def th_setup_tcp_client(self,TCP_Run):
            address=self.address
            print ("TCP  on Addr:", address)
            self.TCPOutQueue.clear()
            return socket.socket(socket.AF_INET,socket.SOCK_STREAM)
            #try:
                #self.reconnect(address)
                #self.tcpclient=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
                #self.tcpclient.connect(address)
                
               # self.isTCPStreamSockConnected= True
                #TCP_Run.set()
                #return self.tcpclient
            #except Exception as e:
                #print ('TCP Client..', e)
                #TCP_Run.clear()
                #return None
                #self.isTCPStreamSockConnected = False
                
        def reconnect(self,address):
            while TCP_Run.is_set():
                try:
                    self.tcpclient=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
                    self.tcpclient.connect(address)
                    
                    self.isTCPStreamSockConnected= True
                    if MODE_VERBOSE:
                        print("server connected")
                    
                    #TCP_Run.set()
                    return self.tcpclient
                except socket.error:
                    self.isTCPStreamSockConnected= False
                    time.sleep(1)
                    
        
    
        def run(self):
        #def Th_TCPClientSend(self):
            #count=0
            #pktlen=0
            packet=""
            self.reconnect(self.address)
            while TCP_Run.is_set():
                if len(self.TCPOutQueue)>0:
                    #print ('TXLen',str(len(self.TCPOutQueue)))
                    #if count==0:
                    while len(self.TCPOutQueue)>0:
                        #print "TCPcount",len (TCPOutQueue)
                        try:
                            packet=self.TCPOutQueue.popleft()
                            sent=self.tcpclient.send(packet)
                            print (sent)
                            
                        except Exception as e:
                            print (e)
                            #probably server has stopped so 
                            self.reconnect(self.address)    
                    
                else :
                    time.sleep(0.1)#TODO: this needs an event to wait on
                    #count=0#break   def ClientConnect(self):
                pass
    

#-----------------------------------------------------------------------------------------------
class Th_UDPStreamPktSend:
    """Threaded Class to send UDP packets to another user, includes methods for server(not implemented) and client"""
    def __init__(self,UDPport,name):
        self.sp_UDPport=UDPport
        self.name=name
        self.udpclient=socket.socket()
        self.isUDPStreamSockConnected=False
        self.UDPOutQueue=deque()# a deque for streaming udp data out

    """
    class ThSocketServer(socketserver.ThreadingMixIn,socketserver.UDPServer):
        daemon_threads = True
        allow_reuse_address = True
        #pass
       
    def Th_setupSrvrSkt(self):
        #global isUDPStreamSockConnected
        address=('localhost',self.sp_UDPport)
        
        try:
            udpserver=self.ThSocketServer(address,self.ThUDPRequestHandler)
            #udpserver.allow_reuse_address = True
            ip,port=udpserver.server_address
            print "UDP Serving on: "+str(ip)+":" +str(port)
            udpserver.isUDPStreamSockConnected=self.isUDPStreamSockConnected
            udpserver.UDPOutQueue=self.UDPOutQueue
            
            self.name=threading.Thread(target=udpserver.serve_forever)
            self.name.setDaemon(True)
            self.name.start()
            UDP_Run.set()
              
        except Exception,e:
            print 'Streaming Server..', e
            UDP_Run.reset()
            
        
    class ThUDPRequestHandler(socketserver.BaseRequestHandler):
        def handle(self):
            #global isUDPStreamSockConnected
            self.udpserver.isUDPStreamSockConnected = True
            data=self.request[0].strip()
            socket=self.request[1]
            try:
                count=0
                #UDPOutQueue.clear()
                while True:
                    if UDPOutQueue>0:
                        #print 'TXLen',str(len(UDPOutQueue))
                        if count==0:
                            print " UDPcount",str(len(self.udpserver.UDPOutQueue))
                            while len(self.udpserver.UDPOutQueue)>0:
                                socket.sendto(self.udpserver.UDPOutQueue.popleft(),self.client_address)
                                #count+=1
                    else :
                        time.sleep(0.1)
                        count=0#break    
            except Exception ,e:
                self.request.close()
                #print e
                print "client closed connection "
                self.udpserver.isUDPStreamSockConnected = False
    """
    # non-serving version               
    def th_setup_udp_client(self,UDP_Run):
        print ("UDP  on port:", str(self.sp_UDPport))
        self.UDPOutQueue.clear()
        try:
            self.udpclient=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
            self.isUDPStreamSockConnected= True
            UDP_Run.set()
            return self.udpclient
        except Exception as e:
            print ('UDP Client..', e)
            UDP_Run.reset()
            return None
            self.isUDPStreamSockConnected = False
            
    def th_udp_client_send(self):
        #count=0
        #pktlen=0
        packet=""
        address=('localhost',self.sp_UDPport)
        while UDP_Run.is_set():
        #while 1:
            if len(self.UDPOutQueue)>0:
                debug_print ('TXLen',str(len(self.UDPOutQueue)))
                #if count==0:
                while len(self.UDPOutQueue)>0:
                    #print "UDPcount",len (UDPOutQueue)
                    try:
                        packet=self.UDPOutQueue.popleft()
                        sent=self.udpclient.sendto(packet,address)
                        
                    except Exception as e:
                        print (e)    
                
            else :
                time.sleep(0.1)#TODO: this needs an event to wait on
                #count=0#break   
                 
class Th_MCStreamPktSend:
    """Threaded Class to send UDP packets to another user, includes methods for server(not implemented) and client"""
    def __init__(self,MCAddr,MCport,MCTtl,name):
        self.MCStrport=MCport
        self.name=name
        self.mcserver=socket.socket()
        self.isMCStreamSockConnected=False
        self.MCOutQueue=deque()# a deque for streaming multicast data out
        self.MCAddr=MCAddr
        self.MCTtl=MCTtl

    # non-serving version               
    def th_setup_mc_server(self,MC_Run):
        print ("Multicast  on port:", str(self.MCStrport))
        self.MCOutQueue.clear()
        try:
            self.mcserver=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
            ttl=struct.pack('b',self.MCTtl)
            self.mcserver.setsockopt(socket.IPPROTO_IP,socket.IP_MULTICAST_TTL,ttl)
            self.mcserver.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
            self.isMCStreamSockConnected= True
            MC_Run.set()
            return self.mcserver
        except Exception as e:
            print ('Multicast Server..', e)
            MC_Run.reset()
            return None
            self.isMCStreamSockConnected = False
            
    def th_mc_send(self):
        #count=0
        #pktlen=0
        packet=""
        address=(self.MCAddr,self.MCStrport)
        while MC_Run.is_set():
        #while 1:
            if len(self.MCOutQueue)>0:
                #print 'TXLen',str(len(self.UDPOutQueue))
                #if count==0:
                while len(self.MCOutQueue)>0:
                    #print "UDPcount",len (UDPOutQueue)
                    try:
                        packet=self.MCOutQueue.popleft()
                        sent=self.mcserver.sendto(packet,address)
                        
                    except Exception as e:
                        print (e)    
                
            else :
                time.sleep(0.1)#TODO: this needs an event to wait on
                #count=0#break   
              
    

#------------------------------------------------------------------------------
# HeartBeat - threaded class to detect heartbeat frames
#---------------
#--------------------------------------------------------------------------------------------------------------------------------
class HeartBeat:
    """ check HeartBeat BFTP packet

        A session is a heartbeat sequence.
        A heartbeat is a simple frame with a timestamp (Session Id + sequence
        number) to identify if the link (physical and logical) is up or down

        The session Id will identify a restart
        The sequence number will identify lost frame

        Because time synchronisation betwen transmission/receiver computer isn't guaranteed,
        timestamp can't be checked in absolute terms.
        """

    # TODO :
    # Add HB from receiver to emission in broadcast to detect bi-directional link

    def __init__(self):
        #Variables locales
        self.hb_pad_size=0
        self.hb_frame_length=0
        self.hb_data_size=0
        self.hb_sessionnum=0
        self.hb_offset=0
        self.hb_session_numframes=0
        self.hb_numframe=0
        self.hb_file_num_frames=1
        self.hb_delay=HB_DELAY
        self.hb_filesize=0
        self.hb_checksum=0
        #self.hb_packettype=Decode.HEARTBEAT_PACKET
        self.hb_filename_length=0
        self.hb_timeout=time.time()+1.25*(self.hb_delay) 
        self.hb_filedate = 0
        
    def newsession(self):
        """ initiate values for a new session """
        self.hb_sessionnum=int(time.time())
        self.hb_numframe=0
        return(self.hb_sessionnum, self.hb_numframe)

    def incsession(self):
        """ increment values in a existing session """
        self.hb_numframe+=1
        self.hb_timeout=time.time()+(self.hb_delay)
        return(self.hb_numframe, self.hb_timeout)

    def print_heartbeat(self,date):
                        
        """ Print internal values of heartbeat """            

        #print ("----- Current HeartBeart -----")
        #print ("Session ID      : %d " %self.hb_sessionnum)
        msg="Sender sequence and time     : %d: %s\r" %(self.hb_numframe, todaytime2str(date))
        #stdout.write("\rSeq             : %d " %self.hb_numframe)
        #stdout.flush()
        print(msg)
        #Console.Print_temp(msg, NL=False)
        sys.stdout.flush()
        #print ("\r Seq             : %d " %self.hb_numframe)
        #print ("Delay           : %d " %self.hb_delay)
        #print ("Current Session : %s " %fulltime2str(self.hb_sessionnum))
        #print ("Next Timeout    : %s " %fulltime2str(self.hb_timeout))
        #print ("----- ------------------ -----")

    def check_heartbeat(self, num_session, frame_num, delay,date):
        """ Check and diagnose last received heartbeat packet """
        if RxSock.get_rx_connect() == False:
            return
        msg=None
        self.hb_filedate=date
        self.print_heartbeat(date)
        # new session identification (session restart)
        if self.hb_sessionnum != num_session:
                if frame_num==0 :
                    msg = 'HeartBeat : transmission restarted \n'
                    AROWLogger.info(msg)
                # lost frame in a new session (receiver start was too late)
                else:
                    # TODO : check the receiver restart (local values to 0)
                    if (self.hb_numframe==0 and self.hb_sessionnum==0):
                        msg = ' HeartBeat : receiver restarted'
                        AROWLogger.info(msg)
                    else:
                        msg = '\n HeartBeat : transmission restarted, lost %d heartbeat(s)' %frame_num
                        AROWLogger.warn(msg)
                # Set correct num_session
                self.hb_sessionnum=num_session
        # lost frame identification
        else:
            hb_lost=frame_num-self.hb_numframe-1
            if bool(hb_lost) :
                msg = '\n HeartBeat : lost or delayed  %d heartbeat(s)' % hb_lost
                AROWLogger.warn(msg)
        # Set new values
        self.hb_numframe=frame_num
        self.hb_timeout=time.time()+10.5*(delay)
        if msg != None:
            print(msg,)
            #Console.Print_temp(msg, NL=True)
            sys.stdout.flush()


    def checktimer_heartbeat(self,HB_Stop):
        """Timer to send alarm if no heartbeat received"""
        #self.print_heartbeat()
        Nbretard=0
        #global HBStop
        while (not HB_Stop.is_set()):
            if RxSock.get_rx_connect() == True:
                try:
                    if self.hb_timeout < time.time():
                        if RxSock.get_rx_connect()==True:      
                        #if isRxConnected==True:      
                        #if isFileRx==False:
                            Nbretard+=1
                            delta=time.time()-self.hb_timeout
                            msg = 'HeartBeat : Waiting to receive  heartbeat number ( %d )' % self.hb_numframe
                            print(msg)
                            #Console.Print_temp(msg, NL=False)
                            sys.stdout.flush()
                            time.sleep(self.hb_delay-1)
                            if Nbretard%10==0:
                                msg = 'Warning  : Heartbeat delayed,  hb  number ( %d ) - %d ' % (self.hb_numframe, Nbretard/10)
                                AROWLogger.warn(msg)
                                print(msg,)
                                #Console.Print_temp(msg, NL=True)
                            else:
                                Nbretard=0
                            time.sleep(1)# suspend if file being received
                    else:
                        time.sleep(0.5)
                except Exception as e:
                    break              
    def Th_checktimeout_heartbeatT(self,HB_Stop):
        """ thread to check heartbeat """
        #global HBStop
        Checkheartbeat=threading.Thread(None, self.checktimer_heartbeat, args =(HB_Stop,)) 
        Checkheartbeat.name="Heartbeat"
        Checkheartbeat.daemon=True
        #HBStop = False
        Checkheartbeat.start()
    
    


#------------------------------------------------------------------------------
# RAISE_PRIORITY
#---------------------

def raise_priority():
    """to raise the process priority , to ensure good reception of frames"""

    if sys.platform == 'win32':
        # Windows:
        process = win32process.GetCurrentProcess()
        #win32process.SetPriorityClass (process, win32process.REALTIME_PRIORITY_CLASS)
        win32process.SetPriorityClass (process, win32process.HIGH_PRIORITY_CLASS)
    else:
        #  Unix:
        try:
            os.nice(-20)
        except:
            print ("Not possible to raise process priority:")
            print ("You need to run with elevated privileges to get the best performance.")

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
        port_TCPStr=0 
        debug = False
        recovery = False
        
        def __repr__(self):
            return("Addr %s,Port %s UDP %s TCP %s") %(self.address,self.port_TCP, self.port_UDP,self.port_TCPStr)
    
    init1=initvalues()
    args={}
    if not config.read(ConfigFile):
        AROWLogger.error("Unable to load initialisation file - Missing or Wrong path?")
        return (None,None)

#    config = ConfigParser.RawConfigParser(allow_no_value=True)
#    config.readfp("AROWbftp.ini")
    section_name= config.sections()
    if config.has_option('AROWReceive','Options'):
        try:
            init1.address = config.get('RecvAddress','ip' )
            init1.port_TCP = config.getint('RecvAddress','port')
            init1.port_UDP = config.getint('RecvAddress','UDPPort')
            init1.port_TCPStr = config.getint('RecvAddress','TCPStrPort')
            init1.recovery=config.getboolean('RecvModes','recovery')
            init1.debug = config.getboolean('RecvModes','debug')
            init1.nodelete = config.getboolean('RecvModes','nodelete')
            args[0] = config.get('RecvPath','folder')
            return (init1,args)
        except:
            AROWLogger.error("Unknown parameters in initialisation file, using Command Arguments")
            return (None,None)
    else:
        AROWLogger.error("Unable to read initialisation file - Empty?") 
        return (None,None)   
    
    
    

#------------------------------------------------------------------------------
# Save Config  File
#---------------------                          
                        
def save_conf_trace(options,args):
    """to backup current parameters"""
    cfgfile = open(ConfigFile,'w')
    config = SafeConfigParser()
    
    config.add_section('AROWReceive')
    config.set('AROWReceive','Options',"")
    config.add_section('RecvAddress')
    config.set ('RecvAddress','IP',str(options.address))
    config.set ('RecvAddress','Port',str(options.port_TCP))
    config.set ('RecvAddress','UDPPort',str(options.port_UDP))
    config.set ('RecvAddress','TCPStrPort',str(options.port_TCPStr))
    config.set ('RecvAddress','MCStrPort',str(options.port_MCStr))
    config.add_section('RecvModes')
    config.set ('RecvModes','Recovery',str(options.recovery))
    config.set ('RecvModes','Debug',str(options.debug))
    config.set ('RecvModes','Nodelete',str(options.nodelete))
    config.add_section('RecvPath')
    config.set ('RecvPath','Folder',args[0])
    config.write(cfgfile)
    cfgfile.close()
    
    
    

#------------------------------------------------------------------------------
# EXIT_HELP : Display Help in case of error
#-------------------

def exit_help():
    "Display a help message in case of error."

    # display the docstring (in the beginning of this file) that contains the help.
    print (__doc__)
    sys.exit(1)


#------------------------------------------------------------------------------
# MTIME2STR : Convert date as a string
#-------------------

def mtime2str(file_date):
    """Convert a file date to string for display"""
    localtime =time.localtime(file_date)
    return time.strftime('%d/%m/%Y %H:%M:%S', localtime)

def fulltime2str(file_date):
    """Convert a file date to string for display."""
    localtime = time.localtime(file_date)
    return time.strftime('%d/%m/%Y %H:%M:%S', localtime)

def todaytime2str(file_date):
    """Convert a file date to string for display."""
    localtime = time.localtime(file_date)
    return time.strftime(' %H:%M:%S', localtime)

#------------------------------------------------------------------------------
# class STATS
#-------------------

class Stats:
    """class for calculating transfer stats."""
    
    def __init__(self,DRef,XFLFile):
        """Stats Object constructor."""
        self.session_num = -1
        self.num_packets_waiting = 0
        self.nb_lost_packets = 0
        #self.recvrate=0
        maxdeq=StatsServer.SECPERIODS
        self.instatsqueue = deque(maxlen=maxdeq)
        #self.statsqueue = deque(maxlen=40)
        self.instatsminqueue = deque(maxlen=60)# minute averaged queue
        self.instatshourqueue = deque(maxlen=24)# minute averaged queue
        self.inCountMin=0
        self.inCountHour=0
        self.inRateHour=0
        self.inRateMin=0
        self.DRef=DRef
        self.XFLFile=XFLFile
        #self.XFLFile=open(XFLFile,'rw')
        self.syncStats=[[0],[0],[0],[0]]
        self.HTTPPort=options.port_Stats
        self.sameFiles=[]
        self.diffFiles=[]
        self.excessFiles=[]
        self.missFiles=[]

    def add_packet (self, packet):
        """to update stats from packet function."""
        # check if all in the same session, otherwise reset
        if packet.session_num != self.session_num:
            self.session_num = packet.session_num
            self.num_packets_waiting = 0
            self.nb_lost_packets = 0
        # any packets lost?
        if packet.session_num_frames != self.num_packets_waiting:
            self.nb_lost_packets += packet.session_num_frames - self.num_packets_waiting
        self.num_packets_waiting = packet.session_num_frames + 1

    def rate_loss (self):
        """calculate the  rate of packets lost as a percentage"""
        # num_packets_waiting correspond to the number sent in the session
        if self.num_packets_waiting > 0:
            rate = (100 * self.nb_lost_packets) / self.num_packets_waiting
        else:
            rate = 0
        return rate
    def add_inrate (self, rate):
        #print rate
        self.instatsqueue.appendleft(rate)
        self.inRateMin+=rate
        self.inCountMin+=1
        #print time.time()
        if self.inCountMin>11:
            #print 'here'
            self.instatsminqueue.appendleft(self.inRateMin/self.inCountMin)
            self.inRateHour+=self.inRateMin/self.inCountMin
            self.inRateMin=0
            self.inCountMin =0
            self.inCountHour+=1
            if self.inCountHour >59:
                self.instatshourqueue.appendleft(self.inRateHour/self.inCountHour)
                self.inRateHour=0
                self.inCountHour=0
        
    def print_stats (self):
        """display the  stats"""
        print ('Rate Loss: %d%%, packets lost : %d/%d' % (self.rate_loss(),
            self.nb_lost_packets, self.num_packets_waiting))
    def get_setup(self):
        return options
    def get_heartbeat(self):
        return HB_receive
    
    def check_manifest(self,depth):
        #self.createManifest(DEST_PATH)# scan the whole directory and write the contents to xml file
        dircount=0
        manilist=self.create_manifest(DEST_PATH,depth)# scan the whole directory and write the contents to xml file
        self.reffile=self.XFLFile
        while dircount < len(manilist):
            root,manifile=os.path.split(manilist[dircount])
            base,ext=os.path.splitext(manifile)
            self.compare_sync_files(self.reffile,(os.path.join(DEST_PATH,"arowsync",manifile)),1,"")
            self.reffile=os.path.join(root,'AROWsynchro_'+str(dircount)+ext)
            dircount+=1
        #print self.sameFiles
    def create_manifest(self,path_dest,depth):
        dircount=0
        maniflist=[]
        sessionFile=self.XFLFile
        if path(sessionFile).isfile():
            self.DRef.read_rcvd_file(path(sessionFile))# may have changed, remove old files
        self.sessRoot,ext=os.path.splitext(sessionFile)
        fileet = ET.Element('dt')
        fileet.set('depth', str(depth))
        fileet.set('n', os.path.split(sessionFile)[0])
        maniflist.append(sessionFile)                    
        scanpathlist=self.DRef.dir_walk(path_dest,followlinks=True,depth=depth)
        del self.sameFiles[:]#clear each stats list and set first element to 0
        self.sameFiles.append(int('0'))
        del self.diffFiles[:]
        self.diffFiles.append(int('0'))
        del self.excessFiles[:]
        self.excessFiles.append(int('0'))
        del self.missFiles[:]
        self.missFiles.append(int('0'))
        while dircount<len(scanpathlist):
            self.XFLFile1=self.sessRoot+'_'+str(dircount)+ext # create the session file to index the iteration files
            self.DRef.read_disk(scanpathlist[dircount],depth)
        #self.DRef.read_disk(path_dest,depth)
            self.DRef.write_file(self.XFLFile1)#write the file that describes the tree
            head,tail=os.path.split(self.XFLFile1)
            e = ET.SubElement(fileet,"file")
            e.text=str(tail)# create the xml entry for the session file
            dircount+=1
            maniflist.append(self.XFLFile1)
                  
        tree=ET.ElementTree(fileet)
        tree.write(sessionFile)# write out the  list of all temp/sync files
        return maniflist
                
    
    def compare_sync_files(self,recvfile,sentfile,LoopCount,relpath):
        #sameFiles=[]
        #diffFiles=[]
        #excessFiles=[]
        #missFiles=[]
        try:
            recvdt=xfl.DirTree()
            sentdt=xfl.DirTree()
            recvdt.read_rcvd_file(recvfile)
            if os.path.isfile(sentfile) and os.path.exists(sentfile):
                sentdt.read_sent_file(sentfile,DEST_PATH)
                same,different,only1,only2=xfl.compare_DT(recvdt,sentdt,LoopCount,relpath)
                self.sameFiles[0]+=self.ilen(same)# keep track of the number and list of files
                for f in same :
                    if MODE_VERBOSE:
                        self.sameFiles.append(f)
                self.diffFiles[0]+=self.ilen(different)
                for f in different :
                    if MODE_VERBOSE:
                        self.diffFiles.append(f)
                self.excessFiles[0]+=self.ilen(only1)
                for f in only1 :
                    if MODE_VERBOSE:
                        self.excessFiles.append(f)
                self.missFiles[0]+=self.ilen(only2)
                for f in only2 :
                    msg='receiver missing: %s'% str(os.path.join(DEST_PATH,f))
                    if MODE_VERBOSE:
                        self.missFiles.append(f)
                        print(msg,)
                        #Console.Print_temp(msg,NL=True)
                    if options.logerrors:
                        AROWLogger.error(msg)    
                self.syncStats=(self.sameFiles,self.diffFiles,self.excessFiles,self.missFiles)
                
                #print 'diff: ', self.ilen(different)
                #for f in only1:
                # print "not in current send manifest: " +f
                #print 'missing: ',self.ilen(only2)
                #for f in only2:
                    #print "missing from receive !: " +f
        except Exception as e:
            print ("comparing sync files "+ sentfile+" "+str(e))
            
    def getSyncStats(self):
        return self.syncStats
        
    def ilen(self,it):
        return len(list(it))
#----------------------------------------------------------------------------------------------------

#------------------------------------------------------------------------------
# invalid_path
#--------------------------------------------------------------

def invalid_path (path):
    """Check if the path is invalid for example
    the case of an absolute path, if it contains "..",  etc..."""
    # if  path is not a string, convert it:
#   if not isinstance(path, str):
#       path = str(path)
    # is the  absolute path under Windows with a letterdrive ?
    if len(path)>=2 and path[0].isalpha() and path[1]==":":
        return True
    # is it an absolute  path starting  "/" or "\" ?
    if path.startswith("/") or path.startswith("\\"):
        return True
    # does it contain ".." ?
    if ".." in path:
        return True
    if "*" in path:                          
                        #print len(RxQueue)
                        #print len(packet)
        return True
    if "?" in path:
        return True
    # TODO: check if unicode is ok ??
    # otherwise path is ok :
    return False

#------------------------------------------------------------------------------
# analyse_options
#---------------------

def analyse_options():

    """analyse command line  options .
    (helper module optparse)"""
    config = SafeConfigParser(allow_no_value = True)
    # create  optparse.OptionParser object , giving as string
    # "usage" the  docstring at the beginning of the file:
    parser = OptionParser_doc(usage="%prog [options] <fi directory>")
    parser.doc = __doc__

    # adds possible options:
    parser.add_option("-a", dest="address", default="localhost", \
        help="Diode High Side Address: IP address or machine name")
    parser.add_option("-c", "--continue", action="store_true", dest="recovery",\
        default=False, help="Recovery file")
    
    parser.add_option("-d", "--debug", action="store_true", dest="debug",\
        default=False, help="Debug Mode")
   
    parser.add_option("-f","--folder",dest="dest_path",default="reception",help= "Destination path")
    parser.add_option("-g","--temp",dest="temp_path",help= "temporary folder path")
    parser.add_option("-i","--ttl", dest="MCTtl",\
        help="Multicast TTL", type="int", default=1)
    parser.add_option("--logerrors", action="store_true", dest="logerrors",\
        default=False, help="log transfer errors to log file")
    parser.add_option("-m", dest="MCGroup", default="224.1.1.2", \
        help="Multicast Address Group to Create: IP address ")
    parser.add_option("-n", dest="port_MCStr",\
        help="Multicast Stream Source Port ", type="int", default=5002)
    parser.add_option("-o", "--output", action="store_true", dest="TCPDir",\
        default=False, help="TCP Streaming direction, True = Client")
    parser.add_option("-p", dest="port_TCP",\
        help="TCP Port ", type="int", default=9876)
    parser.add_option("-r", "--receiver", action="store_true", dest="receiver",\
        default=False, help="receive files into the indicated directory")#command line arguments override stored values in ini file
    parser.add_option("-s", dest="addr_TCPStr", default="localhost", \
        help="TCP client streaming address: IP address or machine name")
    parser.add_option("-t", dest="port_TCPStr",\
        help="TCP streaming  Port ", type="int", default=10000)
    parser.add_option("-u", dest="port_UDP",\
        help="UDP streaming  Port ", type="int", default=8001)
    parser.add_option("-v", "--verbose", action="store_true", dest="verbose",\
        default=False, help="verbose mode")
    parser.add_option("-w", dest="port_Stats",\
        help="Stats Http  Port ", type="int", default=8080)
    
    parser.add_option("-x", "--nodelete", action="store_true", dest="nodelete",\
        default=False, help="Prevent  deletion of received files")
    #if not sys.argv[0:]:
    if not sys.argv[1:]:
        (options,args) = analyse_conf(config)#use the ini file
        if not options:# no command line , no ini file
            print (" using defaults") 
            (options, args) = parser.parse_args(sys.argv[0:])
            #(options, args) = parser.parse_args(sys.argv[1:])
            #if not args:
                #args=['reception']
    
    else:  # parse command line options:
        #(options, args) = parser.parse_args(sys.argv[1:])
        (options, args) = parser.parse_args(sys.argv[0:])
        
        # check that there is only 1 action:
    nb_actions = 0
    
    if options.receiver: nb_actions+=1
    if nb_actions != 1:
        parser.error("You must specify at least one action. (%s -h for complete help)" % SCRIPT_NAME)
    if len(args) < 1:
        parser.error("You must specify exactly one file/directory. (%s -h for complete help)" % SCRIPT_NAME)
    save_conf_trace(options,args)    
    return (options, args)

def cleanup(exitmsg):
        time.sleep(2)
        save_conf_trace( options,args)
        _remove_tmp_files()
        msg=AROW_APP +": "+exitmsg
        AROWLogger.info(msg)
    
        print( msg,)
        #Console.Print_temp( msg, NL=True)
        input("Press any key  to end..." )
        try:
            sys.stdin.close()
        except:
            pass
        raise SystemExit(0)

def setup_logger():
    """ set up the logger to be a mximum size and number of rotations"""
    Logger=logging.getLogger('AROWLog')# use this to propagate instances across submodule classes
    loglevel=logging.DEBUG
        
    # how far down do we go
    Logger.setLevel(loglevel)
    # add other log handlers here, eg smtp, http
    #consolehandler=logging.StreamHandler()
    #consolehandler.setLevel(100)# disable console
    #AROWLogger.addHandler(consolehandler)
    rothandler=logging.handlers.RotatingFileHandler(LOG_FILENAME,mode='a',maxBytes=1E6,backupCount=3)
    rothandler.setLevel(logging.DEBUG)
    formatter=logging.Formatter(logformat,datefmt)
    rothandler.setFormatter(formatter)
    #formatter=logging.Formatter(datefmt)
    #rothandler.setFormatter(formatter)
    Logger.addHandler(rothandler)
    #AROWLogger.removeHandler(consolehandler)
    return Logger

def _remove_tmp_files():
    for tmpfile in path(tempfile.tempdir).files():
        if tmpfile.find("BFTP_")!=-1:
            try:
                os.remove(tmpfile)
            except:
                if MODE_VERBOSE:
                    print ("Failed to remove old temp files from directory %s"%tempfile.tempdir)    
#================================================================================================
# MAIN PROGRAM
#=================================================================================================
                            

if __name__ == '__main__':
     
    def close_threads():
        if MCStrInst != None:
            MCStrInst.shutdown(socket.SHUT_RD)
        if TCPStrInst != None:
            TCPStrInst.shutdown()
        if UDPStrInst != None:
            UDPStrInst.close()
        if StatsServerInst != None:
            StatsServerInst.shutdown() 
    def reset_events():
        HB_Stop.set()# poison the heartbeat thread
        UDP_Run.clear()
        TCP_Run.clear()
        MC_Run.clear()
        Decode_Run.clear()
                                              
 
    TestCount=0
    LOG_FILENAME=AROW_APP +'.log'
    logformat='%(asctime)s %(levelname)-8s %(message)s'
    datefmt='%d/%m/%Y %H:%M:%S'
    AROWLogger=setup_logger()
    AROWLogger.info("Starting "+AROW_APP + AROW_VER )
    HB_receive=HeartBeat()
    HB_Stop = threading.Event()
    
   
    os.stat_float_times(False)
    (options, args) = analyse_options()
    #target = path(args[0])
    HOST = options.address
    PORT = options.port_TCP
    MODE_DEBUG = options.debug
    MODE_VERBOSE=options.verbose
    UDPStrPort=options.port_UDP
    TCPStrPort=options.port_TCPStr
    MCStrPort=options.port_MCStr
    #MCAddr=options.MCGroup
    
    AROWLogger.info(str(options))
    print  ('Destination Path:',options.dest_path,)
    if options.temp_path ==None:
        print ('Temp Path: System')
    else:
        print ('Temp Path:', options.temp_path)
    print ('Data Port:' ,options.address, options.port_TCP,)
    print ('UDP Stream:' ,options.port_UDP,)
    print ('Multicast:' ,"address:",options.MCGroup,'port:', options.port_MCStr,'TTL:',options.MCTtl,)
    print ('TCP Stream:' ,options.addr_TCPStr, options.port_TCPStr,)
    print('Statistics port:', options.port_Stats,)
    print ('Options:' ,'No deletions is', options.nodelete,': Recovery is ',options.recovery,': Logging is',options.logerrors,': Verbose is ',options.verbose,': Debug is',options.debug)
    
    if options.temp_path:
        tempfile.tempdir=options.temp_path # set this to a fast diskstore location for speed
    else:
        tempfile.tempdir=tempfile.gettempdir()
    _remove_tmp_files()
    TCP_Run = threading.Event()
    TCP_Send=Th_TCPStreamPktSend(TCPport=TCPStrPort,name=None,TCPAddr='localhost')# create threading instance
    UDP_Run= threading.Event()
    UDP_Send=Th_UDPStreamPktSend(UDPport=UDPStrPort,name= None)# create threading instance
    MC_Run= threading.Event()
    MC_Send=Th_MCStreamPktSend(MCAddr=options.MCGroup,MCport=MCStrPort,MCTtl=options.MCTtl,name= None)# create threading instance
    
    Decode_Run=threading.Event()
                    
    if test_connection()!=-1:
        
        if options.recovery:
            
            XFLFile=os.path.join(tempfile.tempdir,"AROWsynchro.xml")
            #XFLFile="AROWsynchro.xml"
            #DRef=xfl.DirTree()
            #working = DispProgress.TraitEnCours()
            #DRef.read_disk(target,working.AffChar)
        else:
            try:
                XFLFile_id,XFLFile=tempfile.mkstemp(prefix='BFTP_',suffix='.xml')
            except Exception as e:
                msg="No temp file or path - aborting "
                AROWLogger.error(msg)
                raise cleanup(msg)
        DRef = xfl.DirTree()   
            
        #DEST_PATH = options.receiver
        if sys.platform != 'win32':
            options.dest_path=options.dest_path.replace('\\','/')
            #args[0]=args[0].replace('\\','/')
        #DEST_PATH = path(args[0])
        DEST_PATH = os.path.basename(options.dest_path)
        #DEST_PATH = path(options.dest_path)
        
            # try and raise process priority on receiver:
        raise_priority()
        # heartbeat timeout thread
        stats = Stats(DRef,XFLFile)
        RxSock=BFTPSocket(RxQueue,decodeEvent,stats)
        if(RxSock.connect(HOST,PORT)!=-1):
            # receive stats measurement:
            statsserver=StatsServer(stats )
            StatsServerInst=statsserver.Th_setupStatsServer()# starts Stats thread
            Recv_Stop= threading.Event()
            RxSock.th_receive_tcp(DEST_PATH, Recv_Stop)# starts Receive thread
            
            print ("Files will be saved to the directory " + str(os.path.abspath(DEST_PATH)))
            #print ('Files will be saved to the directory "%s".'% str_lat1(DEST_PATH.abspath(),errors='replace'))
            print ('listening on port %d...' % PORT)
            AROWLogger.info("listening on port " +str(PORT))

            if options.TCPDir==False:
                TCPStrInst=TCP_Send.th_setup_srvr_skt(TCP_Run)#starts TCPStream thread
                if TCPStrInst ==None:
                    print(" Warning! - Unable to allocate TCP stream port - TCP streaming disabled")
            else:
                TCPCl=TCP_Send.TH_TCPStreamClient((options.addr_TCPStr,options.port_TCPStr),TCP_Send.TCPOutQueue)
                TCPStrInst=TCPCl
                #TCPStrInst=TCPCl.Th_setupTCPClient(TCP_Run)#starts TCPStream thread
                if TCPStrInst ==None:
                    print (" Warning! - Unable to allocate TCP stream port - TCP streaming disabled")
                else:
                    TCPCl.name="TCP stream"
                    TCPCl.daemon= True# kills thread on exit
                    TCPCl.start()#starts UDP stream thread
   
            #if TCPStrInst !=None:
            UDPStrInst=UDP_Send.th_setup_udp_client(UDP_Run)
            if UDPStrInst==None:
                print (" Warning! - UDP streaming not available")
            else:
                ThUDP=threading.Thread(None,UDP_Send.th_udp_client_send,None)
                ThUDP.name="UDP stream"
                ThUDP.daemon= True# kills thread on exit
                ThUDP.start()#starts UDP stream thread
            MCStrInst=MC_Send.th_setup_mc_server(MC_Run)
            if MCStrInst==None:
                print (" Warning! - Multicast streaming not available")
            else:
                ThMC=threading.Thread(None,MC_Send.th_mc_send,None)
                ThMC.name="MC stream"
                ThMC.daemon= True# kills thread on exit
                ThMC.start()#starts UDP stream thread
            RxDec=Decode(options,RxQueue,decodeEvent,HB_receive,TCPStrInst,UDP_Send,MC_Send,stats)
            RxDec.th_decode_tcp(Decode_Run)
            HB_receive.Th_checktimeout_heartbeatT(HB_Stop)# start heartbeat checking
            
            while True:
                try:
                    time.sleep(1)
                    if RxDec.sendVersion <0x20000:
                    #TestCount+=1
                    #if TestCount>10:
                        print("The Sending Version is not compatible with this Version")
                        raise KeyboardInterrupt()
                except KeyboardInterrupt:
                
                    Recv_Stop.set()#close the socket
                    time.sleep(1)
                    reset_events()
                    if options.recovery:
                        try:
                            os.remove(XFLFile)
                        except:
                            pass
                    else:
                        os.close(XFLFile_id)
                    close_threads()
                    RxSock.close()
                    #print "Loop end"
                    break
        
            
    else:
        msg="No Socket Connection"# fatal so exit
        print(msg,)
        #Console.Print_temp(msg,NL=True)
        cleanup (msg)
cleanup('Finished')
    

   
