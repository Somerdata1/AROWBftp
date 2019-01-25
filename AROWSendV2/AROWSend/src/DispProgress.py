#!/usr/local/bin/python

"""
----------------------------------------------------------------------------
TraitEncours: Class to display current process pattern (hourglass in TXT).
----------------------------------------------------------------------------

version 0.03 du 24/05/2008

Auteur:
- Laurent VILLEMIN (LV) - Laurent.villemin(a)laposte.net

This software is governed by the CeCILL license under French law and
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
#------------------------------------------------------------------------------
# HISTORY:
# 04/04/2008 v0.01 LV : - version 1
# 05/04/2008 v0.02 LV : 
# 24/05/2008 v0.03 LV : added message truncationre if requeseted
import time,sys

class DisplayType:
    """
        Module for displaying various patterns
        or text version of a graphical hourglass
        Displays available:
            a single character of a string displayed in a loop
            a string scrolling Right to Left
            a string scrolling Left  to Right
            a flashing string
            ...
    """
# Local Variables 
# __chaine : string containing the display pattern
# __mod : length of the string, used for rotating R/L
# __temps : date of last display (optimised display necessary)

    def __init__(self):
        """
        Initialisation default pattern
        """
        self.__string='/-\|'
        self.__mod=len(self.__string)
        self.__temps=time.time()

    def NewString(self, newchaine, LgMax=79, truncate=False):
        """
        New pattern alllocation
        Control of  LgMax parameter
        """

        lg=len(newchaine)
        if truncate==True and lg > LgMax:
            # String too long cut in half and insert  "..." in middle
            l1 = (LgMax - 3) / 2
            l2 = LgMax - l1 - 3
            self.__string = newchaine[0:l1] + "..." + newchaine[lg-l2:lg]
        else:
            self.__string=newchaine
        self.__mod=len(self.__string)

    def StartIte(self,val=None):
        """
        start loop counter
        """
        if val==None:
            self.__ite=0
        else:
            self.__ite=val

    def __IncrementIte(self):
        """
        Increment counter
        """
        self.__ite+=1
        return(self.__ite)

    def __ChDecalDG(self):
        """
        offset for right to left string
        """
        pos=0
        newchaine=''
        while pos <= self.__mod:
            newchaine+=self.__string[(pos-1)%self.__mod]
            pos+=1
        return(newchaine)

    def __ChDecalGD(self):
        """
        offset for string left to right
        """
        pos=0
        newchaine=''
        while pos <= self.__mod:
            newchaine+=self.__string[(pos+1)%self.__mod]
            pos+=1
        return(newchaine)

    def AffChar(self, *args):
        """
        display character to character
        """
        CurrentTime=time.time()
        if CurrentTime-self.__temps > 0.2:
            self.__ite=self.__IncrementIte()
            print (u"%s\r" %self.__string[self.__ite%self.__mod],)
            sys.stdout.flush()
            self.__temps=CurrentTime

    def AffLigneDG(self, *args):
        """
        Display a line according to the "chasing" mode right to left
        """
        CurrentTime=time.time()
        if time.time()-self.__temps > 0.2:
            self.__ite=self.__IncrementIte()
            self.__string=self.__ChDecalGD()
            print(u"%s\r" %self.__string,)
            sys.stdout.flush()
            self.__temps=CurrentTime


    def AffLigneGD(self, *args):
        """
        Display a line according to the "chasing" mode left to right
        """
        CurrentTime=time.time()
        if time.time()-self.__temps > 0.2:
            self.__ite=self.__IncrementIte()
            self.__string=self.__ChDecalDG()
            print(u"%s\r" %self.__string,)
            sys.stdout.flush()
            self.__temps=CurrentTime

    def AffLigneBlink(self, *args):
        """
        Display line in flashing mode
        """
        CurrentTime=time.time()
        if time.time()-self.__temps > 0.4:
            self.__ite=self.__IncrementIte()
            if (self.__ite%2):
                print ("%s\r" %self.__string,)
            else:
                print (" "*self.__mod + "\r",)
            sys.stdout.flush()
            self.__temps=CurrentTime
if __name__ == '__main__':
    print (u"Display module pattern indicates a 'Process in progress'")
    temp=0
    a=DisplayType()
    a.StartIte()
    print (u"Working (character)...")
    while temp < 30:
        temp+=1
        a.AffChar()
        time.sleep(0.1)
    a.StartIte()
    a.NewString('>12345  ')
    print (u"Working (Line Left to Right)...")
    while temp < 60:
        temp+=1
        a.AffLigneGD()
        time.sleep(0.2)
    a.StartIte()
    a.NewString('12345<  ')
    print (u"Working (Line Right to Left)...")
    while temp < 90:
        temp+=1
        a.AffLigneDG()
        time.sleep(0.2)
    a.NewString('Blinking')
    print (u"Working (flashing)...")
    while temp < 120:
        temp+=1
        a.AffLigneBlink()
        time.sleep(0.2)
    a.NewString(u'Blinking message too long for my small terminal which can only display 60 rows. So I must truncate it in the middle', LgMax=59, truncate=True)
    print (u"Working (truncation)")
    while temp < 150:
        temp+=1
        a.AffLigneBlink()
        time.sleep(0.2)

    ToQuit=input("Press enter to exit")


