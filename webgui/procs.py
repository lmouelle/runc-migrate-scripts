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
import json
import os
import psutil
import time

from webgui.p_haul_web_gui import APP

KNOWN_HAUL_TYPES = {'lxc', 'pid'}
HAUL_TYPE_DEFAULT = 'pid'


@APP.route('/procs')
def procs():
    """List processes

    This function is responsible for listing the processes
    on this machine as a JSON object, where children processes
    are stored hierarchically beneath their parent processes.
    """

    def generate():
        """Respond to an HTTP GET request

        Respond to an HTTP GET request with a stream of events
        containing JSON strings.
        """

        oldroot = {}

        while True:
            flatprocs = []
            root = {}

            for p in psutil.process_iter():
                if callable(p.cmdline):
                    if len(p.cmdline()) > 0:
                        name = os.path.basename(p.cmdline()[0])
                    if name is '':
                        name = p.name()
                else:
                    try:
                        name = os.path.basename(p.cmdline[0])
                    except Exception:
                        name = p.name

                is_container = False
                htype = HAUL_TYPE_DEFAULT
                for container in KNOWN_HAUL_TYPES:
                    if container in name:
                        htype = container
                        is_container = True
                        break

                cname = None
                if is_container and htype == 'lxc':
                    cname = name.split()[-1]

                proc = {
                    # name and ppid are either functions or variables in
                    # different versions of psutil.
                    "name": name,
                    "id": p.pid,
                    "parent": p.ppid() if callable(p.ppid) else p.ppid,
                    "children": [],
                    "htype": htype,
                    "is_container": is_container,
                    "cname": cname
                }

                if p.pid == 1:
                    root = proc
                else:
                    flatprocs.append(proc)

            unflatten(flatprocs, root)

            if root != oldroot:
                yield "event: procs\n"
                yield "data: " + json.dumps(root, separators=",:") + "\n"
                yield "\n"

                oldroot = root

            # Poll at 1000ms intervals
            time.sleep(1.0)

    def unflatten(flatprocs, proc):
        """Convert list of processes to a tree

        Utility to convert a flat list of processes with references
        to their parents' PIDs into a tree.
        """

        remainder = []

        for childProc in flatprocs:
            if "parent" in childProc and childProc["parent"] == proc["id"]:
                if proc['is_container']:
                    childProc['is_container'] = proc['is_container']
                    childProc['htype'] = proc['htype']
                proc["children"].append(childProc)
            else:
                remainder.append(childProc)

        for childProc in proc["children"]:
            if not remainder:
                break

            remainder = unflatten(remainder, childProc)

        return remainder

    # This sends the actual answer
    resp = flask.Response(flask.stream_with_context(generate()))
    resp.headers['Content-Type'] = 'text/event-stream'
    resp.headers['Cache-Control'] = 'no-cache'
    resp.headers['Access-Control-Expose-Headers'] = '*'
    return resp
