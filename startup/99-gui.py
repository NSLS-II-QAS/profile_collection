print(__file__)
print("Loading isstools, preparing GUI...")
from PyQt5.QtWidgets import QApplication
import functools
import isstools.xlive
import collections
import atexit

import PyQt5

from bluesky.examples import motor
motor.move = motor.set


detector_dictionary = {#colmirror_diag.name: {'obj': colmirror_diag, 'elements': [colmirror_diag.stats1.total.name, colmirror_diag.stats2.total.name]},
                    #screen_diag.name: {'obj': screen_diag, 'elements': [screen_diag.stats1.total.name, screen_diag.stats2.total.name]},
                    #mono_diag.name: {'obj': mono_diag, 'elements': [mono_diag.stats1.total.name, mono_diag.stats2.total.name]},
                    #dcr_diag.name: {'obj': dcr_diag, 'elements': [dcr_diag.stats1.total.name, dcr_diag.stats2.total.name]},
                    #pba1.adc1.name: {'obj': pba1.adc1, 'elements': ['pba1_adc1_volt']},
                    #pba1.adc3.name: {'obj': pba1.adc3, 'elements': ['pba1_adc3_volt']},
                    #pba1.adc4.name: {'obj': pba1.adc4, 'elements': ['pba1_adc4_volt']},
                    #pba1.adc5.name: {'obj': pba1.adc5, 'elements': ['pba1_adc5_volt']},
                    #pba1.adc6.name: {'obj': pba1.adc6, 'elements': ['pba1_adc6_volt']},
                    #pba1.adc7.name: {'obj': pba1.adc7, 'elements': ['pba1_adc7_volt']},
                    #pba1.adc8.name: {'obj': pba1.adc8, 'elements': ['pba1_adc8_volt']},
                    #pb1.enc1.name: {'obj': pb1.enc1, 'channels': ['pb1_enc1_pos_I']},
                    'I0': {'device': apb_ave, 'channels': ['apb_ave_ch1_mean']},
                    'It': {'device': apb_ave, 'channels': ['apb_ave_ch2_mean']},
                    'Ir': {'device': apb_ave, 'channels': ['apb_ave_ch3_mean']},
                    'PIPS': {'device': apb_ave, 'channels': ['apb_ave_ch4_mean']},
                    'I0 Hutch C': {'device': apb_ave_c, 'channels': ['apb_ave_c_ch1_mean']},
                    'It Hutch C': {'device': apb_ave_c, 'channels': ['apb_ave_c_ch2_mean']},
                    'Ir Hutch C': {'device': apb_ave_c, 'channels': ['apb_ave_c_ch3_mean']},
                    'PIPS Hutch C': {'device': apb_ave_c, 'channels': ['apb_ave_c_ch4_mean']},
                    'xspress3 Hutch B' : {'device': xs, 'channels': ['xs_channel1_rois_roi01_value',
                                                                     'xs_channel1_rois_roi02_value',
                                                                     'xs_channel1_rois_roi03_value',
                                                                     'xs_channel1_rois_roi04_value']},
                    'pilatus': {'device': pilatus, 'channels': ['pilatus_stats1_total']}

}



