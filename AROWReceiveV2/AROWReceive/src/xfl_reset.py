#!/usr/local/bin/python
"""
----------------------------------------------------------------------------
XFL Reset
----------------------------------------------------------------------------
version 0.02 du 04/04/2008

Auteur:
- Laurent VILLEMIN (LV) - Laurent.villemin(a)laposte.net

Re-initialisation module for recovery files for AROWSend
SendAROW includes an architecture that uses a tree structure  for transmission
The sent files are received with recovery files (AROWsynchro*) and are written to disk subsequently.
The architecture allows multiple levels of files and folders to be transmitted, each with its own recovery file (if selected)
File changes recorded in the XML file can be used to force retransmissions from the low side folder in response to the receiver restting the recovery file.
This can be done manually, but this program automates the process. 
The sender checks for changes to its recovery files every scan loop so it is not necessary to restart the sender, just replace the sync files.  
To use AROWSend in this mode requires the use of synchro (options -S) and file recovery (option -c).

There are 4 re-initialisation modes
Initialisation by date
Initialisation by filename
Initialisation by XML comparison (not implemented)
Initialisation by regular expression




"""
#------------------------------------------------------------------------------
# HISTORY:
# 24/03/08 v0.01 LV : - Initial  version
# 28/03/08 v0.02 LV : added regular expression option
# 04/04/08 v0.03 LV : added progrees display module
#Nov 2015 updated to allow for levelled folder transmission
try:
    import DispProgress
except :
    raise ImportError( "Module DispProgress is not accessible")
try:
    import xfl
except:
    raise ImportError( "the XFL module is not installed: see http://www.decalage.info/python/xfl")
try:
    from path import *
except:
    raise ImportError( u"the path module is not installed: "\
                     + u"see http://www.jorendorff.com/articles/python/path/")

import datetime, time, re ,sys,os
from OptionParser_doc import OptionParser_doc

ATTR_CRC = "c"                         # File CRC
ATTR_NBSEND = "NS"                    # Number  sent
ATTR_LASTVIEW = "LV"                # Last View Date
ATTR_LASTSEND = "LS"                # Last Send Date
ATTR_NAME  = "n"
XFLFile="AROWsynchro.xml"

def mtime2str(file_date):
    "Convert a file date to string for display."
    localtime = time.localtime(file_date)
    return time.strftime('%d/%m/%Y %H:%M:%S', localtime)

def debugprint(text):
    "to post a message if MODE_DEBUG = True"

    if MODE_DEBUG:
        print_console ("DEBUG:" + text)

def Fetch(phrase, DefValue):
    """
    Get default value
    """
    question = phrase + '? [' + str(DefValue) + '] '
    val=raw_input(question).strip()
        
    if val == '':
        return(DefValue)
    else:
        return(val)

def InputResetDate():
    """
    Get date and time of the latest check - preinitialisation = Now - 1 day
    """
    print (u"Initialisation last date . \n  Default to  date and time of transmission loss :")
    Incident=datetime.datetime.now()-datetime.timedelta(days=1)

    aaaa= Fetch('    Year  ', Incident.year)
    mmm = Fetch('    Month   ', Incident.month)
    dd  = Fetch('    Day   ', Incident.day)
    hh  = Fetch('    Hour  ', Incident.hour)
    mm  = Fetch('    Minute ', Incident.minute)

    pattern = '%Y-%m-%d %H:%M:%S'
    MyDate="%d-%02d-%02d %02d:%02d:00" %(int(aaaa), int(mmm) , int(dd), int(hh), int(mm))
    epoch = int(time.mktime(time.strptime(MyDate, pattern)))

    debugprint(u"date_initialisation       = %s" % mtime2str(epoch))
    return(epoch)

def resetbyDate(ResetDate,XFLFile):
    """
    Initialisation within the XML file by date
    Use file timestamp within the tree structure to easily identify the time of  non-transmission
    """
    def _checkresetdateTags(DRef):
        DRef.pathdict(directory)
        NbFile=0
        NbReinitFile=0
        for myfile in DRef.dict:
            if(DRef.dict[myfile].tag == xfl.TAG_FILE):
                NbFile+=1
                if float(DRef.dict[myfile].get(ATTR_LASTSEND)) > ResetDate:
                #if float(DRef.dict[myfile].get(bftp.ATTR_LASTSEND)) > ResetDate:
                    NbReinitFile+=1
                    print ("        %s sent earlier than %s \n" % (myfile,ResetDate))
                    for attr in (ATTR_LASTSEND, ATTR_NBSEND):
                        #for attr in (bftp.ATTR_LASTSEND, bftp.ATTR_NBSEND):
                        DRef.dict[myfile].set(attr, str(0))
        debugprint('Initialisation of %d file(s) on %d.' % (NbReinitFile,  NbFile))
        return NbReinitFile
        
    DRef = xfl.DirTree()
    if not path(XFLFile).isfile():
        return
    dirlist=DRef.read_recovery_file(XFLFile)
    dircount=0
    sessionFile=XFLFile
    sessRoot,ext=os.path.splitext(sessionFile)
    while dircount < len(dirlist):
        directory=dirlist[dircount][0]# get the directory name for this iteration
        dirlevel=dirlist[dircount][1]# and the directory level
        XFLFile1=sessRoot+'_'+str(dircount)+ext # create the session file to index the iteration files
        filelist=DRef.read_file(XFLFile1)
    
        NbReinitFile=_checkresetdateTags(DRef)
        if NbReinitFile > 0:
            DRef.write_file(XFLFile1)
        dircount+=1                                  
    print (u"Finished scan, %d files re-initialised" %NbReinitFile)
    
    
