#!/usr/bin/env python3

from configparser import ConfigParser
import coloredlogs, logging
from pathlib import Path

log = logging.getLogger("VRCJOYCON")
configpath = Path("config.ini")
if not configpath.exists():
	configpath = Path("src/config.ini")
	if not configpath.exists():
		configpath = Path("../config.ini")
		if not configpath.exists():
			log.critical("Could not find config.ini")


def setup_config():
	global config, debug, verbose

	config = ConfigParser(default_section="DONOTUSE")
	config.read(configpath)

	debug = config.getboolean("main", "debug")
	verbose = config.getboolean("main", "verbose")
	coloredlogs.install(level=logging.DEBUG if debug else logging.INFO)
	if debug:
		log.debug("DEBUG ON")


setup_config()


from pyjoycon import JoyCon, get_device_ids, joycon
import sys  # , os, threading, time, json
from pythonosc import dispatcher, osc_server
from pythonosc.udp_client import SimpleUDPClient

from functools import reduce
import operator

# from pprint import pprint
import asyncio, argparse, sys, typing, functools

# from contextlib import suppress
# from asynccmd import Cmd
from aioconsole import AsynchronousCli
from os import system

if sys.platform == "win32":
	system("title ChilloutVR/VRChat Joy-Con OSC Connector")
else:
	print("\33]0;ChilloutVR/VRChat Joy-Con OSC Connector\a")


autorestart = config.getboolean("main", "autorestart")
notele = config.getboolean("main", "notele")
log.debug("Debug: %s", debug)
log.debug("verbose: %s", verbose)
log.debug("autorestart: %s", autorestart)
log.debug("notele: %s", notele)
listen_ip = config["listen"]["ip"]
listen_port = int(config["listen"]["port"])

osc_output = SimpleUDPClient(config["osc_output"]["ip"],int(config["osc_output"]["port"])) if config["osc_output"]["enabled"] else None

relay = config["relay"]
relay_port = int(relay["port"])
controllers = config["controllers"]
if verbose:
	for key in controllers:
		print("Finding controller ", key)


def config_save():
	with configpath.open("w") as configfile:
		config.write(configfile)


shutdown_everything = False


parser = argparse.ArgumentParser(description="VRChat Joy-Con OSC Connector")
args = parser.parse_args()

def map_range(x, in_min, in_max, out_min, out_max):
  return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min

def map_float_remap(path):
	data=path.split(":",maxsplit=5)
	myid=data[0]
	if myid != "float_remap":
		return None
	(in_min, in_max, out_min, out_max)=map(float,data[1:5])
	osc_path=data[5]

	def remapper(input):
		return map_range(input,in_min, in_max, out_min, out_max)
	return (remapper,osc_path)

def map_int_remap(path):
	data=path.split(":",maxsplit=5)
	myid=data[0]
	if myid != "int_remap":
		return None
	(in_min, in_max, out_min, out_max)=map(float,data[1:5])
	osc_path=data[5]

	def remapper(input):
		return int(map_range(input,in_min, in_max, out_min, out_max))
	return (remapper,osc_path)

def map_float(path):
	data=path.split(":",maxsplit=1)
	myid=data[0]
	if myid != "float":
		return None
	osc_path=data[1]

	def remapper(input):
		return float(input)
	
	return (remapper,osc_path)

def map_int(path):
	data=path.split(":",maxsplit=1)
	myid=data[0]
	if myid != "int":
		return None
	osc_path=data[1]

	def remapper(input):
		return int(input)
	
	return (remapper,osc_path)
	
uniqueifiers={}
def map_toggle(path):
	data=path.split(":",maxsplit=3)
	myid=data[0]
	if myid != "toggle":
		return None
	(myid,uniqueifier,output_type,osc_path)=data
	uniqueifiers[uniqueifier]=[False,True]
	def remapper(input):
		input=bool(input)

		toggledata=uniqueifiers[uniqueifier]
		(toggle,released_key)=toggledata
		
		if input:
			if released_key:
				toggle=not toggle
				toggledata[0]=toggle
				toggledata[1]=False
		elif not released_key:
			toggledata[1]=True

		if output_type=='bool':
			return bool(toggle)
		elif output_type=='int':
			return int(toggle)
		elif output_type=='float':
			return float(toggle)
		else:
			log.error(f"INVALID OUTPUT TYPE (from config.ini): {output_type}")
			return bool(toggle)
		
	return (remapper,osc_path)
	
def map_bool(path):
	data=path.split(":",maxsplit=1)
	myid=data[0]
	if myid != "bool":
		return None
	osc_path=data[1]

	def remapper(input):
		return bool(input)
	
	return (remapper,osc_path)

