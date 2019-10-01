import matplotlib.pyplot as plt
from datetime import datetime
from subprocess import call
import time
from scipy.optimize import curve_fit
from bluesky.plan_stubs import mv, mvr
import bluesky.preprocessors as bpp
from random import random
from xas.trajectory import trajectory_manager
import json


with open('/nsls2/xf07bm/settings/json/foil_wheel.json') as fp:
    reference_foils = json.load(fp)


def set_reference_foil(element = None):
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

        #yield from mv(foil_wheel.wheel2, reference[element]['foilwheel2'])
        #yield from mv(foil_wheel.wheel1, reference[element]['foilwheel1'])