def resetbyRegexp(expr):
    """
    Re-initialisation of sent files logged in the XML file  using a regexp pattern
    Consult the python howto regexp for the syntax
    Examples:
        .* : all files
        .*\.txt$ : all files with extension ".txt"
        monrep\\.* : all files containing the phrase monrep
    """
    def _checkresetregexTags(DRef):
        DRef.pathdict(directory)
        NbFile=0
        NbReinitFile=0
        pattern=re.compile(expr)
        for myfile in DRef.dict:
            if(DRef.dict[myfile].tag == xfl.TAG_FILE):
                NbFile+=1
                res=pattern.match(str(myfile))
                if res!=None:
                    NbFile+=1
                    NbReinitFile+=1
                    print ("        %s" % myfile)
                    for attr in (ATTR_LASTSEND, ATTR_NBSEND):
                        DRef.dict[myfile].set(attr, str(0))
        debugprint(u'Initialisation of %d file(s) on %d.' % (NbReinitFile,  NbFile))
        
    """
    DRef = xfl.DirTree() #ref directory
    DRef.read_file(XFLFile) 
    DRef.pathdict()
    """
    DRef = xfl.DirTree()
    if not path(XFLFile).isfile():
        return
    dirlist=DRef.read_recovery_file(XFLFile)
    dircount=0
    sessionFile=XFLFile
    sessRoot,ext=os.path.splitext(sessionFile)
    while dircount < len(dirlist):
        directory=dirlist[dircount][0]# get the directory name for this iteration
        dirlevel=dirlist[dircount][1]# and the directory level
        XFLFile1=sessRoot+'_'+str(dircount)+ext # create the session file to index the iteration files
        filelist=DRef.read_file(XFLFile1)
        NbReinitFile=_checkresetregexTags(DRef)
        if NbReinitFile > 0:
            DRef.write_file(XFLFile)
        dircount+=1
    print (u"Finished scan, %d files re-initialised" %NbreinitFile)
    
def resetbyDiff(dirpath):
    """
    Initialisation of sent files within XML sync files by comparison with actually-received tree
    Operational Mode :
        Use the XML files  of  transmissions from the high side(what you think has been sent).
        These should be available in the /[pathtoreceive]/arowsync folder
        Set the file path and top level file as an argument to the program (e.g. /[pathto]/arowsync/AROWsynchro.xml)
        Set the directory path when prompted by the program (e.g. /[pathto]/reception) 
        The file is compared with the received tree structure.
        All files known to have been sent but not received are re-initialised in the xml file.
        (This is most likely to happen when the receiver is started after the sender) 
        Import the modified xml files to the low side, re-intialised files will be re-transmitted at the next scan
    """
    def _checkresetbydiffTags(DRef):
        #DRef.pathdict(directory)
        NbReinitFile=0
        try:
            for myfile in sorted(different):
                if(DRef.dict[myfile].tag == xfl.TAG_FILE):
                    NbReinitFile+=1
                    print ("        %s" % myfile)
                    for attr in (ATTR_LASTSEND, ATTR_NBSEND):
                        DRef.dict[myfile].set(attr, str(0))
        except KeyError:
            pass
            
        try:    
            for myfile in sorted(only1):
                if(DRef.dict[myfile].tag == xfl.TAG_FILE):
                    NbReinitFile+=1
                    print ("        %s" % myfile)
                    for attr in (ATTR_LASTSEND, ATTR_NBSEND):
                        DRef.dict[myfile].set(attr, str(0))
        except KeyError:
            print ("        %s ( extra?)" % myfile)
            pass #the tag may not exist if there are extra files in the path vs the ref file
        debugprint('Initialisation of %d file(s)' % NbReinitFile)
        return NbReinitFile
    
    DRef  = xfl.DirTree()
    DHaut = xfl.DirTree()
    MonAff=DispProgress.DisplayType()
    MonAff.StartIte()
    
    if not path(XFLFile).isfile():
        print (u"Sync file not found")
        return
    dirlist=DRef.read_recovery_file(XFLFile)
    if not dirlist:
        return
    basepath=dirlist[0][0]
    scanpathlist=DHaut.dir_walk(dirpath,followlinks=True,depth=2)
                
    dircount=0
    sessionFile=XFLFile
    sessRoot,ext=os.path.splitext(sessionFile)
    XFLFile1=XFLFile
    while dircount < (len(dirlist) and len(scanpathlist)):
        directory=dirlist[dircount][0]# get the directory name for this iteration
        dirlevel=dirlist[dircount][1]# and the directory level
        XFLFile1=sessRoot+'_'+str(dircount)+ext # create the session file to index the iteration files
        filelist=DRef.read_file(XFLFile1)
        
        DHaut.read_disk(scanpathlist[dircount],2, MonAff.AffChar)
        if directory==basepath:# the path to scan need to match the level of the folder in the structure
            relpath=""
        else:
            relpath=os.path.relpath(directory,basepath)
        same, different, only1, only2 = xfl.compare_DT(DHaut, DRef,1,relpath)
        #same, different, only1, only2 = xfl.compare_DT(DRef, DHaut,1,relpath)
        NbreinitFile=_checkresetbydiffTags(DRef)
        if NbreinitFile > 0:
            DRef.write_file(XFLFile1)
        dircount+=1
    print (u"Finished scan, %d files re-initialised" %NbreinitFile)
    
