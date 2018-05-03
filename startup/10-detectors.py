import uuid
from collections import namedtuple
import os
import time as ttime
from ophyd import (ProsilicaDetector, SingleTrigger, Component as Cpt, Device,
                   EpicsSignal, EpicsSignalRO, ImagePlugin, StatsPlugin, ROIPlugin,
                   DeviceStatus)
from ophyd import DeviceStatus, set_and_wait
from bluesky.examples import NullStatus

from databroker.assets.handlers_base import HandlerBase
from ophyd import (Component as C, FormattedComponent as FC)

from datetime import datetime


class BPM(ProsilicaDetector, SingleTrigger):
    image = Cpt(ImagePlugin, 'image1:')
    stats1 = Cpt(StatsPlugin, 'Stats1:')
    stats2 = Cpt(StatsPlugin, 'Stats2:')
    roi1 = Cpt(ROIPlugin, 'ROI1:')
    roi2 = Cpt(ROIPlugin, 'ROI2:')
    counts = Cpt(EpicsSignal, 'Pos:Counts')
    # Dan Allan guessed about the nature of these signals. Fix them if you need them.
    ins = Cpt(EpicsSignal, 'Cmd:In-Cmd')
    ret = Cpt(EpicsSignal, 'Cmd:Out-Cmd')
    switch_insert = Cpt(EpicsSignalRO, 'Sw:InLim-Sts')
    switch_retract = Cpt(EpicsSignalRO, 'Sw:OutLim-Sts')
    polarity = 'pos'

    def insert(self):
        self.ins.put(1)

    def retract(self):
        self.ret.put(1)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stage_sigs.clear()  # default stage sigs do not apply

class CAMERA(ProsilicaDetector, SingleTrigger):
    image = Cpt(ImagePlugin, 'image1:')
    stats1 = Cpt(StatsPlugin, 'Stats1:')
    stats2 = Cpt(StatsPlugin, 'Stats2:')
    roi1 = Cpt(ROIPlugin, 'ROI1:')
    roi2 = Cpt(ROIPlugin, 'ROI2:')
    polarity = 'pos'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stage_sigs.clear()  # default stage sigs do not apply


colmirror_diag = CAMERA('XF:07BM-BI{Mir:Col}', name='colmirror_diag')
screen_diag = CAMERA('XF:07BM-BI{FS:1}', name='screen_diag') # HOW TO CALL CAMERA UNDER FT DIAGNOSTICS > Diagnostic Screen
mono_diag = CAMERA('XF:07BM-BI{Mono:1}', name='mono_diag')
dcr_diag = CAMERA('XF:07BM-BI{Diag:1}', name='dcr_diag')

# Prosilica detector in hutch 7-BM-B
hutchb_diag = CAMERA('XF:07BMB-BI{Diag:1}', name='hutchb_diag')


for camera in [colmirror_diag, screen_diag, mono_diag, dcr_diag, hutchb_diag]:
    camera.read_attrs = ['stats1', 'stats2']
    camera.image.read_attrs = ['array_data']
    camera.stats1.read_attrs = ['total', 'centroid']
    camera.stats2.read_attrs = ['total', 'centroid']
    camera.hints = {'fields' : [camera.stats1.total.name,
                                camera.stats2.total.name]} 


class Encoder(Device):
    """This class defines components but does not implement actual reading.
    See EncoderFS and EncoderParser"""
    pos_I = Cpt(EpicsSignal, '}Cnt:Pos-I')
    sec_array = Cpt(EpicsSignal, '}T:sec_Bin_')
    nsec_array = Cpt(EpicsSignal, '}T:nsec_Bin_')
    pos_array = Cpt(EpicsSignal, '}Cnt:Pos_Bin_')
    index_array = Cpt(EpicsSignal, '}Cnt:Index_Bin_')
    data_array = Cpt(EpicsSignal, '}Data_Bin_')
    # The '$' in the PV allows us to write 40 chars instead of 20.
    filepath = Cpt(EpicsSignal, '}ID:File.VAL', string=True)
    dev_name = Cpt(EpicsSignal, '}DevName')

    filter_dy = Cpt(EpicsSignal, '}Fltr:dY-SP')
    filter_dt = Cpt(EpicsSignal, '}Fltr:dT-SP')
    reset_counts = Cpt(EpicsSignal, '}Rst-Cmd')

    ignore_rb = Cpt(EpicsSignal, '}Ignore-RB')
    ignore_sel = Cpt(EpicsSignal, '}Ignore-Sel')

    resolution = 1;

    def __init__(self, *args, reg, **kwargs):
        super().__init__(*args, **kwargs)
        self._ready_to_collect = False
        self._reg = reg
        if self.connected:
            self.ignore_sel.put(1)
            # self.filter_dt.put(10000)


