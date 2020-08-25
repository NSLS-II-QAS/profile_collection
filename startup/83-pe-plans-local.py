print(__file__)
import os
import sys

import uuid


# this is the original, correct pe_count
# renamed pe_count_ to hide it from xlive while testing the new pe_count
def pe_count(filename='', exposure = 1, num_images:int = 1, num_dark_images:int = 1, num_repetitions:int = 5, delay = 60):

    year     = RE.md['year']
    cycle    = RE.md['cycle']
    proposal = RE.md['PROPOSAL']
   
    print(proposal)

    #write_path_template = 'Z:\\data\\pe1_data\\%Y\\%m\\%d\\'
    write_path_template = f'Z:\\users\\{year}\\{cycle}\\{proposal}XRD\\'
    file_path = datetime.now().strftime(write_path_template)
    filename = filename + str(uuid.uuid4())[:6]

    yield from bps.mv(pe1.tiff.file_number,1)
    yield from bps.mv(pe1.tiff.file_path, file_path)
  
    init_num_repetitions = num_repetitions

    for indx in range(int(num_repetitions)):
       
        print('\n')
        print("<<<<<<<<<<<<<<<<< Doing repetition {} out of {} >>>>>>>>>>>>>>>>>".format(indx + 1, init_num_repetitions))
 
        yield from bps.mv(pe1.tiff.file_name,filename)         

        if num_dark_images > 0:
            yield from bps.mv(pe1.num_dark_images ,num_dark_images )
            yield from bps.mv(pe1.cam.image_mode, 'Average')
            yield from bps.mv(shutter_fs, 'Close')
            yield from bps.sleep(0.5)
            yield from bps.mv(pe1.tiff.file_write_mode, 'Single')
            yield from bps.mv(pe1c, 'acquire_dark')
            yield from bps.mv(pe1.tiff.write_file, 1)

        ##yield from bps.mv(pe1.cam.image_mode, 'Multiple')
        yield from bps.mv(pe1.cam.image_mode, 'Average')
        yield from bps.mv(pe1.cam.acquire_time, exposure)
        yield from bps.mv(pe1.cam.num_images,num_images)
    
        yield from bps.mv(shutter_fs, 'Open')
        yield from bps.sleep(0.5)
    
        ## Below 'Capture' mode is used with 'Multiple' image_mode
        #yield from bps.mv(pe1.tiff.file_write_mode, 'Capture')

        ## Below 'Single' mode is used with 'Average' image_mode
        yield from bps.mv(pe1.tiff.file_write_mode, 'Single')

        ## Uncomment 'capture' bit settings when used in 'Capture' mode
        #yield from bps.mv(pe1.tiff.capture, 1)
        yield from bps.mv(pe1c, 'acquire_light')
        yield from bps.sleep(1)
        #yield from bps.mv(pe1.tiff.capture, 0)

        ##Below write_file is needed when used in 'Average' mode
        yield from bps.mv(pe1.tiff.write_file, 1)
        
        yield from bps.sleep(delay)

from collections import deque
from pathlib import Path
from event_model import compose_resource
from ophyd import Component as Cpt, DeviceStatus, Staged


class ExternalFileReference(Signal):
    # the "value" of this Signal is not a real PV
    # but is intended to look like one

    def __init__(self, *args, shape, **kwargs):
        super().__init__(*args, **kwargs)
        self.shape = shape

    def describe(self):
        print("describe ExternalFileReferece!")
        res = super().describe()
        res[self.name].update(
            dict(
                external="FILESTORE:", dtype="array", shape=self.shape, dims=("x", "y"),
            )
        )
        return res

    def stage(self):
        print("stage ExternalFileRefernce!")
        return [self]