REMAPPERS = [map_toggle,map_float_remap,map_int_remap,map_float,map_int,map_bool]

class JoyConX(JoyCon):

	current_rumble = False
	rumble_event = None
	status_getters = False

	def __init__(self, osc_outputs, *identifiers):
		super().__init__(*identifiers)
		self.last_gyro_x = 0
		self.last_a = 0
		self.rumble_event = asyncio.Event()
		self.osc_output = osc_output
		self._build_osc(osc_outputs)
		if osc_outputs:
			self.register_update_hook(lambda _: self.on_update_thread())
		
	def _build_osc(self,osc_outputs):
		self.osc_outputs = []
		status_getters = self.get_status_getters()
		for controller_path,osc_definition in osc_outputs.items():
			mapper=None
			osc_path = osc_definition

			for remapper in REMAPPERS:
				ret = remapper(osc_definition)
				if ret:
					log.info("remapping as requested: %s",osc_definition)
					assert not mapper,"two mappers taking ownership"
					(mapper,osc_path) = ret
				
			controller_path = controller_path.split(".")
			try:
				getter = reduce(operator.getitem, controller_path, status_getters)
				if not callable(getter):
					log.error("Omitting %s for %s: not a function",controller_path,id)
					continue
			except KeyError as e:
				log.error("Omitting %s for %s",controller_path,id)
				log.error(e)
			self.osc_outputs.append([None,osc_path,getter,mapper])
		# TODO: not needed? asyncio.run_coroutine_threadsafe()

	def set_rumble(self, f: float):
		self.rumble_event.set()
		self.current_rumble = f

	def on_update_thread(self):
		# print(self.serial,self.get_gyro_x())
		for data in self.osc_outputs:
			(prev,osc_path,getter,mapper) = data
			if mapper:
				val = mapper(getter())
			else:
				val = getter()
			if prev != val:
				data[0] = val
				log.debug(f"send {osc_path} <- {val}")
				self.osc_output.send_message(osc_path,val)

	def get_status_getters(self) -> dict:
		if self.status_getters:
			return self.status_getters
		add_buttons =  {
				"y": self.get_button_y,
				"x": self.get_button_x,
				"b": self.get_button_b,
				"a": self.get_button_a,
				"sr": self.get_button_right_sr,
				"sl": self.get_button_right_sl,
				"r": self.get_button_r,
				"zr": self.get_button_zr,
			} if self.is_right()  else {
				"down": self.get_button_down,
				"up": self.get_button_up,
				"right": self.get_button_right,
				"left": self.get_button_left,
				"sr": self.get_button_left_sr,
				"sl": self.get_button_left_sl,
				"l": self.get_button_l,
				"zl": self.get_button_zl,
			}
		buttons = {
			"minus": self.get_button_minus,
			"plus": self.get_button_plus,
			"r-stick": self.get_button_r_stick,
			"l-stick": self.get_button_l_stick,
			"home": self.get_button_home,
			"capture": self.get_button_capture,
			"charging-grip": self.get_button_charging_grip,
		}
		buttons.update(add_buttons)
		self.status_getters = {
			"battery": {
				"charging": self.get_battery_charging,
				"level": self.get_battery_level,
			},
			"buttons": buttons,
			"analog-sticks": {
					"horizontal": self.get_stick_left_horizontal,
					"vertical": self.get_stick_left_vertical,
				} if self.is_left() else {
					"horizontal": self.get_stick_right_horizontal,
					"vertical": self.get_stick_right_vertical,
				},
			"accel": {
				"x": self.get_accel_x,
				"y": self.get_accel_y,
				"z": self.get_accel_z,
			},
			"gyro": {
				"x": self.get_gyro_x,
				"y": self.get_gyro_y,
				"z": self.get_gyro_z,
			},
		}
		return self.status_getters
	

joycons: typing.Dict[str, JoyConX | None] = {
	id: None for id, serial in controllers.items()
}
# lock = threading.Lock()


