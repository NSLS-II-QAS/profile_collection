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


class DarkSubtractionCallback(DocumentRouter):
    def __init__(self,
                 image_key='pe1_image',
                 primary_stream='primary',
                 dark_stream='dark'):
        """Initializes a dark subtraction callback.

        This will perform dark subtraction and then save to file.

        Parameters
        ----------
        image_key : str (optional)
            The detector image string
        primary_stream : str (optional)
            The primary stream name
        dark_stream : str (optional)
            The dark stream name
        """

        self.pstream = primary_stream
        self.dstream = dark_stream
        self.image_key = image_key
        self.descriptors = {}
        self._last_dark = None
        self._has_started = False

    def start(self, doc):
        if self._has_started:
            raise RuntimeError('Can handle only one run. '
                               'Two start documents found.')
        else:
            self._has_started = True
            return super().start(doc)

    def descriptor(self, doc):
        # Note: we may want to indicate background subtraction
        self.descriptors[doc['uid']] = doc
        return super().descriptor(doc)

    def event_page(self, doc):
        # Note: we may want to update the image key to indicate background
        # subtraction in the outgoing doc.
        stream_name = self.descriptors[doc['descriptor']]['name']

        if stream_name not in [self.pstream, self.dstream]:
            return doc

        if self.image_key in doc['data']:
            if stream_name == self.dstream:
                self._last_dark = doc['data'][self.image_key][-1]
                # TODO: deal with properly-paged data later
                return doc
            elif stream_name == self.pstream:
                # Actual subtraction is happening here:
                return_doc = copy.deepcopy(doc)
                dsub_images = [im - self._last_dark
                               for im in return_doc['data'][self.image_key]]

                return_doc['data'][self.image_key] = dsub_images
                return return_doc
            else:
                raise RuntimeError(f'The stream name "{stream_name}" must be '
                                   f'one of {self.pstream} or {self.dstream}')
        else:
            return doc


# From Tom on 02/21/2019:
class DarkFrameCache(Device):
    def __init__(self, *args, **kwargs):
        # self.det = det
        self.last_collected = None
        self.just_started = True
        self.update_done = False
        return super().__init__(*args, **kwargs)

    def read(self):
        return self._read

    def read_configuration(self):
        return self._read_configuration

    @property
    def configuration_attrs(self):
        return self._configuration_attrs

    @property
    def read_attrs(self):
        return self._read_attrs

    def describe(self):
        return self._describe

    def describe_configuration(self):
        return self._describe_configuration

    # def describe_configuration(self):
    #     return self.det.describe_configuration

    def collect_asset_docs(self):
        # keep track of when we get restaged to restore these
        yield from self._asset_docs_cache
        self._really_cached = self._asset_docs_cache
        self._asset_docs_cache = []

    def stage(self):
        self._asset_docs_cache = self._really_cached


def dark_plan_old(cam, dark_frame_cache, obsolete_secs, shutter):
    if (dark_frame_cache.just_started or  # first run after instantiation
        (dark_frame_cache.last_collected is not None and
         time.monotonic() - dark_frame_cache.last_collected > obsolete_secs)):
        tmp = yield from bps.read(shutter.status)
        init_shutter_state = tmp[shutter.status.name]['value'] if tmp is not None else None
        yield from bps.mv(shutter, 'Close')
        yield from bps.trigger(cam, group='cam')
        yield from bps.wait('cam')
        yield from bps.mv(shutter, init_shutter_state)

        teleport(cam, dark_frame_cache)
        dark_frame_cache.just_started = False
        dark_frame_cache.update_done = True
    else:
        dark_frame_cache.update_done = False


from bluesky_darkframes import DarkSubtraction
from event_model import RunRouter
from suitcase.tiff_series import Serializer


def pilatus_serializer_factory(name, doc):
    serializer = Serializer(
        '/nsls2/data/qas-new/legacy/processed/{year}/{cycle}/{PROPOSAL}XRD'.format(**doc),
        file_prefix = (
            '{start[sample_name]}-'
            '{start[exposure_time]:.1f}s-'
            '{start[scan_id]}-'
        )
    )


def darksubtraction_serializer_factory(name, doc):
    # The problem this is solving is to store documents from this run long
    # enough to cross-reference them (e.g. light frames and dark frames),
    # and then tearing it down when we're done with this run.
    subtractor = DarkSubtraction('pe1_image')
    # CHANGE HERE TO ADJUST HOW THE EXPORTED FILES ARE NAMED
    serializer = Serializer(
        '/nsls2/data/qas-new/legacy/processed/{year}/{cycle}/{PROPOSAL}XRD'.format(**doc),
        file_prefix=(
            '{start[sample_name]}-'
            '{start[exposure_time]:.1f}s-'
            '{descriptor[configuration][pe1][data][pe1_sample_to_detector_distance]}mm-'
            #'{event[data][mono1_energy]:.1f}eV-'
            '{start[scan_id]}-'
        )
    )

    stream_map = dict()

    # And by returning this function below, we are routing all other
    # documents *for this run* through here.
    def subtract_and_serialize(name, doc):
        name, doc = subtractor(name, doc)
        #if name == "descriptor":
        #    stream_map[doc["uid"]] = doc["name"]
        #if "event" in name:
        #    if stream_map[doc["descriptor"]] != "primary":
        #        return
        serializer(name, doc)

    return [subtract_and_serialize], []