def resetbyPath(dirpath):
    """
    Initialisation of send within XML file along a path
    """
    return #not implemented
    DRef = xfl.DirTree()
    DRef.read_file(XFLFile)
    DRef.pathdict()
    if DRef.dict.has_key(dirpath):
        for attr in (ATTR_LASTSEND, ATTR_NBSEND):
            DRef.dict[dirpath].set(attr, str(0))
        DRef.write_file(XFLFile)
    else:
        print (u"Error : No path")

def analyse_options():

    """analyse command line  options .
    (helper module optparse)"""
    # create  optparse.OptionParser object , giving as string
    # "usage" the  docstring at the beginning of the file:
    parser = OptionParser_doc(usage="%prog [options] <fi directory>")
    parser.doc = __doc__

    # adds possible options:
    parser.add_option("-d", "--debug", action="store_true", dest="debug",\
        default=False, help="Debug Mode")
    #parser.add_option("-f","--folder",dest="src_path",default="arowsync",help= "source path for sync file")
    #if not sys.argv[0:]:
    (options, args) = parser.parse_args(sys.argv[0:])
        
        # check that there is only 1 action:
    nb_actions = 0
    #if len(args) < 1:
        #parser.error("You must specify exactly one file/directory. (%s -h for complete help)" % SCRIPT_NAME)
    return (options, args)

#--- MAIN ---------------------------------------------------------------------

if __name__ == "__main__":
    MODE_DEBUG=False
    (options, args) = analyse_options()
    #XFLFile=args[1]
    XFLFile=Fetch('Input the filename and path to the sync file', 'reception/arowsync/AROWsynchro.xml')
    if not path(XFLFile).isfile():
        print (u"Sync file not found")
        input("Press any key  to end..." )
        raise SystemExit(0)
       
    while True:
        print(u" Methods 1 & 2 should be performed on the Send side, Method 3 on the Receive side")
        method=Fetch(u'Choose method to re-initialise ? \n1 : by date of transmission failure \n2 : by regular expression search \n3 : by received tree analysis \n4 :Exit', '4')
        #method=Fetch('Which method to re-initialise ? \n1 : by date \n2 : by file path \n3 : by receive tree analysis \n4 : by regular expression \n5 :Exit', '1')
        if method == '1':
            MyResetDate=InputResetDate()
            resetbyDate(MyResetDate,XFLFile)
        if method == '2':
            print ("HowTo regular expressions http://www.python.org/doc/howto/")
            regexp=Fetch('Regular Expression ', ".*\.txt$")
            resetbyRegexp(regexp)
        if method == '3':
            dirpath=Fetch('Receive Path tree (e.g. "/reception", "c:\\reception" )', "/media/LinuxData/receive")
            #dirpath=Fetch('Receive Path tree  ', "c:\\reception")
            if os.path.isdir(dirpath):
                resetbyDiff(path(dirpath))
        if method == '4':
            break
        """
        if method == '2':
            path=Fetch('Path file ', 'c:\\NotReceivedFile.txt')
            resetbyPath(path)
        """
        
