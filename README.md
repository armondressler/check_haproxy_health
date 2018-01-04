## check_haproxy_health: nagios plugin to check haproxy health

The installation requires python3, the python3 header (python3-devel on CentOS7/Fedora) files and gcc, 
otherwise the installation of haproxyadmin / nagiosplugin with pip3 will fail.


### Basic Usage:

show option and their explanation
_./checkhaproxyhealth.py --help_

#show available ha resources and their state
#Ensure your haproxy.cfg contains a definition for a stats socket, e.g.
#"stats socket /var/run/haproxy.sock mode 600 level admin"
#The user executing the script must be permitted to use the socket

_./checkhaproxyhealth.py -f /var/run/haproxy.sock --scan_

#get percentage of HTTP 5XX requests on backend "app"

_./checkhaproxyhealth.py -f /var/run/haproxy.sock --backend app --metric http5XXpct_

#check for HTTP 4XX on backend "app" without resetting the stats counters after completion
#every value > 10 results in a warning, bigger than 20 is critical

_./checkhaproxyhealth.py -f /var/run/haproxy.sock --nozerocounters --backend app --metric http4XXpct -w 10 -c 20_

CHECKHAPROXYHEALTH CRITICAL - Backend "app" reports: 27.06% of all requests returned HTTP 4XX (outside range 0:20) | http_4XX_pct=27.06%;10;20;0;100


#Get total traffic pushed out of fronted "staging_one" in MB

_./checkhaproxyhealth.py -f /var/run/haproxy.sock --nozerocounters --frontend stagingone --metric totalmegabytesout_

CHECKHAPROXYHEALTH OK - Frontend "staging_one" reports: 0.14MB sent in total | total_megabytes_out=0.14MB;;;0

#Report availability of servers attached to backend "app"
#Notifiy with a warning if less than 60% of servers are available ("UP"), critical at < 49%

_./checkhaproxyhealth.py -f /var/run/haproxy.sock --backend app --metric activeservers -w 60: -c 49:_

  CHECKHAPROXYHEALTH WARNING - Backend "app" reports: 50.0% of all servers available are active (outside range 60:) | active_servers=50.0%;60:;49:;0;100

#Report the sum of new sessions for the last second for backend "app"
#For data reporting tools, reasonable --min and --max values help with the graphing

_./checkhaproxyhealth.py --metric newsessions -w 1800 -c 2200 --backend app --nozerocounters --max 3000_

  CHECKHAPROXYHEALTH OK - Backend "app" reports: Counted 50 new sessions during previous second | new_sessions=50c;1800;2200;0;3000
