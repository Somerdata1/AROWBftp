'''
BFTPDecode - to decode framed information from AROWSend 
Created on 21 Apr 2015
Modified Jan 2019 for Python 3/Unicode
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

@author: somerdata ltd, copyright 2015-2019
'''
UDP_TYPE = False
try:
    import threading
    import time
    import struct
    import sys
    import os
    import tempfile
    import logging
    import socket
    import ipaddress
   # import globs
    
    import TabBits
    import binascii
    import shutil
    import gc
except Exception as e:
    print("BFTPDecode: " + str(e))
    
    
    


from plx import  print_console
if sys.platform == 'darwin':
    # With MacOSX exception 'Message too long' if size is too long (Packet
    # size)
    FRAME_SIZE = 1500
else:
    if UDP_TYPE:
        FRAME_SIZE = 65500
    else:
        FRAME_SIZE = 65536 # max arow can deliver
try:
    from path import path
except:
    # todo: get rid of this module
    raise ImportError("the path module is not installed:" + " see http://www.jorendorff.com/articles/python/path/" + " or http://pypi.python.org/pypi/path.py/ (if first URL is down)")

global MODE_DEBUG
global FilesReceived #TODO: Get rid of these!
global FilesSent
FilesReceived = 0
FilesSent = 0
#global isFileRx
global copy_threads
copy_threads = {}

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
    # - length of file (in octets): Long Long=Q
    # - File checksum CRC32: int32=i (signed)
    # - packet type: uchar=B
    # - file name length (+path): ucharsrc=B
    # (following the file name, then the data)

    # packed for maximum efficiency on 32-bit boundary systems
HEADER_FORMAT = "4B 3I Q 4I Q I 2H" #python3 uses unsigned for crc

   # Correction bug 557 : size of format differs according to OS
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)

# size : Win32 (54) ; Linux (54) ; MacOSX PPC (50)
        
class AppErrors:
    ERROR_SUCCESS=0
    ERROR_FRAME=10
    ERROR_FILE=20
    ERROR_PACKET=30
    FILE_DUPLICATE=100



def mtime2str(file_date):
    "Convert a file date to string for display"
    localtime = time.localtime(file_date)
    return time.strftime('%d/%m/%Y %H:%M:%S', localtime)
