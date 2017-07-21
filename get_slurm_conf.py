#!/usr/bin/env python
import subprocess
import re
import itertools
import argparse
import functools

def max_in_col(data, col_id):
    """If data is a list of tuples, return the maximum """
    return max(int(row[col_id]) for row in data)

def oneline(s):
    """Converts a multi-line string to one line and removes extra spaces"""
    return re.sub("[\s]+", " ", s).strip()

def return_on_error(val):
    """Decorator that makes a function return a default value instead of throwing an exception

    Example:

    @return_on_error("green")
    def foo(x):
        if x:
            return "red"
        else:
            raise Exception("This will be caught and ignored")

    foo(True)  # returns "red"
    foo(False) # returns "green"

    """
    def val_decorator(func):
        @functools.wraps(func)
        def func_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except:
                return val
        return func_wrapper
    return val_decorator

def get_short_intel_model_name(model):
    """Shortens a full Intel processor description"""
    # Clean up text before matching
    model = re.sub("CPU", "", model)
    model = oneline(model)
    m = re.match("Intel\(R\) ([\w]+)\(\w+\) ([\w\d-]+\s?[\w\d]*) @ \d+[.]\d+\w+", model)
    if m:
        family = m.group(1)
        number = m.group(2)
        # HACK: cpuinfo sometimes includes a 0 in place of the version number that we don't care about
        if number.endswith(" 0"):
            number = number[:-2]
        number = number.replace(" ", "")
        model = family + "-" + number
    return model

@return_on_error("UNKNOWN")
def get_cpu_model():
    text = subprocess.check_output(["cat", "/proc/cpuinfo"])
    for line in text.splitlines():
        # Look for model name
        if line.startswith("model name"):
            # Grab processor description
            model = line.split(":")[1]
            if model.startswith(" Intel"):
                return get_short_intel_model_name(model)
            # TODO parse Power8
            else:
                return model

@return_on_error({"cpus":1, "cores":1, "sockets":1})
def get_cpu_info():
    """Return the number of cpus, cores, and sockets on this machine"""
    cpu_text = subprocess.check_output(["lscpu", "--parse=cpu,core,socket"])
    rows = [line.split(",") for line in cpu_text.splitlines() if not line.startswith("#")]
    return {
        "cpus" : max_in_col(rows, 0) + 1,
        "cores" : max_in_col(rows, 1) + 1,
        "sockets" : max_in_col(rows, 2) + 1,
    }

@return_on_error("0")
def get_mem_info():
    """Return the total amount of RAM on this system, in MiB"""
    text = subprocess.check_output(["cat", "/proc/meminfo"])
    m = re.match("MemTotal:\s+(\d+) kB", text)
    if not m:
        return 0
    else:
        total_memory = int(m.group(1)) / 1024
        # Nodes need to hold some memory in reserve for OS, etc
        reserved = 0.05
        return int(total_memory * (1 - reserved))

@return_on_error("UNKNOWN")
def get_hostname():
    """Return this node's hostname"""
    return subprocess.check_output("hostname").splitlines()[0].split(".")[0]

@return_on_error("0.0.0.0")
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


def get_gres_conf(include_gpu_types=False):
    """Return a list of lines for this node's gres.conf

       include_gpu_types: Emit the type field for each gpu.
    """
    template = "NodeName={hostname} Name=gpu File={file}"
    if include_gpu_types:
        template += " Type={type}"
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

def get_gres_desc(include_gpu_types=False):
    """Return a string describing the generic resources available in this node,

       This fills the Gres field in slurm.conf for this node.
    """
    tokens = []
    gpus = get_gpu_names()
    if include_gpu_types:
        for gpu_type, group in itertools.groupby(sorted(gpus)):
            tokens.append("gpu:{}:{}".format(gpu_type, len(list(group))))
    else:
        if len(gpus) > 0:
            tokens.append("gpu:{}".format(len(gpus)))

    if len(tokens) == 0:
        return ""
    else:
        return "Gres=" + ",".join(tokens)

def get_features():
    features = []
    features += [get_cpu_model()]
    features += list(set(get_gpu_names()))
    return ",".join(features)

def get_slurm_conf(include_gpu_types=False, include_hyperthreads=False):
    """Return a line describing this node's resources to put in slurm.conf"""
    cpu_info = get_cpu_info()
    data = {
        "hostname" : get_hostname(),
        "ipaddr" : get_ipaddr(),
        "cpus" : cpu_info["cpus"] if include_hyperthreads else cpu_info["cores"],
        "threads_per_core" : cpu_info["cpus"] / cpu_info["cores"],
        "cores_per_socket" : cpu_info["cores"] / cpu_info["sockets"],
        "num_sockets" : cpu_info["sockets"],
        "memory" : get_mem_info(),
        "feature" : get_features(),
        "gres" : get_gres_desc(include_gpu_types),
    }
    template = oneline("""\
        NodeName={hostname}
        NodeAddr={ipaddr}
        CPUs={cpus}
        ThreadsPerCore={threads_per_core}
        CoresPerSocket={cores_per_socket}
        Sockets={num_sockets}
        RealMemory={memory}
        Feature={feature}
        {gres}
        State=UNKNOWN
    """)
    return template.format(**data)

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("file", help="Which config file to generate: slurm.conf or gres.conf?")
    parser.add_argument("--include-gpu-types", default=False, action="store_true", help="Emit the type field for each gpu")
    parser.add_argument("--include-hyperthreads", default=False, action="store_true", help="Count each hyperthread as a separate CPU")
    args = parser.parse_args()

    if args.file == "slurm.conf":
        print get_slurm_conf(
            include_gpu_types=args.include_gpu_types,
            include_hyperthreads=args.include_hyperthreads
        )
    elif args.file == "gres.conf":
        print get_gres_conf(
            include_gpu_types=args.include_gpu_types
        )
    else:
        raise Exception("I don't know how to generate {}".format(args.file))