darksubtraction_serializer_rr = RunRouter([darksubtraction_serializer_factory], db.reg.handler_reg)

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

def _count_qas(detectors, shutter, sample_name, frame_count, subframe_time, subframe_count, delay):
    """
    Diffraction count plan averaging subframe_count exposures for each frame.

    Open the specified shutter before bp.count()'ing, close it when the plan ends.

    Parameters
    ----------
    detectors: list
        list of devices to be bp.count()'d, should include pe1
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

    def shuttered_oneshot(dets):
        yield from bps.mv(shutter, 'Open')
        ret = yield from one_shot(dets)
        yield from bps.mv(shutter, 'Close')
        return ret

    @bpp.subs_decorator(darksubtraction_serializer_rr)
    def inner_count_qas():
        if pe1 in detectors:
            yield from bps.mv(pe1.cam.acquire_time, subframe_time)
            # set acquire_period to slightly longer than exposure_time
            # to avoid spending a lot of time after the exposure just waiting around
            yield from bps.mv(pe1.cam.acquire_period, subframe_time + 0.1)
            yield from bps.mv(pe1.images_per_set, subframe_count)

        return (
            yield from bp.count(
                detectors,
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


# new dark plan
def dark_plan(cam):
    # Restage to ensure that dark frames goes into a separate file.
    yield from bps.unstage(cam)
    yield from bps.stage(cam)

    # TO TWEAK NUMBER OF FRAME FOR DARK FRAME ADD CHECKS HERE

    tmp = yield from bps.read(shutter_fs.status)
    init_shutter_state = tmp[shutter_fs.status.name]['value'] if tmp is not None else None
    yield from bps.mv(shutter_fs, 'Close')
    # MAY NEED A SLEEP HERE INCASE THE FAST SHUTTER IS LYING TO US
    yield from bps.trigger(cam, group='dark-plan-trigger')
    yield from bps.wait('dark-plan-trigger')
    yield from bps.mv(shutter_fs, init_shutter_state)

    snapshot = bluesky_darkframes.SnapshotDevice(cam)
    # Restage.
    yield from bps.unstage(cam)
    yield from bps.stage(cam)
    return snapshot


    # Always take a fresh dark frame at the beginning of each frame.
dark_frame_preprocessor = bluesky_darkframes.DarkFramePreprocessor(
                          dark_plan=dark_plan,
                          detector=pe1,
                          # HOW LONG IS THE DARKFRAME GOOD FOR IN SECONDS
                          max_age=0,
                          # ANY SIGNALS TO WATCH THAT IF THEY CHANGE INVALIDATE THE DARKFRAME CACHE
                          locked_signals=(),
                          )


def count_qas(sample_name, frame_count, subframe_time, subframe_count, delay=None, **kwargs):
    """

    **If we want to use different number of sub-frames for light and dark averaging,
    it has to be done inside this function call, I think - CD**

    Diffraction count plan averaging subframe_count exposures for each frame.

    Open the specified shutter before bp.count()'ing, close it when the plan ends.

    Parameters
    ----------
    detectors: list
        list of devices to be bp.count()'d, should include pe1
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

    return (yield from dark_frame_preprocessor(
        _count_qas([pe1], shutter_fs, sample_name, frame_count, subframe_time, subframe_count, delay)
        )
        )

def subtract_dark(light_img, dark_img):
    res = np.asarray(light_img, dtype=int) - np.asarray(dark_img, dtype=int)
    return np.clip(res, 0, None)