#-------------------
class Decode :    
    """ class to decode AROW TCP frames in a separate thread"""
    # the packet types - each frame is tagged with one of these so that the correct decoding can be applied
    FILE_PACKET = 5  # File
    INFO_PACKET = 2     
    DIRECTORY_PACKET = 1  # Directory (not yet used)
    HEARTBEAT_PACKET = 10 # HeartBeat
    SCANEND_PACKET = 11# end of loop scan
    DELETEFile_PACKET = 16 # File Delete
    TCP_STREAM_PACKET = 20
    UDP_STREAM_PACKET = 21
    MC_STREAM_PACKET = 22

    def __init__(self,options,RxQueue,decodeEvent,Heartbeat, TCPSend,UDPSend,MCSend,stats):
        global MODE_DEBUG
        global MODE_VERBOSE
        self.frame_length = 0
        self.header = b""
        self.options = options
        self.nodelete = options.nodelete
        self.RxQueue = RxQueue
        self.decodeEvent = decodeEvent
        MODE_DEBUG = options.debug
        MODE_VERBOSE = options.verbose
        self.HeartBeat = Heartbeat
        self.TCPSend = TCPSend
        self.UDPSend = UDPSend
        self.MCSend = MCSend
        self.MAX_FILE_LENGTH = 1024
        self.stats = stats
        self.fileArray = {} 
        self.dest_path = os.path.basename(options.dest_path)
        #self.dest_path=path(options.dest_path)
        self.ScanArray = {}
        self.SessionFilesReceived = []
        self.LostFiles = []
        self.AROWLogger = logging.getLogger('AROWLog')
        self.depth = 0
        self.sendVersion=0x200000
        
    def th_decode_tcp(self,Decode_Run):
        """ thread to decode TCP frames """
        #global DecodeStop
        DecodeTCP = threading.Thread(None, self.decode_stream1, args =(Decode_Run,))
        Decode_Run.set()
        
        DecodeTCP.name = "DecodeTCP"
        DecodeTCP.daemon = True
        #DecodeStop = False
        DecodeTCP.start()
        # DecodeTCP.join()
    
                      
    def decode_stream1(self,Decode_Run): # this is a bit faster. The speed of processing is limited by this, and the file packet reconstruction.
        "To unpack and decode a TCP frame."
        global FilesReceived, FilesSent
        defer_proc = 0.01
        frameerror = 0# counts errored frames.  If excessive, abandons the processing and resets the queue
        while Decode_Run.is_set():
            # only process when data is not being received - this changes the
            # balance between processing and receiving file data and streaming
            # data
            self.decodeEvent.wait(defer_proc)
            #process every defer_proc mS
               
            if frameerror > 10:
                frameerror = 0
                self.RxQueue.clear()
                self.AROWLogger.error('Queue reset, multiple frameerrors')
                print('Reception errors: Queue reset')
            if len(self.RxQueue) > 0:# only process if there is data
                # extract the frame header
                try:
                    self.header,frame_data = self.RxQueue.popleft()
                    (self.frame_marker1,self.frame_marker2,self.frame_marker3,self.frame_pad_size,self.frame_length,
                     self.data_size, self.session_num,self.offset,self.session_num_frames, self.frame_num,
                     self.file_num_frames, self.file_date, self.file_size, self.crc32, self.packet_type,
                         self.name_length) = struct.unpack(HEADER_FORMAT, self.header)# str(self.header))
                except Exception as e:
                    print(e)
                #print("frame length =%d" % self.frame_length)
                if MODE_DEBUG:
                    self.debug_print("pad_size          =%d" % self.frame_pad_size)
                    self.debug_print("frame length      =%d" % self.frame_length)
                    self.debug_print("data_size     = %d" % self.data_size)
                    self.debug_print("session number        = %d" % self.session_num)#integer representation of time
                    self.debug_print("offset             = %d" % self.offset)
                    self.debug_print("number serverframes in session = %d" % self.session_num_frames)
                    self.debug_print("current frame number         = %d" % self.frame_num)
                    self.debug_print("number frames in file        = %d" % self.file_num_frames)
                    self.debug_print("file_size     = %d" % self.file_size)
                    self.debug_print("file_date       = %s" % mtime2str(self.file_date))
                    self.debug_print("CRC32              = %08X" % self.crc32)
                    self.debug_print("frame type        = %d" % self.packet_type)
                    self.debug_print("file name length       = %d" % self.name_length)
                    
                if self.frame_length > FRAME_SIZE:#error
                    self.RxQueue.clear()
                    self.AROWLogger.error(u'Queue reset, frame length error')
                    continue
                #extract the frame for processing
                if self.packet_type not in [self.INFO_PACKET,self.FILE_PACKET, self.HEARTBEAT_PACKET, self.SCANEND_PACKET,self.DELETEFile_PACKET,self.TCP_STREAM_PACKET,self.UDP_STREAM_PACKET]:
                    self.AROWLogger.error('unknown packet type: 0x%x, 0x%s' % (self.packet_type, binascii.hexlify(self.header)))
                    frameerror+=1
                    continue# in general, we don't want to bale out, just keep going and note errors
                # now process the various packet types
                if self.packet_type == self.TCP_STREAM_PACKET:
                    if self.data_size != len(frame_data) - self.frame_pad_size:
                        self.debug_print(u"error:TCP packet size = %d" % len(frame_data))
                        frameerror+=1
                        continue
                    self.data = frame_data
                    # for stream packets , just pass on to the stream queue
                    if self.TCPSend.isTCPStreamSockConnected == True:
                        self.TCPSend.TCPOutQueue.append(self.data)
                    continue#can't be anything else so skip next
                    
                if self.packet_type == self.UDP_STREAM_PACKET:
                    if self.data_size != len(frame_data) - self.frame_pad_size:
                        self.debug_print(u"error:UDP packet size = %d" % len(frame_data))
                        frameerror+=1
                        continue
                    self.data = frame_data
                    
                    if self.UDPSend.isUDPStreamSockConnected:
                        self.UDPSend.UDPOutQueue.append(self.data)
                    continue
                if self.packet_type == self.MC_STREAM_PACKET:
                    if self.data_size != len(frame_data) - self.frame_pad_size:
                        self.debug_print(u"error:MC packet size = %d" % len(frame_data))
                        frameerror+=1
                        continue
                    self.data = frame_data
                    
                    if self.MCSend.isUDPStreamSockConnected:
                        self.MCSend.MCOutQueue.append(self.data)
                    continue
                # a message-containing packet
                if self.packet_type == self.INFO_PACKET:# use to trigger post reception actions - filtering etc.
                    self.process_info_packet(frame_data)
                    continue
                  # a special message indicating sender has finished a scan- used to post-process received files  
                if self.packet_type == self.SCANEND_PACKET:# use to trigger post reception actions - filtering etc.
                    self.process_scan_end_packet()
                    continue
                #packet containing (part of) a file
                if self.packet_type == self.FILE_PACKET:
                    ret=self.process_file_packet(frame_data,frameerror)
                    continue
                    
                if self.packet_type == self.HEARTBEAT_PACKET:
                    self.debug_print(u"Received HEARTBEAT")
                    #check the session number, the frame number and the delay
                    #expected (using file_num_frames variable)
                    self.HeartBeat.check_heartbeat(self.session_num, self.frame_num, self.file_num_frames,self.file_date)
                # tells the receiver to delete a file - can be overriden by local receiver settings
                if self.packet_type == self.DELETEFile_PACKET:
                    self.do_delete_file(frame_data)
                    
            else:
                #print "Tick"# not enough data yet
                time.sleep(1)
        print(u"End")
    
    def process_scan_end_packet(self):
        global FilesSent
        SessionNum = self.session_num
        self.depth = self.offset
        FilesSent = self.session_num_frames
        self.ScanArray[SessionNum] = FilesSent
        msg = u"Sender says:scan complete %d Files sent. (Redundancy Factor %d )" % (FilesSent, self.frame_num)
        print(msg)
        self.AROWLogger.info(msg)
        msg = u"Sender says: Next scan due at %s" % (mtime2str(self.file_date))
        print(msg)
        if self.options.recovery == True:
            if FilesSent == 0:   
                #pass
                self.stats.check_manifest(self.depth)
        DuplicateFiles=0    
               
    def process_info_packet(self,packet):
        # info packets contain coded fixed-message numbers
        if self.session_num == 100:
            self.sendVersion = self.data_size
            #self.sendVersion = str(ipaddress.IPv4Address(self.data_size))
            msg = u"%s Sender says: %s Started %s" % (mtime2str(self.file_date),packet.decode('utf-8'),socket.inet_ntoa(struct.pack('!L',self.offset)))
            print(msg,)
            self.AROWLogger.info(msg)
        elif self.session_num == 101:
            msg = u"%s Sender says: %s Closed %s" % (mtime2str(self.file_date),packet.decode('utf-8'),socket.inet_ntoa(struct.pack('!L',self.offset)))
            print(msg,)
            self.AROWLogger.info(msg)
        elif self.session_num == 102:
            self.sendVersion = self.data_size
            msg = u"%s Sender says: %s Scan starting %s" % (mtime2str(self.file_date),packet.decode('utf-8'),socket.inet_ntoa(struct.pack('!L',self.offset)))
            print(msg,)
            self.AROWLogger.info(msg)
        else:
            msg = "%s Sender says: %s " % (mtime2str(self.file_date),packet,decode('utf-8'))
            print(msg,)
            
    def process_file_packet(self,frame_data,frameerror):
        
        if self.offset + self.data_size > self.file_size:
            self.AROWLogger.error(u'offset or data size incorrect: %d' % (self.offset + self.file_size))
            frameerror = frameerror + 1
            return AppErrors.ERROR_FRAME
        if self.name_length > self.MAX_FILE_LENGTH:
            self.AROWLogger.error(u'file name too long: %d' % self.name_length)
            frameerror = frameerror + 1
            return AppErrors.ERROR_FILE
        try:
            self.file_name = (frame_data[0:self.name_length]).decode('utf-8')
        except Exception as e:
            print(e)
          #self.file_name = str(packet[0:self.name_length])
        if sys.platform == 'win32':#NB Python regards 'win32' as being all windows flavours
            pass
            #self.file_name = self.file_name.decode('utf_8','strict')# p3 doesn't need this
        else:
            self.file_name = self.file_name.replace('\\','/')# to convert win paths to linux paths
            #self.debug_print("file_name = %s" % self.file_name)
        if self.invalid_path(self.file_name):
            self.AROWLogger.error('file name or path incorrect: %s' % self.file_name)
            return
        if self.data_size != len(frame_data) - self.name_length - self.frame_pad_size:
            self.debug_print("error: frame data size = %d" % len(frame_data))
            return
        #transfer the data part of the frame, remove any padding
        self.data = frame_data[self.name_length:len(frame_data) - self.frame_pad_size]
        # measure stats, display over 100 packets
        self.stats.add_packet(self)
        # is the file currently being received ?
        if self.file_name in self.fileArray:
            self.debug_print("rxFile currently being received")
            f = self.fileArray[self.file_name]
            # check the file hasn't changed:
            if f.file_date != self.file_date or f.file_size != self.file_size or self.frame_num == 0:# \this is a resent file after the sender re-started
            #or f.crc32 != self.crc32:# don't check here, check in file recopy
                # start to cancel current reception:
                frameerror+=1
                f.cancel_receive_file()
                # then recreate new file object after packet info:
                self.new_file(frame_data)
            else:#everything ok with file segment
                if self.current_file != self.file_name:
                    #  there has been a change of file
                    if MODE_VERBOSE:
                        msg = 'More of  "%s"...' % self.file_name
                        print(msg,)
                        self.AROWLogger.info(msg)
                    self.current_file = self.file_name
                #process this file segment
                f.process_file_segment(self)
                # invoke this to process without temp file
                #f.process_file_segment_tcp(self,self.f_dest_tcp)
                
        else:
            # does the file already exist on the disk ?
            dest_file_name = os.path.join(self.dest_path,self.file_name)
            
            self.debug_print('dest_file = "%s"' % dest_file_name)
            # if the date and size haven't changed,
            # not necessary to recreate the file so ignore:
            try:
                if os.path.isfile(dest_file_name) and os.path.getsize(dest_file_name) == self.file_size and os.path.getmtime(dest_file_name) == self.file_date:
                #if dest_file.exists()
                #and dest_file.getsize() == self.file_size
                #and dest_file.getmtime() == self.file_date
                #self.debug_print("File not changed, ignore.")
                #you can unverbose this for comfort when previously received
                #files are received again, but this slows down processing
                    if(self.frame_num==self.file_num_frames-1 and MODE_VERBOSE):# only report this once
                    #if MODE_VERBOSE:
                        msg = 'File already received, up to date,not changed: %s ' % (self.file_name)
                        print(msg)
                        sys.stdout.flush()
                    self.decodeEvent.set()# nothing to do so we can whizz round
                    return AppErrors.FILE_DUPLICATE
                else:
                # otherwise create a new file object from frame data:
                    if self.frame_num == 0:
                        self.new_file(frame_data)
                    #self.new_file_tcp()# invoke this to process without temp
                    #file
            except Exception as e :
                self.AROWLogger.info(e)
                print(u"processFilePacket error",e)
                return AppErrors.ERROR_PACKET
                #todo error processing
                
            return AppErrors.ERROR_SUCCESS    
    def do_delete_file(self,packet):
        if self.nodelete:#ignore deletion request
            return
        self.debug_print("Received DeleteFile notification")
        self.file_name = packet[0 :self.name_length].decode('utf-8')
        dest_file_name = os.path.join(self.dest_path, self.file_name)
        # Test for blocking or presence of wildcard characters
        if self.invalid_path(self.file_name):
            msg = 'Warning: invalid path for deletion file "%s"...' % self.file_name
            print(msg,)
            self.AROWLogger.error(msg)
        else:
            msg = 'Deleting "%s"...' % self.file_name
            if os.path.isfile(dest_file_name):
                try:
                    os.remove(dest_file_name)
                except (OSError):
                    msg = 'Deletion failure "%s"...' % self.file_name
                    self.AROWLogger.warn(msg)
                print(msg,)
                if MODE_VERBOSE:
                    # log to remove after qualif.
                    self.AROWLogger.info(msg)
            if os.path.isdir(dest_file_name):
            #if dest_file.isdir():
                # TODO Supression of empty folder on low side (transmission)
                if MODE_VERBOSE:
                    self.AROWLogger.info("suppress folder")
                try:
                    shutil.rmtree(dest_file_name)
                except OSError as e:
                    msg = 'Deletion failed file  "%s"... %s' % (self.file_name,e)
                    print(msg,)
                    self.AROWLogger.warn(msg)
                        
    def invalid_path(self,path):
        """Check if the path is invalid for example
        the case of an absolute path, if it contains "..",  etc..."""
    # if path is not a string, convert it:
        if not isinstance(path, str):
            path = str(path)
    # is the absolute path under Windows with a letterdrive ?
        if len(path) >= 2 and path[0].isalpha() and path[1] == ":":
            return True
        # is it an absolute path starting "/" or "\" ?
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
    
    def shorten_filename(self,filename):
        f = os.path.split(filename)[1]
        return "%s~%s" % (f[:3],f[-16:]) if len(f) > 20 else f
        
    def new_file(self,packet):
     #def new_file(self):
            "to start receiving a new file."
            #global isFileRx
            #if MODE_DEBUG:
            msg = u'Receiving "%s"...' % (self.shorten_filename(self.file_name))
                #hour = time.strftime('%d/%m %H:%M ')
            #msg = str_adjust(msg)+'\r'
            #print_oem(hour + msg)
            print(msg,)
            if MODE_VERBOSE:
                self.AROWLogger.info(msg)
            self.debug_print("New or updated file")
            self.current_file = self.file_name
            
            # write a new file object after the packet header:
            #isFileRx=True
            try:
                newrx_file = RxFile(self, self.fileArray,self.dest_path,self.SessionFilesReceived,self.LostFiles,self.options)
            except Exception as e:
                print(e)
                #store the file info for use in decoder
            self.fileArray[self.file_name] = newrx_file
            newrx_file.process_file_segment(newrx_file.packet)
            #newrx_file.process_file_segment(self)
    
    def new_file_tcp(self):
            """ this is not yet tested so not implemented, will write directly to dest without temp file and 
            perhaps without error checking"""
            "to start receiving a new file."
            #global isFileRx
            self.dest_file = self.dest_path / self.file_name
            if MODE_DEBUG:
                msg = 'Receiving "%s"...' % self.file_name
                hour = time.strftime('%d/%m %H:%M ')
                print(msg,)
            #self.AROWLogger.info(msg)
                self.debug_print("New or updated file")
            self.current_file = self.file_name
            
            # write a new file object after the packet header:
            new_file = RxFile(self,self.fileArray)
    
            #store the file info for use in decoder
            self.fileArray[self.file_name] = new_file
            path_dest = self.dest_file.dirname()
            if not os.path.exists(path_dest):
                path_dest.makedirs()
            elif not os.path.isdir(path_dest):
                path_dest.remove()
                path_dest.mkdir()
            try :
                self.f_dest_tcp = file(self.dest_file, 'wb')
            except:
                print("file  open failed - %s in use?", self.dest_file)
                return
            new_file.process_file_segment_tcp(self,self.f_dest_tcp)
               
    def debug_print(self,text):
        """to post a message if MODE_DEBUG = True"""

        if MODE_DEBUG:
            print_console("DEBUG:" + text)
