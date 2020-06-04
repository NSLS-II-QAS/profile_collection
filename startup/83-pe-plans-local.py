print(__file__)
from datetime import datetime
import os
import sys
import time

import uuid


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

    def describe(self):
        print("describe!")

        description = dict()
        description.update(pe1.describe())
        description.update(shutter_fs.describe())

        return description


    def describe_configuration(self):
        return dict()


    def read_configuration(self):
        return dict()


    def stage(self):
        print("stage!")
        if self._staged:
            raise RedundantStaging()

        pe1.tiff.file_number.put(1)
        pe1.tiff.file_path.put(self.file_path)

        self._staged = True

    def trigger(self):
        print("trigger!")
        pe1.tiff.file_name.put(self.filename)
        if self.num_dark_images > 0:
            pe1.num_dark_images.put(self.num_dark_images)
            pe1.cam.image_mode.put('Average')
            ## shutter_fs.put('Close')
            shutter_fs.set('Close')
            time.sleep(0.5)
            ##yield from bps.sleep(0.5)
            pe1.tiff.file_write_mode.put('Single')
            pe1c.set('acquire_dark')
            pe1.tiff.write_file.put(1)

        status = Status()
        status._finished()
        return status

    def read(self):
        print("read!")
        ##pe1.cam.image_mode.put('Multiple')
        pe1.cam.image_mode.put('Average')
        pe1.cam.acquire_time.put(self.exposure)
        pe1.cam.num_images.put(self.num_images)

        shutter_fs.set('Open')
        ##yield from bps.sleep(0.5)

        ## Below 'Capture' mode is used with 'Multiple' image_mode
        #pe1.tiff.file_write_mode.put('Capture')

        ## Below 'Single' mode is used with 'Average' image_mode
        pe1.tiff.file_write_mode.put('Single')

        ## Uncomment 'capture' bit settings when used in 'Capture' mode
        #pe1.tiff.capture.put(1)
        pe1c.set('acquire_light')
        ##yield from bps.sleep(1)
        pe1.tiff.capture.put(0)

        ##Below write_file is needed when used in 'Average' mode
        pe1.tiff.write_file.put(1)

        return {
            self.name: {"value": 0.0, "timestamp": datetime.now().timestamp()}
        }

    def unstage(self):
        print("unstage!")
        self._staged = False

pe1_dark = QASPerkinElmerDarkDetector()


def pe_count_(
        filename='',
        write_path_template='Z:\\users\\{year}\\{cycle}\\{PROPOSAL}XRD\\',
        exposure=1,
        num_images:int=1,
        num_dark_images:int=1,
        num_repetitions:int=5,
        delay=2
):

    print(f"proposal: {RE.md['PROPOSAL']}")

    pe1_dark.num_dark_images = num_dark_images
    pe1_dark.exposure = exposure
    pe1_dark.num_images = num_images
    pe1_dark.file_path = write_path_template.format(**RE.md)
    pe1_dark.filename = str(uuid.uuid4()) + filename

    yield from bp.count(
        [pe1_dark],
        num=num_repetitions,
        delay=delay
    )
