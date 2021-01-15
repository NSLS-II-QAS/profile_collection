import matplotlib.pyplot as plt
from datetime import datetime
from subprocess import call
import time
from scipy.optimize import curve_fit
from bluesky.plan_stubs import mv, mvr
import bluesky.preprocessors as bpp
from random import random

import json

json_file_path = '/nsls2/xf07bm/settings/json/foil_wheel.json'

with open(json_file_path) as fp:
    reference_foils = json.load(fp)

def set_reference_foil(element = None, **metadata):
    # Adding reference foil element list
    elems = [item['element'] for item in reference_foils]
    if element is None:
        yield from mv(foil_wheel.wheel1, 0,
                      foil_wheel.wheel2, 0)
    else:
        if element in elems:
            indx = elems.index(element)

            yield from mv(foil_wheel.wheel1, reference_foils[indx]['fw1'],
                          foil_wheel.wheel2, reference_foils[indx]['fw2'])
        else:
            yield from mv(foil_wheel.wheel1, 0,
                          foil_wheel.wheel2, 0)

def get_reference_foil():

    the_fw1 = round(foil_wheel.wheel1.user_readback.get())
    the_fw2 = round(foil_wheel.wheel2.user_readback.get())
    the_element = None
    for wheel_setting in reference_foils:
        element = wheel_setting["element"]
        fw1 = wheel_setting["fw1"]
        fw2 = wheel_setting["fw2"]
        if fw1 == the_fw1 and fw2 == the_fw2:
            the_element = element
    if the_element is None:
        raise ValueError(f"failed to find an element for fw1={the_fw1} and fw2={the_fw2} in file {json_file_path}")
    return the_element

    #yield from mv(foil_wheel.wheel2, reference[element]['foilwheel2'])
    #yield from mv(foil_wheel.wheel1, reference[element]['foilwheel1'])