def get_subtracted_image(scan_id=-1, img_field='pe1_image'):
    hdr = db[scan_id]  # noqa
    imgs_dark = np.array(list(hdr.data(img_field, stream_name='dark')))
    imgs_light = np.array(list(hdr.data(img_field, stream_name='primary')))
    dark_avg = np.mean(imgs_dark, axis=0)
    light_avg = np.mean(imgs_light, axis=0)
    sub = subtract_dark(light_avg, dark_avg)
    return sub





    # from bluesky.plan_stubs import one_shot
    #
    # def shuttered_oneshot(dets):
    #     yield from bps.mv(shutter, 'Open')
    #     ret = yield from one_shot(dets)
    #     yield from bps.mv(shutter, 'Close')
    #     return ret
    #
    # @bpp.subs_decorator(darksubtraction_serializer_rr)
    # def inner_count_qas():
    #     if pilatus in detectors:
    #         yield from bps.mv(pilatus.cam.acquire_time, exposure_time)
    #         # set acquire_period to slightly longer than exposure_time
    #         # to avoid spending a lot of time after the exposure just waiting around
    #         yield from bps.mv(pilatus.cam.acquire_period, exposure_time + 0.1)
    #         # yield from bps.mv(pilatus.images_per_set, subframe_count)
    #
    #     return (
    #         yield from bp.count(
    #             detectors,
    #             num=number_of_images,
    #             md={
    #                 "experiment": 'diffraction',
    #                 "sample_name": sample_name,
    #                 "exposure_time": subframe_time * subframe_count
    #             },
    #             per_shot=shuttered_oneshot,
    #             delay=delay
    #         )
    #     )
    #
    # def finally_plan():
    #     yield from bps.mv(shutter, "Open")
    #
    # return (yield from bpp.finalize_wrapper(inner_count_qas(), finally_plan))
    #
    #
    # pass



# def plot_image(data, **kwargs):
#     p = functools.partial(plt.imshow, cmap='gray', clim=(0, 500))  # noqa
#     p(data, **kwargs)
#     from tifffile import TiffWriter
#
#     ##File saving needs to be done properly via suite-case
#     with open('/data/nsls2/qas-new/legacy/raw/pe1_data/2019/05/23/Diffraction_Image.tiff', 'xb') as f:
#         tw = TiffWriter(f)
#         tw.save(data)

