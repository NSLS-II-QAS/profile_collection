print(__file__)
import bluesky as bs
import bluesky.plans as bp
import time as ttime
from subprocess import call
import os
import signal
#from bluesky import RunEngine


### Added by Chanaka and Julien

def slit_scan_plan(detectors, num, slit1, slit2, rel_start, rel_stop):
    ''' Scan slit 1 and slit 2 together relative.

        Parameters
        ----------
        num : number of steps
        detectors : detectors
        slit1 : first slit
        slit2 : second slit
        rel_start : relative begin motion
        rel_stop : relative end motion

        Example
        -------
        You can scan the inboard and outboard slits together from -2 to +2 of
        their current position in 21 steps while measuring the ROI from the
        camera:

        RE(slit_scan_plan([hutchb_diag], 21
                       jj_slits.inboard,
                       jj_slits.outboard,
                       -2, 2))
    '''
    rel_scan = bp.relative_inner_product_scan
    yield from rel_scan(detectors, num,
                        slit1, rel_start, rel_stop,
                        slit2, rel_start, rel_stop)


## TODO :
## Add scans from ISS 95-user.py little by little
## start with the simple scans (no trajectory)



###

def general_scan_plan(detectors, motor, rel_start, rel_stop, num):

    
    plan = bp.relative_scan(detectors, motor, rel_start, rel_stop, num)
    
    if hasattr(detectors[0], 'kickoff'):
        plan = bpp.fly_during_wrapper(plan, detectors)

    yield from plan


def prep_traj_plan(delay = 0.1):
    yield from bps.mv(mono1, 'prepare')
    yield from bps.sleep(delay)


def execute_trajectory(name, ignore_shutter=True, **metadata):
    ''' Execute a trajectory on the flyers given:
            flyers : list of flyers to fly on

        scans on 'mono1' by default

        ignore_shutter : bool, optional
            If True, ignore the shutter
            (suspenders on shutter and ring current will be installed if not)
        ex:
            execute_trajectory(**md)
    '''
    flyers = [pba1.adc3, pba1.adc4, pba1.adc5, pba1.adc6, pba1.adc7, pba1.adc8, pb1.enc1]
    #flyers = [pb1.enc1, pba1.adc3, pba1.adc4]#, pba1.adc5, pba1.adc6, pba1.adc7, pba1.adc8]

    #Terrible hack again following Eli's foot steps
    foil_elem = get_reference_foil()
    i0_gainB  = i0_amp.get_gain()
    it_gainB  = it_amp.get_gain()
    ir_gainB  = ir_amp.get_gain()
    iff_gainB = iff_amp.get_gain()

    mfc1B_he = mfc1_he.flow_rb.get()
    mfc2B_n2 = mfc2_n2.flow_rb.get()
    mfc3B_ar = mfc3_ar.flow_rb.get()
    mfc4B_n2 = mfc4_n2.flow_rb.get()
    mfc5B_ar = mfc5_ar.flow_rb.get()

    incident_beampathB_y = ip_y_stage.user_readback.get()

    incident_slitsB_top      = jj_slits.top.user_readback.get()
    incident_slitsB_bottom   = jj_slits.bottom.user_readback.get()
    incident_slitsB_inboard  = jj_slits.inboard.user_readback.get()
    incident_slitsB_outboard = jj_slits.outboard.user_readback.get()

    sample_stageB_rot = sample_stage1.rotary.user_readback.get()
    sample_stageB_x   = sample_stage1.x.user_readback.get()
    sample_stageB_y   = sample_stage1.y.user_readback.get()
    sample_stageB_z   = sample_stage1.z.user_readback.get()

    pe_y = pe_pos.vertical.user_readback.get()

    cm_xu = cm.hor_up.user_readback.get()
    cm_xd = cm.hor_down.user_readback.get()
    #End of terrible hack

    def inner():
        interp_fn = f"{ROOT_PATH}/{USER_FILEPATH}/{RE.md['year']}/{RE.md['cycle']}/{RE.md['PROPOSAL']}/{name}.raw"
        curr_traj = getattr(mono1, 'traj{:.0f}'.format(mono1.lut_number_rbv.value))
        md = {'plan_args': {},
              'plan_name': 'execute_trajectory',
              'experiment': 'fly_energy_scan',
              'name': name,
              'interp_filename': interp_fn,
              'angle_offset': str(mono1.angle_offset.value),
              'trajectory_name': mono1.trajectory_name.value,
              'element': curr_traj.elem.value,
              'edge': curr_traj.edge.value,
              'e0': curr_traj.e0.value,
              'foil': [foil_elem],
              'pulses_per_deg': mono1.pulses_per_deg,
              'keithley_gainsB': [i0_gainB, it_gainB, ir_gainB, iff_gainB],
              'ionchamber_ratesB': [mfc1B_he, mfc2B_n2, mfc3B_ar, mfc4B_n2, mfc5B_ar],
              'incident_beampathB': [incident_beampathB_y],
              'incident_slits': [incident_slitsB_top, incident_slitsB_bottom, incident_slitsB_inboard, incident_slitsB_outboard],
              'sample_stageB': [sample_stageB_rot, sample_stageB_x, sample_stageB_y, sample_stageB_z],
              'pe_vertical': [pe_y],
              'cm_horizontal':[cm_xu, cm_xd]}

        for flyer in flyers:
            if hasattr(flyer, 'offset'):
                md['{} offset'.format(flyer.name)] = flyer.offset.value
        md.update(**metadata)
        yield from bps.open_run(md=md)

        # TODO Replace this with actual status object logic.
        yield from bps.clear_checkpoint()
        #yield from shutter.open_plan()
        #yield from xia1.start_trigger()
        # this must be a float
        yield from bps.abs_set(mono1.enable_loop, 0, wait=True)

        yield from bpp.finalize_wrapper(bps.mv(mono1, 'start'),
                                        bps.mv(mono1.stop_trajectory, '1'))

        yield from bps.close_run()


    for flyer in flyers:
        yield from bps.stage(flyer)

    # yield from bps.stage(mono1)

    def final_plan():
        #yield from xia1.stop_trigger()
        for flyer in flyers:
            yield from bps.unstage(flyer)
        # yield from bps.unstage(mono1)

    fly_plan = bpp.fly_during_wrapper(bpp.finalize_wrapper(inner(), final_plan()),
                                              flyers)
    # TODO : Add in when suspend_wrapper is avaialable
    #if not ignore_shutter:
        # this will use suspenders defined in 23-suspenders.py
        #fly_plan = bpp.suspend_wrapper(fly_plan, suspenders)

    yield from fly_plan

