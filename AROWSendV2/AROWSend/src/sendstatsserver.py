#!/usr/local/bin/python
#TODO: replace server with flask
""" helper to display stats from AROWSend 
Use localhost:8080 from browser window
Needs index.xslt stylesheet and javascript """
#Revision tracks Main script AROWSend.py
#Mar 2015 correction to html code to display stats correctly
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading,time,os.path
from socketserver import ThreadingMixIn
from socket import gethostname
from os  import curdir,sep
import cgi,os,sys

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

UPDATE_PERIOD = 5 
class StatsServer:
    """ A simple http server to allow interrogation of current status"""
    
    SECPERIODS = 40
    MINPERIODS = 60
    HOURPERIODS=24
    UPDATE_PERIOD =5
    def __init__(self,stats):
        self.name="stats"
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
        
        def do_GET(self):
            xmlop=""
            sendReply =False
            stats=self.server.stats    
                
            if self.path =="/":
                options=stats.get_setup()
                hb=stats.get_heartbeat()
                #for pyinstaller onefile exe to work
                self.path = resource_path(os.path.join("web",os.path.basename('index.xslt')))
                mimetype = 'text/xml'
                xmlop=xmlop+('<?xml version= "1.0" encoding="ISO-8859-1"?>\n')
                xmlop=xmlop+('<?xml-stylesheet type="text/xsl" href="xslt/index.xslt"?>\n')
                xmlop =xmlop+('<statistics> <system> <hostname>%s</hostname>\n <version>%s</version> \n </system>\n '% (gethostname(),"1.0"))
                xmlop=xmlop+('  <setup>\n     <input>\n')
                xmlop=xmlop+('    <inaddress> %s </inaddress>\n ' % options.address)
                xmlop=xmlop+('    <port> %s </port>\n '% options.port_TCP)
                xmlop=xmlop+('    <udpport> %s </udpport>\n ' % options.port_UDP)
                xmlop=xmlop+('    <tcpport> %s </tcpport>\n ' % options.port_TCPStr)
                xmlop=xmlop+('    <status> %s :%s </status>\n ' % (hb.hb_numframe,self.todaytime2str(hb.hb_filedate)))
                xmlop=xmlop+('  </input>\n')
                xmlop=xmlop+(' </setup>\n')
                xmlop=xmlop+('  <modes>\n     <mode>\n    <recovery> %s</recovery>\n ' % options.recovery)
                xmlop=xmlop+('    <debug> %s</debug>\n ' % options.debug)
                xmlop=xmlop+('    <flowrate> %s </flowrate>\n ' % options.flowrate)
                xmlop=xmlop+('    <loop> %s </loop>\n ' % options.loop)
                xmlop=xmlop+('    <pause> %s </pause>\n ' % options.pause)
                xmlop=xmlop+('  </mode>\n')
                xmlop=xmlop+(' </modes>\n')
                xmlop= xmlop+('</statistics>\n')
                sendReply = True
                 
            if self.path =="/stats":
                self.path = resource_path(os.path.join("web",os.path.basename('index.xslt')))
                mimetype = 'text/xml'
                xmlop=xmlop+('<?xml version= "1.0" encoding="ISO-8859-1"?>\n')
                xmlop=xmlop+('<?xml-stylesheet type="text/xsl" href="xslt/stats.xslt"?>\n')
                xmlop=xmlop+('<statistics> \n')
                
                xmlop=xmlop+(' <period> %d </period> \n' % UPDATE_PERIOD)# the update period
                xmlop=xmlop+('  <periods> %d </periods>\n' % 40)
                xmlop=xmlop+('  <input_data>\n ' )
                statslen=len(stats.statsqueue)-1# fix this value to stop changes during process
                for i in range (statslen,0,-1):
                    #print "Q %d %d" %(stats.statsqueue[i],i)
                    xmlop=xmlop+('   <input period=\" %d \" data=\" %f \"/> ' % ((StatsServer.SECPERIODS-i),stats.statsqueue[i]))
                xmlop=xmlop+('  </input_data>\n')
                
                xmlop=xmlop+('  <input_datam>\n ' )
                minstatslen=len(stats.outstatsminqueue)-1# fix this value to stop changes during process
                for i in range (minstatslen,0,-1):
                    xmlop=xmlop+('   <inputm period=\" %d \" data=\" %f \"/> ' % ((StatsServer.MINPERIODS-i),stats.outstatsminqueue[i]))
                xmlop=xmlop+('</input_datam>\n')
                xmlop=xmlop+('  <input_datah>\n ' )
                hourstatslen=len(stats.outstatshourqueue)-1# fix this value to stop changes during process
                for i in range (hourstatslen,0,-1):
                    xmlop=xmlop+('   <inputh period=\" %d \" data=\" %f \"/> ' % ((StatsServer.HOURPERIODS-i),stats.outstatshourqueue[i]))
                xmlop=xmlop+('</input_datah>\n')
                
                xmlop=xmlop+('</statistics>\n')
                sendReply=True
            if "/xslt" in self.path:
                mimetype = 'text/xml'
                #filepath="index.xslt"
                self.path = resource_path(os.path.join("web",os.path.basename('index.xslt')))
                sendReply = True
                
            try:
                if self.path.endswith ("html"):
                    mimetype = 'text/html'
                    sendReply = True
                
                if self.path.endswith ("js"):
                    mimetype = 'application/javascript'
                    self.path = resource_path(os.path.join("web",os.path.basename(self.path)))
                    sendReply = True
                if sendReply ==True:
                    webfile=self.path
                    f= open (webfile)
                    self.send_response(200)
                    self.send_header('Content-type', mimetype)
                    self.send_header('Content-length',os.path.getsize(webfile))
                    #self.send_header('Content-length',os.path.getsize(curdir + sep +self.path))
                    self.send_header('cache-control','no-cache')
                    self.send_header('Pragma','no-cache')
                    self.send_header('Expires','-1')
                    self.end_headers()# blank line
                    if not xmlop:
                        self.wfile.write(f.read())  
                    else:
                        self.wfile.write(xmlop)
                   
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
        # suppress log messages by overriding
        def log_message(self,strformat, *args):
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