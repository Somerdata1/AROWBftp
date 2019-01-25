#!/usr/bin/env python
"""
docstring
"""
import argparse
from binascii import hexlify, unhexlify
#import serial
import socket
import sys, os
import time


__author__ = 'Tim Brooks'
__date__ = '21 March 2012'
__version__ = '0.0.1'

som = 'S'
eom = '\r'

apn  = '0000'
arev = '0001'
asnl = '0002'
asnh = '0003'
acom = '0004' # commit number
ahw  = '0005' # hardware status

amacl   = '1000'
amach   = '1001'
aip     = '1002'
aipf    = '1003'
afdrp   = '1010'
aoddrp  = '1011'
addrusd = '1012'
addrhi  = '1013'

aopt  = '0100'

PORT = 10001


def wr_msg(addr,data):
#	ser.settimeout(5.0)
	if (data == ""):
		r_w = unhexlify('00')
		data = unhexlify('00000000')
	else:
		r_w = unhexlify('01')
		data = unhexlify(data)
	add = unhexlify(addr)
	msg = som+r_w+add+data+eom	
	#padd = hexlify(msg)[4:8]
	#pdata = hexlify(msg)[8:16]
	#print('writing {0}, add {1}, data {2}'.format(hexlify(msg), padd, pdata))
	ser.sendall(msg)
	red_msg = ""
	while len(red_msg) < 9 :
		red_msg += ser.recv(1024)				
	# if message format is wrong
	if (hexlify(red_msg)[:2] != '53' or hexlify(red_msg)[-2:] != '0d'): 
		# print
		print ('invalid message markers! red_msg = {0}'.format(hexlify(red_msg)))	
	padd = hexlify(red_msg)[4:8]
	pdata = hexlify(red_msg)[8:16]
	#print('read {0}, add {1}, data {2}'.format(hexlify(red_msg),padd,pdata))
	return padd,pdata

