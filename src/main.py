#/usr/bin/env python3

from pyjoycon import JoyCon, get_R_id, get_L_id, joycon
import logging,sys,os,threading,time
from pythonosc import dispatcher
from pythonosc import osc_server
from pythonosc.udp_client import SimpleUDPClient
from pprint import pprint
import asyncio
import sys
from contextlib import suppress
from asynccmd import Cmd


from os import system
system("title VRChat Joy-Con OSC Connector")

import argparse




class Commander(Cmd):

	def __init__(self, intro, prompt):


		if sys.platform == 'win32':
			loop = asyncio.ProactorEventLoop()
			mode = "Run"
		else:
			loop = asyncio.get_event_loop()
			mode = "Reader"

		super().__init__(mode=mode)
		self.intro = intro
		self.prompt = prompt
		self.loop = None

	def do_sleep(self, arg):
		"""
		Our example cmd-command-method for sleep. sleep <arg>
		:param arg: contain args that go after command
		:return: None
		"""
		self.loop.create_task(sleep_n_print(self.loop, arg))

	def do_tasks(self, arg):
		"""
		Our example method. Type "tasks <arg>"
		:param arg: contain args that go after command
		:return: None
		"""
		for task in asyncio.Task.all_tasks(loop=self.loop):
			print(task)

	def start(self, loop=None):
		self.loop = loop
		super().cmdloop(loop)




def is_port(string):
	try:
		value = int(string)
	except Exception:
		value=0
	if not (value>0 and value<65535):
		msg = "%r is not a valid port number" % string
		raise argparse.ArgumentTypeError(msg)
	return value

logging.basicConfig(level=logging.DEBUG)

parser = argparse.ArgumentParser(description='VRChat Joy-Con OSC Connector')
parser.add_argument('--listen', type=str, help='Listening port. By default only IPv4 localhost.',default="127.0.0.1")
parser.add_argument('--port', type=is_port, help='listening port',default=9001)
parser.add_argument('--verbose', help='Verbose mode',action="store_true")
parser.add_argument('--to-port', type=is_port, help='(advanced) for relaying the rest of OSC messages to another processor')
parser.add_argument('--to-ip', type=str, help='(advanced) for relaying the rest of OSC messages to another processor.',default="127.0.0.1")
args = parser.parse_args()


joyconrumble = [False, False]
joycons=[False,False]
lock = threading.Lock()

def headpatter_thread(conGetter, conid):
	for i in range(13):
		joycon_id = False

		while True:
			with lock:
				joycon_id = conGetter()
			if joycon_id and joycon_id[0]:
				break
			time.sleep(0.4)

		id = conid-1
		name = conid == 1 and "LEFT" or "RIGHT"
		with lock:
			joycon = JoyCon(*joycon_id)
			joycons[id]=joycon

		print("\nFound JoyCon", name,"\n")
		with lock:
			joycon.set_player_lamp_on(conid) # required to keep controller running

		logging.debug("Testing vibration")
		time.sleep(1)
		with lock:
			joycon.rumble_simple()
		time.sleep(1.5)
		with lock:
			joycon.rumble_simple()
		time.sleep(0.5)
		with lock:
			joycon.rumble_stop()
		logging.debug("Vibrated")
		time.sleep(0.5)
		while joycon.connected():
			time.sleep(0.4) # TODO: Signaling, sleep otherwise
			pat_status = joyconrumble[id]
			if pat_status:
				with lock:
					joycon.rumble_simple()
				print("Vibrating", name)

			elif pat_status is not False:
				joyconrumble[id] = False
				print("STOP", name)
				with lock:
					joycon.rumble_stop()
		print("LOST JOYCON",name)
		with lock:
			del joycon
			joycons[id]=False
	print("TOO MANY FAILURES, CLOSING")

threads = []
server: osc_server.AsyncIOOSCUDPServer = None
client: SimpleUDPClient = None

async def startOSC(loop):
	global server,client
	def joyconrumble_1_handler(address, *args):
		logging.debug("joyconrumble_1_handler %s %s", str(address), str(args))
		joyconrumble[0] = args[0] if (type(args[0]) == int or type(args[0]) == float) else args[0][0]

	def joyconrumble_2_handler(address, *args):
		logging.debug("joyconrumble_2_handler %s %s", str(address), str(args))
#		joyconrumble[1] = args[0][0]
		joyconrumble[1] = args[0] if (type(args[0]) == int or type(args[0]) == float) else args[0][0]
	def joyconrumble_3_handler(key,*params):
		if client:
			client.send_message("/brr", float(params[0]))
		if args.verbose:
			print("RELAY: ",key,params)
	def default_handler(key,*vals):
		if client:
			client.send_message(key, vals)
		if args.verbose:
			print("RELAY: ",key,vals)
			
	d = dispatcher.Dispatcher()
	d.map("/avatar/parameters/joyconrumble1", joyconrumble_1_handler)
	d.map("/avatar/parameters/joyconrumble2", joyconrumble_2_handler)
	if args.to_port or args.verbose:
		d.map("/avatar/parameters/joyconrumble3", joyconrumble_3_handler)
#		d.set_default_handler(default_handler)

	server = osc_server.AsyncIOOSCUDPServer(
		(args.listen, args.port), d, loop)
	transport, protocol = await server.create_serve_endpoint()  # Create datagram endpoint and start serving
	print("Listening on host,port {}".format(transport))
	print("")
	if args.to_port:
		client = SimpleUDPClient(args.to_ip, args.to_port)
		print("Relaying other messages to {} on port {}".format(args.to_ip,args.to_port))
		print("")

def watchdog():
	while True:
		anyAlive=False
		for t in threads:
			t.join(0.2)
			if t.is_alive():
				anyAlive=True
		if not anyAlive:
			server.shutdown()
			print("\nFATAL: Lost all JoyCon threads\n")
			return
		"""
		
		hadAny=False
		anyAlive=False
		for id,c in enumerate(joycons):
			if c==False:
				continue
			hadAny=True

			# TODO: Race condition here?
			c._update_input_report_thread.join(0.2)
			if c._update_input_report_thread.is_alive():
				anyAlive=True

		if hadAny and not anyAlive:
			server.shutdown()
			print("\nFATAL: Lost all JoyCons\n")
			return
		
		"""

def startJoyCons():
	print("Attempting to locate joycons")
	for conGetter, id in [(get_L_id, 1), (get_R_id, 2)]:
		x = threading.Thread(target=headpatter_thread,
							 args=(conGetter, id), daemon=True,name="joyconController"+str(id))
		x.start()
		threads.append(x)

	# Watchdog
	x = threading.Thread(target=watchdog,
							args=(), daemon=True,name="watchdog")
	x.start()

async def amain():

	if sys.platform == 'win32':
		loop = asyncio.ProactorEventLoop()
	else:
		loop = asyncio.get_event_loop()
	
	await startOSC(loop)
	startJoyCons()

	# asyncio.set_event_loop(loop)
	cmd = Commander(intro="This is example", prompt="example> ")
	cmd.start(loop)
	
	shutdown_everything=False
	while not shutdown_everything:
		await asyncio.sleep(1)

	#transport.close()

if __name__ == "__main__":
	asyncio.run(amain())
	#server.serve_forever()
	input("SHUTTING DOWN. PRESS ENTER TO CLOSE.")
