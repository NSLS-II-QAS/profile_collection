print(__file__)
print("Loading isstools, preparing GUI...")

from IPython import get_ipython
from PyQt5.QtWidgets import QApplication
import functools
import isstools.xlive
import collections
import atexit

import PyQt5


from ophyd.sim import motor
motor.move = motor.set

## MEMORY LEAK MONITORING
# 03/10/2026 - Kbarry

# import os
# import tracemalloc
# import linecache
# import threading
# import time
# import sys
# 
# def display_top(snapshot, key_type='lineno', limit=10):
#     snapshot = snapshot.filter_traces((
#         tracemalloc.Filter(False, "<frozen importlib._bootstrap>"),
#         tracemalloc.Filter(False, "<unknown>"),
#     ))
#     top_stats = snapshot.statistics(key_type)
# 
#     print("Top %s lines" % limit)
#     for index, stat in enumerate(top_stats[:limit], 1):
#         frame = stat.traceback[0]
#         print("#%s: %s:%s: %.1f KiB"
#               % (index, frame.filename, frame.lineno, stat.size / 1024))
#         line = linecache.getline(frame.filename, frame.lineno).strip()
#         if line:
#             print('    %s' % line)
# 
#     other = top_stats[limit:]
#     if other:
#         size = sum(stat.size for stat in other)
#         print("%s other: %.1f KiB" % (len(other), size / 1024))
#     total = sum(stat.size for stat in top_stats)
#     print("Total allocated size: %.1f KiB" % (total / 1024))
# 
# tracemalloc.start()


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
                                                                     'xs_channel2_rois_roi01_value',
                                                                     'xs_channel3_rois_roi01_value',
                                                                     'xs_channel4_rois_roi01_value',
                                                                     'xs_channel6_rois_roi01_value',
                                                                     'xs_channel6_rois_roi04_value']},
                    'pilatus': {'device': pilatus, 'channels': ['pilatus_stats1_total']},
                    'xspress3x Hutch B' : {'device': xsx, 'channels': [f'xsx_channel{ch+1:02d}_mcaroi01_total_rbv' for ch in range(8)]}
                                                                       # 'xsx_channel3_rois_roi01_value',
                                                                       # 'xsx_channel4_rois_roi01_value',
                                                                       # 'xsx_channel5_rois_roi01_value',
                                                                       # 'xsx_channel6_rois_roi01_value',
                                                                       # 'xsx_channel7_rois_roi01_value',
                                                                       # 'xsx_channel8_rois_roi01_value',
                                                                       # 'xsx_channel6_rois_roi04_value']}


}



motors_dictionary = {jj_slits_hutchB.xctr.name: {'name': jj_slits_hutchB.xctr.name, 'description':'B hutch_inc_slits_xcenter',     'object': jj_slits_hutchB.xctr, 'keyword': 'B hutch ins xcenter',     'user_motor': False},
                     jj_slits_hutchC.xctr.name: {'name': jj_slits_hutchC.xctr.name, 'description':'C hutch_inc_slits_xcenter',     'object': jj_slits_hutchC.xctr, 'keyword': 'C hutch ins xcenter',     'user_motor': False},
                     jj_slits_hutchB.xgap.name : {'name': jj_slits_hutchC.xgap.name, 'description':'B hutch_inc_slits_xgap',       'object': jj_slits_hutchB.xgap, 'keyword': 'C hutch ins xgap',        'user_motor': False},
                     drifts.drifts_x.name:      {'name': drifts.drifts_x.name,      'description':'C hutch_DRIFTS_horiz',          'object': drifts.drifts_x,      'keyword': 'C hutch DRIFTS horiz',    'user_motor': False},
                     drifts.drifts_z.name:      {'name': drifts.drifts_z.name,      'description':'C hutch_DRIFTS_z',              'object': drifts.drifts_z,      'keyword': 'C hutch DRIFTS z',        'user_motor': False},
                     beamstop.horizontal.name:  {'name': beamstop.horizontal.name,  'description': 'B hutch_beamstop_horiz',       'object':beamstop.horizontal,   'keyword': 'B hutch BS horiz',        'user_motor': False},
                     beamstop.vertical.name:    {'name': beamstop.vertical.name,    'description': 'B hutch_beamstop_vertical',    'object': beamstop.vertical,    'keyword': 'B hutchB BS vertical',    'user_motor': False},
                     ibp_hutchB.name:           {'name': ibp_hutchB.name,           'description': 'B hutch_inc_beam_path',        'object': ibp_hutchB,           'keyword': 'B hutch inc beam path',   'user_motor': False},
                     ibp_hutchC.name:           {'name': ibp_hutchC.name,           'description': 'C hutch_inc_beam_path',        'object': ibp_hutchC,           'keyword': 'C hutch inc beam path',   'user_motor': False},
                     sample_stage1.x.name:      {'name': sample_stage1.x.name,      'description':'B hutch_sample_stage_x',        'object':sample_stage1.x,       'keyword': 'B hutch sample x',        'user_motor': True},
                     sample_stage1.y.name:      {'name': sample_stage1.y.name,      'description':'B hutch_sample_stage_y',        'object':sample_stage1.y,       'keyword': 'B hutch sample y',        'user_motor': True},
                     sample_stage1.z.name:      {'name': sample_stage1.z.name,      'description':'B hutch_sample_stage_z',        'object':sample_stage1.z,       'keyword': 'B hutch sample z',        'user_motor': True},
                     sample_stage1.rotary.name: {'name': sample_stage1.rotary.name, 'description':'B hutch_sample_stage_rotation', 'object':sample_stage1.rotary,  'keyword': 'B hutch sample rotation', 'user_motor': True},
                     sample_stage1.theta.name:  {'name': sample_stage1.theta.name,  'description':'B hutch_sample_stage_theta',    'object':sample_stage1.theta,   'keyword': 'B hutch sample theta',    'user_motor': False},
                     sample_stage1.chi.name:    {'name': sample_stage1.chi.name,    'description':'B hutch_sample_stage_chi',      'object':sample_stage1.chi,     'keyword': 'B hutch sample chi',      'user_motor': False},
                     mono1.energy.name :        {'name' :mono1.energy.name,         'description': 'Mono Energy',                  'object': mono1.energy,         'keyword': 'Monochromator Energy',    'user_motor': False},
                     pilatus_motion.x.name :    {'name': pilatus_motion.x.name,     'description': 'Pilatus X motion',              'object': pilatus_motion.x,    'keyword': 'Pilatus X motion',        'user_motor': False},
                     pilatus_motion.y.name :    {'name': pilatus_motion.y.name,     'description': 'Pilatus Y motion',              'object': pilatus_motion.y,    'keyword': 'Pilatus Y motion',        'user_motor': False},
                     hutchC_ic_motor.y.name :    {'name': hutchC_ic_motor.y.name,     'description': 'C Hutch IonChamber Y motion',  'object': hutchC_ic_motor.y,    'keyword': 'C hutch ICY motion',        'user_motor': False},
                     #exp_table_c.vert_up_in.name:{'name': exp_table_c.vert_up_in.name,     'description': 'C Hutch exp_table_vert_up_in',  'object': exp_table_c.vert_up_in,    'keyword': 'C Hutch table_vert_up_in',      'user_motor': False},
                    }