class EncoderFS(Encoder):
    "Encoder Device, when read, returns references to data in filestore."
    chunk_size = 1024
    write_path_template = '/nsls2/xf07bm/data/pizza_box_data/%Y/%m/%d/'

    def stage(self):
        "Set the filename and record it in a 'resource' document in the filestore database."

        if(self.connected):
        #if True:
            print(self.name, 'stage')
            DIRECTORY = datetime.now().strftime(self.write_path_template)
            #DIRECTORY = "/nsls2/xf07bm/data/pb_data"

            filename = 'en_' + str(uuid.uuid4())[:6]
            self._full_path = os.path.join(DIRECTORY, filename)  # stash for future reference
            print("writing data to {}".format(self._full_path))

            self.filepath.put(self._full_path)
            self.resource_uid = self._reg.register_resource(
                'PIZZABOX_ENC_FILE_TXT',
                DIRECTORY, self._full_path,
                {'chunk_size': self.chunk_size})

            super().stage()
        else:
            print("encoder was not staged : {}".format(self.name))

    def unstage(self):
        if(self.connected):
            set_and_wait(self.ignore_sel, 1)
            return super().unstage()

    def kickoff(self):
        "Start writing data into the file."

        print('kickoff', self.name)
        self._ready_to_collect = True

        # set_and_wait(self.ignore_sel, 0)
        st = self.ignore_sel.set(0)

        # Return a 'status object' that immediately reports we are 'done' ---
        # ready to collect at any time.
        # return NullStatus()
        return st

    def complete(self):
        print('complete', self.name, '| filepath', self._full_path)
        if not self._ready_to_collect:
            raise RuntimeError("must called kickoff() method before calling complete()")
        # Stop adding new data to the file.
        #set_and_wait(self.ignore_sel, 1)
        st = self.ignore_sel.set(1)
        #while not os.path.isfile(self._full_path):
        #    ttime.sleep(.1)
        #return NullStatus()
        return st

    def collect(self):
        """
        Record a 'datum' document in the filestore database for each encoder.
        Return a dictionary with references to these documents.
        """
        print('collect', self.name)
        self._ready_to_collect = False

        # Create an Event document and a datum record in filestore for each line
        # in the text file.
        now = ttime.time()
        ttime.sleep(1)  # wait for file to be written by pizza box
        if os.path.isfile(self._full_path):
            with open(self._full_path, 'r') as f:
                linecount = len(list(f))
            chunk_count = linecount // self.chunk_size + int(linecount % self.chunk_size != 0)
            for chunk_num in range(chunk_count):
                datum_uid = self._reg.register_datum(
                    self.resource_uid, {'chunk_num': chunk_num})
                data = {self.name: datum_uid}
                yield {'data': data,
                       'timestamps': {key: now for key in data}, 'time': now}
        else:
            print('collect {}: File was not created'.format(self.name))
            print("filename : {}", self._full_path)

    def describe_collect(self):
        # TODO Return correct shape (array dims)
        now = ttime.time()
        return {self.name: {self.name:
                     {'filename': self._full_path,
                      'devname': self.dev_name.value,
                      'source': 'pizzabox-enc-file',
                      'external': 'FILESTORE:',
                      'shape': [1024, 5],
                      'dtype': 'array'}}}


class DigitalOutput(Device):
    """ DigitalOutput """
    enable = Cpt(EpicsSignal, '}Ena-Cmd')
    period_sp = Cpt(EpicsSignal, '}Period-SP')
    unit_sel = Cpt(EpicsSignal, '}Unit-Sel')
    dutycycle_sp = Cpt(EpicsSignal, '}DutyCycle-SP')
    default_pol = Cpt(EpicsSignal, '}Dflt-Sel')

    def __init__(self, *args, reg, **kwargs):
        self._reg = reg
        super().__init__(*args, **kwargs)
        self._ready_to_collect = False
        if self.connected:
            self.enable.put(0)


