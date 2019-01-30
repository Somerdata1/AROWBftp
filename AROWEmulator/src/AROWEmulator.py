'''
Created on 31 May 2013
Jan 2019 Python V3/2.7 version
@author: somerdata
A dummy server to simulate AROW responses.
What it does - supports control for two modules, high and low, data for a single diode instance
Static information replaces the normal diode static information, serial number, version etc
Dynamic information is created to try and mimic the diode buffering and socket connections
Supports udp and tcp streaming
What it doesn't do - there is no attempt to mimic the redundancy feature of AROW, or to support
the 4 modules that would simultaneously be used in that configuration. For use on a single platform
the default values for port numbers are set so they don't conflict - the low side control port
is 10001 and the high side control port is 10002 for example, similarly the data ports used are 9876 and 9875.
Mimicking the behaviour of a fast hardware buffer is also tricky so it tends to be significantly slower than a real device.   

'''
from __future__ import absolute_import
from __future__ import print_function
try:# p2.7 compatiblity
    input = raw_input
except NameError:
    pass
import sys, socket, struct, time, os, os.path, tempfile, logging, traceback
import threading
try :
    import configparser #p3
except:
   import ConfigParser #p2.7
from collections import  deque
from threading import Lock
import errno

try:
    from socketserver import ThreadingMixIn, UDPServer, BaseRequestHandler , TCPServer #p3
except: 
   from  SocketServer import ThreadingMixIn, UDPServer, BaseRequestHandler ,TCPServer #p2.7
from OptionParser_doc import *
try:
    from path import path
except:
    raise ImportError( "the path module is not installed:")
import random
global isHiStreamSockConnected
isHiStreamSockConnected = False
global isLoStreamSockConnected
isLoStreamSockConnected = False
global isLoThread
isLoThread= False;
global isHiThread
isHiThread= False;
global isCtlLoThread
isCtlLoThread= False;
global isCtlHiThread
isCtlHiThread= False;
global TCP_Hi
lock =Lock()
import gc
""" Set the type of hardware device to emulate here (exclusive values, set only one to be true)"""
AROW_SINGLE=True
AROW_DUAL=False
AROW_REDUNDANT=False
# todo
GATED=False

     
MAX_QUEUE_LEN =5000

TCPInQueue=deque()# a deque for streaming  data out
UDPInQueue=deque()
SCRIPT_NAME = os.path.basename(__file__)    # script filename
UDP_TYPE=False
BUFSIZE = 67108864# dwords should be the same as the AROW ddr3 buffer size
BUFTHRESHHI= BUFSIZE -12000
BUFTHRESHLO =1000
HiTide =0
LoTide = BUFSIZE
BufLevel=0
BufOverCnt=0
FifoOverCnt=0
StatusFlags=(1<<1)
isGo= True

HiNetIP= 0xc0a802d2 #just a number
HiMaskIP = 0xFFFFFF00
HiGateIP = 0xc0a802d1
LoNetIP= 0xc0a802d3 #just a number
LoMaskIP = 0xFFFFFF00
LoGateIP = 0xc0a802d3
# register addresses ( AROW-MAN-0601 chapter 8 refers)
PART_NUM_REG =0
VER_REV_REG= 0x0001
SERNUM_LO_REG=0x0002
SERNUM_HI_REG=0x0003
COMMIT_REG = 0x0004
HW_STATUS_REG = 0x0005

MAC_LO_REG= 0x1000
MAC_HI_REG= 0x1001
NET_IP_REG = 0x1002
IP_FLAGS_REG = 0x1003
NET_IP_GATE_REG = 0x1004
NET_IP_MASK_REG = 0x1005
LINK_REG= 0x0100
#ILOC_BUF_REG = 0x0101
FIFO_OVR_CTR_REG = 0x1010
DDR_OVR_CTR_REG = 0x1011
BUF_CTR_REG = 0x1012
BUF_HI_REG = 0x1013