motors_dictionary = {jj_slits_hutchB.xctr.name: {'name': jj_slits_hutchB.xctr.name, 'description':'B hutch_inc_slits_xcenter',     'object': jj_slits_hutchB.xctr, 'keyword': 'B hutch ins xcenter'},
                     jj_slits_hutchC.xctr.name: {'name': jj_slits_hutchC.xctr.name, 'description':'C hutch_inc_slits_xcenter',     'object': jj_slits_hutchC.xctr, 'keyword': 'C hutch ins xcenter'},
                     drifts.drifts_x.name:      {'name': drifts.drifts_x.name,      'description':'C hutch_DRIFTS_horiz',          'object': drifts.drifts_x,      'keyword': 'C hutch DRIFTS horiz'},
                     drifts.drifts_z.name:      {'name': drifts.drifts_z.name,      'description':'C hutch_DRIFTS_z',              'object': drifts.drifts_z,      'keyword': 'C hutch DRIFTS z'},
                     beamstop.horizontal.name:  {'name': beamstop.horizontal.name,  'description': 'B hutch_beamstop_horiz',       'object':beamstop.horizontal,   'keyword': 'B hutch BS horiz'},
                     beamstop.vertical.name:    {'name': beamstop.vertical.name,    'description': 'B hutch_beamstop_vertical',    'object': beamstop.vertical,    'keyword': 'B hutchB BS vertical'},
                     ibp_hutchB.name:           {'name': ibp_hutchB.name,           'description': 'B hutch_inc_beam_path',        'object': ibp_hutchB,           'keyword': 'B hutch inc beam path'},
                     ibp_hutchC.name:           {'name': ibp_hutchC.name,           'description': 'C hutch_inc_beam_path',        'object': ibp_hutchC,           'keyword': 'C hutch inc beam path'},
                     sample_stage1.rotary.name: {'name': sample_stage1.rotary.name, 'description':'B hutch_sample_stage_rotation', 'object':sample_stage1.rotary,  'keyword': 'B hutch sample rotation'},
                     sample_stage1.x.name:      {'name': sample_stage1.x.name,      'description':'B hutch_sample_stage_x',        'object':sample_stage1.x,       'keyword': 'B hutch sample x'},
                     sample_stage1.y.name:      {'name': sample_stage1.y.name,      'description':'B hutch_sample_stage_y',        'object':sample_stage1.y,       'keyword': 'B hutch sample y'},
                     sample_stage1.z.name:      {'name': sample_stage1.z.name,      'description':'B hutch_sample_stage_z',        'object':sample_stage1.z,       'keyword': 'B hutch sample z'},
                     sample_stage1.theta.name:  {'name': sample_stage1.theta.name,  'description':'B hutch_sample_stage_theta',    'object':sample_stage1.theta,   'keyword': 'B hutch sample theta'},
                     sample_stage1.chi.name:    {'name': sample_stage1.chi.name,    'description':'B hutch_sample_stage_chi',      'object':sample_stage1.chi,     'keyword': 'B hutch sample chi'},
                     mono1.energy.name :        {'name' :mono1.energy.name,         'description': 'Mono Energy',                  'object': mono1.energy,         'keyword': 'Monochromator Energy'}
                    }

shutters_dictionary = {
                       shutter_fe.name: shutter_fe,
                       shutter_ph.name: shutter_ph,
                       shutter_fs.name: shutter_fs,
                       }

service_plan_funcs = {
    'get_offsets': get_offsets,
    'xs_count': xs_count,
    'set Reference foil': set_reference_foil,
    'sleep': sleep_plan,
    }

sample_stages = [{'x': sample_stage1.x.name, 'y': sample_stage1.y.name}]

aux_plan_funcs = {
    'Set Reference Foil': set_reference_foil,
    'Get Reference Foil': get_reference_foil,
    'General Scan': general_scan,
}

plan_funcs = {
    'XAS fly scan': fly_scan_with_apb,
    # 'Fly scan in C': fly_scan_with_apb_c,
    'XAS fly scan w/SDD': fly_scan_with_xs3,
    'XRD take pattern': count_qas
}

for shutter in shutters_dictionary.values():
    shutter.status.wait_for_connection()

app = QApplication(sys.argv)

newApp = PyQt5.QtWidgets.QApplication(sys.argv)

xlive_gui = isstools.xlive.XliveGui(plan_funcs=plan_funcs,
                                    diff_plans=[count_qas, dark_frame_preprocessor],
                                    aux_plan_funcs =aux_plan_funcs,
                                    service_plan_funcs=service_plan_funcs,
                                    prep_traj_plan= prep_traj_plan,
                                    RE=RE,
                                    db=db,
                                    apb = apb,
                                    apb_c = None ,
                                    accelerator=nsls_ii,
                                    mono=mono1,
                                    sdd = xs,
                                    pe1 = pe1, # xs or None # put back to get xs back or opt out!
                                    shutters_dict=shutters_dictionary,
                                    det_dict=detector_dictionary,
                                    motors_dict=motors_dictionary,
                                    general_scan_func=general_scan,
                                    sample_stage = sample_stage1,
                                    wps = wps,
                                    mfc = mfc,
                                    window_title="XLive@QAS/7-BM NSLS-II",
                                   )

sys.stdout = xlive_gui.emitstream_out

def xlive():
    xlive_gui.show()



xlive()
