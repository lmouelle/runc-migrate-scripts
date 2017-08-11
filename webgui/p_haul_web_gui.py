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

default_port = 8080
partner = "localhost"
myself = "localhost"
rpc_port = 12345

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
               myself, "address": "http://%s:8080" %
               myself}, {"name": "Second Host (%s)" %
                         partner, "address": "http://%s:8080" %
                         partner}]
    return flask.jsonify(results=result)


@APP.route('/register', methods=['POST'])
def register():
    global partner
    global myself

    myself = flask.request.form.get("partner")
    partner = flask.request.remote_addr
    return flask.jsonify({"your_ip": partner})


@APP.route('/migrate')
def migrate():
    """Attempt to migrate a process

    Attempt to migrate a process, where the PID is given in the URL
    parameter "pid".
    """
    cname = flask.request.args.get('cname')
    pid = flask.request.args.get('pid')
    htype = flask.request.args.get('htype') or webgui.procs.HAUL_TYPE_DEFAULT

    if not pid or not pid.isnumeric():
        return flask.jsonify({"succeeded": False, "why": "No PID specified"})

    if htype not in webgui.procs.KNOWN_HAUL_TYPES:
        return flask.jsonify({"succeeded": False,
                              "why": "Unsupported htype {0}".format(htype)})

    dest_host = partner, rpc_port
    rpc_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    rpc_socket.connect(dest_host)

    mem_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    mem_socket.connect(dest_host)

    identifier = pid
    if htype != 'pid':
        if cname:
            identifier = cname
        else:
            return flask.jsonify({"succeeded": False,
                                  "why": "No container name given"})

    target_args = ['./p.haul'] + [str(htype), str(identifier),
                                  '--to', str(partner),
                                  '--fdrpc', str(rpc_socket.fileno()),
                                  '--fdmem', str(mem_socket.fileno()),
                                  '-v', str(4),
                                  '--shell-job']

    cmd = ' '.join(target_args)
    print("Exec p.haul: {0}".format(cmd))
    result = subprocess.call(cmd, shell=True)

    return flask.jsonify({"succeeded": int(result) == 0,
                          "why": "p.haul exited with code {0}".format(result)})


def start_web_gui(migration_partner, _rpc_port, _debug=False):
    global partner
    global myself
    global rpc_port
    rpc_port = _rpc_port
    partner = migration_partner
    if partner:
        try:
            myself = requests.post("http://%s:%d/register" %
                                   (partner, default_port),
                                   data={"partner": partner}
                                   ).json()['your_ip']
        except Exception:
            pass
    APP.run(host='0.0.0.0', port=default_port, debug=_debug, threaded=True)