ILOC_BUF = 0x000
ILOC_PKT_CTR = 0x1010
ILOC_FIFO_CTR = 0x1011
#ILOC_BUF_PKT = 0x1012
ILOC_PKT_ERR = 0x1013
ILOC_BUF_CNT = 1250
ILOC_BUF_HI = 0x1015
ILOC_BUF_LO = 0x1016
ILOC_TX_PKT_CNT = 0x1010
ILOC_IQ_RATE = 0x61a5000b

#------------------------------------------------------------------------------------
def setup_hw_values(hw_Type):
    """ Dictionary of register values to return"""
    # register values
    if hw_Type==1:#single
        LoHwStatus='0x10006'
        HiHwStatus='0x10007'
    elif hw_Type==2:#dual
        LoHwStatus='0x10006'
        HiHwStatus='0x10007'
    elif hw_Type==3:#redundant
        LoHwStatus='0xe'
        HiHwStatus='0xf'
        
    return{'PART_NUM':'0xa000101',
            'VER_REV':'0x89abcdef',
            'LO_SERNUM_LO':'0x1234567',
            'LO_SERNUM_HI':'0x20130501',
            'HI_SERNUM_LO':'0x1234568',
            'HI_SERNUM_HI':'0x20130501',
            'COMMIT':'0xc012345',
            'HI_HW_STATUS':HiHwStatus,
            'LO_HW_STATUS':LoHwStatus,
            'HI_MAC_LO':'0xc25dd000',
            'HI_MAC_HI':'0x0050',
            'LO_MAC_LO':'0xc25dd001',
            'LO_MAC_HI':'0x0050',
            'NET_IP':'0xc0a802d2',
            'NET_IP_GATE':'0xc0a802d2',#192.168.2.209
            'NET_IP_MASK':'0xFFFFFF00',#255,255,255,0
            'LINK_FLAGS':'0x0003' # live and back up ok
            }

def TestConnection(Host,Port):
    """ Used to test connection on startup or restart.Returns -1 if no socket available"""
    if UDP_TYPE:
        s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        #s.bind((HOST,PORT))
    else:
        s=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        try:
            print (" AROWEmulator Checking %s Port %d " %(Host,Port))
            
            s.connect((Host,Port))
            s.close()
        except Exception as e:
            if s:
                s.close()
            print ("AROWEmulator No Connection %s" %(e))
            return(-1)    
