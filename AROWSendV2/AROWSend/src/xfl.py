#!/usr/bin/python
"""
XFL - XML File List v0.06 2008-02-06 - Philippe Lagadec

A module to store directory trees and file information in XML
files, and to track changes in files and directories.

Project website: http://www.decalage.info/python/xfl

License: CeCILL v2, open-source (GPL compatible)
         see http://www.cecill.info/licences/Licence_CeCILL_V2-en.html
"""

#------------------------------------------------------------------------------
# CHANGELOG:
# 2006-08-04 v0.01 PL: - 1st version
# 2006-06-08 v0.03 PL
# 2007-08-15 v0.04 PL: - improved dir callback
# 2007-08-15 v0.05 PL: - added file callback, added element to callbacks
# 2008-02-06 v0.06 PL: - first public release
#2015-09-01  v0.07    -  added shutdown and first comparison speed-up code,support for xml levelling

#------------------------------------------------------------------------------
# TODO:
# + store timestamps with XML-Schema dateTime format
# - options to store owner
# + add simple methods like isfile, isdir, which take a path as arg
# + handle exceptions file-by-file and store them in the XML
# ? replace callback functions by DirTree methods which may be overloaded ?
# - allow callback functions for dirs and files (path + object)
# - DirTree options to handle owner, hash, ...

#--- IMPORTS ------------------------------------------------------------------
import sys, time,threading
import collections

# path module to easily handle files and dirs:
try:
    from path import *
except:
    raise ImportError ( u"the path module is not installed: " + u"see http://www.jorendorff.com/articles/python/path/")

### import LXML for pythonic XML:
##try:
##    import lxml.etree as ET
##except:
##    raise ImportError, "You must install lxml: http://codespeak.net/lxml"

# ElementTree for pythonic XML:
try:
#    if sys.hexversion >= 0x02050000:
        # ElementTree is included in the standard library since Python 2.5
    #from lxml import etree as ET
    import xml.etree.cElementTree as ET
 #   else:
        # external ElemenTree for Python <=2.4
except ImportError:
    import xml.elementtree.ElementTree as ET
    #raise ImportError, "the ElementTree module is not installed: "+ "see http://effbot.org/zone/element-index.htm"
import os,stat
from collections import  deque
try:
    from walkdir import  filtered_walk,dir_paths
except:
    print (u"the walkdir module is not installed: see http://walkdir.readthedocs.org/en/latest/")
    raise ImportError 
import itertools 

#--- CONSTANTS ----------------------------------------------------------------

# XML tags
TAG_DIRTREE = "dt"
TAG_DIR     = "d"
TAG_FILE    = "f"
#TAG_DIRTREE = "dirtree"
#TAG_DIR     = "dir"
#TAG_FILE    = "file"

# XML attributes
ATTR_NAME  = "n"
ATTR_TIME  = "t"
ATTR_MTIME = "mt"
ATTR_SIZE  = "s"
ATTR_OWNER = "o"
#ATTR_NAME  = "name"
#ATTR_TIME  = "time"
#ATTR_MTIME = "mtime"
#ATTR_SIZE  = "size"
#ATTR_OWNER = "owner"

#--- CLASSES ------------------------------------------------------------------