def main(args):
	"""
	run arow control with arguments
	"""
	parser = argparse.ArgumentParser(description='Controls and collects status from AROW prototype board')
	parser.add_argument('--version', 
		action='version', 
		version=__version__)
	#g = parser.add_argument_group(required=True)
	parser.add_argument('-t', '--tcp_rst', 
		default=False, 
		action = 'store_true', 
		help='reset the tcp stack'
	)
	parser.add_argument('-o', '--optics_rst', 
		default=False, 
		action = 'store_true', 
		help='reset the optical link'
	)
	parser.add_argument('-m', '--hightide_rst', 
		default=False, 
		action = 'store_true', 
		help='reset the ddr buffer high tide mark and the buffer overrun counters'
	)	
	parser.add_argument('-D', '--defaults', 
		default=False, 
		action = 'store_true', 
		help='set all NV registers to default values'
	)
	parser.add_argument('-s', '--status', 
		default=False, 
		action = 'store_true', 
		help='collect status'
	)
	parser.add_argument('-i', '--ipaddr', 
		nargs='?', 
		const = '0', 
		default='', 
		help='Sets (or gets when no IP address provided) the IP address of the data port. doted ip address string'
	)
	parser.add_argument('-M', '--mac', 
		nargs='?', 
		const = '0', 
		default='', 
		help='gets the MAC address of the data port. (sets the last 3 charchters `035`, for example)'
	)
	parser.add_argument('-a', '--addr', 
		default='', 
		help='hexadecimal (`0010` for example) representaion of the address of the register to access'
	)
	parser.add_argument('-d', '--data', 
		default='', 
		help='hexadecimal (`00100000` for example) representaion of the register to write. If no -d is specified, a read access is implied'
	)
	parser.add_argument('-H', '--HOST', 
		default='192.168.2.220', 
		help="IP address of control port. Default is '192.168.2.220'"
	)
	args = parser.parse_args(args)

	global ser
	ser=socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	ser.connect((args.HOST, PORT))
	#check len of add and data
	if (args.addr == ""):
		if (args.tcp_rst):
			radd,rdata = wr_msg(addr=aipf,data='00010000')
			radd,rdata = wr_msg(addr=aipf,data='00000000')
			print('tcp stack reset')

		if (args.hightide_rst):
			radd,rdata = wr_msg(addr=aipf,data='000e0000')
			radd,rdata = wr_msg(addr=aipf,data='00000000')
			print('high tide mark and buffer overrun count reset')

		if (args.optics_rst):
			radd,rdata = wr_msg(addr=aopt,data='00030000')
			radd,rdata = wr_msg(addr=aopt,data='00000000')
			print('optical link reset')

		if (args.defaults): 
			print("setting defaults: ")
			radd,rdata = wr_msg(addr=aopt,data='00000000')
			print("."),
			#radd,rdata = wr_msg(addr=amacl,data='00000000') # mac address
			#radd,rdata = wr_msg(addr=aip,data='00000000') # ipaddress
			radd,rdata = wr_msg(addr=ahw,data='00000000')
			print("."),
			radd,rdata = wr_msg(addr=aipf,data='00000000')
			print("."),
			radd,rdata = wr_msg(addr=aopt,data='00000000')
			print("."),
			radd,rdata = wr_msg(addr='2400',data='00000000')
			print("."),
			radd,rdata = wr_msg(addr='2404',data='10000000')
			print("."),
			radd,rdata = wr_msg(addr='2408',data='10000000')
			print("."),
			radd,rdata = wr_msg(addr='240C',data='80000000')
			print("."),
			radd,rdata = wr_msg(addr='2410',data='60000000')
			print("."),
			radd,rdata = wr_msg(addr='2414',data='000005ee')
			print("."),
			radd,rdata = wr_msg(addr='2418',data='000005ee')
			print("."),
			radd,rdata = wr_msg(addr='2700',data='00000000')
			print("."),
			radd,rdata = wr_msg(addr='2704',data='00000000')
			print("."),
			radd,rdata = wr_msg(addr='2708',data='80000000')
			print("."),
			radd,rdata = wr_msg(addr='270C',data='00000000')
			print("."),
			print("defaults set. ")#\n\tHave you set the IP address and mac address?")

		if (args.ipaddr == '0'):
			#read IP address
			radd,rdata = wr_msg(addr=aip,data="")		
			#print((radd))		
			print("data port's ip address is currently {0}".format(socket.inet_ntoa(unhexlify(rdata))))

		elif (args.ipaddr != ''):
			#try to set IP address
			try:
				socket.inet_aton(args.ipaddr)
				i = socket.inet_aton(args.ipaddr)
				#print(hexlify(i))
				radd,rdata = wr_msg(addr=aip,data=hexlify(i))
				print("data port's ip address is now set to {0}".format(socket.inet_ntoa(unhexlify(rdata))))
			except:
				print('{0} is an invalid IP address\n\tIP address not set!'.format(args.ipaddr))

		if (args.mac == '0'):
			radd,macl = wr_msg(addr=amacl,data="")
			radd,mach = wr_msg(addr=amach,data="")
			mac = mach[4:8]+macl	
			blocks = [mac[x:x+2] for x in xrange(0, len(mac), 2)]
			fmac = ':'.join(blocks)
			print('data port MAC address: {0}'.format(fmac))

		elif (args.mac != ''):
			i = '10000'
			#print (i)
			i += args.mac
			#print (i)
			radd,rdata = wr_msg(addr=amacl,data=i)
			#print (rdata)
			radd,rdata = wr_msg(addr=amacl,data='00000000')
			radd,macl = wr_msg(addr=amacl,data="")
			radd,mach = wr_msg(addr=amach,data="")
			mac = mach[4:8]+macl	
			blocks = [mac[x:x+2] for x in xrange(0, len(mac), 2)]
			fmac = ':'.join(blocks)
			print('data port MAC address set to: {0}'.format(fmac))
			
		if (args.status):
			#read part number, serial number, firmware revision, mac address, IP address
			radd,pn = wr_msg(addr=apn,data="")
			print('part number: {0}'.format(pn))
			radd,snl = wr_msg(addr=asnl,data="")
			radd,snh = wr_msg(addr=asnh,data="")
			print('serial number: {0}{1}'.format(snh,snl))
			radd,fw = wr_msg(addr=arev,data="")				
			rev= (int(fw,16)&0xFFFF) >> 0
			ver= (int(fw,16)&0xFFFF0000) >> 16
			radd,cmt = wr_msg(addr=acom,data="")				
			print('firmware version: {0} revision: {1} commit: 0x{2}'.format(ver,rev,cmt[1:])) #.lstrip('0')
			radd,macl = wr_msg(addr=amacl,data="")
			radd,mach = wr_msg(addr=amach,data="")
			mac = mach[4:8]+macl	
			blocks = [mac[x:x+2] for x in xrange(0, len(mac), 2)]
			fmac = ':'.join(blocks)
			print('MAC address: {0}'.format(fmac))
			radd,rdata = wr_msg(addr=aip,data="")		
			print("IP address: {0}".format(socket.inet_ntoa(unhexlify(rdata))))
			radd,rdata = wr_msg(addr=ahw,data="")
			print('hardwar regs: {0}'.format(rdata))	
			if (int(rdata,16)& 0x1 ) == 1:
				module_hi = 'High'
			else:
				module_hi = 'low'
			print('module is {0}, '.format(module_hi))
			if (int(rdata,16)& 0x2 )>> 1 == 1:
				module_live_p = 'Live'
			else:
				module_live_p = 'Backup'
			print('module in {0} position, '.format(module_live_p))
			if (int(rdata,16)& 0x4 )>>2 == 1:
				module_live = 'live'
			else:
				module_live = 'backup'
			print('module is a {0} module, '.format(module_live))
			if (int(rdata,16)& 0x8 )>>3 == 1:
				module_lb_up = 'up'
			else:
				module_lb_up = 'down'
			print('live-backup link is {0}, '.format(module_lb_up))
			if ((int(rdata,16)&0x00010000)>>16) == 1:
				module_std_aln = 'standalone'
			else:
				module_std_aln = 'redundant'
			print('module is in a {0} system'.format(module_std_aln))
			print(" ddr used| Hightide|fifo drops|ddr drops| TCP| opt| timestamp ")
			print("---------+---------+----------+---------+----+----+----------------------------")
			#loop status?
			hightide = 0
			from datetime import datetime
			colorred = "\033[01;91m{0}\033[00m"
			colorgrn = "\033[1;92m{0}\033[00m"
			while True:
				# read flags, current buffer level, hightide mark, number of dropped packets.
				radd,ddcnt = wr_msg(addr=aoddrp,data="")
				radd,fdcnt = wr_msg(addr=afdrp,data="")
				radd,hitide = wr_msg(addr=addrhi,data="")
				radd,used = wr_msg(addr=addrusd,data="")
				print('{0}'.format(used)),
				print('|{0}'.format(hitide)),
				print('| {0}'.format(fdcnt)),
				print('|{0}'.format(ddcnt)),
				radd,ipf = wr_msg(addr=aipf,data="")
				if (int(ipf,16)& 0x1) >>0 == 1:
					tcp_up = '1'
					print '|' + colorgrn.format('{0}'.format(tcp_up)),
				else:
					tcp_up = '0'
					print ('|{0}'.format(tcp_up)),					
				if (int(ipf,16)& 0x8) >>3 == 1:
					DDR_full = '1'
					print colorred.format('{0}'.format(DDR_full)),
				else:
					DDR_full = '0'
					print colorgrn.format('{0}'.format(DDR_full)),
				#if (int(ipf,16)& 0x2) >>1 == 1:
				#	sfp_pres = '1'
				#else:
				#	sfp_pres = '0'
				#print('{0}'.format(sfp_pres)),
				#if (int(ipf,16)& 0x4) >>2 == 1:
				#	link_up = '1'
				#else:
				#	link_up = '0'
				#print('{0}'.format(link_up)),
				radd,opt = wr_msg(addr=aopt,data="")
				if (int(opt,16)& 0x1) >>0 == 1:
					L_up = '1'
					print '|'+colorgrn.format('1'),
				else:
					L_up = '0'
					print '|'+colorred.format('0'),
				if (int(opt,16)& 0x2) >>1 == 1:
					B_up = '1'
					print colorgrn.format('1'),
				else:
					print colorred.format('0'),
					B_up = '0'
				if (int(hitide,16)>hightide or DDR_full == '1'):
					hightide = int(hitide,16)
					print('| {0}'.format(datetime.now()))
				else:
					print('| {0}\r'.format(datetime.now())),


			
	elif len(args.addr) == 4: 
		if (args.data == ""):
			# read command			
			print ('read status')
			radd,rdata = wr_msg(args.addr, args.data)
			print ('read address 0x{0}, got register 0x{1}'.format(radd,rdata))
		elif (len(args.data) == 8):
			#write cmd to serial
			print ('write command')
			radd,rdata = wr_msg(args.addr, args.data)
			print ('wrote 0x{1} to address 0x{0}'.format(radd,rdata))
		else:
			#data length is wrong
			print ('expecting 8 characters for data option. got {0} length {1}'.format(args.data, len(args.data)))
	else:
		print ('expecting 4 characters for address option. got {0} length {1}'.format(args.addr, len(args.addr)))				
	ser.close() 
	print('serial connection closed')
	
	
if __name__ == '__main__':
	main(sys.argv[1:])
