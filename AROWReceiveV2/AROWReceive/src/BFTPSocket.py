'''
Created on 21 Apr 2015

@author: somerdata
'''
import  socket, time,struct,sys,   logging, traceback
import threading
from  AROWSocket import globs
from functools import partial
import errno
    
"""A note on buffer/queue sizing. 
The most common failure mode of diode transfer is overrun of the buffer on the receiving ( high) side of the diode.
This is most often caused by delayed receive-side processing, in turn usually due to slow disk write access. 
This can happen when you run out of free ram as well. Buffer overruns are catastrophic, resulting in irretrievable data loss.
AROWV1R7 onwards forces a socket reset on buffer overrun, giving the best chance for automatic continuation, although this behaviour can be overridden
AROWBftp uses a number of strategies to recover from this, to enable processing to recommence without intervention.
The loss of free RAM causes extra slowing, usually slow swap memory is invoked by the os, this delays recovery considerably.
So in general, it is best to limit the queue length to < half the available RAM. Then when this limit is reached, data will be lost,
 but recovery can take place quickly. As a rough order, the queue is populated by items of about FRAME_LENGTH long, usually 32k.
 On a system with only 2GB 0f RAM, this means the queue length should be set to about 30000. More RAM can extend this, but
 unless file transfers are infrequent this extra capacity is unlikely to be useful - the receiving system processing speed
 must still on average exceed the sending ( lo) side processing speed by about 20 % to allow for overheads.
 So the best way to deal with restricted processing speed on the hi side is to use the rate limitng option on the lo side
 to control the sending data rate. Note that use of AROW-G does not require this, since the sending rate is 
 throttled automatically  """


