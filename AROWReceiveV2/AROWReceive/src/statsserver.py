#!/usr/local/bin/python
"""helper to display stats from AROWReceive 
Use localhost:8080 from browser window
Needs index.xslt style sheet and javascript """
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading,time,os.path
from socketserver import ThreadingMixIn
from socket import gethostname
from os  import curdir,sep
import cgi,os,sys

#UPDATE_PERIOD = 5
#PERIODS = 40
#for installer
def resource_path(relative_path):
    """Get absolute path to resource, for PyInstaller """
    #try:
        #PyInstaller creates a temp folder and stores path in _MEIPASS
    if hasattr(sys,"_MEIPASS"):
            #base_path=sys._MEIPASS
        return os.path.join(sys._MEIPASS,relative_path)
    #except:
        #base_path =os.path.abspath(".")
    return os.path.join(relative_path)

class StatsServer:
    """ A simple http server to allow interrogation of current status"""
    SECPERIODS = 40
    MINPERIODS=60
    HOURPERIODS=24
    UPDATE_PERIOD = 5
    def __init__(self,stats):
        self.name=""
        #self.opts=options
        #self.HB_receive= HB_receive
        self.stats=stats
        
        
    def Th_setupStatsServer(self):
        server= self.ThStatsServer(('localhost',self.stats.HTTPPort),self.StatsHandler,self.stats)
        #server= self.ThStatsServer(('localhost',8080),self.StatsHandler,(self.opts,self.HB_receive,self.stats))
        self.name=threading.Thread(target=server.serve_forever)
        self.name.setDaemon(True)
        self.name.name="Stats"
        self.name.start()
        return server
            
    class ThStatsServer(ThreadingMixIn,HTTPServer):
        daemon_threads =True
        #we have to override the http server class to pass in our parameters to the base handler
        def __init__(self,server_address,RequestHandlerClass,stats):
            HTTPServer.__init__(self,server_address,RequestHandlerClass)
            #self.handler=handler
            self.stats=stats
   
               
    
    class StatsHandler(BaseHTTPRequestHandler):
        #def __init__(self):
            #self.opts=opts
            #self.HB_receive= HB_receive
           # self.stats=stats  
        
        def do_GET(self):
            xmlstr=""
            sendReply =False
            stats=self.server.stats    
                
            if self.path =="/":
                options=stats.get_setup()
                hb=stats.get_heartbeat()
                #for pyinstaller onefile exe to work
                self.path = resource_path(os.path.join("web",os.path.basename('index.xslt')))
                #self.path = "/index.xslt"
                mimetype = 'text/xml'
                xmlstr=xmlstr+('<?xml version= "1.0" encoding="ISO-8859-1"?>\n')
                xmlstr=xmlstr+('<?xml-stylesheet type="text/xsl" href="xslt/index.xslt"?>\n')
                xmlstr =xmlstr+('<statistics> <system> <hostname>%s</hostname>\n <version>%s</version> \n </system>\n '% (gethostname(),"1.0"))
                xmlstr=xmlstr+('  <setup>\n     <input>\n')
                xmlstr=xmlstr+('    <inaddress> %s </inaddress>\n ' % options.address)
                xmlstr=xmlstr+('    <port> %s </port>\n '% options.port_TCP)
                xmlstr=xmlstr+('    <udpport> %s </udpport>\n ' % options.port_UDP)
                xmlstr=xmlstr+('    <tcpport> %s </tcpport>\n ' % options.port_TCPStr)
                xmlstr=xmlstr+('    <status> %s :%s </status>\n ' % (hb.hb_numframe,self.todaytime2str(hb.hb_filedate)))
                xmlstr=xmlstr+('  </input>\n')
                xmlstr=xmlstr+(' </setup>\n')
                xmlstr=xmlstr+('  <modes>\n     <mode>\n    <recovery> %s</recovery>\n ' % options.recovery)
                xmlstr=xmlstr+('    <debug> %s</debug>\n ' % options.debug)
                xmlstr=xmlstr+('  </mode>\n')
                xmlstr=xmlstr+(' </modes>\n')
                xmlstr= xmlstr+('</statistics>\n')
                sendReply = True
                 
            if self.path =="/stats":
                syncStats=stats.getSyncStats()
                self.path = resource_path(os.path.join("web",os.path.basename('index.xslt')))
                #self.path = "web" +sep+os.path.basename("index.xslt")#"/stats.xslt"
                #self.path = "/index.xslt"#"/stats.xslt"
                mimetype = 'text/xml'
                xmlstr=xmlstr+('<?xml version= "1.0" encoding="ISO-8859-1"?>\n')
                xmlstr=xmlstr+('<?xml-stylesheet type="text/xsl" href="xslt/stats.xslt"?>\n')
                xmlstr=xmlstr+('<statistics> \n')
                
                xmlstr=xmlstr+(' <period> %d </period> \n' % StatsServer.UPDATE_PERIOD)
                xmlstr=xmlstr+('  <periods> %d </periods>\n' % StatsServer.SECPERIODS)
                xmlstr=xmlstr+('  <input_data>\n ' )
                statslen= len(stats.instatsqueue)-1
                for i in range (statslen, 0, -1):
                    xmlstr=xmlstr+('   <input period=\" %s \" data=\" %d \"/> ' % ((StatsServer.SECPERIODS-i),stats.instatsqueue[i]))
                xmlstr=xmlstr+('</input_data>\n')
                xmlstr=xmlstr+('  <input_datam>\n ' )
                instatsminlen= len(stats.instatsminqueue)
                for i in range (instatsminlen, 0, -1):
                # this is the no. of bytes in the collection period, script converts to bits and rate
                    xmlstr=xmlstr+('   <inputm period=\"%d\" data=\"%d\"/>\n' % ((StatsServer.MINPERIODS-i),stats.instatsminqueue[i-1]))
                xmlstr=xmlstr+('  </input_datam>\n ' )
                xmlstr=xmlstr+('  <input_datah>\n ' )
                instatshourlen= len(stats.instatshourqueue)
                for i in range (instatshourlen, 0, -1):
                # this is the no. of bytes in the collection period, script converts to bits and rate
                    xmlstr=xmlstr+('   <inputh period=\"%d\" data=\"%d\"/>\n' % ((StatsServer.HOURPERIODS-i),stats.instatshourqueue[i-1]))
                xmlstr=xmlstr+('  </input_datah>\n ' )
                xmlstr=xmlstr+(' <synchro> \n ' )
                if syncStats:
                    xmlstr=xmlstr+('   <same> %d </same>\n' % (syncStats[0][0]))
                    xmlstr=xmlstr+('   <diff> %d </diff>\n' % (syncStats[1][0]))
                    xmlstr=xmlstr+('   <extra> %d </extra>\n' % (syncStats[2][0]))
                    xmlstr=xmlstr+('   <miss> %d </miss>\n' % (syncStats[3][0]))
                
                xmlstr=xmlstr+(' </synchro>\n ' )
                xmlstr=xmlstr+('</statistics>\n')
                sendReply=True
            if "/xslt" in self.path:
                mimetype = 'text/xml'
                #filepath="web/index.xslt"
                #filepath="index.xslt"
                self.path = resource_path(os.path.join("web",os.path.basename('index.xslt')))
                #self.path="./index.xslt"
                sendReply = True
                
            try:
                if self.path.endswith ("html"):
                    mimetype = 'text/html'
                    sendReply = True
                
                if self.path.endswith ("js"):
                    mimetype = 'application/javascript'
                    self.path = resource_path(os.path.join("web",os.path.basename(self.path)))
                    #self.path='web'+sep+os.path.basename(self.path)
                    sendReply = True
                if sendReply ==True:
                    webfile=self.path
                    #webfile=curdir + sep +self.path
                    f= open (webfile)
                    #f= open (curdir + sep +self.path)
                    self.send_response(200)
                    self.send_header('Content-type', mimetype)
                    self.send_header('Content-length',os.path.getsize(webfile))
                    #self.send_header('Content-length',os.path.getsize(curdir + sep +self.path))
                    self.send_header('cache-control','no-cache')
                    self.send_header('Pragma','no-cache')
                    self.send_header('Expires','-1')
                    #self.send_header('Connection','keep-alive')
                    #self.send_header('','')
                    self.end_headers()# blank line
                    if not xmlstr:
                        self.wfile.write(f.read())  
                    else:
                        self.wfile.write(xmlstr)
                   
                    f.close()
                return
            except IOError:
                self.send_error(404,'File Missing %s' %webfile)
        def do_POST(self):# placeholder
            if self.path =='/send':
                form =cgi.FieldStorage(
                    fp=self.rfile,
                    headers=self.headers,
                    environ={'REQUEST_METHOD':'POST',
                    'CONTENT_TYPE': self.headers['Content-Type'],
                    })
                self.send_response(200)
                self.end_headers()
                self.wfile.write("stuff %s" %form(['your_name'].value))
                return
        #suppress log messages by overriding
        def log_message(self,format,*args):
            return
        
        def todaytime2str(self,file_date):
            "Convert a file date to string for display."
            localtime = time.localtime(file_date)
            return time.strftime(' %H:%M:%S', localtime)
     # the overridden httpserver class 
    class HTTPServer:
        def __init__(self,name,host,port,handler):
            self.name=name
            self.host=host
            self.port=port
            self.handler=handler
            self.server=None
        def start(self):
            self.server=self.ThStatsServer((self.host,self.port),self.StatsHandler,self.handler) 
            self.server.serve_forever()

        def stop(self):
            if self.server:
                self.server.shutdown()
        
#------------------------------------------------------------------------------