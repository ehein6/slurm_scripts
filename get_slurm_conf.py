#!/usr/bin/env python
import subprocess
import re

def max_in_col(data, col_id):
    return max(int(row[col_id]) for row in data)
    
def get_cpu_info():
    cpu_text = subprocess.check_output(["lscpu", "--parse=cpu,core,socket"])
    rows = [line.split(",") for line in cpu_text.splitlines() if not line.startswith("#")]
    return {
        "cpus" : max_in_col(rows, 0) + 1,
        "cores" : max_in_col(rows, 1) + 1,
        "sockets" : max_in_col(rows, 2) + 1,
    }
    
def get_mem_info():
    text = subprocess.check_output(["cat", "/proc/meminfo"])
    m = re.match("MemTotal:\s+(\d+) kB", text)
    if not m:
        return 0
    else:
        return int(m.group(1)) / 1024

def get_hostname():
    return subprocess.check_output("hostname").splitlines()[0].split(".")[0]

def get_ipaddr():
    interfaces = ["eno1", "eno2"]
    for interface in interfaces:
        text = subprocess.check_output(["ip", "-o", "-4", "addr", "show", "dev", interface])
        if not text:
            continue
        else:
            return text.split()[3].split("/")[0]
    else:
        return "0.0.0.0"
    
def get_slurm_conf():
    cpu_info = get_cpu_info()
    data = {
        "hostname" : get_hostname(),
        "ipaddr" : get_ipaddr(),
        "cpus" : cpu_info["cpus"],
        "threads_per_core" : cpu_info["cpus"] / cpu_info["cores"],
        "cores_per_socket" : cpu_info["cores"] / cpu_info["sockets"],
        "num_sockets" : cpu_info["sockets"],
        "memory" : get_mem_info(),
    }
    template = "NodeName={hostname} NodeAddr={ipaddr} CPUs={cpus} ThreadsPerCore={threads_per_core} CoresPerSocket={cores_per_socket} Sockets={num_sockets} RealMemory={memory} State=UNKNOWN"
    return template.format(**data)
    
if __name__ == "__main__":
    print get_slurm_conf()
