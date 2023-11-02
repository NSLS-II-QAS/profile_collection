print(__file__)

# Try to capture 'core dump' reasons.
import faulthandler
from pprint import pprint, pformat
faulthandler.enable()

import appdirs
import sys
import psutil
import subprocess
from pathlib import Path

import logging
from logging.handlers import TimedRotatingFileHandler

logger_open_files = logging.getLogger("QAS")
logger_open_files.setLevel(logging.DEBUG)
# logger_open_files.setLevel(logging.INFO)
debug_log_file = str(Path(appdirs.user_log_dir(appname="bluesky")) / Path("debug-open-files.log"))
handler1 = TimedRotatingFileHandler(debug_log_file, when="W0", backupCount=10)
handler1.setLevel(logging.DEBUG)
log_file_format = (
    "[%(levelname)1.1s %(asctime)s.%(msecs)03d %(name)s"
    "  %(module)s:%(lineno)d] %(message)s"
)
handler1.setFormatter(logging.Formatter(fmt=log_file_format))
logger_open_files.addHandler(handler1)
logger_open_files.propagate = False


def audit(event, args):
    if event == "open":
        logger_open_files.debug(f"Opening file: {args}")


def stop_callback(name, doc):
    res = subprocess.run("cat /proc/sys/fs/file-nr".split(), capture_output=True)
    nums = res.stdout.decode().split()

    proc = psutil.Process()

    logger_open_files.info(f"\nBluesky scan UID: {doc['run_start']}\n"
                           f"Current open files: {nums[0]}  |  Max open files: {nums[-1]}\n"
                           f"{pformat(proc.open_files())}")


import nslsii

# warn the user if there is another bsui running
def get_bsui_processes():
    bsui_processes = []
    for process in psutil.process_iter():
        if "bsui" in process.name():
            bsui_processes.append(process)
    return bsui_processes

bsui_processes = get_bsui_processes()
if len(bsui_processes) > 1:
    print("WARNING: more than one bsui process is running!")
    print("\n".join([str(process) for process in bsui_processes]))
    input("Press CTRL-C to quit (recommended) or ENTER to continue")

import ophyd

GLOBAL_TIMEOUT = 60

ophyd.signal.EpicsSignalBase.set_defaults(timeout=GLOBAL_TIMEOUT, connection_timeout=GLOBAL_TIMEOUT)
ophyd.signal.EpicsSignal.set_defaults(timeout=GLOBAL_TIMEOUT, connection_timeout=GLOBAL_TIMEOUT)
ophyd.signal.EpicsSignalRO.set_defaults(timeout=GLOBAL_TIMEOUT, connection_timeout=GLOBAL_TIMEOUT)

beamline_id = 'qas'

from databroker.v0 import Broker
db = Broker.named(beamline_id)
nslsii.configure_base(get_ipython().user_ns, db, bec=False, pbar=False,
                      publish_documents_with_kafka=False)
nslsii.configure_kafka_publisher(RE, 'qas')

# TODO: remove after testing.
# sys.addaudithook(audit)
RE.subscribe(stop_callback, name='stop')

# nslsii.configure_base(get_ipython().user_ns, beamline_id, bec=False)


# At the end of every run, verify that files were saved and
# print a confirmation message.
from bluesky.callbacks.broker import verify_files_saved
# RE.subscribe(post_run(verify_files_saved), 'stop')

# Optional: set any metadata that rarely changes.


# convenience imports
from bluesky.callbacks import *
from bluesky.callbacks.broker import *
from bluesky.simulators import *
from bluesky.plans import *
import numpy as np

from pyOlog.ophyd_tools import *


import os
import sys
from datetime import datetime
import functools

from bluesky.utils import ts_msg_hook
# The logs will be saved to the profile dir.
profile_startup_dir = get_ipython().profile_dir.startup_dir
# The name of the log file consists of the beamline id and the timestamp at the
# startup of bsui, so we don't have collisions of the names.
#log_filename = f'{beamline_id}-bsui-{datetime.now().strftime("%Y%m%d%H%M%S")}.log'
#log_filename = os.path.join(profile_startup_dir, log_filename)
#print(f'\n!!! The logs will be written to {log_filename} !!!\n')
#file = open(log_filename, 'a')
#func = functools.partial(ts_msg_hook, file=file)
#RE.msg_hook = func
RE.msg_hook = ts_msg_hook

#import caproto
import logging

logging.getLogger('caproto').setLevel('ERROR')
logging.getLogger('caproto.ch').setLevel('ERROR')

# caproto_log = os.path.join(profile_startup_dir, f'{beamline_id}-caproto-{datetime.now().strftime("%Y%m%d%H%M%S")}.log')
# caproto.set_handler(file=caproto_log)

# logging.getLogger('bluesky').setLevel('NOTSET')
# import bluesky
# bluesky_log = os.path.join(profile_startup_dir, f'{beamline_id}-bluesky-{datetime.now().strftime("%Y%m%d%H%M%S")}.log')
# bluesky.set_handler(file=bluesky_log)

