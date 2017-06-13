#!/usr/bin/env python
import subprocess
import re
import itertools

def max_in_col(data, col_id):
    """If data is a list of tuples, return the maximum """
    return max(int(row[col_id]) for row in data)

def oneline(s):
    """Converts a multi-line string to one line"""
    return re.sub("[\s]+", " ", s).strip()

def get_cpu_info():
    """Return the number of cpus, cores, and sockets on this machine"""
    cpu_text = subprocess.check_output(["lscpu", "--parse=cpu,core,socket"])
    rows = [line.split(",") for line in cpu_text.splitlines() if not line.startswith("#")]
    return {
        "cpus" : max_in_col(rows, 0) + 1,
        "cores" : max_in_col(rows, 1) + 1,
        "sockets" : max_in_col(rows, 2) + 1,
    }

def get_mem_info():
    """Return the total amount of RAM on this system, in MiB"""
    text = subprocess.check_output(["cat", "/proc/meminfo"])
    m = re.match("MemTotal:\s+(\d+) kB", text)
    if not m:
        return 0
    else:
        return int(m.group(1)) / 1024

def get_hostname():
    """Return this node's hostname"""
    return subprocess.check_output("hostname").splitlines()[0].split(".")[0]

def get_ipaddr():
    """Return this node's IP address"""
    interfaces = ["eno1", "eno2"]
    for interface in interfaces:
        text = subprocess.check_output(["ip", "-o", "-4", "addr", "show", "dev", interface])
        if not text:
            continue
        else:
            return text.split()[3].split("/")[0]
    else:
        return "0.0.0.0"

def get_gpu_names():
    """Return a list of names of GPU's on this node"""
    try:
        text = subprocess.check_output(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"])
        lines = text.splitlines()
        return [line.replace(" ", "") for line in lines]
    except subprocess.CalledProcessError:
        return []
    except OSError:
        return []

def get_phi_names():
    """Not implemented"""
    return []

def get_gres_conf():
    """Return a list of lines for this node's gres.conf"""
    template = "NodeName={hostname} Name=gpu Type={type} File={file}"
    gpu_list = get_gpu_names()
    out_lines = []
    for n, line in enumerate(gpu_list):
        data = {
            "hostname" : get_hostname(),
            "type" : line,
            "file" : "/dev/nvidia%i"%n, # HACK ordering from nvidia-smi might not match device ID's
        }
        out_lines.append(template.format(**data))
    return "\n".join(out_lines)

def get_gres_desc():
    """Return a string describing the generic resources available in this node,

       This fills the Gres field in slurm.conf for this node.
    """
    tokens = []
    gpus = get_gpu_names()
    for gpu_type, group in itertools.groupby(sorted(gpus)):
        tokens.append("gpu:{}:{}".format(gpu_type, len(list(group))))
    if len(tokens) == 0:
        return ""
    else:
        return "Gres=" + ",".join(tokens)

def get_slurm_conf():
    """Return a line describing this node's resources to put in slurm.conf"""
    cpu_info = get_cpu_info()
    data = {
        "hostname" : get_hostname(),
        "ipaddr" : get_ipaddr(),
        "cpus" : cpu_info["cpus"],
        "threads_per_core" : cpu_info["cpus"] / cpu_info["cores"],
        "cores_per_socket" : cpu_info["cores"] / cpu_info["sockets"],
        "num_sockets" : cpu_info["sockets"],
        "memory" : get_mem_info(),
        "gres" : get_gres_desc(),
    }
    template = oneline("""\
        NodeName={hostname}
        NodeAddr={ipaddr}
        CPUs={cpus}
        ThreadsPerCore={threads_per_core}
        CoresPerSocket={cores_per_socket}
        Sockets={num_sockets}
        RealMemory={memory}
        {gres}
        State=UNKNOWN
    """)
    return template.format(**data)

if __name__ == "__main__":
    hostname = get_hostname()
    with open("{}-slurm.conf".format(hostname), "w") as f:
        f.write(get_slurm_conf() + "\n")
    with open("{}-gres.conf".format(hostname), "w") as f:
        f.write(get_gres_conf() + "\n")