class DirTree:
    """
    class representing a tree of directories and files,
    that can be written or read from an XML file.
    """

    #def __init__(self, rootpath=""):
    def __init__(self, rootpath="",isStop=None):
        """
        DirTree constructor.
        """
        self.rootpath = path(rootpath)
        if isStop==None:
            self.isStop= threading.Event()
        else:    
            self.isStop=isStop
        #self.tree=ET

    def read_disk(self, pathlist, depth, callback_dir=None ):
        """
        to read the DirTree from the disk.
        """
        # creation of the root ElementTree:
        self.et = ET.Element(TAG_DIRTREE)
        #print self.et.tag
        if pathlist:
            self.rootpath = path(pathlist[0])
            level=pathlist[1]
        # name attribute = rootpath
        self.et.set(ATTR_NAME, self.rootpath)
        # time attribute = time of scan
        self.et.set(ATTR_TIME, str(time.time()))
        #e = ET.SubElement(self.et, TAG_DIR)
        #e.set(ATTR_NAME, self.rootpath)
        try:
            self._scan_dir(self.rootpath, level,depth,self.et, callback_dir)
            if self.et.get(ATTR_NAME)=="":
                #print self.tree.getroot()
                #self.et=ET.Element("a")
                pass
        except Exception as e:
            print(" Error : unable to scan the directory %s %s " % (self.rootpath,e))
            raise
    
        
    def _scan_dir(self, dir, dirlevel,depth, parent, callback_dir=None):
        """
        to scan a dir on the disk (recursive scan).
        (this is a private method)
        """
        # find just the files in the directory
        if callback_dir:
        	callback_dir(dir, parent)
        
        try:
            for f in iter(dir.files()):
                if(self.isStop.is_set()==False):
                #st=os.stat(f)
                #if stat.S_ISLNK(st.st_mode):
                    #if os.path.islink(f):
                    #linkto=os.readlink(f)
                    e = ET.SubElement(parent, TAG_FILE)
                    e.set(ATTR_NAME, f.name)
                    e.set(ATTR_SIZE, str(f.getsize()))
                    e.set(ATTR_MTIME, str(int(f.getmtime())))
                    """ # this isn't used yet
                    try:
                        #e.set(ATTR_OWNER, f.get_owner())
                    except:
                        pass
                    """
        
            for d in sorted(dir.dirs()):
                #print d
                if dirlevel <depth:
                    if d.files()or d.dirs():
                        e = ET.SubElement(parent, "l")
                        e.set(ATTR_NAME, d.name)
                    #continue
                else:
                    if d.files()or d.dirs():#don't tag empty folders
                        e = ET.SubElement(parent, TAG_DIR)
                        e.set(ATTR_NAME, d.name)
                        try:
                            self._scan_dir(d, dirlevel,depth,e, callback_dir)
                        except Exception as e:
                            print(u"Error : unable to scan the subdirectory %s " % d)
                            raise
                            
        except Exception as e:# the file may have been deleted
            #parent.remove(self.et)
            self.et.set(ATTR_NAME, "")
            self.et.set(ATTR_TIME, str(0))
    
    def write_file(self, filename, encode="utf-8"):
        """
        to write the DirTree in an XML file.
        """
        tree = ET.ElementTree(self.et)
        try:
        #tree.write(filename) # if compression used, parser auto detects on read from file ( not memeory)
            tree.write(filename, encoding=encode)
            #tree.write(filename, encoding=encode,compression =0 )# for lxml
        except Exception as e:
            print ("xml file write "+str(e))
            

    def read_file(self, filename):
        """
        to read the DirTree from an XML file.
        """
        flist=[]
        self.tree = ET.parse(filename)
        self.et = self.tree.getroot()
        self.rootpath = self.et.get(ATTR_NAME)
        if "AROWsynchro.xml" in filename:
            dirs=self.et.findall('file')
            for f in path(self.rootpath).files("AROWsynchro_*"):
                found=False
                for dirt in dirs:
                    if os.path.split(f)[1] == dirt.text:
                    #f= path(child.tag)
                    #g=os.path.join(self.rootpath,f)
                        found=True
                        flist.append(f)
                if not found:
                    os.remove(f)
        return flist       

    def pathdict(self,relpath):
        """
        to create a dictionary which indexes all objects by their paths.
        """
        self.dict = collections.OrderedDict()
       # self.dict = {}
        self._pathdict_dir(path(relpath), self.et)
        #self._pathdict_dir(path(""), self.et)

    def _pathdict_dir(self, base, et):
        """
        (private method)
        """
        
        levels = et.findall("l")
        for l in levels:
            dpath = base / l.get(ATTR_NAME)
            self.dict[dpath] = l
            self._pathdict_dir(dpath, l)
        dirs = et.findall(TAG_DIR)
        for d in dirs:
            dpath = base / d.get(ATTR_NAME)
            self.dict[dpath] = d
            self._pathdict_dir(dpath, d)
        files = et.findall(TAG_FILE)
        for f in files:
            fpath = base / f.get(ATTR_NAME)
            self.dict[fpath] = f
            
    def dir_walk(self,walkpath,followlinks,depth): 
        """ Make a list of directories under the top level
        The depth determines how many folders will be used in order to limit the memory used.
        """
        if not os.path.isdir(walkpath):
            raise IOError ( walkpath)
        level=0# if 0 it starts in and includes the root directory
        directoriesInLevels=[]
        directoriesInLevels.append((walkpath,level))
        level+=1
        #scan each level and make a list of base folders down to the depth requested, include links
        while level <=depth:
            for dirname in dir_paths(filtered_walk(str(walkpath),depth=level,min_depth=level,followlinks=followlinks)):
                directoriesInLevels.append((dirname,level))
            level+=1
            
        #for dirs in dir_paths(filtered_walk(walkpath,depth=depth,min_depth=depth,followlinks=followlinks)):
            #x.append((dirs,depth))
        #x=[dirs[0:len(dirs)] for dirs in dir_paths(filtered_walk(walkpath,depth =1,min_depth=1,followlinks=followlinks))]
        return directoriesInLevels
    
    def read_recovery_file(self,filename):
        """ Creates a directory tree from the top level recovery file, reads the directory depth and scans the other 
        recovery files """
        dirlist=[]
        try:
            tree = ET.parse(filename)
            root = tree.getroot()
            rootpath = path(root.get(ATTR_NAME))
            depth=int(path(root.get('depth','2')))
            #print rootpath
            while depth>1:
                try:
                    level=0
                    if len(root)>0:
                        for child in root.iter('file'):
                            #print child.text
                            f= path(child.text)
                            g=os.path.join(rootpath,f)
                            #recfilelist.append(g)
                            tree1 = ET.parse(g)
                            root1 = tree1.getroot()
                            rootpath1 = path(root1.get(ATTR_NAME))
                            #print rootpath1
                            dirlist.append((rootpath1,level))
                            level +=1
                            
                        depth-=1 
                    else:
                        dirlist.append((rootpath,0))# catch no folders in root
                               
                except IOError: # a recovery file may be missing
                    msg= "Missing recovery file %s - defaulting to full scan"%f
                    raise IOError(msg)
                      
            return dirlist
        
        
        except Exception as e:
            
            raise (e)
        

