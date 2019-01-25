#!/usr/bin/python

"""
----------------------------------------------------------------------------
OptionParser_doc: Class to manage command line options.
----------------------------------------------------------------------------

Inherited from OptionParser to modify its display.

Copyright Philippe Lagadec 2005-2007
Auteur:
- Philippe Lagadec (PL) - philippe.lagadec(a)laposte.net

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

from optparse import OptionParser


#------------------------------------------------------------------------------
# classe OptionParser_doc
#--------------------------

class OptionParser_doc (OptionParser):
	"""class inherited from optparse.OptionParser, that adds display of 
	the file docstring before the normal help of OptionParser."""
	
	def print_help(self, docfile=None):
		"Display the file docstring then help from OptionParser."
		print (self.doc)
		OptionParser.print_help(self, docfile)

