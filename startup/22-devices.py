print(__file__)

from bluesky.plan_stubs import mv, abs_set
from nslsii.devices import TwoButtonShutter


class EPS_Shutter(Device):
    state = Cpt(EpicsSignal, 'Pos-Sts')
    cls = Cpt(EpicsSignal, 'Cmd:Cls-Cmd')
    opn = Cpt(EpicsSignal, 'Cmd:Opn-Cmd')
    error = Cpt(EpicsSignal,'Err-Sts')
    permit = Cpt(EpicsSignal, 'Permit:Enbl-Sts')
    enabled = Cpt(EpicsSignal, 'Enbl-Sts')


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.color = 'red'

    def open_plan(self):
        yield from mv(self.opn, 1,wait=True)

    def close_plan(self):
        yield from abs_set(self.cls, 1, wait=True)

    def open(self):
        print('Opening {}'.format(self.name))
        self.opn.put(1)

    def close(self):
        print('Closing {}'.format(self.name))
        self.cls.put(1)


class TwoButtonShutterQAS(TwoButtonShutter):
    def stop(self, success=False):
        pass


class QASFastShutter(Device):
    IO_status = Cpt(EpicsSignal, '', kind='omitted')
    status = Cpt(EpicsSignal, '', kind='omitted', string=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setmap = {'Open': 1, 'Close': 0}
        self.readmap = {v: k for k, v in self.setmap.items()}
        self.status.get = self.get
        self.status.set = self.set

    def set(self, val):
        return self.IO_status.set(self.setmap[val])

    def get(self):
        return self.readmap[self.IO_status.get()]

    def read(self):
        d = super().read()
        d[self.name] = {'value': self.get(), 'timestamp': time.time()}
        return d


shutter_fe = TwoButtonShutterQAS('XF:07BM-PPS{Sh:FE}', name = 'FE Shutter')
shutter_fe.shutter_type = 'FE'
shutter_ph = TwoButtonShutterQAS('XF:07BMA-PPS{Sh:A}', name = 'PH Shutter')
shutter_ph.shutter_type = 'PH'
shutter_fs = QASFastShutter('XF:07BMB-CT{PBA:1}:GPIO:0-SP',
                            name='Fast Shutter')
shutter_fs.shutter_type = 'FS'


class LinkamThermal(Device):

    #Set-and-read signals
    cmd = Cpt(EpicsSignal, 'STARTHEAT')
    temperature_setpoint = Cpt(EpicsSignal, 'SETPOINT:SET')
    temperature_rate_setpoint = Cpt(EpicsSignal, 'RAMPRATE:SET')

    #Read-Only signals
    status_power = Cpt(EpicsSignalRO, 'STARTHEAT')
    status_code =  Cpt(EpicsSignalRO, 'STATUS') 
    # status_code = Cpt(EpicsSignal, 'STATUS')
    # done = Cpt(AtSetpoint, parent_attr = 'status_code')
    temperature_current = Cpt(EpicsSignalRO, 'TEMP')
    temperature_rate_current = Cpt(EpicsSignalRO, 'RAMPRATE')

    #not commonly used
    init = Cpt(EpicsSignal, 'INIT')
    model_array = Cpt(EpicsSignal, 'MODEL')
    serial_array = Cpt(EpicsSignal, 'SERIAL')
    stage_model_array = Cpt(EpicsSignal, 'STAGE:MODEL')
    stage_serial_array = Cpt(EpicsSignal, 'STAGE:SERIAL')
    firm_ver = Cpt(EpicsSignal, 'FIRM:VER')
    hard_ver = Cpt(EpicsSignal, 'HARD:VER')
    ctrllr_err = Cpt(EpicsSignal, 'CTRLLR:ERR')
    config = Cpt(EpicsSignal, 'CONFIG')
    stage_config = Cpt(EpicsSignal, 'STAGE:CONFIG')
    disable = Cpt(EpicsSignal, 'DISABLE')
    dsc = Cpt(EpicsSignal, 'DSC')
    # RR_set = Cpt(EpicsSignal, 'RAMPRATE:SET')
    # RR = Cpt(EpicsSignal, 'RAMPRATE')
    ramptime = Cpt(EpicsSignal, 'RAMPTIME')
    # startheat = Cpt(EpicsSignal, 'STARTHEAT')
    holdtime_set = Cpt(EpicsSignal, 'HOLDTIME:SET')
    holdtime = Cpt(EpicsSignal, 'HOLDTIME')
    power = Cpt(EpicsSignalRO, 'POWER')
    lnp_speed = Cpt(EpicsSignal, 'LNP_SPEED')
    lnp_mode_set = Cpt(EpicsSignal, 'LNP_MODE:SET')
    lnp_speed_set = Cpt(EpicsSignal, 'LNP_SPEED:SET')
    ramprate = Cpt(EpicsSignal, 'RAMPRATE')
    ramprate_set = Cpt(EpicsSignal, 'RAMPRATE:SET')


    def on(self):
        return self.cmd.put(1)

    def _on(self):
        yield from bps.mv(self.cmd,1)

    def off(self):
        return self.cmd.put(0)

    def _off(self):
        yield from bps.mv(self.cmd,0)

    def setTemperature(self, temperature):
        return self.temperature_setpoint.put(temperature)

    def setTemperatureRate(self, temperature_rate):
        return self.temperature_rate_setpoint.put(temperature_rate)

    def temperature(self):
        return self.temperature_current.get()

    def temperatureRate(self):
        return self.temperature_rate_current.get()

    @property
    def serial(self):
        return self.arr2word(self.serial_array.get())

    @property
    def model(self):
        return self.arr2word(self.model_array.get())
    
    @property
    def stage_model(self):
        return self.arr2word(self.stage_model_array.get())
    
    @property
    def stage_serial(self):
        return self.arr2word(self.stage_serial_array.get())

    @property
    def firmware_version(self):
        return self.arr2word(self.firm_ver.get())

    @property
    def hardware_version(self):
        return self.arr2word(self.hard_ver.get())

    def status(self):
        text = f'\nCurrent temperature = {self.temperature():.1f}, setpoint = {self.temperature_setpoint.get():.1f}\n\n'
        code = int(self.status_code.get())
        
        if code & 1:  #Error
            text += 'Error        : yes' + '\n'
        else:
            text += 'Error        : no\n'
        if code & 2: # at setpoint 
            text += 'At setpoint  : yes' + '\n'
        else:
            text += 'At setpoint  : no\n'
        if code & 4: #heater
            text += 'Heater       : on' + '\n'
        else:
            text += 'Heater       : off\n'
        if code & 8: #pump
            text += 'Pump         : on' + '\n'
        else:
            text += 'Pump         : off\n'
        if code & 16: # pump auto
            text += 'Pump Auto    : yes' + '\n'
        else:
            text += 'Pump Auto    : no\n'
            
        print( text )

linkam = LinkamThermal('XF:07BM-B{Linkam:1}:', name='linkam')

class EPS_MFC(Device):
    ch1_he_rb = Cpt(EpicsSignal, '-AI}MFC1_FB')
    ch1_he_sp = Cpt(EpicsSignal, '-AO}MFC1_SP')

    ch2_n2_rb = Cpt(EpicsSignal, '-AI}MFC2_FB')
    ch2_n2_sp = Cpt(EpicsSignal, '-AO}MFC2_SP')

    ch3_ar_rb = Cpt(EpicsSignal, '-AI}MFC3_FB')
    ch3_ar_sp = Cpt(EpicsSignal, '-AO}MFC3_SP')

    ch4_n2_rb = Cpt(EpicsSignal, '-AI}MFC4_FB')
    ch4_n2_sp = Cpt(EpicsSignal, '-AO}MFC4_SP')

    ch5_ar_rb = Cpt(EpicsSignal, '-AI}MFC5_FB')
    ch5_ar_sp = Cpt(EpicsSignal, '-AO}MFC5_SP')

mfc = EPS_MFC('XF:07BMA-CT{MFC', name='mfc')

class EPS_MFC1(Device):
    flow_rb = Cpt(EpicsSignal, '-AI}MFC1_FB')
    flow_sp = Cpt(EpicsSignal, '-AO}MFC1_SP')

mfc1_he = EPS_MFC1('XF:07BMA-CT{MFC', name='mfc1_he')

class EPS_MFC2(Device):
    flow_rb = Cpt(EpicsSignal, '-AI}MFC2_FB')
    flow_sp = Cpt(EpicsSignal, '-AO}MFC2_SP')

mfc2_n2 = EPS_MFC2('XF:07BMA-CT{MFC', name='mfc2_n2')

class EPS_MFC3(Device):
    flow_rb = Cpt(EpicsSignal, '-AI}MFC3_FB')
    flow_sp = Cpt(EpicsSignal, '-AO}MFC3_SP')

mfc3_ar = EPS_MFC3('XF:07BMA-CT{MFC', name='mfc3_ar')

class EPS_MFC4(Device):
    flow_rb = Cpt(EpicsSignal, '-AI}MFC4_FB')
    flow_sp = Cpt(EpicsSignal, '-AO}MFC4_SP')

mfc4_n2 = EPS_MFC4('XF:07BMA-CT{MFC', name='mfc4_n2')

class EPS_MFC5(Device):
    flow_rb = Cpt(EpicsSignal, '-AI}MFC5_FB')
    flow_sp = Cpt(EpicsSignal, '-AO}MFC5_SP')

mfc5_ar = EPS_MFC5('XF:07BMA-CT{MFC', name='mfc5_ar')



'''
Here is the amplifier definition

'''


class WienerPowerSupply(Device):
    i0_plate_rb = Cpt(EpicsSignal, 'u300}V-Sense')
    i0_plate_sp = Cpt(EpicsSignal, 'u300}V-Set')

    i0_grid_rb = Cpt(EpicsSignal, 'u301}V-Sense')
    i0_grid_sp = Cpt(EpicsSignal, 'u301}V-Set')

    it_plate_rb = Cpt(EpicsSignal, 'u302}V-Sense')
    it_plate_sp = Cpt(EpicsSignal, 'u302}V-Set')

    it_grid_rb = Cpt(EpicsSignal, 'u303}V-Sense')
    it_grid_sp = Cpt(EpicsSignal, 'u303}V-Set')

    ir_plate_rb = Cpt(EpicsSignal, 'u304}V-Sense')
    ir_plate_sp = Cpt(EpicsSignal, 'u304}V-Set')

    ir_grid_rb = Cpt(EpicsSignal, 'u305}V-Sense')
    ir_grid_sp = Cpt(EpicsSignal, 'u305}V-Set')

wps = WienerPowerSupply("XF:07BMC-OP{WPS:01-HV:", name='wps') # For hutch C
# wps = WienerPowerSupply("XF:07BMB-OP{WPS:01-HV:", name='wps') For hutch B
class ICAmplifier(Device):

    gain = Cpt(EpicsSignal,'Gain')
    risetime = Cpt(EpicsSignal,'RiseTime')
    supr_mode = Cpt(EpicsSignal, 'SuppressionMode')
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


    def get_gain(self):
        return self.gain.get()+3

    def set_gain(self, gain):
        self.gain.set(gain-3)



i0_amp = ICAmplifier('XF:07BM:K428:A:',name='i0_amp')
 
it_amp = ICAmplifier('XF:07BM:K428:B:',name='it_amp')

ir_amp = ICAmplifier('XF:07BM:K428:C:',name='ir_amp')

iff_amp = ICAmplifier('XF:07BM:K428:D:',name='iff_amp')


'''
ir_amp = ICAmplifier('XF:08IDB-CT{', gain_0='ES-DO}2_10_0', gain_1='ES-DO}2_10_1',
                     gain_2='ES-DO}2_10_2', hspeed_bit='ES-DO}2_10_3', bw_10mhz_bit='ES-DO}2_10_4', bw_1mhz_bit='ES-DO}2_10_5',
                     lnoise='Amp-LN}Ir', hspeed='Amp-HS}Ir', bwidth='Amp-BW}Ir', name='ir_amp')

iff_amp = ICAmplifier('XF:08IDB-CT{', gain_0='ES-DO}2_11_0', gain_1='ES-DO}2_11_1',
                     gain_2='ES-DO}2_11_2', hspeed_bit='ES-DO}2_11_3', bw_10mhz_bit='ES-DO}2_11_4', bw_1mhz_bit='ES-DO}2_11_5',
lnoise='Amp-LN}If', hspeed='Amp-HS}If', bwidth='Amp-BW}If', name='iff_amp')
self.gain_1 = EpicsSignal(self.prefix + gain_1, name=self.name + '_gain_1')
        self.gain_2 = EpicsSignal(self.prefix + gain_2, name=self.name + '_gain_2')
        self.hspeed_bit = EpicsSignal(self.prefix + hspeed_bit, name=self.name + '_hspeed_bit')
        self.bw_10mhz_bit = EpicsSignal(self.prefix + bw_10mhz_bit, name=self.name + '_bw_10mhz_bit')
        self.bw_1mhz_bit = EpicsSignal(self.prefix + bw_1mhz_bit, name=self.name + '_bw_1mhz_bit')
        self.low_noise_gain = EpicsSignal(self.prefix + lnoise, name=self.name + '_lnoise')
        self.high_speed_gain = EpicsSignal(self.prefix + hspeed, name=self.name + '_hspeed')
        self.band_width = EpicsSignal(self.prefix + bwidth, name=self.name + '_bwidth')
        self.par = par
       


    def set_gain(self, value: int, high_speed: bool):

        val = int(value) - 2
        if not ((high_speed and (1 <= val < 7)) or (not high_speed and (0 <= val < 6))):
            print('{} invalid value. Ignored...'.format(self.name))
            return 'Aborted'

        if high_speed:
            val -= 1
            self.low_noise_gain.put(0)
            self.high_speed_gain.put(val + 1)
            self.hspeed_bit.put(1)
        else:
            self.low_noise_gain.put(val + 1)
            self.high_speed_gain.put(0)
            self.hspeed_bit.put(0)

        self.gain_0.put((val >> 0) & 1)
        self.gain_1.put((val >> 1) & 1)
        self.gain_2.put((val >> 2) & 1)

    def set_gain_plan(self, value: int, high_speed: bool):

        val = int(value) - 2
        if not ((high_speed and (1 <= val < 7)) or (not high_speed and (0 <= val < 6))):
            print('{} invalid value. Ignored...'.format(self.name))
            return 'Aborted'

        if high_speed:
            val -= 1
            yield from bp.abs_set(self.low_noise_gain, 0)
            yield from bp.abs_set(self.high_speed_gain, val + 1)
            yield from bp.abs_set(self.hspeed_bit, 1)
        else:
            yield from bp.abs_set(self.low_noise_gain, val + 1)
            yield from bp.abs_set(self.high_speed_gain, 0)
            yield from bp.abs_set(self.hspeed_bit, 0)

        yield from bp.abs_set(self.gain_0, (val >> 0) & 1)
        yield from bp.abs_set(self.gain_1, (val >> 1) & 1)
        yield from bp.abs_set(self.gain_2, (val >> 2) & 1)

    def get_gain(self):
        if self.low_noise_gain.get() == 0:
            return [self.high_speed_gain.enum_strs[self.high_speed_gain.get()], 1]
        elif self.high_speed_gain.get() == 0:
            return [self.low_noise_gain.enum_strs[self.low_noise_gain.get()], 0]
        else:
            return ['0', 0]


'''