class DigitalInput(Device):
    """This class defines components but does not implement actual reading.
    See DigitalInputFS """
    data_I = Cpt(EpicsSignal, '}Raw:Data-I_')
    sec_array = Cpt(EpicsSignal, '}T:sec_Bin_')
    nsec_array = Cpt(EpicsSignal, '}T:nsec_Bin_')
    index_array = Cpt(EpicsSignal, '}Cnt:Index_Bin_')
    data_array = Cpt(EpicsSignal, '}Data_Bin_')
    # The '$' in the PV allows us to write 40 chars instead of 20.
    filepath = Cpt(EpicsSignal, '}ID:File.VAL', string=True)
    dev_name = Cpt(EpicsSignal, '}DevName')

    ignore_rb = Cpt(EpicsSignal, '}Ignore-RB')
    ignore_sel = Cpt(EpicsSignal, '}Ignore-Sel')

    def __init__(self, *args, reg, **kwargs):
        self._reg = reg
        super().__init__(*args, **kwargs)
        self._ready_to_collect = False
        if self.connected:
            self.ignore_sel.put(1)


class DIFS(DigitalInput):
    "Encoder Device, when read, returns references to data in filestore."
    chunk_size = 1024
    write_path_template = '/nsls2/xf07bm/data/pizza_box_data/%Y/%m/%d/'

    def stage(self):
        "Set the filename and record it in a 'resource' document in the filestore database."


        print(self.name, 'stage')
        DIRECTORY = datetime.now().strftime(self.write_path_template)
        #DIRECTORY = "/nsls2/xf07bm/data/pb_data"

        filename = 'di_' + str(uuid.uuid4())[:6]
        self._full_path = os.path.join(DIRECTORY, filename)  # stash for future reference

        self.filepath.put(self._full_path)
        self.resource_uid = self._reg.register_resource(
            'PIZZABOX_DI_FILE_TXT',
            DIRECTORY, full_path,
            {'chunk_size': self.chunk_size})

        super().stage()

    def unstage(self):
        set_and_wait(self.ignore_sel, 1)
        return super().unstage()

    def kickoff(self):
        print('kickoff', self.name)
        self._ready_to_collect = True
        "Start writing data into the file."

        # set_and_wait(self.ignore_sel, 0)
        st = self.ignore_sel.set(0)

        # Return a 'status object' that immediately reports we are 'done' ---
        # ready to collect at any time.
        # return NullStatus()
        return st

    def complete(self):
        print('complete', self.name, '| filepath', self._full_path)
        if not self._ready_to_collect:
            raise RuntimeError("must called kickoff() method before calling complete()")
        # Stop adding new data to the file.
        set_and_wait(self.ignore_sel, 1)
        #while not os.path.isfile(self._full_path):
        #    ttime.sleep(.1)
        return NullStatus()

    def collect(self):
        """
        Record a 'datum' document in the filestore database for each encoder.
        Return a dictionary with references to these documents.
        """
        print('collect', self.name)
        self._ready_to_collect = False

        # Create an Event document and a datum record in filestore for each line
        # in the text file.
        now = ttime.time()
        ttime.sleep(1)  # wait for file to be written by pizza box
        if os.path.isfile(self._full_path):
            with open(self._full_path, 'r') as f:
                linecount = len(list(f))
            chunk_count = linecount // self.chunk_size + int(linecount % self.chunk_size != 0)
            for chunk_num in range(chunk_count):
                datum_uid = self._reg.register_datum(self.resource_uid,
                                                     {'chunk_num': chunk_num})
                data = {self.name: datum_uid}

                yield {'data': data,
                       'timestamps': {key: now for key in data}, 'time': now}
        else:
            print('collect {}: File was not created'.format(self.name))
            print("filename : {}", self._full_path)

    def describe_collect(self):
        # TODO Return correct shape (array dims)
        now = ttime.time()
        return {self.name: {self.name:
                     {'filename': self._full_path,
                      'devname': self.dev_name.value,
                      'source': 'pizzabox-di-file',
                      'external': 'FILESTORE:',
                      'shape': [1024, 5],
                      'dtype': 'array'}}}

