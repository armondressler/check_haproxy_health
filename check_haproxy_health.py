#!/usr/bin/env python3

import argparse
import operator
import nagiosplugin as nag
from haproxyadmin import haproxy as hapm

__author__ = "Armon Dressler"
__license__ = "BSD2C"
__version__ = "0.4"
__email__ = "armon.dressler@gmail.com"

'''
Check plugin for monitoring a haproxy instance.
Output is in line with nagios plugins development guidelines.

Copyright 2018 armon.dressler@gmail.com

Redistribution and use in source and binary forms, with or without modification,
are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice,
this list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
this list of conditions and the following disclaimer in the documentation and/or 
other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, 
INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE 
ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR 
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE
USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
'''


class CheckHaproxyHealth(nag.Resource):

    def __init__(self,
                 metric,
                 frontend=None,
                 backend=None,
                 server=None,
                 hasocketdir=None,
                 hasocketfile=None,
                 nozerocounters=False,
                 min=None,
                 max=None,
                 scan=False):

        self.haadmin = hapm.HAProxy(socket_dir=hasocketdir, socket_file=hasocketfile)
        self.metric = metric
        self.frontend = frontend
        self.backend = backend
        self.server = server
        self.set_mode()
        self.nozerocounters = nozerocounters
        self.min = min
        self.max = max

        if scan:
            self.scan()
            exit()
        else:
            if not self.get_ha_resource():
                raise ValueError("HA resource was not found. Use --scan to check for resources.")

    def set_mode(self):
        if self.backend:
            self.mode = "backend"
        elif self.frontend:
            self.mode = "frontend"
        elif self.server:
            self.mode = "server"

    def get_ha_resource(self):
        if self.mode == "frontend":
            return self.frontend in self.haadmin.frontends()
        elif self.mode == "backend":
            return self.backend in self.haadmin.backends()
        elif self.mode == "server":
            return self.server in self.haadmin.servers()

    def get_metric(self, metric):
        try:
            if self.mode == "frontend":
                return self.haadmin.frontend(self.frontend).metric(metric)
            elif self.mode == "backend":
                return self.haadmin.backend(self.backend).metric(metric)
            elif self.mode == "server":
                return self.haadmin.server(self.server)[0].metric(metric)
        except ValueError:
            raise ValueError("\"{}\" is not a valid metric for mode {}".format(metric, self.mode))

    def _get_percentage(self, part, total):
        try:
            part = sum(part)
        except TypeError:
            pass
        try:
            total = sum(total)
        except TypeError:
            pass
        return round(part / total * 100, 2)

    def scan(self):
        print("Available assets on this node ({}):\n".format(self.haadmin.nodename))
        for backend in self.haadmin.backends():
            print("Backend: {} ({})".format(backend.name,backend.status))
            for index,server in enumerate(backend.servers()):
                print("{:^12}{} ({})".format("Server {}:".format(index),server.name,server.status))
            print()
        for frontend in self.haadmin.frontends():
            print("Frontend: {} ({})".format(frontend.name,frontend.status))

    def probe(self):
        metric_dict = operator.methodcaller("get_" + self.metric)(self)
        if self.min:
            metric_dict["min"] = self.min
        if self.max:
            metric_dict["max"] = self.max
        if not self.nozerocounters:
            self.haadmin.clearcounters(all=True)
        return nag.Metric(metric_dict["name"],
                          metric_dict["value"],
                          uom=metric_dict.get("uom"),
                          min=metric_dict.get("min"),
                          max=metric_dict.get("max"),
                          context=metric_dict.get("context"))

    def get_active_servers(self):
        # Backend
        # make sure your haproxy backend does checks for its servers
        if self.mode != "backend":
            raise ValueError("active_servers is not a valid metric for this mode.")
        server_list = self.haadmin.backend(self.backend).servers()
        server_count = len(server_list)
        if server_count < 1:
            raise ValueError("Backend {} does not contain any servers".format("self.backend.name"))
        return {
            "value": self._get_percentage([1 for server in server_list if server.status == "UP"], server_count),
            "name": "active_servers",
            "uom": "%",
            "min": 0,
            "max": 100}

    def get_http_4XX_pct(self):
        # Frontend,Backend,Server
        failed_types = ["hrsp_4xx"]
        if self.mode == "frontend":
            req_tot = self.get_metric("req_tot")
        else:
            req_tot = sum([self.get_metric(metric) for metric in ["hrsp_1xx",
                                                                  "hrsp_2xx",
                                                                  "hrsp_3xx",
                                                                  "hrsp_4xx",
                                                                  "hrsp_5xx",
                                                                  "hrsp_other"]])
        if req_tot == 0:
            req_tot = 1
        return {
            "value": self._get_percentage([self.get_metric(metric) for metric in failed_types], req_tot),
            "name": "http_4XX_pct",
            "uom": "%",
            "min": 0,
            "max": 100}

    def get_http_5XX_pct(self):
        # Frontend,Backend,Server
        failed_types = ["hrsp_5xx","hrsp_other"]
        if self.mode == "frontend":
            req_tot = self.get_metric("req_tot")
        else:
            req_tot = sum([self.get_metric(metric) for metric in ["hrsp_1xx",
                                                                  "hrsp_2xx",
                                                                  "hrsp_3xx",
                                                                  "hrsp_4xx",
                                                                  "hrsp_5xx",
                                                                  "hrsp_other"]])
        if req_tot == 0:
            req_tot = 1
        return {
            "value": self._get_percentage([self.get_metric(metric) for metric in failed_types], req_tot),
            "name": "http_5XX_pct",
            "uom": "%",
            "min": 0,
            "max": 100}

    def get_session_capacity_pct(self):
        # Frontend,Backend,Server
        slim = self.get_metric("slim")
        if slim == 0:
            raise ValueError("No session limit defined in haproxy config.")
        return {
            "value": self._get_percentage(self.get_metric("scur"), slim),
            "name": "session_capacity_pct",
            "uom": "%",
            "min": 0,
            "max": 100}

    def get_session_rate_capacity_pct(self):
        # Frontend
        # capacity of sessions created per second
        rate_lim = self.haadmin.ratelimitsess
        if rate_lim == 0:
            raise ValueError("No session rate limit defined in haproxy config.")
        return {
            "value": self._get_percentage(self.get_metric("rate_max"), rate_lim),
            "name": "session_rate_capacity_pct",
            "uom": "%",
            "min": 0,
            "max": 100}

    def get_average_response_time(self):
        # Backend only, in ms
        return {
            "value": self.get_metric("rtime"),
            "name": "average_response_time",
            "uom": "ms",
            "min": 0}

    def get_total_megabytes_in(self):
        # Frontend,Backend,Server
        return {
            "value": round(self.get_metric("bin") / 1024**2, 2),
            "name": "total_megabytes_in",
            "uom": "MB",
            "min": 0}

    def get_total_megabytes_out(self):
        # Frontend,Backend,Server
        return {
            "value": round(self.get_metric("bout") / 1024**2, 2),
            "name": "total_megabytes_out",
            "uom": "MB",
            "min": 0}

    def get_error_requests(self):
        # Frontend
        # errors during request from client (timeout, disco, ACL fuckery)
        return {
            "value": self.get_metric("ereq"),
            "name": "error_requests",
            "uom": "c",
            "min": 0}

    def get_denied_requests(self):
        # Frontend,Backend
        # subset of ereq, denied reqs because of ACLs
        return {
            "value": self.get_metric("dreq"),
            "name": "denied_requests",
            "uom": "c",
            "min": 0}

    def get_backend_failures(self):
        # Backend,Server
        # errors during response from backend or while connecting to backend
        return {
            "value": sum([self.get_metric("econ"),self.get_metric("eresp")]),
            "name": "backend_failures",
            "uom": "c",
            "min": 0}

    def get_queue_capacity_pct(self):
        # Backend,Server
        # amount of requests currently queued
        qmax = self.get_metric("qmax")
        if qmax == 0:
            raise ValueError("No queue limit defined in haproxy config.")
        return {
            "value": self._get_percentage(self.get_metric("qcur"),qmax),
            "name": "queue_capacity_pct",
            "uom": "%",
            "min": 0}

    def get_queue_time(self):
        # Backend,Server
        # time in ms spent in socket queue for last 1024 reqs
        return {
            "value": self.get_metric("qtime"),
            "name": "queue_time",
            "uom": "ms",
            "min": 0}

    def get_new_sessions(self):
        # Frontend,Backend,Server
        # new sessions over the last 1 sec
        return {
            "value": self.get_metric("rate"),
            "name": "new_sessions",
            "uom": "c",
            "min": 0}

    def get_new_requests(self):
        # Frontend
        # requests over the last 1 sec
        return {
            "value": self.get_metric("req_rate"),
            "name": "new_requests",
            "uom": "c",
            "min": 0}