#--------------------------------------------------------------------------------------------------------
class RxFile:
    """class representing a file to be received."""
    
    
    def __init__(self,packet,file_Array,dest_path,filesreceived,fileslost,options):
        """Constructor rxFile object.
        packet: packet object contains file info."""
        global FilesReceived,FilesSent
        self.AROWLogger = logging.getLogger('AROWLog')
        self.packet=packet
        self.file_name = self.packet.file_name
        self.file_date = self.packet.file_date
        self.file_size = self.packet.file_size
        self.file_num_frames = self.packet.file_num_frames
        self.file_session = self.packet.session_num
        self.fileArray = file_Array# mutable list
        self.dest_path = dest_path
        self.files_received_list = filesreceived
        self.FilesLost = fileslost
        #self.stats=stats
        self.num_files_received= len(filesreceived)
        self.options=options
        
        # destination file path
        dest_file_name = os.path.join(self.dest_path,self.file_name)
        path_dest=os.path.dirname(dest_file_name)
        if not os.path.exists(path_dest):
            os.makedirs(path_dest)
        #elif not os.path.isdir(path_dest):
            #path_dest.remove()
            #path_dest.mkdir()
        self.files_received_list.append((self.file_session,self.file_name))
        if MODE_VERBOSE:
            msg = 'dest_file = "%s containing  %d frames"' % (dest_file_name,self.file_num_frames)
            #msg = 'dest_file = "%s containing  %d frames"' % (self.dest_file,self.file_num_frames)
            print(msg,)
            #debug('dest_file = "%s of %d"' %
            #(self.dest_file,self.file_num_frames))
        # create temporary file (object file):
        # on Windows, can't rename an open file so it needs to be closed and
        # deleted separately
        # mode is not really necessary since it defaults to w+b - on windows
        # w+t gives wrong size value
        self.temp_file = tempfile.NamedTemporaryFile(prefix='BFTP_',mode='w+b',delete=False)
        #debug('temp_file = "%s"' % self.temp_file.name)#
        self.received_packets = TabBits.TabBits(self.file_num_frames)
        self.received_packets.nb_true = 0
        #print 'Receipt of file "%s"...' % self.file_name
        self.isFinished = False    # flag indicates reception complete
        self.crc32 = self.packet.crc32 # file CRC32
        self.frame_num = 0
        FilesReceived +=1
        try: #create the final destination file
            self.dest_file=open(dest_file_name,'w')
        except Exception as e:
            print(e)

    def process_file_segment(self,fpacket):
        global copy_threads
        """to process a frame containing a piece of a file.
        frames could be received incorrectly, eg part way through a transmission.
        We use a bit array to check if a particular frame has already been received. If not we use the frame offset to 
        write to that position in the temp file and continue until all frames for that file have been received.
        The reconstructed temp file is then crc checked and written to its final destination""" 
        # check that the packet is not already received
        # this is a new packet: write to the temp file
        #debug("offset = %d" % offset)
        #if there are errors, the file is corrupt so bail out except if the file has been resent
        #frame numbers out of sequence that are higher than expected are wrong,
        #but frame numbers lower are ok - the file offset will be overwritten
        # any missing frames will be caught by the crc check
        if fpacket.frame_num > self.frame_num :
            if MODE_DEBUG:
                debug("frame number error packet %d frame %d " % packet.frame_num,self.frame_num)
            self.cancel_receive_file()
            return 
        self.frame_num+=1
        try:
            self.temp_file.seek(fpacket.offset)
        # note: if the file pointer is moved beyond file end,it is filled with  null data, which suits us :-).
            self.temp_file.write(fpacket.data)
            
        except IOError as e:
            print("Error writing temp file - disk full? %s" % e)
            self.AROWLogger.error('Error writing temp file - disk full? "%s"',e)
            return
        #update the frame count array - this is really only needed for udp
        #self.received_packets.set(packet.frame_num, True)
        self.received_packets.nb_true+=1
        if MODE_DEBUG:
            debug("offset after = %d" % self.temp_file.tell())
        percentage = 100 * (self.received_packets.nb_true) / self.file_num_frames
            # post the percentage: comma avoids a carriage return
        msg = "%d%% Frame No.%d is %d of %d " % (percentage,fpacket.frame_num,self.received_packets.nb_true,self.file_num_frames)
        print(msg)    
    # force a display update
        sys.stdout.flush()
        # if the file is finished, recopy to the destination:
        if self.received_packets.nb_true == self.file_num_frames:
                self.crc32 = fpacket.crc32# the final frame contains the entire file crc
                print("Received %d frames of %d \r" % (self.received_packets.nb_true,self.file_num_frames))
                # set a recopy thread going to free resource from the receiver
                self.received_packets.nb_true = 0
                recopy = threading.Thread(name=self.dest_file, target=self.recopy_destination_file,)
                # we don't want to copy the same file twice
                if recopy.name not in copy_threads:
                    copy_threads[recopy.name] = True
                    #msg="Copy threads %d"%len(copy_threads)
                    #print(msg,)
                    recopy.start()
                else:
                    self.temp_file.close()# get rid of unwanted file
                    os.remove(self.temp_file.name)
                #recopy.join()
                #print '%15s.exitcode '%(recopy.name)
                sys.stdout.flush()
                # ...and assume there are no other references:
                # garbage collector should delete memory.
                #TODO: needs a catch on failure
                    
            
    def cancel_receive_file(self):
        "to cancel the reception of a current file."
        # close and delete temporary file only if its still open
        # (otherwise initialise entirely)
        del self.fileArray[self.file_name]
        self.FilesLost.append((self.file_session,self.file_name))
            
        try:
            self.temp_file.close()
            os.remove(self.temp_file.name)
        except Exception as e:
            msg = "Temp file not closed %s: %s" % (self.temp_file.name, e)
            #msg= "Temp file not closed %s: %s"%(self.temp_file.name, str (e))
            print(msg,)
            self.AROWLogger.error(msg)
            
        msg = "File error- receive cancelled %s " % self.file_name
        self.AROWLogger.error(msg)
        print(msg,)
        debug('File receive cancelled.')
    
    
    def recopy_destination_file(self):
        """to copy the temp file to the destination until its finished. For speed we use move instead of copy
        If the temp file and final destination are on the same file system, the temp file will be renamed, if not
        the file will be copied"""
        global FilesReceived,FilesSent,copy_threads
        isFileOK = True
        if MODE_VERBOSE:
            msg = 'OK, file %s receipt  finished, checking and copying....' % self.dest_file
            print(msg,)
        # write the destination path, if necessary with makedirs
        path_dest=os.path.dirname(self.dest_file.name)
        if not os.path.exists(path_dest):
            path_dest.makedirs()
        elif not os.path.isdir(path_dest):
            path_dest.remove()
            path_dest.mkdir()
        
        #V1_1_2 changed to use shutil move without intermediate write
        #TODO: copy file permissions (needs change to sender)
        self.temp_file.seek(0)
        buf = self.temp_file.read(16384)
        # start the crc32 calculation:
        crc32 = binascii.crc32(buf)
        while len(buf) != 0:
            buf = self.temp_file.read(16384)
            # continue CRC32 calculation:
            crc32 = binascii.crc32(buf, crc32) #seed with current crc
            #print( "recalculated frame crc "+str(crc32))
        # check that obtained size is correct
        if self.temp_file.tell() != self.file_size:
            debug("file_size = %d, size obtained = %d" % (self.file_size, self.temp_file.tell()))
            self.AROWLogger.error('File Size incorrect: "%s"' % self.file_name)
            print('File Size incorrect: "%s" expected %d got %d' % (self.file_name,self.file_size, self.temp_file.tell()))
            isFileOK = False
            
        # check if checksum CRC32 is correct
        if self.crc32 != crc32:
            msg = 'File Integrity check failed: "%s"' % (self.file_name)
            debug("CRC32 file = %X, CRC32 expected = %X" % (crc32, self.crc32))
            self.AROWLogger.error(msg)
            print(msg,)
            isFileOK = False
            
        # update modification date: tuple (atime,mtime)
        if isFileOK == True:
            try:
                if os.path.isfile(self.dest_file.name):
                    self.dest_file.close()
                    os.remove(self.dest_file.name)
                try:# if the dest file is in the same file system it will be renamed,otherwise it
                    # will be copied using shutil.copy2
                    self.temp_file.close()
                    shutil.move(self.temp_file.name,self.dest_file.name)
                    os.utime(self.dest_file.name,(self.file_date, self.file_date))
                    #self.dest_file.utime((self.file_date, self.file_date))
                except Exception as e:
                    msg = "File copy failed %s " % (e)
                    print(msg,)
                    #self.AROWLogger.error(msg)
                    raise e
                if (self.file_session,self.file_name) in self.files_received_list:
                    self.files_received_list.remove((self.file_session,self.file_name))
                    #FilesReceived +=1
                msg = "Scan Session %s Files:still to process : %d " % (self.file_session,len(self.files_received_list))
                print(msg,)
                if MODE_VERBOSE:
                    self.AROWLogger.info(msg)
            except Exception as e:
                msg = 'File %s failed %s' % (self.dest_file.name, e)
                self.files_lost(msg)
                if (self.file_session,self.file_name) in self.files_received_list:
                    self.files_received_list.remove((self.file_session,self.file_name))
                return
                
        # close the temp file
            try:
                self.temp_file.close()
                os.remove(self.temp_file)
            except:
                pass#if the temp file has been renamed it doesn't exist
        # after the temp file is closed it is deleted automatically
            self.current_file = False
        # post end of function
            debug("rxFile finished.")
        
        
            #self.AROWLogger.info('rxFile "%s" all received, recopy to
            #destination.'% self.file_name)
            # in case the file dictionary is missing
            self.isFinished = True
            del self.fileArray[self.file_name]
            
            msg = 'File %s received and checked' % os.path.basename(self.dest_file.name)
            print(msg,)
            if MODE_VERBOSE:
               print(u"Files left to process %d" % len(self.fileArray),)
            del copy_threads[threading.current_thread().name]
        else :
            msg = 'File %s failed' % self.dest_file.name
            self.files_lost(msg)
            
        if FilesReceived == FilesSent:# there are no more files so this must be the end of copying
            msg = "New or changed Files sent %d Lost %d" % (FilesSent,len(self.FilesLost))
            self.AROWLogger.info(msg)
            print(msg,)
            gc.collect()# encourage the release of memory
            FilesReceived = 0 #reset counters
            FileSent = 0
            self.FilesLost = 0
            #if self.options.recovery == True:
                #self.stats.checkManifest()
                    
    def files_lost(self,msg):
        
        print(msg,)
        self.AROWLogger.error(msg) 
        try:
            self.temp_file.close()
            del self.fileArray[self.file_name]
            if os.path.isfile(self.dest_file):
                os.remove(self.dest_file)
            if os.path.isfile(self.temp_file.name):
                os.remove(self.temp_file.name)
            
        except Exception as e:
            self.AROWLogger.error(e)    
        self.FilesLost.append((self.file_session,self.file_name))
    
    
    def process_file_segment_tcp(self, packet,f_dest):
        """ this is not yet tested so not implemented, will write directly to dest without temp file and 
        perhaps without error checking"""
        if packet.frame_num != self.frame_num:
            return
        self.frame_num +=1
        try:
            f_dest.write(packet.data)
        except Exception as e:
            print(e)
      #if MODE_DEBUG:
        percentage = 100 * (packet.frame_num) / self.file_num_frames
            # post the percentage: comma avoids a carriage return
        print("%d%% Frame No.%d of %d \r" % (percentage,packet.frame_num,self.file_num_frames))
            # force a display update
        sys.stdout.flush()
        #self.crc32_tcp = binascii.crc32(packet.data)
          
        # check that obtained size is correct
        #if self.received_packets.nb_true == self.file_num_frames:
        if packet.frame_num == self.file_num_frames - 1:
            if self.dest_file.getsize() != self.file_size:
                debug("file_size = %d, size obtained = %d" % (self.file_size, self.dest_file.getsize()))
                self.AROWLogger.error('File Size incorrect: "%s"' % self.file_name)
                #raise IOError, 'file size incorrect.'
        # check if checksum CRC32 is correct
            """
            if self.crc32_tcp != self.crc32:
                debug ("CRC32 file = %X, CRC32 expected = %X" %(self.crc32_tcp, self.crc32))
                self.AROWLogger.error('File Integrity check failed: "%s"'% (self.file_name))
                print "File CRC Error: %s"% (self.file_name)
            
            #raise IOError, "File Integrity check failed."
        """
            self.dest_file.utime((self.file_date, self.file_date))
            self.current_file = False
        # post end of function
            debug("rxFile finished.")
        
        # in case the file dictionary is missing
            f_dest.close()
            self.isFinished = True
            msg = 'File %s received -checking..' % self.dest_file
            print(msg)
        
#-----------------------------------------------------------------------------------------------
def debug(text):
    """to post a message if MODE_DEBUG = True"""

    if MODE_DEBUG:
        print_console("DEBUG:" + text)