class PizzaBoxFS(Device):
    ts_sec = Cpt(EpicsSignal, '}T:sec-I')
    #internal_ts_sel = Cpt(EpicsSignal, '}T:Internal-Sel')

    enc1 = Cpt(EncoderFS, ':1', reg=db.reg)
    enc2 = Cpt(EncoderFS, ':2', reg=db.reg)
    enc3 = Cpt(EncoderFS, ':3', reg=db.reg)
    enc4 = Cpt(EncoderFS, ':4', reg=db.reg)
    di = Cpt(DIFS, ':DI', reg=db.reg)
    do0 = Cpt(DigitalOutput, '-DO:0', reg=db.reg)
    do1 = Cpt(DigitalOutput, '-DO:1', reg=db.reg)
    do2 = Cpt(DigitalOutput, '-DO:2', reg=db.reg)
    do3 = Cpt(DigitalOutput, '-DO:3', reg=db.reg)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # must use internal timestamps or no bytes are written

    def kickoff(self):
        "Call encoder.kickoff() for every encoder."
        for attr_name in ['enc1', 'enc2', 'enc3', 'enc4']:
            status = getattr(self, attr_name).kickoff()
            print("Eli's test", self.attr_name)
        # it's fine to just return one of the status objects
        return status

    def collect(self):
        "Call encoder.collect() for every encoder."
        # Stop writing data to the file in all encoders.
        for attr_name in ['enc1', 'enc2', 'enc3', 'enc4']:
            set_and_wait(getattr(self, attr_name).ignore_sel, 1)
        # Now collect the data accumulated by all encoders.
        for attr_name in ['enc1', 'enc2', 'enc3', 'enc4']:
            yield from getattr(self, attr_name).collect()


pb1 = PizzaBoxFS('XF:07BM-CT{Enc01', name = 'pb1')
#pb1.enc1.pulses_per_deg = 9400000/360
pb1.enc1.pulses_per_deg=23600*400/360


class Adc(Device):
    file_size = Cpt(EpicsSignal, '}FileSize')
    reset = Cpt(EpicsSignal, '}Rst-Cmd')
    filepath = Cpt(EpicsSignal, '}ID:File.VAL', string=True)
    sec_array = Cpt(EpicsSignal, '}T:sec_Bin_')
    nsec_array = Cpt(EpicsSignal, '}T:nsec_Bin_')
    #pos_array = Cpt(EpicsSignal, '}Cnt:Pos_Bin_')
    index_array = Cpt(EpicsSignal, '}Cnt:Index_Bin_')
    data_array = Cpt(EpicsSignal, '}Data_Bin_')
    sample_rate = Cpt(EpicsSignal,'}F:Sample-I_', write_pv='}F:Sample-SP')
    enable_averaging = Cpt(EpicsSignal, '}Avrg-Sts', write_pv='}Avrg-Sel')
    averaging_points = Cpt(EpicsSignal, '}Avrg-SP')
    averaging_points_rbv = Cpt(EpicsSignal, '}GP-ADC:Reg0-RB_')
    volt_array = Cpt(EpicsSignal, '}V-I')
    volt = Cpt(EpicsSignal, '}E-I')
    offset = Cpt(EpicsSignal, '}Offset')
    dev_name = Cpt(EpicsSignal, '}DevName')
    dev_saturation = Cpt(EpicsSignal, '}DevSat')
    polarity = 'neg'

    enable_sel = Cpt(EpicsSignal, '}Ena-Sel')
    enable_rb = Cpt(EpicsSignal, '}Ena-Sts')

    def timeout_handler(self, signum, frame):
        print("{}.connected timeout".format(self.name))
        raise Exception("end of time")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._ready_to_collect = False

        #signal.signal(signal.SIGALRM, self.timeout_handler)
        #signal.setitimer(signal.ITIMER_REAL, 2)
        #try:
        #    while(self.connected == False):
        #        pass
        if self.connected:
            #self.enable_sel.put(1)
            #self.sample_rate.put(350)
            self.enable_averaging.put(1)
            if self.averaging_points.value == 0:
                self.averaging_points.put("1024")
        #except Exception as exc:
        #    pass
        #signal.alarm(0)