async def joycon_worker(joycon_serial, id):
	for i in range(13):
		if shutdown_everything:
			break
		joycon_id = False

		while not joycon_id:
			# TODO: move to thread spawning thread

			for vendor_id, product_id, serial in get_device_ids():
				if serial == joycon_serial:
					joycon_id = (vendor_id, product_id, serial)
					break

			if joycon_id:
				assert joycon_id[0]
				break
			if verbose:
				log.debug(f"Finding {id}")
			await asyncio.sleep(0.4421 if not verbose else 2.3)

		name = "Controller-" + str(id)
		log.info("Found JoyCon %s (%s)\n", name, joycon_id)
		
		osc_output_id = "osc_output."+str(id)
		osc_outputs =  config[osc_output_id] if osc_output_id in config else  None
		joycon = JoyConX(osc_outputs,*joycon_id)
		joycons[id] = joycon


		joycon.set_player_lamp_on(
			(int(id) + 1) % 3 + 1
		)  # required to keep fake controller running

		log.debug("Testing vibration")
		await asyncio.sleep(1)

		joycon.rumble_simple()
		await asyncio.sleep(1.5)

		joycon.rumble_simple()
		await asyncio.sleep(0.5)

		joycon.rumble_stop()
		log.debug("Vibrated")
		if notele:
			await asyncio.sleep(0.02)

			await asyncio.sleep(0.02)
			joycon._write_output_report(b"\x01", b"\x03", b"\x00")

		while not shutdown_everything and joycon.connected():
			await joycon.rumble_event.wait()

			status = joycon.current_rumble
			if status:

				joycon.rumble_simple()
				if verbose:
					# too spammy even for debug
					log.debug("Vibrating %s @ %s", name, str(status))

				await asyncio.sleep(0.35)

			elif status is not False:
				joycon.current_rumble = False
				log.debug("STOP %s", name)
				joycon.rumble_event.clear()
				joycon.rumble_stop()

		log.error("LOST JOYCON %s", name)

		del joycon
		joycons[id] = False
	log.critical(f"TOO MANY FAILURES, CLOSING {id}")


controller_tasks = []
server_osc: osc_server.AsyncIOOSCUDPServer = None
osc_relayer: SimpleUDPClient = None

#TODO: untested
def gen_relay(relayinfo,dispatcher):
	relay = SimpleUDPClient(relayinfo["ip"],int(relayinfo["port"]))
	remappings={k:v for k,v in relayinfo.items() if k!="ip" and k!="port"}
	for map_from,map_to in remappings.items():
		log.info(" - Relaying '%s' as '%s'",map_from,map_to)
		dispatcher.map(map_from, (lambda map_to=map_to: lambda _,*args: relay.send_message(map_to,args))() )

async def startOSC(loop):
	global server_osc, osc_relayer

	def default_handler(key, *vals):
		if osc_relayer:
			osc_relayer.send_message(key, vals)
		if verbose:
			logging.error("osc received unhandled: %s %s", key, vals)

	def osc_rumble(id, address, *args):
		log.debug(
			"osc_rumble(id=%s,address=%s,*args=%s)", str(id), str(address), str(args)
		)
		j: JoyConX | None = joycons.get(id, None)
		if not j:
			log.debug("CANNOT RUMBLE CONTROLLER %s (does not exist)", id)
			return

		val = 0
		if len(args) > 0:
			val = args[0]
			if isinstance(val, list):
				if len(val) == 0:
					log.error(f"Unhandled {id} {address} {val}")
					return
				val = val[0]

		rumble_strength = 0
		if type(val) == int or type(val) == float:
			rumble_strength = val
		elif type(val) == bool:
			rumble_strength = 1 if val else 0
		else:
			log.error("Unknown type received")

		log.info(f"JoyCon {id}: set_rumble(rumble_strength={rumble_strength})")
		j.set_rumble(rumble_strength)

	d = dispatcher.Dispatcher()

	for id, osc_paths in config["osc.rumble"].items():
		for osc_path in osc_paths.splitlines():
			# def handler(address,*args):
			# 	osc_rumble(id,address,*args)

			# Captures id
			handler = (
				lambda id: lambda address, *args: osc_rumble(id, address, *args)
			)(id)
			d.map(osc_path, handler)  # We could use the extra param here also

			log.debug("Map %s <- %s", id, osc_path)
	if relay_port > 0:
		d.set_default_handler(default_handler)

	server_osc = osc_server.AsyncIOOSCUDPServer((listen_ip, listen_port), d, loop)
	log.info(f"[osc_server] listen_ip={listen_ip} listen_port={listen_port}")
	(
		transport,
		protocol,
	) = (
		await server_osc.create_serve_endpoint()
	)  # Create datagram endpoint and start serving

	if relay_port > 0:
		osc_relayer = SimpleUDPClient(relay["ip"], relay_port)
		log.info(
			"Relaying other messages to {} on port {}".format(relay["ip"], relay_port)
		)

	for relayinfo in [config[sect] for sect in config.sections() if sect.startswith("relay.")]:
		if int(relayinfo["port"])>0:
			log.info("Creating relay to %s port %s",relayinfo["ip"],relayinfo["port"])
			gen_relay(relayinfo,d)