# print(f'\nThe caproto logs will be written to {caproto_log}')
# print(f'The bluesky logs will be written to {bluesky_log}\n')

ROOT_PATH        = '/nsls2/data/qas-new/legacy'
ROOT_PATH_SHARED = '/nsls2/data/qas-new/shared'
RAW_FILEPATH = 'raw'
USER_FILEPATH = 'processed'

#def print_to_gui(string, stdout=sys.stdout):
#    print(string, file=stdout, flush=True)

try:
    from bluesky.utils import PersistentDict
except ImportError:
    import msgpack
    import msgpack_numpy
    import zict

    class PersistentDict(zict.Func):
        """
        A MutableMapping which syncs it contents to disk.
        The contents are stored as msgpack-serialized files, with one file per item
        in the mapping.
        Note that when an item is *mutated* it is not immediately synced:
        >>> d['sample'] = {"color": "red"}  # immediately synced
        >>> d['sample']['shape'] = 'bar'  # not immediately synced
        but that the full contents are synced to disk when the PersistentDict
        instance is garbage collected.
        """
        def __init__(self, directory):
            self._directory = directory
            self._file = zict.File(directory)
            self._cache = {}
            super().__init__(self._dump, self._load, self._file)
            self.reload()

            # Similar to flush() or _do_update(), but without reference to self
            # to avoid circular reference preventing collection.
            # NOTE: This still doesn't guarantee call on delete or gc.collect()!
            #       Explicitly call flush() if immediate write to disk required.
            def finalize(zfile, cache, dump):
                zfile.update((k, dump(v)) for k, v in cache.items())

            import weakref
            self._finalizer = weakref.finalize(
                self, finalize, self._file, self._cache, PersistentDict._dump)

        @property
        def directory(self):
            return self._directory

        def __setitem__(self, key, value):
            self._cache[key] = value
            super().__setitem__(key, value)

        def __getitem__(self, key):
            return self._cache[key]

        def __delitem__(self, key):
            del self._cache[key]
            super().__delitem__(key)

        def __repr__(self):
            return f"<{self.__class__.__name__} {dict(self)!r}>"

        @staticmethod
        def _dump(obj):
            "Encode as msgpack using numpy-aware encoder."
            # See https://github.com/msgpack/msgpack-python#string-and-binary-type
            # for more on use_bin_type.
            return msgpack.packb(
                obj,
                default=msgpack_numpy.encode,
                use_bin_type=True)

        @staticmethod
        def _load(file):
            return msgpack.unpackb(
                file,
                object_hook=msgpack_numpy.decode,
                raw=False)

        def flush(self):
            """Force a write of the current state to disk"""
            for k, v in self.items():
                super().__setitem__(k, v)

        def reload(self):
            """Force a reload from disk, overwriting current cache"""
            self._cache = dict(super().items())

# runengine_metadata_dir = appdirs.user_data_dir(appname="bluesky") / Path("runengine-metadata")  # writes to ~/.local/...
runengine_metadata_dir = Path(f'{ROOT_PATH_SHARED}/config/bluesky/') / Path("runengine-metadata")
RE.md = PersistentDict(runengine_metadata_dir) # PersistentDict will create the directory if it does not exist

# these should *always* be QAS
RE.md['group'] = beamline_id
RE.md['beamline_id'] = beamline_id.upper()


RE.md['Facility'] = 'NSLS-II'
# RE.md['Mono_pulses_per_deg']=

# isstools reads these

# check these keys exist, if not set to default
keys = ["PI", "PROPOSAL", "SAF", "year", "cycle", "proposal_id"]
defaults = ["No PI", None, None, 2018, 1, None]
for key, default in zip(keys, defaults):
    if key not in RE.md:
        print("Warning {} not in RE.md.".format(key))
        print("Set to default : {}".format(default))
        RE.md[key] = default

RE.is_aborted = False

# This enables counters of PVs.
ophyd.set_cl(pv_telemetry=True)

def print_now():
    return datetime.strftime(datetime.now(), '%Y-%m-%d %H:%M:%S.%f')
    if timeout is DEFAULT_CONNECTION_TIMEOUT:
        timeout = self.connection_timeout
    # print(f'{print_now()}: waiting for {self.name} to connect within {timeout:.4f} s...')


def warmup_hdf5_plugins(detectors):
    """
    Warm-up the hdf5 plugins.

    This is necessary for when the corresponding IOC restarts we have to trigger one image
    for the hdf5 plugin to work correctly, else we get file writing errors.

    Parameter:
    ----------
    detectors: list
    """
    for det in detectors:
        _array_size = det.hdf5.array_size.get()
        if 0 in [_array_size.height, _array_size.width] and hasattr(det, "hdf5"):
            print(f"\n  Warming up HDF5 plugin for {det.name} as the array_size={_array_size}...")
            det.hdf5.warmup()
            print(f"  Warming up HDF5 plugin for {det.name} is done. array_size={det.hdf5.array_size.get()}\n")
        else:
            print(f"\n  Warming up of the HDF5 plugin is not needed for {det.name} as the array_size={_array_size}.")