#.....................................................
class Th_UDPStreamPktSend:
    "Threaded Class to send UDP packets to another client includes methods for server and client"
    def __init__(self,UDPAddr,UDPport,name):
        self.sp_UDPport=UDPport
        self.sp_UDPAddr=UDPAddr
        self.name=name
        self.udpclient=socket.socket()
    
    class ThSocketServer(ThreadingMixIn,UDPServer):
        daemon_threads = True
        allow_reuse_address = True
        #pass
       
    def Th_setupSrvrSkt(self):
        #global isUDPStreamSockConnected
        address=(self.sp_UDPAddr,self.sp_UDPport)
        
        try:
            if self.name=="Lo":
                udpserver=self.ThSocketServer(address,self.ThUDPLoRequestHandler)
            #udpserver.allow_reuse_address = True
            ip,port=udpserver.server_address
            print ("UDP In on: "+str(ip)+":" +str(port))
            self.name=threading.Thread(target=udpserver.serve_forever)
            self.name.setDaemon(True)
            self.name.start()
            UDP_Run.set()
            return udpserver
              
        except Exception as e:
            print ('Streaming Server..', e)
            #UDP_Run.reset()
            
        
    class ThUDPLoRequestHandler(BaseRequestHandler):
        def handle(self):
            global isUDPStreamSockConnected
            isUDPStreamSockConnected = True
            data=self.request[0].strip()
            #print data
            socket=self.request[1]
            try:
                #count=0
                if len(UDPInQueue)<MAX_QUEUE_LEN:
                    UDPInQueue.append(data)
                else :
                    time.sleep(0.1)
                    #count=0#break    
            except Exception as e:
                self.request.close()
                #print e
                print ("client closed connection ")
                isUDPStreamSockConnected = False
    # non-serving version               
    
    def Th_setupUDPClient(self,UDP_Run):
        #global isUDPStreamSockConnected
        print ("UDP out on port:", str(self.sp_UDPport))
        UDPInQueue.clear()
        try:
            self.udpclient=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
            #isUDPStreamSockConnected= True
            UDP_Run.set()
            return self.udpclient
        except Exception as e:
            print ('UDP Client..', e)
            UDP_Run.reset()
            return None
            #isUDPStreamSockConnected = False
            
    def Th_UDPClientSend(self):
        count=0
        #pktlen=0
        packet=""
        address=(self.sp_UDPAddr,self.sp_UDPport)
        while 1:
            if len(UDPInQueue)>0:
                #print 'TXLen',str(len(UDPInQueue))
                if count==0:
                    while len(UDPInQueue)>0:
                        #print "UDPcount",len (UDPOutQueue)
                        try:
                            packet=UDPInQueue.popleft()
                            #print "outudp ",len(packet) 
                            sent=self.udpclient.sendto(packet,address)
                            #print "pkt len ",sent#str(len(packet)),
                           
                        except Exception as e:
                            print (e )   
                    
            else :
                time.sleep(0.01)
                gc.collect()
                count=0#break   
                 
              
    

