import itertools
import uuid
from collections import OrderedDict, deque

from nslsii.ad33 import SingleTriggerV33, StatsPluginV33
from ophyd import Component as Cpt
from ophyd import Device, EpicsSignal, HDF5Plugin, OverlayPlugin, ROIPlugin, Signal
from ophyd.areadetector import TIFFPlugin
from ophyd.areadetector.base import DDC_EpicsSignalRO, DDC_SignalWithRBV
from ophyd.areadetector.base import EpicsSignalWithRBV as SignalWithRBV
from ophyd.areadetector.cam import PilatusDetectorCam
from ophyd.areadetector.detectors import PilatusDetector
from ophyd.areadetector.filestore_mixins import FileStoreHDF5IterativeWrite, FileStoreTIFFIterativeWrite
from ophyd.areadetector.plugins import ImagePlugin_V33, ROIStatPlugin_V34
from ophyd.sim import NullStatus

ROOT_PATH = "/nsls2/data/qas-new/legacy"
ROOT_PATH_SHARED = "/nsls2/data/qas-new/shared"
RAW_PATH = "raw"
USER_FILEPATH = "processed"

######################################################################################

import ophyd
from ophyd.areadetector import (AreaDetector, CamBase, HDF5Plugin, ImagePlugin, ProcessPlugin, ROIPlugin, StatsPlugin,
                                TIFFPlugin)
from ophyd.areadetector.filestore_mixins import (FileStoreBase, FileStoreHDF5IterativeWrite, FileStoreIterativeWrite,
                                                 FileStorePluginBase, FileStoreTIFF, FileStoreTIFFIterativeWrite,
                                                 FileStoreTIFFSquashing)
from ophyd.areadetector.plugins import HDF5Plugin_V33

######################################################################################


class PilatusDetectorCamV33(PilatusDetectorCam):
    """This is used to update the Pilatus to AD33."""

    file_path = Cpt(SignalWithRBV, "FilePath", string=True)
    file_name = Cpt(SignalWithRBV, "FileName", string=True)
    file_template = Cpt(SignalWithRBV, "FileName", string=True)
    file_number = Cpt(SignalWithRBV, "FileNumber")
    file_auto_increment = Cpt(SignalWithRBV, "AutoIncrement")
    set_energy = Cpt(SignalWithRBV, "Energy")

    wait_for_plugins = Cpt(EpicsSignal, "WaitForPlugins", string=True, kind="config")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stage_sigs.update(
            {
                "wait_for_plugins": "Yes",
                "file_auto_increment": "Yes",
                "file_number": 0,
            }
        )

    def ensure_nonblocking(self):
        self.stage_sigs["wait_for_plugins"] = "Yes"
        for c in self.parent.component_names:
            cpt = getattr(self.parent, c)
            if cpt is self:
                continue
            if hasattr(cpt, "ensure_nonblocking"):
                cpt.ensure_nonblocking()


