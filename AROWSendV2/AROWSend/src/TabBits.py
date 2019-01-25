#!/usr/bin/python

"""
----------------------------------------------------------------------------
TabBits: Class to manipulate a large bit array.
----------------------------------------------------------------------------

version 0.03 du 08/07/2005


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

# HISTORIQUE:
# 03/07/2005 v0.01: - Initial version
# 06/07/2005 v0.02: - replacement of buffer string by an array object
# 08/07/2005 v0.03: - add bit counting to 1

# TODO:
# + check if index is out of table range (<0 or >N-1)
# - import string or file or boolean list
# - export through string or file
# - interface Python table
# - dynamic size

import array

#------------------------------------------------------------------------------
# classe TabBits
#--------------------------

class TabBits:
	"""Class manipulating a large bit table."""
	
	def __init__ (self, size, buffer=None, readFile=None):
		"""TabBits Constructor.
		
		size: number of bits in the array.
		buffer: string used to fill the array (optional).
		readFile: file used to fill the array (optional).
		"""
		self._size = size
		self.nb_true = 0    # number of bits � 1, 0 by default
		if buffer == None and readFile == None:
			# calculate the number of octets needed for the buffer
			buffer_size = (size+7)/8
			# create buffer of this size, initialise to zero:
			# self._buffer = chr(0)*buffer_size
			# create an array object of Bytes
			self._buffer = array.array('B')
			# add N null elements
			# (to optimise: loop to avoid creating a list ?)
			self._buffer.fromlist([0]*buffer_size)
		else:
			# don't create it again...
			raise NotImplementedError

	def get (self, indexBit):
		"""Reads a bit into the array. Returns a  bool."""
		# octet index corresponds to buffer and offset of  bit in octet
		indexOctet, remainder =  divmod (indexBit, 8)
		octet = self._buffer[indexOctet]
		mask = 1 << remainder
		bit = octet & mask
		# return a bool
		return bool(bit)

	def set (self, indexBit, value):
		"""to write a bit into the array."""
		# make sure the value is boolean
		value = bool(value)
		# index of the octet corresponding shift in the buffer and the bit in the octet
		indexOctet, remainder =  divmod (indexBit, 8)
		octet = self._buffer[indexOctet]
		mask = 1 << remainder
		old_value = bool(octet & mask)
		if value == True and old_value == False:
			# we must position the bit to 1
			octet = octet | mask
			self._buffer[indexOctet] = octet
			self.nb_true += 1
		elif value == False and old_value == True:
			# must position the bit to 0
			mask = 0xFF ^ mask
			octet = octet & mask
			self._buffer[indexOctet] = octet
			self.nb_true -= 1

	def __str__ (self):
		"""to convert TabBits in a string containing 0's and 1's."""
		string = ""
		for i in range(0, self._size):
			bit = self.get(i)
			if bit:
				string += "1"
			else:
				string += "0"
		return string
		
if __name__ == "__main__":
	# some  tests if the module is launched directly
	N=100
	tb = TabBits(N)
	print (str(tb))
	tb.set(2, True)
	tb.set(7, True)
	tb.set(N-1, True)
	print (str(tb))
	print ("tb[0] = %d" % tb.get(0))
	print ("tb[2] = %d" % tb.get(2))
	print ("tb[%d] = %d" % (N-1, tb.get(N-1)))
	print ("size bits = %d" % tb._size)
	print ("size buffer = %d" % len(tb._buffer))
			
		