#------------------------------------------------------------------------------
#..............................................................................................
class Th_TCPServer:
    "Threaded Class to send TCP packets to another client"
    def __init__(self,Address,TCPport,name):
        self.sp_TCPport=TCPport
        self.sp_Addr =Address
        self.name=name
        self.eom=0x0d
        self.retMsg=0xFFFFFFF
        self.msgAddr=0
        self.msgData=0
       
        self.BufLevel=0
        self.isRead=True
       
    
        
        
    class ThSocketServer(ThreadingMixIn,TCPServer):
        #Ctrl-C will cleanly kill all spawned threads
        daemon_threads =True 
        # faster rebinding
        allow_reuse_address = True
        #pass
    
        
    
    class ThLoCtrlReqHandler(BaseRequestHandler):
        """ Lo side receive message handler"""
        def parseData(self,rxdata):
            if rxdata[0]!= 0x53:
                return -1
            if rxdata[1]==1:
                self.isRead=False
            else :
                self.isRead =True   
            self.msgAddr= rxdata[2]
            self.msgData = rxdata[3] 
            self.eom= rxdata[4]      

        def HandleMessage(self):
            time.sleep(0.02)# emulate serial delay
            if self.isRead:
                return(self.get_msg_status()) 
            else :
                if self.msgAddr ==IP_FLAGS_REG:
                    if self.msgData & (1<<16):#reset tcp/ip
                        return self.msgData &~(1<<16)
                    if self.msgData & (1<<17):# reset fifo 
                        FifoOverCnt=0;
                        return self.msgData &~(1<<17)
                    if self.msgData & (1<<18):# reset ddr 
                        BufOverCnt=0;
                        return self.msgData &~(1<<18)
                    if self.msgData & (1<<19):# reset hitide 
                        HiTide=0;
                        #BufLevel =0
                        return self.msgData &~(1<<19)
               
                if self.msgAddr ==NET_IP_REG:
                    LoNetIP = self.msgData
                    #if isHiStreamSockConnected == True:
                    #TCP_Hi.stop()
                    
                    #TCP_Hi=Th_TCPServer(Address= HiNetIP,TCPport=HIPORT,name='Hi')# create threading instance
                        
                    return LoNetIP
                if self.msgAddr ==NET_IP_GATE_REG:
                    LoGateIP = self.msgData
                    return LoGateIP
                if self.msgAddr ==NET_IP_MASK_REG:
                    LoMaskIP = self.msgData
                    return LoMaskIP
                return 0xFFFFFF
            
        def get_msg_status(self):
            global HiTide, BufLevel, isHiStreamSockConnected
            global BufOverCnt,FifoOverCnt,isGo, StatusFlags
            global  HiNetIP,HiGateIP,HiMaskIP,TCP_Hi
                
            if self.msgAddr ==PART_NUM_REG:
                return int(hwv['PART_NUM'],16)
            if self.msgAddr ==VER_REV_REG:
                return int(hwv['VER_REV'],16)
            if self.msgAddr ==SERNUM_LO_REG:
                return int(hwv['LO_SERNUM_LO'],16)
            if self.msgAddr ==SERNUM_HI_REG:
                return int(hwv['LO_SERNUM_HI'],16)
            if self.msgAddr ==COMMIT_REG:
                return int(hwv['COMMIT'],16)
            if self.msgAddr ==HW_STATUS_REG:
                return int(hwv['LO_HW_STATUS'],16)
            if self.msgAddr ==IP_FLAGS_REG:
                return StatusFlags
            if self.msgAddr ==MAC_LO_REG:
                return int(hwv['LO_MAC_LO'],16)
            if self.msgAddr ==MAC_HI_REG:
                return int(hwv['LO_MAC_HI'],16)
            if self.msgAddr ==NET_IP_REG:
                return LoNetIP
            if self.msgAddr ==NET_IP_GATE_REG:
                return LoGateIP
            if self.msgAddr ==NET_IP_MASK_REG:
                return LoMaskIP
            if self.msgAddr ==LINK_REG:
                #StatusFlags|=DataWidthAlias <<20
                return int(hwv['LINK_FLAGS'],16)
            #if self.msgAddr ==ILOC_BUF_REG:
                #return LatencyThresh<<16
            if self.msgAddr ==FIFO_OVR_CTR_REG:
                return (FifoOverCnt)
            if self.msgAddr ==DDR_OVR_CTR_REG:
                return (BufOverCnt )
            
            if self.msgAddr ==BUF_HI_REG:
                return (HiTide)
            if self.msgAddr ==BUF_CTR_REG:
                if isHiStreamSockConnected == True:
                    #BufLevel= random.randint(0,132000)
                    if BufLevel >HiTide :
                        HiTide=BufLevel
                else:
                    BufLevel =0
                return BufLevel     
        def handle(self):
            global isTCPStreamSockConnected, isCtlLoThread
            isTCPStreamSockConnected = True
            print ("AROWEmulator Lo side Send Control Client opened connection ")
            try:
                #count=0
                senddata=""
                #TCPInQueue.clear()
                while isTCPStreamSockConnected ==True:
                    
                    data=self.request.recv(1024)
                    if data =="":
                        break
                    data= struct.unpack("!BBHIB",data)
                    if self.parseData(data) !=-1:
                        self.retMsg=self.HandleMessage()
                        if self.retMsg !=None:
                            senddata = struct.pack("!BBHIB",0x53,0,self.msgAddr,self.retMsg,self.eom )
                            self.request.send(senddata)
                return
            except Exception as e:
                self.request.close()
                print ("AROWEmulator Lo Side Send Control Client closed connection " +str(e))
                isTCPStreamSockConnected = False
            
                            
    class ThHiCtrlReqHandler(BaseRequestHandler):
        """ Hi side receive message handler"""
            
                                  
        def parseData(self,rxdata):
            if rxdata[0]!= 0x53:
                return -1
            if rxdata[1]==1:
                self.isRead=False
            else :
                self.isRead =True   
            self.msgAddr= rxdata[2]
            self.msgData = rxdata[3] 
            self.eom= rxdata[4]
            
        
        def HandleMessage(self):
            global HiTide, BufLevel, isHiStreamSockConnected
            global BufOverCnt,FifoOverCnt,isGo, StatusFlags
            global  HiNetIP,HiGateIP,HiMaskIP,TCP_Hi
            time.sleep(0.02)# serial delay 
            if self.isRead:
                return(self.get_msg_status())
            else :
                if self.msgAddr ==IP_FLAGS_REG:
                    if self.msgData & (1<<16):#reset tcp/ip
                        return self.msgData &~(1<<16)
                    if self.msgData & (1<<17):# reset fifo 
                        FifoOverCnt=0;
                        return self.msgData &~(1<<17)
                    if self.msgData & (1<<18):# reset ddr 
                        BufOverCnt=0;
                        return self.msgData &~(1<<18)
                    if self.msgData & (1<<19):# reset hitide 
                        HiTide=0;
                        #BufLevel =0
                        return self.msgData &~(1<<19)
               
                if self.msgAddr ==NET_IP_REG:
                    HiNetIP = self.msgData
                    #if isHiStreamSockConnected == True:
                    #TCP_Hi.stop()
                    
                    #TCP_Hi=Th_TCPServer(Address= HiNetIP,TCPport=HIPORT,name='Hi')# create threading instance
                        
                    return HiNetIP
                if self.msgAddr ==NET_IP_GATE_REG:
                    HiGateIP = self.msgData
                    return HiGateIP
                if self.msgAddr ==NET_IP_MASK_REG:
                    HiMaskIP = self.msgData
                    return HiMaskIP
                return 0xFFFFFF
                
        def get_msg_status(self):
            global HiTide, BufLevel, isHiStreamSockConnected
            global BufOverCnt,FifoOverCnt,isGo, StatusFlags
            global  HiNetIP,HiGateIP,HiMaskIP,TCP_Hi
                
            if self.msgAddr ==PART_NUM_REG:
                return int(hwv['PART_NUM'],16)
            elif self.msgAddr ==VER_REV_REG:
                return int(hwv['VER_REV'],16)
            elif self.msgAddr ==SERNUM_LO_REG:
                return int(hwv['LO_SERNUM_LO'],16)
            elif self.msgAddr ==SERNUM_HI_REG:
                return int(hwv['LO_SERNUM_HI'],16)
            elif self.msgAddr ==COMMIT_REG:
                return int(hwv['COMMIT'],16)
            elif self.msgAddr ==HW_STATUS_REG:
                return int(hwv['HI_HW_STATUS'],16)
            elif self.msgAddr ==IP_FLAGS_REG:
                return StatusFlags
            elif self.msgAddr ==MAC_LO_REG:
                return int(hwv['HI_MAC_LO'],16)
            elif self.msgAddr ==MAC_HI_REG:
                return int(hwv['HI_MAC_HI'],16)
            elif self.msgAddr ==NET_IP_REG:
                return HiNetIP
            elif self.msgAddr ==NET_IP_GATE_REG:
                return HiGateIP
            elif self.msgAddr ==NET_IP_MASK_REG:
                return HiMaskIP
            elif self.msgAddr ==LINK_REG:
                #StatusFlags|=DataWidthAlias <<20
                return int(hwv['LINK_FLAGS'],16)
            #if self.msgAddr ==ILOC_BUF_REG:
                #return LatencyThresh<<16
            elif self.msgAddr ==FIFO_OVR_CTR_REG:
                return (FifoOverCnt)
            elif self.msgAddr ==DDR_OVR_CTR_REG:
                return (BufOverCnt )
            
            elif self.msgAddr ==BUF_HI_REG:
                return (HiTide)
            elif self.msgAddr ==BUF_CTR_REG:
                if isHiStreamSockConnected == True:
                    #BufLevel= random.randint(0,132000)
                    if BufLevel >HiTide :
                        HiTide=BufLevel
                else:
                    BufLevel =0
                return BufLevel     
      
        def handle(self):
            global isTCPStreamSockConnected, isCtlLoThread
            isTCPStreamSockConnected = True
            print ("AROWEmulator Hi Side Receive Control Client opened connection ")
            try:
                #count=0
                senddata=""
                #TCPInQueue.clear()
                while isTCPStreamSockConnected ==True:
                    
                    data=self.request.recv(1024)
                    if data =="":
                        break
                    data= struct.unpack("!BBHIB",data)
                    if self.parseData(data) !=-1:
                        self.retMsg=self.HandleMessage()
                        if self.retMsg !=None:
                            senddata = struct.pack("!BBHIB",0x53,0,self.msgAddr,self.retMsg,self.eom )
                            self.request.send(senddata)
                return
            except Exception as e:
                self.request.close()
                print ("AROWEmulator Hi Side receive Control Client closed connection " +str(e))
                isTCPStreamSockConnected = False
                
                  
    class ThLoReqHandler(BaseRequestHandler):
                          
        def handle(self):
            global isLoStreamSockConnected, isLoThread,BufLevel,StatusFlags,isHiStreamSockConnected
            isLoStreamSockConnected = True
            print ("AROWEmulator Low Side Data opened connection ")
            data=""
            maxcount=0
            try:
                #count=0
                #senddata=""
                #TCPInQueue.clear()
                while isLoStreamSockConnected==True:
                    data=self.request.recv(65536)
                    if data=="":
                        break
                    if isHiStreamSockConnected:# only add to the q if there is a low-side connection
                        if len(TCPInQueue)<MAX_QUEUE_LEN:
                            TCPInQueue.append(data)
                        #TCPInQueue.extend(data[0:len(data)])
                        if len(TCPInQueue) > maxcount:
                            maxcount= len(TCPInQueue)
                        # invoke to keep an eye on the buffer usage
                        #print "\r No of objects in queue: High Tide:%d ' current:%d " %(maxcount,len(TCPInQueue)),
                        sys.stdout.flush()
                        lock.acquire()
                        BufLevel= BufLevel+len(data)
                        if BufLevel >  BUFSIZE :
                            BufLevel = BUFSIZE
                            StatusFlags |= (1<<3)
                        else :
                            StatusFlags &= ~(1<<3)
                        lock.release()     
                print ("AROW Lo Client Data disconnected")
                return    
                
            except Exception as e:
                self.request.close()
                # print e
                print ( "AROW Test Low side closed connection " +str(e))
                isLoStreamSockConnected = False
                
        
    class ThHiReqHandler(BaseRequestHandler):
        
        def finish(self):
            pass
            global isHiStreamSockConnected, StatusFlags
           
        def finish_request(self):
            global StatusFlags
            StatusFlags &= ~ (1<<2)                  
            StatusFlags &= ~ (1<<0)                         
        def close_request (self,request):
            return socketserver.TCPServer.close_request(self, request)
        def handle(self):
            global isHiStreamSockConnected, isHiThread,BufLevel, StatusFlags
            isHiStreamSockConnected = True
            StatusFlags |= (1<<2)
            StatusFlags |= (1<<0) 
            print ("AROWEmulator Hi Side data  opened connection ")
           #self.request.send(" ".encode('utf-8'))
            try:
                #count=0
                #senddata=""
                TCPInQueue.clear()
                BufLevel=0
                while isHiStreamSockConnected==True:
                    if len(TCPInQueue)>0:
                        #print 'AROW Test Hi Buffer',str(len(TCPInQueue))
                        while len(TCPInQueue)>0:
                            print ("\r AROWEmulator Queue count",str(len(TCPInQueue)),)
                            t=TCPInQueue.popleft()
                            self.request.sendall(t)
                            lock.acquire()
                            BufLevel -= len(t)
                            if BufLevel <0:
                                BufLevel = 0
                            lock.release()    
                    else:
                        time.sleep(0.1)
                        BufLevel=0
                        self.request.send(" ".encode('utf-8'))
                return         
                
            except socket.error as se:
                if se.args[0] == errno.EPIPE:
                    pass
                elif se.args[0] ==errno.ECONNRESET:
                    print ("AROWEmulator Hi Side client disconnected" )
                    TCPInQueue.clear()
                    isHiStreamSockConnected=False
                    #print "AROWEmulator Hi Side disconnected" +str(se)
                    
                else:
                    pass
                
            except Exception as e:
                self.request.close()
                # print e
                print ("AROWEmulator Hi Side closed connection with " +str(e))
                isHiStreamSockConnected = False
                StatusFlags &= ~ (1<<2)                  
                StatusFlags &= ~ (1<<0)
                TCPInQueue.clear()
                
    def Th_setupSrvrSkt(self):
        global isLoThread, isHiThread, isCtlLoThread,isCtlHiThread, isHiStreamSockConnected
        address=(self.sp_Addr,self.sp_TCPport)
        #address=('localhost',self.sp_TCPport)
        try:
            if self.name == "LoCtrl":
                server=self.ThSocketServer(address,self.ThLoCtrlReqHandler)
                isCtlLoThread=True;
            if self.name == "HiCtrl":
                server=self.ThSocketServer(address,self.ThHiCtrlReqHandler)
                isCtlHiThread=True;
            if self.name == "Lo":
                server=self.ThSocketServer(address,self.ThLoReqHandler)
                #server.allow_reuse_address = True
                
                isLoThread = True
            if self.name == "Hi":
                server=self.ThSocketServer(address,self.ThHiReqHandler)
                isHiThread= True
                
            ip,port=server.server_address
            server.allow_reuse_address = True
            print("AROWEmulator TCP Serving on: "+self.name +" " +str(ip)+": "+ str(port))
            THinst=threading.Thread(target=server.serve_forever)
            THinst.setDaemon(True)
            THinst.start()
            return server
           
            
        except Exception as e:
            print ('Streaming Server..' +self.name +" "+str(address)+" ", e)
            isLoStreamSockConnected = False
            return None
    
    