class FileStoreHDF5Squashing(FileStorePluginBase):
    r"""Write out 'squashed' HDF5

    .. note::

       See :class:`FileStoreBase` for the rest of the required parametrs

    This mixin will also configure the ``cam`` and ``proc`` plugins
    on the parent.

    This is useful to work around the dynamic range of detectors
    and minimizing disk spaced used by synthetically increasing
    the exposure time of the saved images.

    Parameters
    ----------
    images_per_set_name, number_of_sets_name : str, optional
        The names of the signals on the parent to get the
        images_pre_set and number_of_sets from.

        The total number of frames extracted from the camera will be
        :math:`number\_of\_sets * images\_per\_set` and result in
        ``number_of_sets`` frames in the HDF5 file each of which is the average of
        ``images_per_set`` frames from the detector.

        Defaults to ``'images_per_set'`` and ``'number_of_sets'``

    cam_name : str, optional
        The name of the :class:`~ophyd.areadetector.cam.CamBase`
        instance on the parent.

        Defaults to ``'cam'``

    proc_name : str, optional
        The name of the
        :class:`~ophyd.areadetector.plugins.ProcessPlugin` instance on
        the parent.

        Defaults to ``'proc1'``

    Notes
    -----

    This class in cooperative and expected to particpate in multiple
    inheritance, all ``*args`` and extra ``**kwargs`` are passed up the
    MRO chain.

    """

    def __init__(
        self,
        *args,
        images_per_set_name="images_per_set",
        number_of_sets_name="number_of_sets",
        cam_name="cam",
        proc_name="proc",
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.filestore_spec = "AD_HDF5_SWMR"  # spec name stored in resource doc
        self._ips_name = images_per_set_name
        self._num_sets_name = number_of_sets_name
        self._cam_name = cam_name
        self._proc_name = proc_name
        cam = getattr(self.parent, self._cam_name)
        proc = getattr(self.parent, self._proc_name)
        self.stage_sigs.update(
            [
                ("file_template", "%s%s_%6.6d.h5"),
                ("file_write_mode", "Stream"),
                ("capture", 1),
                (proc.nd_array_port, cam.port_name.get()),
                (proc.reset_filter, 1),
                (proc.enable_filter, 1),
                (proc.filter_type, "RecursiveAve"),
                (proc.auto_reset_filter, 1),
                (proc.filter_callbacks, 1),
                ("nd_array_port", proc.port_name.get()),
            ]
        )

    def get_frames_per_point(self):
        return getattr(self.parent, self._num_sets_name).get()

    def stage(self):
        # print(f"Before staging: {self._fn = }\n{self._fp = }")

        cam = getattr(self.parent, self._cam_name)
        proc = getattr(self.parent, self._proc_name)
        images_per_set = getattr(self.parent, self._ips_name).get()
        num_sets = getattr(self.parent, self._num_sets_name).get()

        self.stage_sigs.update(
            [
                (proc.num_filter, images_per_set),
                (cam.num_images, images_per_set * num_sets),
            ]
        )
        super().stage()
        resource_kwargs = {
            "frame_per_point": self.get_frames_per_point(),
        }
        self._generate_resource(resource_kwargs)
        # print(f"After staging: {self._fn = }\n{self._fp = }")


class QASHDF5Plugin(HDF5Plugin_V33, FileStoreHDF5Squashing, FileStoreIterativeWrite):
    pass


class HDF5PluginWithFileStore(HDF5Plugin_V33, FileStoreHDF5IterativeWrite):
    """Add this as a component to detectors that write HDF5s."""

    def get_frames_per_point(self):
        return 1
        # if not self.parent.is_flying:
        #     return self.parent.cam.num_images.get()
        # else:
        #     return 1


# Making ROIStatPlugin that is actually useful
class QASROIStatPlugin(ROIStatPlugin_V34):
    for i in range(1, 5):
        _attr = f"roi{i}"
        _attr_min_x = f"min_x"
        _attr_min_y = f"min_y"
        _pv_min_x = f"{i}:MinX"
        _pv_min_y = f"{i}:MinY"
        _attr_size_x = f"size_x"
        _attr_size_y = f"size_y"
        _pv_size_x = f"{i}:SizeX"
        _pv_size_y = f"{i}:SizeY"

        # this does work:
        vars()[_attr] = DDC_SignalWithRBV(
            (_attr_min_x, _pv_min_x),
            (_attr_min_y, _pv_min_y),
            (_attr_size_x, _pv_size_x),
            (_attr_size_y, _pv_size_y),
            doc="ROI position and size in XY",
            kind="normal",
        )

        _attr = f"stats{i}"
        _attr_total = f"total"
        _pv_total = f"{i}:Total_RBV"
        _attr_max = f"max_value"
        _pv_max = f"{i}:MaxValue_RBV"
        vars()[_attr] = DDC_EpicsSignalRO(
            (_attr_total, _pv_total),
            (_attr_max, _pv_max),
            doc="ROI stats",
            kind="normal",
        )


class PilatusDetectorNonBlocking(PilatusDetector):
    cam = Cpt(PilatusDetectorCamV33, "cam1:")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cam.ensure_nonblocking()


class PilatusBase(SingleTriggerV33, PilatusDetectorNonBlocking):
    roi1 = Cpt(ROIPlugin, "ROI1:")
    roi2 = Cpt(ROIPlugin, "ROI2:")
    roi3 = Cpt(ROIPlugin, "ROI3:")
    roi4 = Cpt(ROIPlugin, "ROI4:")

    stats1 = Cpt(StatsPluginV33, "Stats1:", read_attrs=["total", "max_value"])
    stats2 = Cpt(StatsPluginV33, "Stats2:", read_attrs=["total"])
    stats3 = Cpt(StatsPluginV33, "Stats3:", read_attrs=["total"])
    stats4 = Cpt(StatsPluginV33, "Stats4:", read_attrs=["total"])
    image = Cpt(ImagePlugin_V33, "image1:")

    roistat = Cpt(QASROIStatPlugin, "ROIStat1:")
    # roistat = Cpt(ROIStatPlugin_V34, 'ROIStat1:')

    over1 = Cpt(OverlayPlugin, "Over1:")

    readout = 0.0025  # seconds; actually it is 0.0023, but we are conservative

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.hint_channels()
        # self._is_flying = False

    def hint_channels(self):
        self.stats1.kind = "hinted"
        self.stats1.total.kind = "hinted"
        self.stats2.kind = "hinted"
        self.stats2.total.kind = "hinted"
        self.stats3.kind = "hinted"
        self.stats3.total.kind = "hinted"
        self.stats4.kind = "hinted"
        self.stats4.total.kind = "hinted"

    def read_exposure_time(self):
        return self.cam.acquire_period.get()

    def set_exposure_time(self, exp_t):
        self.cam.acquire_time.put(np.floor((exp_t - self.readout) * 1000) / 1000)
        self.cam.acquire_period.put(exp_t)

    def set_num_images(self, num):
        self.cam.num_images.put(num)
        self.hdf5.num_capture.put(num)

    # def det_next_file(self, n):
    #     self.cam.file_number.put(n)

    def enforce_roi_match_between_plugins(self):
        for i in range(1, 5):
            _attr = getattr(self, f"roi{i}")
            _x = _attr.min_xyz.min_x.get()
            _y = _attr.min_xyz.min_y.get()
            _xs = _attr.size.x.get()
            _ys = _attr.size.y.get()
            _attr2 = getattr(self.roistat, f"roi{i}")
            _attr2.min_x.set(_x)
            _attr2.min_y.set(_y)
            _attr2.size_x.set(_xs)
            _attr2.size_y.set(_ys)

    def stage(self):
        self.enforce_roi_match_between_plugins()
        self.cam.file_name.put(f"{str(uuid.uuid4())[:8]}_")
        return super().stage()

    def get_roi_coords(self, roi_num):
        x = getattr(self, f"roi{roi_num}").min_xyz.min_x.get()
        y = getattr(self, f"roi{roi_num}").min_xyz.min_y.get()
        dx = getattr(self, f"roi{roi_num}").size.x.get()
        dy = getattr(self, f"roi{roi_num}").size.y.get()
        return x, y, dx, dy

    @property
    def roi_metadata(self):
        md = {}
        key_table = {"x": "min_x", "dx": "size_x", "y": "min_y", "dy": "size_y"}
        for i in range(1, 5):
            k_roi = f"roi{i}"
            roi_md = {}
            for k_md, k_epics in key_table.items():
                roi_md[k_md] = getattr(self.roistat, f"{k_roi}.{k_epics}").value
            md[k_roi] = roi_md
        return md

    def read_config_metadata(self):
        md = {}
        md["device_name"] = self.name
        md["roi"] = self.roi_metadata
        return md


class PilatusHDF5(PilatusBase):
    hdf5 = Cpt(
        HDF5PluginWithFileStore,
        suffix="HDF1:",
        root="/",
        write_path_template=f"{ROOT_PATH}/{RAW_PATH}/pilatus3/%Y/%m/%d",
    )  # ,
    # write_path_template=f'/nsls2/xf08id/data/pil900k/%Y/%m/%d')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_primary_roi(1)
        # self.set_primary_roi(2)
        # self.set_primary_roi(3)
        # self.set_primary_roi(4)

        self.hdf5.stage_sigs.update(
            [
                (self.hdf5.swmr_mode, "On"),
                (self.hdf5.num_frames_flush, 1),
            ]
        )

    def set_primary_roi(self, num):
        st = f"stats{num}"
        # self.read_attrs = [st, 'tiff']
        self.read_attrs = [st, "hdf5"]
        getattr(self, st).kind = "hinted"


class PilatusHDF5Squashing(PilatusHDF5):
    image = Cpt(ImagePlugin, "image1:")
    hdf5 = Cpt(
        QASHDF5Plugin,
        "HDF1:",
        write_path_template=f"{ROOT_PATH}/{RAW_PATH}/pilatus3/%Y/%m/%d",
        cam_name="cam",
        proc_name="proc",
        read_attrs=[],
        root=f"{ROOT_PATH}/{RAW_PATH}/pilatus3",
    )
    proc = Cpt(ProcessPlugin, "Proc1:")

    # These attributes together replace `num_images`. They control
    # summing images before they are stored by the detector (a.k.a. "tiff
    # squashing").
    images_per_set = Cpt(Signal, value=1, add_prefix=())
    number_of_sets = Cpt(Signal, value=1, add_prefix=())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.proc.stage_sigs.update(
            [
                (self.proc.filter_type, "RecursiveAve"),
                (self.proc.data_type_out, "UInt16"),
            ]
        )
        self.cam.stage_sigs.update(
            [
                (self.cam.image_mode, "Single"),
            ]
        )


class PilatusStreamHDF5(PilatusHDF5):
    def __init__(self, *args, ext_trigger_device=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.ext_trigger_device = ext_trigger_device
        self._asset_docs_cache = deque()
        self._datum_counter = None

        self.datum_keys = [{"data_type": "image", "roi_num": 0}]
        for i in range(4):
            self.datum_keys.append({"data_type": "roi", "roi_num": i + 1})

    def format_datum_key(self, input_dict):
        output = f'pilatus_{input_dict["data_type"]}'
        if input_dict["data_type"] == "roi":
            output += f'{input_dict["roi_num"]:01d}'
        return output

    def prepare_to_fly(self, traj_duration):
        self.acq_rate = self.ext_trigger_device.freq.get()
        self.num_points = int(self.acq_rate * (traj_duration + 1))
        self.ext_trigger_device.prepare_to_fly(traj_duration)

    # TODO: change blocking to NO upon staging of this class !!!
    def stage(self):
        staged_list = super().stage()
        self._datum_counter = itertools.count()
        # self.is_flying = True
        self.hdf5._asset_docs_cache[0][1]["spec"] = "PILATUS_HDF5"  # This is to make the files to go to correct handler
        self.hdf5._asset_docs_cache[0][1]["resource_kwargs"] = {}  # This is to make the files to go to correct handler

        self.set_num_images(self.num_points)
        # for i in range(10):
        #     if self.cam.num_images.get() != self.num_points:
        #         self.set_num_images(self.num_points)
        #         ttime.sleep(0.1)
        #     else:
        #         break
        self.set_exposure_time(1 / self.acq_rate)
        self.cam.array_counter.put(0)
        # pilatus_stream.cam.trigger_mode.enum_strs: ('Internal', 'Ext. Enable', 'Ext. Trigger', 'Mult. Trigger', 'Alignment')
        self.cam.trigger_mode.put(2)  # 'Ext. Trigger'
        # pilatus_stream.cam.image_mode.enum_strs: ('Single', 'Multiple', 'Continuous')
        self.cam.image_mode.put(1)  # 'Multiple'

        # self.hdf5.blocking_callbacks.put(1)

        # staged_list += self.ext_trigger_device.stage()
        return staged_list

    def unstage(self):
        self._datum_counter = None

        unstaged_list = super().unstage()
        self.cam.trigger_mode.put(0)
        self.cam.image_mode.put(0)
        self.set_num_images(1)
        self.set_exposure_time(1)
        # self.hdf5.blocking_callbacks.put(0)
        # unstaged_list += self.ext_trigger_device.unstage()
        return unstaged_list

    def kickoff(self):
        self.cam.acquire.set(1).wait()
        return self.ext_trigger_device.kickoff()

    def complete(self):
        print(f"Pilatus complete is starting...", add_timestamp=True)
        acquire_status = self.cam.acquire.set(0)
        capture_status = self.hdf5.capture.set(0)
        (acquire_status and capture_status).wait()

        ext_trigger_status = self.ext_trigger_device.complete()
        for resource in self.hdf5._asset_docs_cache:
            self._asset_docs_cache.append(("resource", resource[1]))
        self._datum_ids = []
        # num_frames = self.hdf5.num_captured.get()
        _resource_uid = self.hdf5._resource_uid
        self._datum_ids = {}

        for datum_key_dict in self.datum_keys:
            datum_key = self.format_datum_key(datum_key_dict)
            datum_id = f"{_resource_uid}/{datum_key}"
            self._datum_ids[datum_key] = datum_id
            doc = {
                "resource": _resource_uid,
                "datum_id": datum_id,
                "datum_kwargs": datum_key_dict,
            }
            self._asset_docs_cache.append(("datum", doc))

        # datum_kwargs = [{'frame': i} for i in range(num_frames)]
        # doc = compose_bulk_datum(resource_uid=_resource_uid,
        #                          counter=self._datum_counter,
        #                          datum_kwargs=datum_kwargs)
        # self._asset_docs_cache.append(('bulk_datum', doc))
        # _datum_id_counter = itertools.count()
        # for frame_num in range(num_frames):
        #     datum_id = '{}/{}'.format(_resource_uid, next(_datum_id_counter))
        #     self._datum_ids.append(datum_id)

        # print_to_gui(f'Pilatus complete is done.', add_timestamp=True)
        return NullStatus() and ext_trigger_status

    def collect(self):
        # print_to_gui(f'Pilatus collect is starting...', add_timestamp=True)
        ts = ttime.time()
        yield {
            "data": self._datum_ids,
            "timestamps": {self.format_datum_key(key_dict): ts for key_dict in self.datum_keys},
            "time": ts,  # TODO: use the proper timestamps from the mono start and stop times
            "filled": {self.format_datum_key(key_dict): False for key_dict in self.datum_keys},
        }

        # num_frames = len(self._datum_ids)
        #
        # for frame_num in range(num_frames):
        #     datum_id = self._datum_ids[frame_num]
        #     data = {self.name: datum_id}
        #
        #     ts = ttime.time()
        #
        #     yield {'data': data,
        #            'timestamps': {key: ts for key in data},
        #            'time': ts,  # TODO: use the proper timestamps from the mono start and stop times
        #            'filled': {key: False for key in data}}
        # print_to_gui(f'Pilatus collect is complete', add_timestamp=True)
        yield from self.ext_trigger_device.collect()

    def describe_collect(self):
        pil900k_spectra_dicts = {}
        for datum_key_dict in self.datum_keys:
            datum_key = self.format_datum_key(datum_key_dict)
            if datum_key_dict["data_type"] == "image":
                value = {
                    "source": "PILATUS_HDF5",
                    "dtype": "array",
                    # 'shape': [self.cam.num_images.get(),
                    "shape": [
                        self.hdf5.num_capture.get(),
                        self.hdf5.array_size.height.get(),
                        self.hdf5.array_size.width.get(),
                    ],
                    "dims": ["frames", "row", "col"],
                    "external": "FILESTORE:",
                }
            elif datum_key_dict["data_type"] == "roi":
                value = {
                    "source": "PILATUS_HDF5",
                    "dtype": "array",
                    # 'shape': [self.cam.num_images.get()],
                    "shape": [self.hdf5.num_capture.get()],
                    "dims": ["frames"],
                    "external": "FILESTORE:",
                }
            else:
                raise KeyError(f'data_type={datum_key_dict["data_type"]} not supported')
            pil900k_spectra_dicts[datum_key] = value

        return_dict_pil900k = {self.name: pil900k_spectra_dicts}

        # return_dict_pil900k = {self.name:
        #                    {f'{self.name}': {'source': 'PIL900k_HDF5',
        #                                      'dtype': 'array',
        #                                      'shape': [self.cam.num_images.get(),
        #                                                #self.settings.array_counter.get()
        #                                                self.hdf5.array_size.height.get(),
        #                                                self.hdf5.array_size.width.get()],
        #                                     'filename': f'{self.hdf5.full_file_name.get()}',
        #                                      'external': 'FILESTORE:'}}}
        #
        return_dict_trig = self.ext_trigger_device.describe_collect()
        return {**return_dict_pil900k, **return_dict_trig}

    def collect_asset_docs(self):
        items = list(self._asset_docs_cache)
        self._asset_docs_cache.clear()
        for item in items:
            yield item
        yield from self.ext_trigger_device.collect_asset_docs()


pilatus = PilatusHDF5Squashing("XF:07BM-ES{Det-Pil3}:", name="pilatus")  # , detector_id="SAXS")
pilatus.cam.ensure_nonblocking()

pilatus.images_per_set.put(1)
warmup_hdf5_plugins([pilatus])

pilatus_stream = PilatusStreamHDF5(
    "XF:07BM-ES{Det-Pil3}:",
    name="pilatus_stream",
    ext_trigger_device=apb_trigger_pil900k,
)

pilatus.set_primary_roi(1)
pilatus.stats1.kind = "hinted"
pilatus.stats2.kind = "hinted"
pilatus.stats3.kind = "hinted"
pilatus.stats4.kind = "hinted"


# pil900k.cam.ensure_nonblocking()


def take_pil900k_test_image_plan():
    yield from shutter.open_plan()
    pilatus.cam.acquire.set(1)
    yield from bps.sleep(pilatus.cam.acquire_time.value + 0.1)
    yield from shutter.close_plan()


def pil_count(acq_time: int = 1, num_frames: int = 1, open_shutter: bool = True):
    if open_shutter:
        yield from shutter.open_plan()
    yield from bp.count([pilatus, apb_ave])
    if open_shutter:
        yield from shutter.close_plan()


from itertools import product

import pandas as pd
from databroker.assets.handlers import AreaDetectorTiffHandler, HandlerBase, PilatusCBFHandler, Xspress3HDF5Handler, AreaDetectorHDF5SWMRHandler
# Note: the databroker is v0 and follows the old code path, so it uses databroker.assets.handlers.AreaDetectorHDF5SWMRHandler.
# from area_detector_handlers.handlers import AreaDetectorHDF5SWMRHandler


class QASAreaDetectorHDF5SWMRHandler(AreaDetectorHDF5SWMRHandler):
    '''
    The reason we need this custom handles is that the reference to `self._dataset` is not refreshed correctly,
    so we redefine `self._dataset` on every call.

    file = "<path>/575d134b-adf9-453a-a1a8_000000.h5"
    swmr = AreaDetectorHDF5SWMRHandler(file)


    In [150]: swmr._file["/entry/data/data"]
    Out[150]: <HDF5 dataset "data": shape (3, 1043, 981), type "<u2">

    In [151]: swmr._dataset
    Out[151]: <HDF5 dataset "data": shape (1, 1043, 981), type "<u2">

    ERROR:
    ------

    In [186]: list(swmr(0))
    Out[186]:
    [Frame([[    0,     0,     0, ...,     0,     0,     0],
            [    0,     0,     0, ...,     0,     0,     0],
            [    0,     0,     0, ...,     0,     0,     0],
            ...,
            [    0,     0,     0, ..., 65534, 65534, 65534],
            [    0,     0,     0, ..., 65534, 65534, 65534],
            [    0,     0,     0, ..., 65534, 65534, 65534]], dtype=uint16)]

    In [187]: list(swmr(1))
    ---------------------------------------------------------------------------
    IndexError                                Traceback (most recent call last)
    Cell In[187], line 1
    ----> 1 list(swmr(1))

    File /nsls2/conda/envs/2023-1.3-py310-tiled/lib/python3.10/site-packages/slicerator/__init__.py:226, in <genexpr>(.0)
        225 def __iter__(self):
    --> 226     return (self._get(i) for i in self.indices)

    File /nsls2/conda/envs/2023-1.3-py310-tiled/lib/python3.10/site-packages/slicerator/__init__.py:206, in Slicerator._get(self, key)
        205 def _get(self, key):
    --> 206     return self._ancestor[key]

    File /nsls2/conda/envs/2023-1.3-py310-tiled/lib/python3.10/site-packages/slicerator/__init__.py:187, in Slicerator.from_class.<locals>.SliceratorSubclass.__getitem__(self, i)
        185 indices, new_length = key_to_indices(i, len(self))
        186 if new_length is None:
    --> 187     return self._get(indices)
        188 else:
        189     return cls(self, indices, new_length, propagate_attrs)

    File /nsls2/conda/envs/2023-1.3-py310-tiled/lib/python3.10/site-packages/pims/base_frames.py:100, in FramesSequence.__getitem__(self, key)
        97 def __getitem__(self, key):
        98     """__getitem__ is handled by Slicerator. In all pims readers, the data
        99     returning function is get_frame."""
    --> 100     return self.get_frame(key)

    File /nsls2/conda/envs/2023-1.3-py310-tiled/lib/python3.10/site-packages/databroker/assets/handlers.py:37, in ImageStack.get_frame(self, i)
        36 def get_frame(self, i):
    ---> 37     return Frame(self._dataset[self._start + i], frame_no=i)

    File h5py/_objects.pyx:54, in h5py._objects.with_phil.wrapper()

    File h5py/_objects.pyx:55, in h5py._objects.with_phil.wrapper()

    File /nsls2/conda/envs/2023-1.3-py310-tiled/lib/python3.10/site-packages/h5py/_hl/dataset.py:741, in Dataset.__getitem__(self, args, new_dtype)
        739 if self._fast_read_ok and (new_dtype is None):
        740     try:
    --> 741         return self._fast_reader.read(args)
        742     except TypeError:
        743         pass  # Fall back to Python read pathway below

    File h5py/_selector.pyx:355, in h5py._selector.Reader.read()

    File h5py/_selector.pyx:151, in h5py._selector.Selector.apply_args()

    IndexError: Index (1) out of range for (0-0)
    '''
    def __call__(self, point_number):
        self._dataset = self._file["/entry/data/data"]
        return super().__call__(point_number)


db.reg.register_handler('AD_HDF5_SWMR',
                         QASAreaDetectorHDF5SWMRHandler, overwrite=True)

# An exception has occurred, use '%tb verbose' to see the full traceback.
# AttributeError: 'Array' object has no attribute 'id'

# See /home/xf07bm/.cache/bluesky/log/bluesky.log for the full traceback.

# In [2]: %debug
# > /nsls2/conda/envs/2023-1.3-py310-tiled/lib/python3.10/site-packages/area_detector_handlers/handlers.py(211)__call__()
#     209     def __call__(self, point_number):
#     210         if self._dataset is not None:
# --> 211             self._dataset.id.refresh()
#     212         rtn = super().__call__(point_number)
#     213

# ipdb> p self._dataset.id.refresh()
# *** AttributeError: 'Array' object has no attribute 'id'
# ipdb> p self._dataset.id
# *** AttributeError: 'Array' object has no attribute 'id'
# ipdb> p self._dataset
# dask.array<array, shape=(1, 1043, 981), dtype=uint16, chunksize=(1, 1043, 981), chunktype=numpy.ndarray>
# ipdb>


# PIL900k_HDF_DATA_KEY = 'entry/instrument/NDAttributes'
# class QASPilatusHDF5Handler(Xspress3HDF5Handler): # Denis: I used Xspress3HDF5Handler as basis since it has all the basic functionality and I more or less understand how it works
#     specs = {'PIL900k_HDF5'} | HandlerBase.specs
#     HANDLER_NAME = 'PIL900k_HDF5'
#
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, key=PIL900k_HDF_DATA_KEY, **kwargs)
#         self._roi_data = None
#         self.hdfrois = [f'ROI{i + 1}' for i in range(4)]
#         self.chanrois = [f'pil900k_ROI{i + 1}' for i in range(4)]
#
#
#     def _get_dataset(self):
#         if self._dataset is not None:
#             return
#
#         _data_columns = [self._file[self._key + f'/_{chanroi}Total'][()] for chanroi in self.hdfrois]
#         self._roi_data = np.vstack(_data_columns).T
#         self._image_data = self._file['entry/data/data'][()]
#         # self._roi_data = pd.DataFrame(data_columns, columns=self.chanrois)
#         # self._dataset = data_columns
#
#     def __call__(self, data_type:str='image', roi_num=None):
#         # print(f'{ttime.ctime()} XS dataset retrieving starting...')
#         self._get_dataset()
#
#         if data_type=='image':
#             # print(output.shape, output.squeeze().shape)
#             return self._image_data
#
#         elif data_type=='roi':
#             return self._roi_data[:, roi_num - 1].squeeze()
#
#         else:
#             raise KeyError(f'data_type={data_type} not supported')

# def __call__(self, *args, frame=None,  **kwargs):
#     self._get_dataset()
#     return_dict = {chanroi: self._roi_data[chanroi][frame] for chanroi in self.chanrois}
#     # return_dict['image'] = self._image_data[frame, :, :].squeeze()
#     return return_dict
#     # return self._roi_data

#
# from xas.handlers import QASPilatusHDF5Handler
# db.reg.register_handler('PIL900k_HDF5',
#                          QASPilatusHDF5Handler, overwrite=True)