class CheckHaproxyHealthContext(nag.ScalarContext):
    fmt_helper = {
        "active_servers": "{value}{uom} of all servers available are active",
        "http_4XX_pct": "{value}{uom} of all requests returned HTTP 4XX",
        "http_5XX_pct": "{value}{uom} of all requests returned HTTP 5XX or undef",
        "session_capacity_pct": "Operating at {value}{uom} of maximum session capacity",
        "session_rate_capacity_pct": "Session rate reached {value}{uom}",
        "average_response_time": "Average response time at {value}{uom}",
        "total_megabytes_in": "{value}{uom} received in total",
        "total_megabytes_out": "{value}{uom} sent in total",
        "error_requests": "Got {value} bad requests (disconnect,timeout,ACL hit etc.) from clients",
        "denied_requests": "Discarded {value} requests due to ACL hits (subset of error_requests)",
        "backend_failures": "Counted {value} errors for this resource",
        "queue_capacity_pct": "Queue is at {value}{uom} of maximum capacity",
        "queue_time": "Average time spent in queue is {value}{uom} for the last 1024 requests",
        "new_sessions": "Counted {value} new sessions during previous second",
        "new_requests": "Counted {value} requests during previous second"
    }

    def __init__(self, name, warning=None, critical=None,
                 fmt_metric='{name} is {valueunit}', result_cls=nag.Result):

        try:
            metric_helper_text = CheckHaproxyHealthContext.fmt_helper[name]
        except KeyError:
            raise ValueError("Metric \"{}\" not found. Use --help to check for metrics available.".format(name))
        super(CheckHaproxyHealthContext, self).__init__(name,
                                                        warning=warning,
                                                        critical=critical,
                                                        fmt_metric=metric_helper_text,
                                                        result_cls=result_cls)