#-----------------------------------------------------------------------------------------------
                  
def analyse_options():
    """analyse command line  options .
    (helper module optparse)"""

    # create  optparse.OptionParser object , giving as string
    # "usage" the  docstring at the beginning of the file:
    parser = OptionParser_doc(usage="%prog [options] <fi directory>")
    parser.doc = __doc__

    # adds possible options:
    parser.add_option("--lca",dest="LoCtrlAddress", default="localhost", \
        help="AROW Lo Control Address: IP address or machine name")
    parser.add_option("--hca",dest="HiCtrlAddress", default="localhost", \
        help="AROW Hi Control Address: IP address or machine name")
    parser.add_option("--cp", dest="CtrlPort",\
        help="Control Port ", type="int", default=10001)
    parser.add_option("--la",dest="LoAddress", default="localhost", \
        help="AROW Low Address: IP address or machine name")
    parser.add_option("--lp", dest="LoPort",\
        help="Lo  Port ", type="int", default=9876)
    parser.add_option("--ha",dest="HiAddress", default="localhost", \
        help="AROW Hi Address: IP address or machine name")
    parser.add_option("--hp", dest="HiPort",\
        help="Hi Port ", type="int", default=9875)
    parser.add_option("-d", "--debug", action="store_true", dest="debug",\
        default=False, help="Debug Mode")
    
    # parse command line options:
    (options, args) = parser.parse_args(sys.argv[1:])
    # check that there is only 1 action:
    nb_actions = 0
    
    if options.LoCtrlAddress: nb_actions+=1
    if nb_actions != 1:
        parser.error("You must specify at least one action. (%s -h for complete help)" % SCRIPT_NAME)
    
    return (options, args)
  
                 
              
    