#--- FUNCTIONS ----------------------------------------------------------------

def compare_files (et1, et2):
    """
    to compare two files or dirs.
    returns True if files/dirs information are identical,
    False otherwise.
    """
    if et1.tag != et2.tag:
        return False
    if et1.tag == TAG_DIR:
        if et1.get(ATTR_NAME) != et2.get(ATTR_NAME):
            return False
        else:
            return True
    
    elif et1.tag == "l":
        if et1.get(ATTR_NAME) != et2.get(ATTR_NAME):
            return False
        else:
            return True
    
    elif et1.tag == TAG_FILE:
        if et1.get(ATTR_NAME) != et2.get(ATTR_NAME):
            return False
        if et1.get(ATTR_SIZE) != et2.get(ATTR_SIZE):
            return False
        if et1.get(ATTR_MTIME) != et2.get(ATTR_MTIME):
            return False
        else:
            return True
    else:
        raise TypeError

def compare_DT (dirTree1, dirTree2,LoopCount,relpath):
    """
    to compare two DirTrees, and report which files have changed.
    returns a tuple of 4 lists of paths: same files, different files,
    files only in dt1, files only in dt2.If it's the first time, just copy
    dirTree1 is the scanned, dirTree2 is the ref.
    """
    same=deque()
    #same = []
    different = deque()
    only1 = deque()
    #only2 = deque()
    #different = []
    #only1 = []
    only2 = []
    dirTree1.pathdict(relpath)
    paths1 = list(dirTree1.dict.keys())
    #print("")
    #paths1 = dirTree1.dict.keys()
    dirTree2.pathdict(relpath)
    paths2 = list(dirTree2.dict.keys())
    #paths2 = dirTree2.dict.keys()
        
    if LoopCount==0:
        same.extend(paths1[0:len(paths1)])
        #for p in iter(paths1):
            #same.append(p)
    else:        
        
        for p in iter(paths1):
            if str(p).find("AROWsynchro") !=-1:# ignore sync files
                if p in paths2:
                    paths2.remove(p)
                continue
            #print "paths 1 %d 2 %d"%(len(paths1),len(paths2))
            time.sleep(0)#relinquish time slice
            if p in paths2:
                # path is in the 2 DT, we have to compare file info
                f1 = dirTree1.dict[p]
                f2 = dirTree2.dict[p]
                if compare_files(f1, f2):
                    # files/dirs are the same
                    same.append(p)
                else:
                    different.append(p)
                paths2.remove(p)
            else:
                only1.append(p)
        #paths1.remove(p)
    
        # now paths2 should contain only files and dirs that weren't in paths1
        #only2.extend(paths2[0:len(paths2)])
        only2 = paths2
    return same, different, only1, only2

def callback_dir_print(dir, element):
    """
    sample callback function to print dir path.
    """
    print (dir)

def callback_dir_print2(dir, element):
    """
    sample callback function to print dir path.
    """
    lg=len(dir)
    if lg > 75:
        l1 = (75 - 3)/2
        l2 = 75 - l1 - 3
        pathdir = dir[0:l1]+"..."+dir[lg-l2:lg]
    else:
        pathdir=dir + (75-lg)*" "
    print (" %s\r" %pathdir,)

def callback_file_print(file, element):
    """
    sample callback function to print file path.
    """
    print (" - " + file)



#--- MAIN ---------------------------------------------------------------------

if __name__ == "__main__":

    if len(sys.argv) < 3:
        print (__doc__)
        print (u"usage: python %s <root path> <xml file> [previous xml file]" % path(sys.argv[0]).name)
        sys.exit(1)
    d = DirTree()
    d.read_disk(sys.argv[1], callback_dir_print, callback_file_print)
    d.write_file(sys.argv[2])
    if len(sys.argv)>3:
        d2 = DirTree()
        d2.read_file(sys.argv[3])
        same, different, only1, only2 = compare_DT(d, d2)
        print ("\nSAME:")
        for f in sorted(same):
            print ("  "+f)
        print (u"\nDIFFERENT:")
        for f in sorted(different):
            print ("  "+f)
        print (u"\nNEW:")
        for f in sorted(only1):
            print (u"  "+f)
        print (u"\nDELETED:")
        for f in sorted(only2):
            print (u"  "+f)



