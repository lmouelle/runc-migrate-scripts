#!/usr/bin/env python

import os
import socket
import argparse
import thread

import webgui.migrate_web_gui_service
from subprocess import Popen
from os.path import realpath
from os.path import dirname
from os.path import join

# Usage
# p.haul-wrap service
# p.haul-wrap client <destination> <type> <id>
#
# p.haul-wrap is a helper script which perform primitive connections
# establishment and call p.haul or p.haul-service specifying created
# connections via command line arguments. Use it exclusively for testing
# purposes!
#
# E.g.
# p.haul-wrap service
# p.haul-wrap client 10.0.0.1 vz 100
#


default_rpc_port = 12345
default_service_bind_addr = "0.0.0.0"


def start_web_gui(partner, rpc_port):
	"""Start web gui if requested"""

	server_path = join(dirname(realpath(__file__)), 'migrate_server.py')
	result = Popen(server_path, shell=True)
	if not result:
		raise Exception('Migration server failed to start')
	thread.start_new_thread(webgui.migrate_web_gui_service.start_web_gui,
		(partner, rpc_port))


def run_phaul_service(args, unknown_args):
	"""Run p.haul-service"""

	if args.web_gui:
		start_web_gui(args.web_partner, args.bind_port)

	print "Waiting for connection..."

	# Establish connection
	host = args.bind_addr, args.bind_port
	server_sk = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	server_sk.bind(host)
	server_sk.listen(8)
	connection_sks = [None, None]
	while True:
		for i in range(len(connection_sks)):
			connection_sks[i], dummy = server_sk.accept()

		# Organize p.haul-service args
		target_args = [args.path]
		target_args.extend(unknown_args)
		target_args.extend(["--fdrpc", str(connection_sks[0].fileno()),
			"--fdmem", str(connection_sks[1].fileno())])

		# Call p.haul-service
		cmdline = " ".join(target_args)
		print "Exec p.haul-service: {0}".format(cmdline)
		if args.one_shot:
			os.system(cmdline)
			return
		else:
			thread.start_new_thread(os.system, tuple([cmdline]))


def run_phaul_client(args, unknown_args):
	"""Run p.haul"""

	print "Establish connection..."

	# Establish connection
	dest_host = args.to, args.port

	connection_sks = [None, None]
	for i in range(len(connection_sks)):
		connection_sks[i] = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		connection_sks[i].connect(dest_host)

	# Organize p.haul args
	target_args = [args.path]
	target_args.extend(unknown_args)
	target_args.extend(["--to", args.to,
		"--fdrpc", str(connection_sks[0].fileno()),
		"--fdmem", str(connection_sks[1].fileno())])

	# Call p.haul
	print "Exec p.haul: {0}".format(" ".join(target_args))
	os.system(" ".join(target_args))


# Initialize arguments parser
parser = argparse.ArgumentParser("Process HAULer wrap")
subparsers = parser.add_subparsers(title="Subcommands")

# Initialize service mode arguments parser
service_parser = subparsers.add_parser("service", help="Service mode")
service_parser.set_defaults(func=run_phaul_service)
service_parser.add_argument("--bind-addr", help="IP to bind to", type=str,
	default=default_service_bind_addr)
service_parser.add_argument("--bind-port", help="Port to bind to", type=int,
	default=default_rpc_port)
service_parser.add_argument("--path", help="Path to p.haul-service script",
	default=os.path.join(os.path.dirname(__file__), "p.haul-service"))
service_parser.add_argument("--one-shot",
	help="Do not run in loop to accept multiple connections",
	default=False, action='store_true')
service_parser.add_argument("--web-gui",
	help="Start web gui", default = False, action = 'store_true')
service_parser.add_argument("--web-partner",
	help="Start web gui", type = str, default = None)

# Initialize client mode arguments parser
client_parser = subparsers.add_parser("client", help="Client mode")
client_parser.set_defaults(func=run_phaul_client)
client_parser.add_argument("to", help="IP where to haul")
client_parser.add_argument("--port", help="Port where to haul", type=int,
	default=default_rpc_port)
client_parser.add_argument("--path", help="Path to p.haul script",
	default=os.path.join(os.path.dirname(__file__), "p.haul"))

# Parse arguments and run wrap in specified mode
args, unknown_args = parser.parse_known_args()
try:
	args.func(args, unknown_args)
except KeyboardInterrupt:
	pass