#-----------------------------------------------------------------------------------------------

if __name__ == '__main__':
    if AROW_SINGLE==True:
        AROWHW_Type=1
    elif AROW_DUAL==True:
        AROWHW_Type=2
    elif AROW_REDUNDANT ==True:
        AROWHW_Type=3
    else:
        AROWHW_Type=1#default
    hwv=setup_hw_values(AROWHW_Type)
    (options, args) = analyse_options()
    LOCTRLHOST = options.LoCtrlAddress
    HICTRLHOST = options.HiCtrlAddress
    CTRLPORT = options.CtrlPort
    LOHOST = options.LoAddress
    LOPORT = options.LoPort
    HIHOST = options.HiAddress
    HIPORT = options.HiPort
    
    logging.basicConfig(level=logging.DEBUG,
                format='%(asctime)s %(levelname)-8s %(message)s',
                datefmt='%d/%m/%Y %H:%M:%S',
                filename='AROWEmulator.log',
                filemode='a')
    logging.info("Starting AROWEmulator")
    
    LoCtrl_Send=Th_TCPServer(Address= LOCTRLHOST,TCPport=CTRLPORT,name='LoCtrl')# create threading instance
    HiCtrl_Recv=Th_TCPServer(Address= HICTRLHOST,TCPport=CTRLPORT+1,name='HiCtrl')# create threading instance
    TCP_Lo=Th_TCPServer(Address= LOHOST,TCPport=LOPORT,name='Lo')# create threading instance
    TCP_Hi=Th_TCPServer(Address= HIHOST,TCPport=HIPORT,name='Hi')# create threading instance
    UDPStrPort=8100
    
    UDP_Run= threading.Event()
    UDP_Send=Th_UDPStreamPktSend(UDPAddr=LOHOST,UDPport=UDPStrPort,name= 'Lo')# create threading instance
    UDP_Recv=Th_UDPStreamPktSend(UDPAddr=LOHOST,UDPport=UDPStrPort+1,name= 'Hi')# create threading instance
    UDPLoStrInst=UDP_Send.Th_setupSrvrSkt()
    if UDPLoStrInst==None:
        print (" Warning! - UDP streaming not available")
    UDPHiStrInst=UDP_Recv.Th_setupUDPClient(UDP_Run)
    if UDPHiStrInst==None:
        print (" Warning! - UDP streaming not available")
    else:
        ThUDP=threading.Thread(None,UDP_Recv.Th_UDPClientSend,None)
        ThUDP.daemon= True# kills thread on exit
        ThUDP.start()                
    HiCtrl=HiCtrl_Recv.Th_setupSrvrSkt()
    LoCtrl=LoCtrl_Send.Th_setupSrvrSkt()
    if LoCtrl != None:
        t2 =TCP_Hi.Th_setupSrvrSkt()
        if t2 != None:
            t3=TCP_Lo.Th_setupSrvrSkt()
            if t3 != None:
                while True:
                    try:
                        if isGo ==True:# create some dummy data to get counters etc working
                            if BufLevel >BUFTHRESHHI:
                                BufOverCnt +=1
                                if BufOverCnt > 65535:
                                    BufOverCnt=65535
                                FifoOverCnt += random.randint(0,100)
                                if FifoOverCnt > 65535:
                                    FifoOverCnt=65535 
                            
                        time.sleep(1)
                    except KeyboardInterrupt:
                        isCtlLoThread = False
                        LoCtrl.shutdown()
                        HiCtrl.shutdown()
                        t2.shutdown()
                        t3.shutdown()
                        
                        isLoThread = False
                        isHiThread = False
                        #print "Goodbye"
                        break    
                        
    else:
        print ("No Socket Connection")# fatal so exit
    
    logging.info("AROWEmulator Finished")
    print ("AROWEmulator Finished")
    input("Press any key to close this window..." )
    try:
        sys.stdin.close()
    except:
        exit()
    raise SystemExit(0)
    
