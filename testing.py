from check_haproxy_health import CheckHaproxyHealth, CheckHaproxyHealthSummary, CheckHaproxyHealthContext
import nagiosplugin as nag
import haproxyadmin as hapm
import requests
import argparse
import random
from joblib import Parallel, delayed

def debug():
    if random.randint(0, 1):
        requests.get("http://localhost")
    else:
        requests.get("http://localhost/blka")


Parallel(n_jobs=5,backend="threading")([ delayed(debug)() for _ in range(50) ])


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
    parser.add_argument('--metric', action='store', required=True,
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
