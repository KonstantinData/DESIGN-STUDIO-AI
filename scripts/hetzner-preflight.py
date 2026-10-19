#!/usr/bin/env python3
"""Read-only server inventory. No installation, configuration or restart."""
import ipaddress,json,os,re,shutil,subprocess,sys

def command(args):
    try:
        p=subprocess.run(args,capture_output=True,text=True,timeout=15)
        return {'returncode':p.returncode,'output':p.stdout.strip()}
    except (OSError,subprocess.SubprocessError):return {'returncode':-1,'output':'unavailable'}

result={name:command(args) for name,args in {
    'system':['uname','-srm'],'cpus':['getconf','_NPROCESSORS_ONLN'],
    'memory':['free','-m'],'disk':['df','-h','/'],'listening_ports':['ss','-lnt'],
    'docker':['docker','version','--format','{{.Server.Version}}'],
    'containers':['docker','ps','--format','{{.Names}} | {{.Image}} | {{.Ports}} | {{.Status}}'],
}.items()}
conflicts=[]
networks=command(['docker','network','ls','-q'])
if networks['returncode']==0:
    for identifier in networks['output'].splitlines():
        info=command(['docker','network','inspect','--format','{{json .IPAM.Config}}',identifier])
        if info['returncode']!=0:continue
        for item in json.loads(info['output']) or []:
            subnet=item.get('Subnet')
            if subnet and ipaddress.ip_network(subnet).version==4 and any(ipaddress.ip_network(subnet).overlaps(ipaddress.ip_network(required)) for required in ('172.30.74.0/28','172.30.75.0/28')):
                conflicts.append(identifier)
result['proxy_ipam_conflict']=bool(conflicts)
blocked = bool(conflicts) or result['docker']['returncode'] != 0
try:
    import socket
    with socket.socket() as probe:
        probe.bind(('127.0.0.1',8788))
    result['loopback_8788_available']=True
except OSError:
    result['loopback_8788_available']=False; blocked=True
free_bytes=shutil.disk_usage(os.getcwd()).free
available_kib=next(int(line.split()[1]) for line in open('/proc/meminfo') if line.startswith('MemAvailable:'))
result['at_least_12GiB_disk_free']=free_bytes >= 12*1024**3
result['at_least_3GiB_memory_available']=available_kib >= 3*1024**2
blocked |= not result['at_least_12GiB_disk_free'] or not result['at_least_3GiB_memory_available']

# Capture privately: never print full nginx configuration, certificates or auth data.
nginx=shutil.which('nginx')
if nginx:
    try:
        config=subprocess.run([nginx,'-T'],capture_output=True,text=True,timeout=15)
        names=[name.lower().rstrip('.') for block in re.findall(r'\bserver_name\s+([^;]+);',re.sub(r'(?m)#.*$','',config.stdout)) for name in block.split()]
        duplicate='studio.mein-kuechenexperte.de' in names
        result['nginx_valid']=config.returncode==0
        result['selected_hostname_already_configured']=duplicate
        blocked |= duplicate or config.returncode!=0
    except (OSError,subprocess.SubprocessError): blocked=True;result['nginx_valid']=False
else:
    result['nginx_valid']=False;blocked=True
result['decision']='BLOCKED' if blocked else 'INVENTORY_ONLY_REVIEW_PORTS_RESOURCES_AND_EXISTING_PROXY'
print(json.dumps(result,indent=2))
sys.exit(2 if blocked else 0)
