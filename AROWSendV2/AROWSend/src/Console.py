#!/usr/local/bin/python

"""
----------------------------------------------------------------------------
Console: to  simplify the display of strings to the console.
----------------------------------------------------------------------------


"""

#------------------------------------------------------------------------------

#------------------------------------------------------------------------------

#=== IMPORTS ==================================================================

import sys

#=== CONSTANTS ===============================================================

global _char_temp
_char_temp = 0


#------------------------------------------------------------------------------
# print_console
#-------------------
def print_console (msg, errors='replace', newline=True):
    """
    To send a correct string containing accented characters to a command line terminal in Windows 
    (conversion to code page "cp850")
    Post as received if not  Windows.

    errors: cf. help module codecs
    newline: indicates adding newline character to the line
    """
    if sys.platform == 'win32':
        print (type(msg))
        if type(msg) is str:
        #if type(msg) == 'str':
            # if a string, assume  latin_1
            # conversion to unicode:
            msg = msg.decode('latin_1', errors)
        msg = str(msg.encode('cp850', errors))
    if newline:
        print (msg)
    else:
        print (msg,)

#------------------------------------------------------------------------------
# Print
#-------------------
def Print (msg):
    """Send a string to the  console, pass to the next line,as print
    If  Print_temp was called previously , later characters are truncated to obtain a correct display
        """
    global _char_temp
    if _char_temp > len(msg):
        print (" "*_char_temp + "\r",)
    _char_temp = 0
    print_console(msg)

#------------------------------------------------------------------------------
# Print_temp
#-------------------
def Print_temp (sequence, size_max=79, NL=False):
    """post a temporary string to the console, minus the previous line and truncated to less than size_max.
    If  Print_temp was used previously , final characters are erased to obtain
    a correct display.
    """
    global _char_temp
    lc = len(sequence)
    if lc > size_max:
        # if the sequence is too long, truncate to 2 and add .... to the middle
        
        l1 = (size_max - 3) / 2
        l2 = size_max - l1 - 3
        sequence = sequence[0:l1] + "..." + sequence[lc-l2:lc]
        lc = len(sequence)
        if lc != size_max:
            raise ValueError( "error in Print_temp(): lc=%d" % lc)
    if _char_temp > lc:
        print (u" "*_char_temp + u"\r",)
    _char_temp = lc
    print_console (sequence + u"\r", newline=NL)



#------------------------------------------------------------------------------
# MAIN
#-------------------
if __name__ == "__main__":
    Print (u"test for long string: " + "a"*200)
    Print_temp("temp long string...")
    Print_temp("short string")
    print ("")
    Print_temp("temp long string...")
    Print("following")
    Print_temp("string too long: "+"a"*100)
    print ("")
    Print_temp("accented string very long...")
    Print_temp("string truncated.")
    print ("")