class AdcFS(Adc):
    "Adc Device, when read, returns references to data in filestore."
    chunk_size = 1024
    write_path_template = '/nsls2/xf07bm/data/pizza_box_data/%Y/%m/%d/'

    def __init__(self, *args, reg, **kwargs):
        self._reg = reg
        super().__init__(*args, **kwargs)

    def stage(self):
        "Set the filename and record it in a 'resource' document in the filestore database."


        if(self.connected):
        #if True:
            print(self.name, 'stage')
            DIRECTORY = datetime.now().strftime(self.write_path_template)
            #DIRECTORY = "/nsls2/xf07bm/data/pb_data"

            filename = 'an_' + str(uuid.uuid4())[:6]
            self._full_path = os.path.join(DIRECTORY, filename)  # stash for future reference
            print("writing to {}".format(self._full_path))

            self.filepath.put(self._full_path)
            self.resource_uid = self._reg.register_resource(
                'PIZZABOX_AN_FILE_TXT',
                DIRECTORY, self._full_path,
                {'chunk_size': self.chunk_size})

            super().stage()
        else:
            print("{} not staged".format(self.name))

    def unstage(self):
        if(self.connected):
            set_and_wait(self.enable_sel, 1)
            return super().unstage()

    def kickoff(self):
        print('kickoff', self.name)
        self._ready_to_collect = True
        "Start writing data into the file."

        # set_and_wait(self.enable_sel, 0)
        st = self.enable_sel.set(0)

        # Return a 'status object' that immediately reports we are 'done' ---
        # ready to collect at any time.
        # return NullStatus()
        return st

    def complete(self):
        print('complete', self.name, '| filepath', self._full_path)
        if not self._ready_to_collect:
            raise RuntimeError("must called kickoff() method before calling complete()")
        # Stop adding new data to the file.
        set_and_wait(self.enable_sel, 1)
        return NullStatus()

    def collect(self):
        """
        Record a 'datum' document in the filestore database for each encoder.

        Return a dictionary with references to these documents.
        """
        print('collect', self.name)
        self._ready_to_collect = False

        # Create an Event document and a datum record in filestore for each line
        # in the text file.
        now = ttime.time()
        ttime.sleep(1)  # wait for file to be written by pizza box
        if os.path.isfile(self._full_path):
            with open(self._full_path, 'r') as f:
                linecount = 0
                for ln in f:
                    linecount += 1

            chunk_count = linecount // self.chunk_size + int(linecount % self.chunk_size != 0)
            for chunk_num in range(chunk_count):
                datum_uid = self._reg.register_datum(self.resource_uid,
                                                     {'chunk_num': chunk_num})
                data = {self.name: datum_uid}

                yield {'data': data,
                       'timestamps': {key: now for key in data}, 'time': now}
        else:
            print('collect {}: File was not created'.format(self.name))
            print("filename : {}".format(self._full_path))

    def describe_collect(self):
        # TODO Return correct shape (array dims)
        now = ttime.time()
        return {self.name: {self.name:
                     {'filename': self._full_path,
                      'devname': self.dev_name.value,
                      'source': 'pizzabox-adc-file',
                      'external': 'FILESTORE:',
                      'shape': [5,],
                      'dtype': 'array'}}}