def watchdog():
	while True:
		anyAlive = False
		for t in controller_tasks:
			t.join(0.2)
			if t.is_alive():
				anyAlive = True
		if not anyAlive:
			global shutdown_everything
			shutdown_everything = True
			log.critical("Lost all JoyCon threads")
			# print("\nFATAL: Lost all JoyCon threads\n")
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


async def startJoyCons():
	log.info(
		"Attempting to locate joycons. Known controllers: %s",
		{k: v for k, v in controllers.items()},
	)
	if len(controllers) == 0 or False:
		print("ATTENTION: Start all joycons (to discover serial IDs")
		print("THEN:    modify config.ini to set up proper ids for your osc...")
		found = []
		while not shutdown_everything:

			for vendor_id, product_id, serial in get_device_ids():
				if serial not in found:
					found.append(serial)
					id = len(found)
					controllers[str(id)] = serial
					print(
						"Saving found: ",
						f"vendor_id={vendor_id}, product_id={product_id}, serial={serial} id={id}",
						"LEFT" if product_id == 0x2006 else "RIGHT",
					)
					print("Type exit and press enter to save! Then restart vrcjoycon.")
					config_save()

			sys.stdout.write(".")
			sys.stdout.flush()
			await asyncio.sleep(2.123)
		print("Stopping joycon discovery")
		return

	for id, serial in controllers.items():
		# x = threading.Thread(target=joycon_worker,
		# 					 args=(serial, id), daemon=True,name="joyconController"+str(id))
		# x.start()
		x = asyncio.create_task(joycon_worker(serial, id),name="JoyConController-"+str(id))
		
		controller_tasks.append(x)

	# Watchdog
	# x = threading.Thread(target=watchdog,
	# 						args=(), daemon=True,name="watchdog")
	# x.start()


do_status_args = argparse.ArgumentParser(description="Random status info")

import pprint
async def do_status(reader, writer):
	for id,con in joycons.items():
		print("JOYCON: ",id,"=",con)
		if con:
			print("        Connected=",con.connected(),"status=")
			pprint.pprint(con.get_status())



do_exit_args = argparse.ArgumentParser(description="Exits")


async def do_exit(reader, writer):
	log.warning("Setting shutdown_everything=True ...")
	global shutdown_everything
	shutdown_everything = True



do_tasks_args = argparse.ArgumentParser(description="List tasks")


async def do_tasks(reader, writer):
	for task in asyncio.all_tasks():
		print(task)

do_vibrate_args = argparse.ArgumentParser(description="Vibrates a controller")
do_vibrate_args.add_argument("id", nargs='?',default="1", help="controller id")


async def do_vibrate(reader, writer, id=1):
	log.warning(f"vibrating {id}")
	joycon = joycons.get(id)
	if joycon:
		joycon.set_rumble(1)
		await asyncio.sleep(3)
		joycon.set_rumble(0)
	else:
		writer.write("no such joycon\n")


CLI_CMDS = {"vibrate": (do_vibrate, do_vibrate_args), "status": (do_status, do_status_args), "exit": (do_exit, do_exit_args), "tasks": (do_tasks, do_tasks_args)}

async def startCLI(loop):

	cli = AsynchronousCli(CLI_CMDS, prog="cvrcjoycon", loop=loop)
	await cli.interact()

async def amain():

	loop = asyncio.get_event_loop()

	await startOSC(loop)
	

	jcstarter=asyncio.create_task(startJoyCons(),name="startJoyCons")
	clitask=asyncio.create_task(startCLI(loop),name="CLI")

	while not shutdown_everything:
		for task in controller_tasks:
			try:
				task.result()
			except asyncio.InvalidStateError:
				pass
		try:
			jcstarter.result()
		except asyncio.InvalidStateError:
			pass

		await asyncio.wait([clitask],timeout=1.234)
		
	log.info("shutdown_everything=1")
	for task in asyncio.all_tasks():
		task.cancel()

	# cmd = Commander(intro="===== VR JoyCon Command Prompt =====", prompt="vrcjoycon> ")
	# cmd.start(loop)


if __name__ == "__main__":
	try:
		asyncio.run(amain(),debug=debug)
	except SystemExit as e:
		pass	
	except Exception as e:
		if verbose or debug:
			
			try:
				#TODO: BUG: aioconsole likely closes stdin/stderr/etc...
				input("SHUTTING DOWN. PRESS ENTER TO CLOSE.")
			except Exception:
				pass

		raise

	# server.serve_forever()