#..............................................................................................
#AROWSocket class
#............................................................................
class BFTPSocket:
    """ BFTPSocket - A class to control socket access and data reception """
           
    
    def __init__ (self,RxQueue,decodeEvent,stats,sock=None): 
        self.RxQueue=RxQueue
        self.decodeEvent=decodeEvent
        self.RX_BUF_LEN=65536
        self.MAX_QUEUE_LEN =RxQueue.maxlen #items , could be up to 2GB depending on frame size
        self.stats=stats
        self.isRxConnected=False
        self.MARKER1 = 0xB6
        self.MARKER2= 0x3A
        self.MARKER3 = 0x07
        self.HEADER_SIZE=globs.HEADER_SIZE
        self.AROWLogger=logging.getLogger('AROWLog')

      
    def get_rx_connect(self):
        return self.isRxConnected
    
    def connect(self,host,port): 
        self.host=host
        self.port=port
        try:
            self.sock=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
            #we don't want to delay the data from AROW or the buffer may fill so override the socket default(disable Nagle)
            self.sock.setsockopt(socket.SOL_TCP, socket.TCP_NODELAY, 0)
            #self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 524288)
            self.sock.settimeout(1) # see receive def for value determination
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR,1)
            self.sock.connect((host,port))
            self.isRxConnected = True
            self.RxQueue.clear()# initialise queue on connect
            self.AROWLogger.info("Receiver connected " +str(host))
            
                        
        except Exception as e:
            print ("Receiver:No server connection -  %s" %(e))
            self.AROWLogger.info("Receiver:No server connection " +str(e))
            self.isRxConnected= False
            
            return(-1)        
        
    def th_receive_tcp(self,directory,Recv_Stop):
        """ thread to decode TCP packets """
       
        #DEST_PATH = directory
        ReceiveTCP=threading.Thread(None, self.receive, args=(Recv_Stop,))
        ReceiveTCP.name = "Receive"  
 
        #ReceiveTCP.daemon=True
        ReceiveTCP.start()
        
        
    
    def receive(self,Recv_Stop):
        """For TCPIP receiver """
    # from 1.0.1 this is a separate thread. It needs to run at highest priority and to fill the deque
    #without being delayed, so decodeEvent is cleared when there is data to be received. 
    #Using the socket timeout to set the decodeEvent means there is no data currently and also forces data decoding to be 
    #deferred for a period of at least the socket timeout value.
    # hack: changing the contents of a global variable
        
        options=self.stats.get_setup()
        strttime=time.time()
        statlen=0
        period=5
        toread=self.RX_BUF_LEN
        frame_data=""
        header=""
        isSync= False
        buf=bytearray()
        reconnectTimeout=2
        chunk=""
        lenf=0
        index1=0
        while (not Recv_Stop.is_set()):
            try:
                #socket will block until at least 1 byte is available (default)
                try:
                    toread=self.RX_BUF_LEN
                    intvltime=time.time()-strttime
                    
                    while toread :
                        if len(buf) >6:
                            #print len(buf)
                            if buf[0]==self.MARKER1 and isSync ==True:
                                lenf=buf[4]|buf[5]<<8    
                                pass# we've landed on a frame boundary so carry on
                            else:
                                isSync=False    
                            while isSync==False and len(buf)>6:
                                index1=buf.find(b'\xb6\x3a\x07')# find the marker sequence
                                if index1==0:
                                    isSync= True
                                    lenf=buf[4]|buf[5]<<8
                                    #print ("Sync")
                                    break
                                elif index1==-1:
                                    toread-=len(buf)-2
                                    del buf[0:len(buf)-2]
                                    
                                elif index1>0:
                                    del buf[0:index1] 
                                    toread-=index1   
                                isSync=False
                                lenf=0
                        #"""
                                  
                        if len(buf)>=lenf+self.HEADER_SIZE:# enough data to create frame
                            header = buf[0:self.HEADER_SIZE]
                            frame_data= buf[self.HEADER_SIZE:self.HEADER_SIZE+lenf]
                            del buf[0:self.HEADER_SIZE+lenf]
                            break           
                        else:
                            try:
                                chunk =self.sock.recv(toread)
                                if chunk==b"":#socket lost
                                    break
                                buf.extend(chunk)
                            except ConnectionResetError :
                                chunk=None
                                msg=' Peer reset - buffer overflow?'
                                print (msg +'\n')
                                self.AROWLogger.critical(msg)
                                break
                            except TimeoutError:
                                pass
                            except Exception as e:
                                if Recv_Stop.is_set():
                                    raise KeyboardInterrupt
                            
                            #except socket.error as e:
                                #errcode=e.args[0]
                                #if errcode==errno.ECONNRESET:
                                #if e.errorno == OSError.errno.ECONNRESET:
                                    #chunk=None
                                    #msg=' Peer reset - buffer overflow?'
                                    #print (msg +'\n')
                                    #self.AROWLogger.critical(msg)
                                    #break
                                #if Recv_Stop.is_set():
                                    #raise KeyboardInterrupt
                            #toread-=len(chunk)
                            #print len(chunk)
                            #print binascii.hexlify(buf[0:3])
                            
                            #toread=0
                    
                    statlen+=len(frame_data)
                    if intvltime>period:
                        self.stats.add_inrate(statlen)
                        strttime=time.time()
                        statlen=0
                   
                    #decodeEvent.clear()# this causes the processing to wait until the socket has timed out
                except socket.timeout:
                    self.decodeEvent.set()
                    continue
                        
                if not chunk:# stream has disconnected
                    try:
                        self.isRxConnected=False
                        raise Exception ("socket lost")
                    except Exception as e:
                        msg=" Receiver:No server connection -  %s, trying to reconnect every %d secs" %(e,reconnectTimeout)
                        print (msg)
                        self.AROWLogger.error(msg)
                        #Recv_Stop.set()
                        self.isRxConnected= False
                        self.close()
                        time.sleep(reconnectTimeout)#secs
                        self.connect(self.host,self.port)
                       
                else:
                    try:
                        #the queue is getting full so start processing
                            
                        if len(self.RxQueue)>self.MAX_QUEUE_LEN/2:
                            self.decodeEvent.set()
                            #time.sleep(0.1) #secs # allow processing to take place - this is about the size of the arow buffer
                        #elif len(RxQueue)<MAX_QUEUE_LEN/4:
                                #decodeEvent.clear()
                        if len(self.RxQueue)>self.MAX_QUEUE_LEN:
                            self.AROWLogger.error("Queue Overrun %d, data lost",len(self.RxQueue) ) 
                            #something horrible has happened so reset 
                            print ("Queue overrun, data lost len %d",len(self.RxQueue))
                            self.RxQueue.clear()
                            self.decodeEvent.clear()
                            
                        else:
                            #length returned is variable so dump to deque
                            self.RxQueue.append((header,frame_data))
                            
                               
                    except Exception:
                        msg = "Error in packet decoding: %s" % traceback.format_exc(1)
                        print (msg)
                        traceback.print_exc()
                        self.AROWLogger.error(msg)
            except KeyboardInterrupt:
                self.decodeEvent.clear()
                break
    def close(self):
        self.sock.close()          
#------------------------------------------------------------------------------