class DualAdcFS(Adc):
    '''
    Adc Device, when read, returns references to data in filestore.
        This is for a dual device. It defines one ADC which
            uses a shared triggering mechanism for file writing.
        The adc is either a 'master' or 'slave'. If 'master', then kickoff()
            should trigger the 'Ena-Sel' PV (which starts collecting data to file).
        If 'slave', then it should check that the 'Ena-Sel' PV is set.
        TODO : Need to add a good waiting mechanism for this.
    '''
    # these are for the dual ADC FS
    # column is the column and enable_sel is what triggers the collection
    # rename because of existing children pv's
    dual_enable_sel = FC(EpicsSignal, '{self._adc_trigger}}}Ena-Sel')
    dual_filepath = FC(EpicsSignal, '{self._adc_trigger}}}ID:File.VAL', string=True)
    chunk_size = 1024
    write_path_template = '/nsls2/xf07bm/data/pizza_box_data/%Y/%m/%d/'

    def __init__(self, *args, adc_column, adc_trigger_name, mode='master', reg,
                 **kwargs):
        '''
            This is for a dual ADC system.
            adc_column : the column
            adc_trigger: the adc pv used for triggering for this dual channel
            mode : {'master', 'slave'}
                The mode. Master will create a new file and resource during kickoff
                    Slave assumes the new file and resource are already created.
                    Slave should check if acquisition has been triggered first,
                    else return an error.

            Notes:
                The adc master and adc for triggering are not necessarily the same
                    (for ex, adc6 and adc7 triggered using adc1, but adc6 is
                     what will put to adc1's trigger)
        '''
        self._reg = reg
        self._column = adc_column
        self._adc_trigger = adc_trigger_name
        self._mode = mode
        super().__init__(*args, **kwargs)

    def stage(self):
        "Set the filename and record it in a 'resource' document in the filestore database."


        if self.connected:
            if self._mode == 'master':
        #if True:
                print(self.name, 'stage')
                DIRECTORY = datetime.now().strftime(self.write_path_template)
                #DIRECTORY = "/nsls2/xf07bm/data/pb_data"

                filename = 'an_' + str(uuid.uuid4())[:6]
                self._full_path = os.path.join(DIRECTORY, filename)  # stash for future reference
                print("writing to {}".format(self._full_path))

                self.dual_filepath.put(self._full_path)
                self.resource_uid = self._reg.register_resource(
                    'PIZZABOX_AN_FILE_TXT',
                    DIRECTORY, self._full_path,
                    {'chunk_size': self.chunk_size})

                super().stage()
            else:
                print("This is a slave ADC. File path already set to {}".format(self.dual_filepath.get()))
        else:
            msg = "Error, adc {} not ready for acquiring\n".format(self.name)
            raise ValueError(msg)


    def unstage(self):
        if(self.connected):
            set_and_wait(self.dual_enable_sel, 1)
            # either master or slave can unstage if needed, safer
            return super().unstage()

    def kickoff(self):
        if self._mode == 'master':
            print('kickoff', self.name)
            self._ready_to_collect = True
            "Start writing data into the file."
   
            # set_and_wait(self.enable_sel, 0)
            st = self.dual_enable_sel.set(0)
           
   
            # Return a 'status object' that immediately reports we are 'done' ---
            # ready to collect at any time.
            # return NullStatus()
            return st
        else:
            # TODO : clean up this logic
            # the main issue is I want the slave adc to appear as a normal adc
            # so that it is backwards compat with Bruno's code
            # (and we can just fly([flyer1, flyer2, ...]) etc without
            # additional complications)
            dual_enable_sel = self.dual_enable_sel.get()
            if dual_enable_sel != 1:
                cnt = 0
                while True:
                    # current attempt for waiting
                    print("Enable-sel from master not set. Waiting...")
                    # wait a little bit
                    if dual_enable_sel == 1:
                        st = Status()
                        st._finished(success=False)
                        # return unhappy status object
                        return st
                    cnt +=1
                    time.sleep(.1)
            st = Status()
            st._finished()
            return st

    def complete(self):
        print('complete', self.name, '| filepath', self._full_path)
        if not self._ready_to_collect:
            raise RuntimeError("must called kickoff() method before calling complete()")
        # Stop adding new data to the file.
        set_and_wait(self.dual_enable_sel, 1)
        return NullStatus()

    def collect(self):
        """
        Record a 'datum' document in the filestore database for each encoder.

        Return a dictionary with references to these documents.
        """
        print('collect', self.name)
        self._ready_to_collect = False

        # Create an Event document and a datum record in filestore for each line
        # in the text file.
        now = ttime.time()
        ttime.sleep(1)  # wait for file to be written by pizza box
        if os.path.isfile(self._full_path):
            with open(self._full_path, 'r') as f:
                linecount = 0
                for ln in f:
                    linecount += 1

            chunk_count = linecount // self.chunk_size + int(linecount % self.chunk_size != 0)
            for chunk_num in range(chunk_count):
                datum_uid = self._reg.register_datum(self.resource_uid,
                                                     {'chunk_num': chunk_num,
                                                      'column' : self._column})
                data = {self.name: datum_uid}

                yield {'data': data,
                       'timestamps': {key: now for key in data}, 'time': now}
        else:
            print('collect {}: File was not created'.format(self.name))
            print("filename : {}".format(self._full_path))

    def describe_collect(self):
        # TODO Return correct shape (array dims)
        now = ttime.time()
        return {self.name: {self.name:
                     {'filename': self._full_path,
                      'devname': self.dev_name.value,
                      'source': 'pizzabox-adc-file',
                      'external': 'FILESTORE:',
                      'shape': [5,],
                      'dtype': 'array'}}}