class CheckHaproxyHealthSummary(nag.Summary):

    def __init__(self,frontend=None,backend=None,server=None):
        if backend:
            self.ha_resource = backend
            self.mode = "backend"
        elif frontend:
            self.ha_resource = frontend
            self.mode = "frontend"
        else:
            self.ha_resource = server
            self.mode = "server"

    def ok(self, results):
        if len(results.most_significant) > 1:
            info_message = ", ".join([str(result) for result in results.results])
        else:
            info_message = " ".join([str(result) for result in results.results])
        return "{} \"{}\" reports: {}".format(self.mode.capitalize(), self.ha_resource, info_message)

    def problem(self, results):
        if len(results.most_significant) > 1:
            info_message = " ,".join([str(result) for result in results.results])
        else:
            info_message = " ".join([str(result) for result in results.results])
        return "{} \"{}\" reports: {}".format(self.mode.capitalize(), self.ha_resource, info_message)


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('-w', '--warning', metavar='RANGE', default='',
                        help='return warning if load is outside RANGE,\
                            RANGE is defined as an number or an interval, e.g. 5:25 or :30  or 95:')
    parser.add_argument('-c', '--critical', metavar='RANGE', default='',
                        help='return critical if load is outside RANGE,\
                            RANGE is defined as an number or an interval, e.g. 5:25 or :30  or 95:')
    parser.add_argument('-s', '--socketdir', action='store',
                        help='path to directory containing haproxy sockets')
    parser.add_argument('-f', '--socketfile', action='store', default='/var/run/haproxy.sock',
                        help='path to haproxy socketfile')
    ha_resource_type = parser.add_mutually_exclusive_group(required=True)
    ha_resource_type.add_argument('--backend', action='store', default=None,
                                  help='name of backend, use --scan to check for resources available')
    ha_resource_type.add_argument('--frontend', action='store', default=None,
                                  help='name of frontend, use --scan to check for resources available')
    ha_resource_type.add_argument('--server', action='store', default=None,
                                  help='name of server in backend, use --scan to check for resources available')
    ha_resource_type.add_argument('--scan', action='store_true', default=False,
                                  help='Show haproxy resources available (frontend,backend and server)')

    parser.add_argument('--max', action='store', default=None,
                        help='maximum value for performance data')
    parser.add_argument('--min', action='store', default=None,
                        help='minimum value for performance data')
    parser.add_argument('--metric', action='store', required=False,
                        help='Supported keywords: {}'.format(
                          ", ".join(CheckHaproxyHealthContext.fmt_helper.keys())))
    parser.add_argument('-v', '--verbose', action='count', default=0,
                        help='increase output verbosity (use up to 3 times)')
    parser.add_argument('--nozerocounters', action='store_true', default=False,
                        help='do not zero out stat counters after every run')

    return parser.parse_args()


@nag.guarded
def main():
    args = parse_arguments()
    check = nag.Check(
        CheckHaproxyHealth(
            args.metric,
            frontend=args.frontend,
            backend=args.backend,
            server=args.server,
            hasocketdir=args.socketdir,
            hasocketfile=args.socketfile,
            min=args.min,
            max=args.max,
            scan=args.scan,
            nozerocounters=args.nozerocounters),
        CheckHaproxyHealthContext(args.metric, warning=args.warning, critical=args.critical),
        CheckHaproxyHealthSummary(frontend=args.frontend,backend=args.backend,server=args.server)
    )
    check.main(verbose=args.verbose)


if __name__ == '__main__':
    main()
