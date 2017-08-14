# Copyright (C) 2015 Red Hat Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

import flask
import subprocess
import requests
import socket

DEFAULT_PORT = 8080
PARTNER_ADDRESS = "localhost"
SELF_ADDRESS = "localhost"
RPC_PORT = 12345

APP = flask.Flask(__name__)

# Import required for /procs and the pstree.js to render
import webgui.procs


@APP.after_request
def add_header(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response


@APP.route('/')
def index():
    return flask.redirect(flask.url_for('static', filename='index.html'))


@APP.route('/partners')
def partners():
    result = [{"name": "First Host (%s)" %
               SELF_ADDRESS, "address": "http://%s:8080" %
               SELF_ADDRESS}, {"name": "Second Host (%s)" %
                         PARTNER_ADDRESS, "address": "http://%s:8080" %
                         PARTNER_ADDRESS}]
    return flask.jsonify(results=result)


@APP.route('/register', methods=['POST'])
def register():
    global PARTNER
    global SELF_ADDRESS

    SELF_ADDRESS = flask.request.form.get("partner")
    PARTNER_ADDRESS = flask.request.remote_addr
    return flask.jsonify({"your_ip": PARTNER_ADDRESS})


@APP.route('/migrate')
def migrate():
    """Attempt to migrate a process

    Attempt to migrate a process, where the PID is given in the URL
    parameter "pid".
    """
    def pid_cmd_call(identifier):
        rpc_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        rpc_socket.connect(dest_host)

        mem_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        mem_socket.connect(dest_host)

        cmd = ['./p.haul', 'pid', identifier,
               '--to', PARTNER_ADDRESS,
               '--fdrpc', str(rpc_socket.fileno()),
               '--fdmem', str(mem_socket.fileno()),
               '-v 4',
               '--shell-job']
        return subprocess.call(' '.join(cmd), shell=True)

    def runc_cmd_call(identifier):
        cmd = ['./migrate', str(identifier), PARTNER_ADDRESS]
        return subprocess.call(' '.join(cmd), shell=True)

    def cmd_call(htype, identifier):
        if htype == 'pid':
            return pid_cmd_call(identifier)
        elif htype == 'runc':
            return runc_cmd_call(identifier)
        else:
            raise Exception("Cannot determine call for unknown htype {0}"
                            .format(htype))

    cname = flask.request.args.get('cname')
    pid = flask.request.args.get('pid')
    htype = flask.request.args.get('htype') or webgui.procs.HAUL_TYPE_DEFAULT

    if not pid or not pid.isnumeric():
        return flask.jsonify({"succeeded": False, "why": "No PID specified"})

    if htype not in webgui.procs.KNOWN_HAUL_TYPES:
        return flask.jsonify({"succeeded": False,
                              "why": "Unsupported htype {0}".format(htype)})

    dest_host = PARTNER_ADDRESS, RPC_PORT

    identifier = pid
    if htype != 'pid':
        if cname:
            identifier = cname
        else:
            return flask.jsonify({"succeeded": False,
                                  "why": "No container name given"})

    result = cmd_call(htype, identifier)

    return flask.jsonify({"succeeded": int(result) == 0,
                          "why": "Exited with code {0}".format(result)})


def start_web_gui(migration_partner, rpc_port, _debug=False):
    global PARTNER_ADDRESS
    global SELF_ADDRESS
    global RPC_PORT
    RPC_PORT = rpc_port
    PARTNER_ADDRESS = migration_partner
    if PARTNER_ADDRESS:
        try:
            SELF_ADDRESS = requests.post("http://%s:%d/register" %
                                         (PARTNER_ADDRESS, DEFAULT_PORT),
                                         data={"partner": PARTNER_ADDRESS}).json()['your_ip']
        except Exception:
            pass
    APP.run(host='0.0.0.0', port=DEFAULT_PORT, debug=_debug, threaded=True)
