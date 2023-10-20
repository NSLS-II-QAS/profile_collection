import copy
import functools
import numpy as np
import time

import bluesky.plan_stubs as bps
import bluesky.plans as bp  # noqa
import bluesky.preprocessors as bpp
import bluesky_darkframes

from event_model import DocumentRouter
from ophyd import Device, Component as Cpt, EpicsSignal

from bluesky.utils import ts_msg_hook
RE.msg_hook = ts_msg_hook  # noqa


# this is not needed if you have ophyd >= 1.5.4, maybe
# monkey patch for trailing slash problem
def _ensure_trailing_slash(path, path_semantics=None):
    """
    'a/b/c' -> 'a/b/c/'

    EPICS adds the trailing slash itself if we do not, so in order for the
    setpoint filepath to match the readback filepath, we need to add the
    trailing slash ourselves.
    """
    newpath = os.path.join(path, '')
    if newpath[0] != '/' and newpath[-1] == '/':
        # make it a windows slash
        newpath = newpath[:-1]
    return newpath

ophyd.areadetector.filestore_mixins._ensure_trailing_slash = _ensure_trailing_slash

from event_model import RunRouter
from suitcase.tiff_series import Serializer


def pilatus_serializer_factory(name, doc):
    serializer = Serializer(
        '/nsls2/data/qas-new/legacy/processed/{year}/{cycle}/{PROPOSAL}Pilatus'.format(**doc),
        file_prefix = (
            '{start[sample_name]}-'
            '{start[exposure_time]:.1f}s-'
            '{start[scan_id]}-'
        )
    )
    return [serializer], []


pilatus_serializer_rr = RunRouter([pilatus_serializer_factory], db.reg.handler_reg)

# usage with dark frames:
#   RE(
#       dark_frame_preprocessor(
#           count_qas(
#               [pe1, mono1.energy], shutter_fs, sample_name=?,
#               frame_count=?, subframe_time, subframe_count=?
#           )
#       ),
#       purpose="pe1 debugging"
#    )

def count_pilatus_qas(sample_name, frame_count, subframe_time, subframe_count, delay=None, shutter=shutter_fs, detector=pilatus, **kwargs):
    """

    Diffraction count plan averaging subframe_count exposures for each frame.

    Open the specified shutter before bp.count()'ing, close it when the plan ends.

    Parameters
    ----------
    shutter: Device (but a shutter)
        the shutter to close for background exposures
    sample_name: str
        added to the start document with key "sample_name"
    frame_count: int
        passed to bp.count(..., num=frame_count)
    subframe_time: float
        exposure time for each subframe, total exposure time will be subframe_time*subframe_count
    subframe_count: int
        number of exposures to average for each frame

    Returns
    -------
    run start id
    """
    from bluesky.plan_stubs import one_shot

    def shuttered_oneshot(dets=[detector]):
        yield from bps.mv(shutter, 'Open')
        ret = yield from one_shot(dets)
        yield from bps.mv(shutter, 'Close')
        return ret

    @bpp.subs_decorator(pilatus_serializer_rr)
    def inner_count_qas():
        yield from bps.mv(detector.cam.acquire_time, subframe_time)
        # set acquire_period to slightly longer than exposure_time
        # to avoid spending a lot of time after the exposure just waiting around
        yield from bps.mv(detector.cam.acquire_period, subframe_time + 0.1)
        yield from bps.mv(detector.images_per_set, subframe_count)

        return (
            yield from bp.count(
                detector,
                num=frame_count,
                md={
                    "experiment": 'diffraction',
                    "sample_name": sample_name,
                    "exposure_time": subframe_time * subframe_count
                },
                per_shot=shuttered_oneshot,
                delay=delay
            )
        )

    def finally_plan():
        yield from bps.mv(shutter, "Open")

    return (yield from bpp.finalize_wrapper(inner_count_qas(), finally_plan))