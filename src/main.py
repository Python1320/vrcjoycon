
from pyjoycon import JoyCon, get_R_id, get_L_id, joycon
import logging,sys,os,threading,time
from pythonosc import dispatcher
from pythonosc import osc_server

from os import system
system("title VRChat Joy-Con OSC Connector")

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
server: osc_server.ThreadingOSCUDPServer = None

def startOSC():
	global server
	def joyconrumble_1_handler(address, *args):
		logging.debug("joyconrumble_1_handler %s %s", str(address), str(args))
		joyconrumble[0] = args[0]

	def joyconrumble_2_handler(address, *args):
		logging.debug("joyconrumble_2_handler %s %s", str(address), str(args))
		joyconrumble[1] = args[0]

	d = dispatcher.Dispatcher()
	d.map("/avatar/parameters/joyconrumble1", joyconrumble_1_handler)
	d.map("/avatar/parameters/joyconrumble2", joyconrumble_2_handler)
	server = osc_server.ThreadingOSCUDPServer(
		("127.0.0.1", 9001), d)
	print("Listening on default OSC port 8991 at {}".format(server.server_address))
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

if __name__ == "__main__":
	startOSC()
	startJoyCons()
	server.serve_forever()
	input("SHUTTING DOWN. PRESS ENTER TO CLOSE.")