class PizzaBoxAnalogFS(Device):
    #internal_ts_sel = Cpt(EpicsSignal, 'Gen}T:Internal-Sel')

    adc1 = Cpt(AdcFS, 'ADC:1', reg=db.reg)
    adc6 = Cpt(AdcFS, 'ADC:6', reg=db.reg)
    adc7 = Cpt(AdcFS, 'ADC:7', reg=db.reg)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # must use internal timestamps or no bytes are written
        # self.stage_sigs[self.internal_ts_sel] = 1

    def kickoff(self):
        "Call encoder.kickoff() for every encoder."
        for attr_name in ['adc1']: #, 'adc2', 'adc3', 'adc4']:
            status = getattr(self, attr_name).kickoff()
        # it's fine to just return one of the status objects
        return status

    def collect(self):
        "Call adc.collect() for every encoder."
        # Stop writing data to the file in all encoders.
        for attr_name in ['adc1']: #, 'adc2', 'adc3', 'adc4']:
            set_and_wait(getattr(self, attr_name).enable_sel, 0)
        # Now collect the data accumulated by all encoders.
        for attr_name in ['adc1']: #, 'adc2', 'adc3', 'adc4']:
            yield from getattr(self, attr_name).collect()


# the 2 channel pizza box, uncomment to use (and comment out 6 channel)
#pba1 = PizzaBoxAnalogFS('XF:07BMB-CT{GP1-', name = 'pba1')
# set the PV's that are 'i0', 'it' and 'ir' (if any)
#pba1.adc6.dev_name.put('i0')
#pba1.adc7.dev_name.put('it')

class PizzaBoxDualAnalogFS(Device):
    #internal_ts_sel = Cpt(EpicsSignal, 'Gen}T:Internal-Sel')

    # for these, you need a master and a slave
    # set the PV that will always trigger to master and any additional to slave
    # first pair
    '''
        Some comments about defining these adc's for the pizza boxes:
            adc_column: int
                this is the column in the file that the data is written
                0, being the first column with encoder data
            adc_trigger_name : str
                This is the PV string for the Epics PV we must talk to 
                to begin the triggering
            mode: {'master', 'slave', 'disabled'}
                This is the mode.
                In slave mode, the adc won't trigger the collection.
                In disabled mode, the adc won't stage when the parent stage() method
                    is called.
                In master mode, the adc will trigger the collection of data.
                If you use just one PV in a pair, make sure it is in 'master' mode.
                If you use both PV's in a pair, make sure only one is set to "master"
                Another option is we could remove this option and just have
                each PV check if the collection has been triggered and trigger
                otherwise.

        An alternative to defining these is to create an object per pair of ADC's.
        However, this is not backwards compatible with the way iss runs on the
        pizza boxes. Some care must be taken to modify the plans and the GUI if
        doing this.
    '''
    adc3 = Cpt(DualAdcFS, 'ADC:3', reg=db.reg,
               adc_column=0, adc_trigger_name="XF:07BMB-CT{GP2-ADC:1",
               mode='disabled')
    adc4 = Cpt(DualAdcFS, 'ADC:4', reg=db.reg,
               adc_column=1, adc_trigger_name="XF:07BMB-CT{GP2-ADC:1",
               mode='disabled')

    # second pair
    # if using both, one must be master, the other slave
    adc5 = Cpt(DualAdcFS, 'ADC:5', reg=db.reg,
               adc_column=0, adc_trigger_name="XF:07BMB-CT{GP2-ADC:6",
               mode='disabled')
    adc6 = Cpt(DualAdcFS, 'ADC:6', reg=db.reg,
               adc_column=1, adc_trigger_name="XF:07BMB-CT{GP2-ADC:6",
               mode='master')

    # third pair
    adc7 = Cpt(DualAdcFS, 'ADC:7', reg=db.reg,
               adc_column=0, adc_trigger_name="XF:07BMB-CT{GP2-ADC:7",
               mode='master')

    adc8 = Cpt(DualAdcFS, 'ADC:8', reg=db.reg,
               adc_column=1, adc_trigger_name="XF:07BMB-CT{GP2-ADC:7",
               mode='disabled')


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # must use internal timestamps or no bytes are written
        # self.stage_sigs[self.internal_ts_sel] = 1

    def _get_active_devices(self):
        devices = [getattr(self, name) for name in self.component_names]
        devices = [device for device in devices if device._mode != 'disabled']
        return devices

    def stage(self):
        devices = self._get_active_devices()
        for device in devices:
            device.stage()

    def unstage(self):
        devices = self._get_active_devices()
        for device in devices:
            device.unstage()

    def kickoff(self):
        '''Call encoder.kickoff() for every encoder.

            This is untested. Currently isstools uses the underlying adc
                children.
        '''
        devices = self._get_active_devices()
        compound_status = None
        for device in devices:
            new_status = device.kickoff()
            if compound_status is None:
                new_status = compound_status
            else:
                new_status = ophyd.AndStatus(compound_status, new_status)
        return new_status

    def complete(self):
        '''Call encoder.complete() for every encoder.

            This is untested. Currently isstools uses the underlying adc
                children.
        '''
        devices = self._get_active_devices()
        compound_status = None
        for device in devices:
            new_status = device.complete()
            if compound_status is None:
                new_status = compound_status
            else:
                new_status = ophyd.AndStatus(compound_status, new_status)
        return new_status

    def collect(self):
        "Call adc.collect() for every encoder."
        devices = self._get_active_devices()
        for device in devices:
            yield from device.collect()