# RE(dark_frame_aware_plan(cam, dc))
# # BOILERPLATE SETUP
#
# from bluesky import RunEngine
# from bluesky.plans import rel_grid_scan, count
# from bluesky.plan_stubs import mv
# from event_model import Filler
# from ophyd import Device, EpicsSignal, Component
# from ophyd.signal import EpicsSignalBase
# from ophyd.areadetector.filestore_mixins import resource_factory
# from databroker import Broker
# from bluesky.preprocessors import SupplementalData
# import bluesky.plan_stubs as bps
# import bluesky.preprocessors
# import time
# import os
# import uuid
# from pathlib import Path
# import numpy
#
#
# def handler(resource_path, **kwargs):
#     resource_path = resource_path
#
#     def get():
#         return numpy.load(resource_path)
#
#     return get
#
#
# class DarkFrameCache(Device):
#     def __init__(self, *args, **kwargs):
#         # self.det = det
#         self.last_collected = None
#         self.just_started = True
#         self.update_done = False
#         self._assets_collected = True
#         return super().__init__(*args, **kwargs)
#
#     def read(self):
#         return self._read
#
#     def read_configuration(self):
#         return self._read_configuration
#
#     @property
#     def configuration_attrs(self):
#         return self._configuration_attrs
#
#     @property
#     def read_attrs(self):
#         return self._read_attrs
#
#     def describe(self):
#         return self._describe
#
#     def describe_configuration(self):
#         return self._describe_configuration
#
#     # def describe_configuration(self):
#     #     return self.det.describe_configuration
#
#     def collect_asset_docs(self):
#         if self._assets_collected:
#             yield from []
#         else:
#             yield from self._asset_docs_cache
#
#     def stage(self):
#         self._assets_collected = False
#
# def teleport(camera, dark_frame_cache):
#     dark_frame_cache._describe = camera.describe()
#     dark_frame_cache._describe_configuration = camera.describe_configuration()
#     dark_frame_cache._read = camera.read()
#     dark_frame_cache._read_configuration = camera.read_configuration()
#     dark_frame_cache._read_attrs = list(camera.read())
#     dark_frame_cache._configuration_attrs = list(camera.read_configuration())
#     dark_frame_cache._asset_docs_cache = list(camera.collect_asset_docs())
#     dark_frame_cache.last_collected = time.monotonic()
#
#
# dark_frame_cache = DarkFrameCache(name='dark_frame_cache')
#
#
# class InsertReferenceToDarkFrame:
#     """
#     A plan preprocessor that ensures one 'dark' Event per run.
#     """
#     def __init__(self, dark_frame_cache, stream_name='dark'):
#         self.dark_frame_cache = dark_frame_cache
#         self.stream_name = stream_name
#
#     def __call__(self, plan):
#
#         def insert_reference_to_dark_frame(msg):
#             if msg.command == 'open_run':
#                 return (
#                     bluesky.preprocessors.pchain(
#                         bluesky.preprocessors.single_gen(msg),
#                         bps.stage(self.dark_frame_cache),
#                         bps.trigger_and_read([self.dark_frame_cache], name='dark'),
#                         bps.unstage(self.dark_frame_cache)
#                     ),
#                     None,
#                 )
#             else:
#                 return None, None
#
#         return (yield from bluesky.preprocessors.plan_mutator(
#             plan, insert_reference_to_dark_frame))
#
#
# def dark_plan(detector, dark_frame_cache, max_age, shutter):
#     if (dark_frame_cache.just_started or  # first run after instantiation
#         (dark_frame_cache.last_collected is not None and
#          time.monotonic() - dark_frame_cache.last_collected > max_age)):
#         init_shutter_state = shutter.get()
#         yield from bps.mv(shutter, 'Close')
#         yield from bps.trigger(detector, group='cam')
#         yield from bps.wait('cam')
#         yield from bps.mv(shutter, init_shutter_state)
#
#
#         teleport(detector, dark_frame_cache)
#         dark_frame_cache.just_started = False
#         dark_frame_cache.update_done = True
#     else:
#         dark_frame_cache.update_done = False
#
#
# class TakeDarkFrames:
#     def __init__(self, detector, dark_frame_cache, max_age, shutter):
#         self.detector = detector
#         self.dark_frame_cache = dark_frame_cache
#         self.max_age = max_age
#         self.shutter = shutter
#
#     def __call__(self, plan):
#
#         def insert_take_dark(msg):
#             if msg.command == 'open_run':
#                 return (
#                     bluesky.preprocessors.pchain(
#                         dark_plan(
#                             self.detector,
#                             self.dark_frame_cache,
#                             self.max_age,
#                             self.shutter),
#                         bluesky.preprocessors.single_gen(msg),
#                     ),
#                     None,
#                 )
#             else:
#                 return None, None
#
#         return (yield from bluesky.preprocessors.plan_mutator(plan, insert_take_dark))
#
#
# take_dark_frames = TakeDarkFrames(pe1c, dark_frame_cache, 10, shutter_fs)
# insert_reference_to_dark_frame = InsertReferenceToDarkFrame(dark_frame_cache)
# RE.preprocessors.append(insert_reference_to_dark_frame)
# RE.preprocessors.append(take_dark_frames)
#
#
# import event_model
# import suitcase.tiff_series
#
#
# class DarkSubtraction(event_model.DocumentRouter):
#     def __init__(self, *args, **kwargs):
#         self.dark_descriptor = None
#         self.primary_descriptor = None
#         self.dark_frame = None
#         super().__init__(*args, **kwargs)
#
#     def descriptor(self, doc):
#         if doc['name'] == 'dark':
#             self.dark_descriptor = doc['uid']
#         elif doc['name'] == 'primary':
#             self.primary_descriptor = doc['uid']
#         return super().descriptor(doc)
#
#     def event_page(self, doc):
#         event = self.event  # Avoid attribute lookup in hot loop.
#         filled_events = []
#
#         for event_doc in event_model.unpack_event_page(doc):
#             filled_events.append(event(event_doc))
#         new_event_page = event_model.pack_event_page(*filled_events)
#         # Modify original doc in place, as we do with 'event'.
#         doc['data'] = new_event_page['data']
#         return doc
#
#     def event(self, doc):
#         FIELD = 'pe1_image'  # TODO Do not hard-code this.
#         if doc['descriptor'] == self.dark_descriptor:
#             self.dark_frame = doc['data']['pe1_image']
#         if doc['descriptor'] == self.primary_descriptor:
#             doc['data'][FIELD] = self.subtract(doc['data'][FIELD], self.dark_frame)
#         return doc
#
#     def subtract(self, light, dark):
#         return numpy.clip(light - dark, a_min=0, a_max=None).astype(numpy.uint16)
#
#
# def factory(name, start_doc):
#
#     # Fill externally-stored data into Documents.
#     filler = Filler(db.reg.handler_reg)
#     filler(name, start_doc)  # modifies doc in place
#     # Do dark subtraction "in place".
#     dark_subtraction = DarkSubtraction()
#     dark_subtraction(name, start_doc)
#
#     def subfactory(name, descriptor_doc):
#         if descriptor_doc['name'] == 'primary':
#             serializer = suitcase.tiff_series.Serializer(
#                     'exported/', file_prefix='{start[uid]:.8}-')
#             serializer('start', start_doc)
#             serializer('descriptor', descriptor_doc)
#             return [serializer]
#         else:
#             return []
#
#     # Uncomment this to export un-subtracted images as well.
#     # raw_serializer = suitcase.tiff_series.Serializer('exported/',
#     #         file_prefix='RAW-{start[name]}-{start[uid]:.8}-')
#     # raw_serializer('start', start_doc)
#     # return [filler, raw_serializer, dark_subtraction], [subfactory]
#
#     return [filler, dark_subtraction], [subfactory]
#
#
# from event_model import RunRouter
# rr = RunRouter([factory])
# RE.subscribe(rr)