class QASPerkinElmerDarkDetector():

    def __init__(self):
        self.name = "dark-detector"
        self.prefix = "prefix"
        self.parent = None

        self._staged = False

        self.num_dark_images = None
        self.file_path = None
        self.filename = None
        self.exposure = None
        self.num_images = None

        self.external_file_ref = ExternalFileReference(name="external_file_ref", shape=(2048, 2048))

        self.resouce_root = None
        self.resource_path = None

        self._resource = None
        self._datum_factory = None
        self._asset_docs_cache = deque()


    def describe(self):
        print("describe!")

        description = dict()
        description.update(
            {
                self.name: {"source": "astral plane", "dtype": "array", "shape": []}
            }
        )
        description.update(pe1c.describe())
        description.update(self.external_file_ref.describe())
        description.update(shutter_fs.describe())

        print(description)
        return description


    def describe_configuration(self):
        print("describe_configuration!")
        configuration = dict()
 
        configuration.update(
            {self.name: {"source": "??", "dtype": "array", "shape": (2048, 2048)}}
        )
        configuration.update(pe1c.describe_configuration())
        configuration.update(self.external_file_ref.describe_configuration())
        configuration.update(shutter_fs.describe_configuration())
        
        print(configuration)
        return configuration


    def read_configuration(self):
        print("read_configuration!")
        configuration = dict()

        configuration.update(
            {self.name: {"value": 0, "timestamp": time.time()}}
        )
        configuration.update(pe1c.read_configuration())
        configuration.update(shutter_fs.read_configuration())
        configuration.update(self.external_file_ref.read_configuration())

        print(configuration)
        return configuration


    def stage(self):
        print("stage!")
        if self._staged:
            raise RedundantStaging()

        self.file_path = self.resource_root + self.resource_dir_path + self.filename
        self._resource, self._datum_factory, _ = compose_resource(
            start={"uid": "a lie"},
            spec="ADC_TIFF",
            root=self.resource_root,  # "/",
            resource_path=self.resource_dir_path + self.filename,
            resource_kwargs={"image_shape": (2048, 2048)},
        )
        self._resource.pop("run_start")
        self._asset_docs_cache.append(("resource", self._resource))

        pe1c.tiff.file_number.put(1)
        pe1c.tiff.file_path.put(self.file_path)

        self._staged = True


    def trigger(self):
        print("trigger!")
        
        # what about file path?
        pe1c.tiff.file_name.put(self.filename)
        if self.num_dark_images > 0:
            pe1.num_dark_images.put(self.num_dark_images)
            pe1.cam.image_mode.put('Average')
            ## shutter_fs.put('Close')
            shutter_fs.get('Close')
            time.sleep(0.5)
            ##yield from bps.sleep(0.5)
            pe1.tiff.file_write_mode.put('Single')
            pe1c.put('acquire_dark')
            pe1.tiff.write_file.put(1)

        datum = self._datum_factory(
            datum_kwargs={"???": "???"}
        )
        # this is important
        self.external_file_ref.put(datum["datum_id"])
        self._asset_docs_cache.append(("datum", datum))

        status = Status()
        status._finished()
        return status


    def read(self):
        print("read!")
        ##pe1c.cam.image_mode.put('Multiple')
        pe1c.cam.image_mode.put('Average')
        pe1.cam.acquire_time.put(self.exposure)
        pe1c.cam.num_images.put(self.num_images)

        shutter_fs.get('Open')
        ##yield from bps.sleep(0.5)

        ## Below 'Capture' mode is used with 'Multiple' image_mode
        #pe1c.tiff.file_write_mode.put('Capture')

        ## Below 'Single' mode is used with 'Average' image_mode
        pe1c.tiff.file_write_mode.put('Single')

        ## Uncomment 'capture' bit settings when used in 'Capture' mode
        #pe1c.tiff.capture.put(1)
        pe1c.put('acquire_light')
        ##yield from bps.sleep(1)
        pe1c.tiff.capture.put(0)

        ##Below write_file is needed when used in 'Average' mode
        pe1c.tiff.write_file.put(1)

        read_results = dict()
        read_results.update({self.name: {"value": 0, "timestamp": time.time()}})
        read_results.update(pe1c.read())
        read_results.update(shutter_fs.read())
        read_results.update(self.external_file_ref.read())

        print(read_results)

        return read_results


    def unstage(self):
        print("unstage!")
        self._resource = None
        self._datum_factory = None
        self._staged = False


    def collect_asset_docs(self):
        print("collect asset docs from DetectorC!")
        items = list(self._asset_docs_cache)
        self._asset_docs_cache.clear()
        for item in items:
            yield item


pe1_dark = QASPerkinElmerDarkDetector()


from functools import partial


# this is the new, experimental pe_count
def pe_count_(
        resource_root='Z:\\users\\',
        resource_dir_path='{year}\\{cycle}\\{PROPOSAL}XRD\\',
        filename='',
        #write_path_template='Z:\\users\\{year}\\{cycle}\\{PROPOSAL}XRD\\',
        exposure=1,
        num_images:int=1,
        num_dark_images:int=1,
        num_repetitions:int=1,
        delay=2
):

    print(f"proposal: {RE.md['PROPOSAL']}")

    pe1_dark.num_dark_images = num_dark_images
    pe1_dark.exposure = exposure
    pe1_dark.num_images = num_images
    #pe1_dark.file_path = write_path_template.format(**RE.md)
    #pe1_dark.filename = str(uuid.uuid4()) + filename

    pe1_dark.resource_root = resource_root
    pe1_dark.resource_dir_path = resource_dir_path.format(**RE.md)
    pe1_dark.filename = str(uuid.uuid4()) + filename

    yield from bp.count(
        [pe1_dark],
        num=num_repetitions,
        delay=delay,
    )

    # assuming pe_count should not start a run, try this
    # but using this gave
    # bluesky.utils.IllegalMessageSequence: Cannot bundle readings without an open run.
    # so maybe pe_count should start a run

    # pe1_dark.stage()
    # yield from bps.repeat(
    #     partial(bps.trigger_and_read, [pe1_dark]),
    #     num=num_repetitions,
    #     delay=delay
    # )
    # pe1_dark.unstage()


