print(__file__)
import nslsii

beamline_id = 'qas'

nslsii.configure_base(get_ipython().user_ns, beamline_id, bec=False)


# At the end of every run, verify that files were saved and
# print a confirmation message.
from bluesky.callbacks.broker import verify_files_saved
# RE.subscribe(post_run(verify_files_saved), 'stop')

# Optional: set any metadata that rarely changes.

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


# convenience imports
from bluesky.callbacks import *
from bluesky.callbacks.broker import *
from bluesky.simulators import *
from bluesky.plans import *
import numpy as np

from pyOlog.ophyd_tools import *

# Uncomment the following lines to turn on verbose messages for
# debugging.
import logging
# ophyd.logger.setLevel(logging.DEBUG)
# logging.basicConfig(level=logging.DEBUG)

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

import caproto

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

ROOT_PATH = '/nsls2/xf07bm'
RAW_FILEPATH = 'data'
USER_FILEPATH = 'users'