def execute_trajectory_xs3(name, ignore_shutter=True, **metadata):
    ''' Execute a trajectory on the flyers given:
            flyers : list of flyers to fly on

        scans on 'mono1' by default

        ignore_shutter : bool, optional
            If True, ignore the shutter
            (suspenders on shutter and ring current will be installed if not)
        ex:
            execute_trajectory(**md)
    '''
    flyers = [pba1.adc3, pba1.adc4, pba1.adc5, pba1.adc6, pba1.adc7, pba1.adc8, pb1.enc1]

    interp_fn = f"{ROOT_PATH}/{USER_FILEPATH}/{RE.md['year']}/{RE.md['cycle']}/{RE.md['PROPOSAL']}/{name}.raw"
    curr_traj = getattr(mono1, 'traj{:.0f}'.format(mono1.lut_number_rbv.value))

    #Terrible hack again following Eli's foot steps
    foil_elem = get_reference_foil()
    i0_gainB  = i0_amp.get_gain()
    it_gainB  = it_amp.get_gain()
    ir_gainB  = ir_amp.get_gain()
    iff_gainB = iff_amp.get_gain()

    mfc1B_he = mfc1_he.flow_rb.get()
    mfc2B_n2 = mfc2_n2.flow_rb.get()
    mfc3B_ar = mfc3_ar.flow_rb.get()
    mfc4B_n2 = mfc4_n2.flow_rb.get()
    mfc5B_ar = mfc5_ar.flow_rb.get()

    incident_beampathB_y = ip_y_stage.user_readback.get()

    incident_slitsB_top      = jj_slits.top.user_readback.get()
    incident_slitsB_bottom   = jj_slits.bottom.user_readback.get()
    incident_slitsB_inboard  = jj_slits.inboard.user_readback.get()
    incident_slitsB_outboard = jj_slits.outboard.user_readback.get()

    sample_stageB_rot = sample_stage1.rotary.user_readback.get()
    sample_stageB_x   = sample_stage1.x.user_readback.get()
    sample_stageB_y   = sample_stage1.y.user_readback.get()
    sample_stageB_z   = sample_stage1.z.user_readback.get()

    pe_y = pe_pos.vertical.user_readback.get()

    cm_xu = cm.hor_up.user_readback.get()
    cm_xd = cm.hor_down.user_readback.get()
    #End of terrible hack

    # wip terrible hack
    roi1_ch1_lo = xs.channel1.rois.roi01.bin_low.get()
    roi2_ch1_lo = xs.channel1.rois.roi02.bin_low.get()
    roi3_ch1_lo = xs.channel1.rois.roi03.bin_low.get()
    roi4_ch1_lo = xs.channel1.rois.roi04.bin_low.get()

    roi1_ch1_hi = xs.channel1.rois.roi01.bin_high.get()
    roi2_ch1_hi = xs.channel1.rois.roi02.bin_high.get()
    roi3_ch1_hi = xs.channel1.rois.roi03.bin_high.get()
    roi4_ch1_hi = xs.channel1.rois.roi04.bin_high.get()

    roi1_ch2_lo = xs.channel2.rois.roi01.bin_low.get()
    roi2_ch2_lo = xs.channel2.rois.roi02.bin_low.get()
    roi3_ch2_lo = xs.channel2.rois.roi03.bin_low.get()
    roi4_ch2_lo = xs.channel2.rois.roi04.bin_low.get()

    roi1_ch2_hi = xs.channel2.rois.roi01.bin_high.get()
    roi2_ch2_hi = xs.channel2.rois.roi02.bin_high.get()
    roi3_ch2_hi = xs.channel2.rois.roi03.bin_high.get()
    roi4_ch2_hi = xs.channel2.rois.roi04.bin_high.get()

    roi1_ch3_lo = xs.channel3.rois.roi01.bin_low.get()
    roi2_ch3_lo = xs.channel3.rois.roi02.bin_low.get()
    roi3_ch3_lo = xs.channel3.rois.roi03.bin_low.get()
    roi4_ch3_lo = xs.channel3.rois.roi04.bin_low.get()

    roi1_ch3_hi = xs.channel3.rois.roi01.bin_high.get()
    roi2_ch3_hi = xs.channel3.rois.roi02.bin_high.get()
    roi3_ch3_hi = xs.channel3.rois.roi03.bin_high.get()
    roi4_ch3_hi = xs.channel3.rois.roi04.bin_high.get()

    roi1_ch4_lo = xs.channel4.rois.roi01.bin_low.get()
    roi2_ch4_lo = xs.channel4.rois.roi02.bin_low.get()
    roi3_ch4_lo = xs.channel4.rois.roi03.bin_low.get()
    roi4_ch4_lo = xs.channel4.rois.roi04.bin_low.get()

    roi1_ch4_hi = xs.channel4.rois.roi01.bin_high.get()
    roi2_ch4_hi = xs.channel4.rois.roi02.bin_high.get()
    roi3_ch4_hi = xs.channel4.rois.roi03.bin_high.get()
    roi4_ch4_hi = xs.channel4.rois.roi04.bin_high.get()
    # end of terrible hack

    xs_fn = xs.hdf5.full_file_name.get()

    md = {'plan_args': {},
          'plan_name': 'execute_trajectory_xs3',
          'experiment': 'fly_energy_scan_xs3',
          'name': name,
          'interp_filename': interp_fn,
          'xs3_filename': xs_fn,
          'angle_offset': str(mono1.angle_offset.value),
          'trajectory_name': mono1.trajectory_name.value,
          'element': curr_traj.elem.value,
          'edge': curr_traj.edge.value,
          'e0': curr_traj.e0.value,
          'pulses_per_deg': mono1.pulses_per_deg,
          'keithley_gainsB': [i0_gainB, it_gainB, ir_gainB, iff_gainB],
          'ionchamber_ratesB': [mfc1B_he, mfc2B_n2, mfc3B_ar, mfc4B_n2, mfc5B_ar],
          'incident_beampathB': [incident_beampathB_y],
          'incident_slits': [incident_slitsB_top, incident_slitsB_bottom, incident_slitsB_inboard, incident_slitsB_outboard],
          'sample_stageB': [sample_stageB_rot, sample_stageB_x, sample_stageB_y, sample_stageB_z],
          'pe_vertical': [pe_y],
          'cm_horizontal':[cm_xu, cm_xd],
          'rois': [[roi1_ch1_lo, roi1_ch1_hi, roi2_ch1_lo, roi2_ch1_hi, roi3_ch1_lo, roi3_ch1_hi, roi4_ch1_lo, roi4_ch1_hi],
                   [roi1_ch2_lo, roi1_ch2_hi, roi2_ch2_lo, roi2_ch2_hi, roi3_ch2_lo, roi3_ch2_hi, roi4_ch2_lo, roi4_ch2_hi],
                   [roi1_ch3_lo, roi1_ch3_hi, roi2_ch3_lo, roi2_ch3_hi, roi3_ch3_lo, roi3_ch3_hi, roi4_ch3_lo, roi4_ch3_hi],
                   [roi1_ch4_lo, roi1_ch4_hi, roi2_ch4_lo, roi2_ch4_hi, roi3_ch4_lo, roi3_ch4_hi, roi4_ch4_lo, roi4_ch4_hi]]}
    for flyer in flyers:
        if hasattr(flyer, 'offset'):
            md['{} offset'.format(flyer.name)] = flyer.offset.value
    md.update(metadata)
    #RE.md.update(md)
    yield from xs_plan(plan_md=md)


def get_offsets_plan(detectors, num = 1, name = '', **metadata):
    """
    Example
    -------
    >>> RE(get_offset([pba1.adc1, pba1.adc6, pba1.adc7, pba2.adc6]))
    """

    flyers = detectors 

    plan = bp.count(flyers, num, md={'plan_name': 'get_offset', 'name': name}, delay = 0.5)

    def set_offsets():
        for flyer in flyers:
            ret = flyer.volt.value
            yield from bps.abs_set(flyer.offset, ret, wait=True)

    yield from bpp.fly_during_wrapper(bpp.finalize_wrapper(plan, set_offsets()), flyers)