# ion_chambers = ['i0', 'it', 'ir']
# voltage_destination = ['plate', 'grid']
#
# wps_dictionary = {}
# for ic in ion_chambers:
#     for vd in voltage_destination:
#         string = f"{ic}_{vd}_sp"
#         wps_dictionary[getattr(wps, string).name] = {'name': getattr(wps, string).name, 'description': f"WPS {ic} {vd} voltage", 'object': getattr(wps, string), 'Keyword': f"Voltage {ic} {vd}", 'user_motor': False}


# motors_dictionary = {**motors_dictionary, **wps_dictionary}

shutters_dictionary = {
                       shutter_fe.name: shutter_fe,
                       shutter_ph.name: shutter_ph,
                       shutter_fs.name: shutter_fs,
                       }

service_plan_funcs = {
    'get_offsets': get_offsets,
    'xs_count': xs_count,
    'xsx_count': xsx_count,
    'set Reference foil': set_reference_foil,
    'sleep': sleep_plan,
    'move_energy': move_energy,
    'set_lakeshore': set_lakeshore_temp,
    'set_linkam': set_linkam_temp,
    'set_gains': set_gains
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
    'XAS fly scan w/XSX': fly_scan_with_xs3x,
    'XRD take pattern': count_qas,
    'XRD take pattern w/Pilatus':count_pilatus_qas,
    'XAS controlled loop scan' : fly_scan_with_apb_with_controlled_loop,
    'XAS hardware trigger scan' : fly_scan_with_hardware_trigger,
    'XAS constant exposure': constant_exposure,
}

for shutter in shutters_dictionary.values():
    shutter.status.wait_for_connection()

# raise RuntimeError()

ipython = get_ipython()
if ipython is not None:
    ipython.run_line_magic('gui', 'qt')

app = QApplication.instance()

if not app:
    app = QApplication(sys.argv)

#newApp = PyQt5.QtWidgets.QApplication(sys.argv)
print("Authenticating XliveGUI Tiled Client:")
xlive_tiled_client = from_uri("https://tiled.nsls2.bnl.gov", username=None, remember_me=False)
xlive_gui = isstools.xlive.XliveGui(plan_funcs=plan_funcs,
                                    diff_plans=[count_qas, dark_frame_preprocessor, count_pilatus_qas, count_pilatus_qas_dafs],
                                    aux_plan_funcs =aux_plan_funcs,
                                    service_plan_funcs=service_plan_funcs,
                                    prep_traj_plan= prep_traj_plan,
                                    RE=RE,
                                    db=db,
                                    apb = apb,
                                    apb_c = apb_c ,
                                    accelerator=nsls_ii,
                                    mono=mono1,
                                    sdd = xs,
                                    xspress3x=xsx,
                                    pe1 = pilatus, # xs or None # put back to get xs back or opt out!
                                    shutters_dict=shutters_dictionary,
                                    det_dict=detector_dictionary,
                                    motors_dict=motors_dictionary,
                                    general_scan_func=general_scan,
                                    sample_stage = sample_stage1,
                                    wps = wps,
                                    mfc = mfc,
                                    window_title="XLive@QAS/7-BM NSLS-II",
                                    tiled_client=xlive_tiled_client
                                   )

sys.stdout = xlive_gui.emitstream_out


def xlive():
    xlive_gui.show()


xlive()

# def _tracemalloc_reporter(interval=60):
#     try:
#         while True:
#             time.sleep(interval)
#             snapshot = tracemalloc.take_snapshot()
#             print("\nTracemalloc periodic report:")
#             display_top(snapshot)
#     except Exception as _:
#         pass
# 
# _tracemalloc_thread = threading.Thread(target=_tracemalloc_reporter, args=(60,), daemon=True)
# _tracemalloc_thread.start()