# the 6 channel pizza box
pba1 = PizzaBoxDualAnalogFS('XF:07BMB-CT{GP2-', name = 'pba1')
# set the PV's that are 'i0', 'it' and 'ir' (if any)
pba1.adc6.dev_name.put('i0')
pba1.adc7.dev_name.put('it')

# the 6 channel pizza box
#pba1_6chan = PizzaBoxAnalogFS('XF:07BMB-CT{GP2-', name = 'pba1_6chan')
# set the PV's that are 'i0', 'it' and 'ir' (if any)
#pba1_6chan.adc6.dev_name.put('i0')
#pba1_6chan.adc7.dev_name.put('it')

# the 6 channel pizza box
#pba1 = PizzaBoxAnalogFS('XF:07BMB-CT{GP2-', name = 'pba1')
# set the PV's that are 'i0', 'it' and 'ir' (if any)
#pba1.adc6.dev_name.put('i0')
#pba1.adc7.dev_name.put('it')

# cludge for now


# TODO : move upstream
class PizzaBoxEncHandlerTxt(HandlerBase):
    encoder_row = namedtuple('encoder_row',
                             ['ts_s', 'ts_ns', 'encoder', 'index', 'state'])
    "Read PizzaBox text files using info from filestore."
    def __init__(self, fpath, chunk_size):
        self.chunk_size = chunk_size
        with open(fpath, 'r') as f:
            self.lines = list(f)

    def __call__(self, chunk_num):
        cs = self.chunk_size
        return [self.encoder_row(*(int(v) for v in ln.split()))
                for ln in self.lines[chunk_num*cs:(chunk_num+1)*cs]]


class PizzaBoxDIHandlerTxt(HandlerBase):
    di_row = namedtuple('di_row', ['ts_s', 'ts_ns', 'encoder', 'index', 'di'])
    "Read PizzaBox text files using info from filestore."
    def __init__(self, fpath, chunk_size):
        self.chunk_size = chunk_size
        with open(fpath, 'r') as f:
            self.lines = list(f)

    def __call__(self, chunk_num):
        cs = self.chunk_size
        return [self.di_row(*(int(v) for v in ln.split()))
                for ln in self.lines[chunk_num*cs:(chunk_num+1)*cs]]


class PizzaBoxAnHandlerTxt(HandlerBase):
    ''' Like pizza box handler except each file has two columns
    '''
    "Read PizzaBox text files using info from filestore."

    def __init__(self, fpath, chunk_size):
        self.chunk_size = chunk_size
        print("chunk size : {}".format(chunk_size))
        with open(fpath, 'r') as f:
            self.lines = list(f)
        print(fpath)
        self.ncols = len(self.lines[0].split())
        print("number of columns is {}".format(self.ncols))
        self.cols = ['ts_s', 'ts_ns', 'index', 'adc']
        self.bases = [10, 10, 10, 16]
        self.encoder_row = namedtuple('encoder_row', self.cols)

    def __call__(self, chunk_num, column=0):

        cs = self.chunk_size
        col_index = column + 3
        # TODO : clean up this logic, maybe use pandas?
        # need to first look at how isstools parses this
        return [self.encoder_row(*(int(v, base=b) for v, b in zip((ln.split()[i] for i in [0,1,2,col_index]), self.bases)))
                for ln in self.lines[chunk_num*cs:(chunk_num+1)*cs]]



db.reg.register_handler('PIZZABOX_AN_FILE_TXT',
                        PizzaBoxAnHandlerTxt, overwrite=True)
db.reg.register_handler('PIZZABOX_ENC_FILE_TXT',
                        PizzaBoxEncHandlerTxt, overwrite=True)
db.reg.register_handler('PIZZABOX_DI_FILE_TXT',
                        PizzaBoxDIHandlerTxt, overwrite=True)
