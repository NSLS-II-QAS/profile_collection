print(__file__)
print("Loading isstools, preparing GUI...")

import functools
import isstools.xlive
import collections
import atexit

import PyQt5

from bluesky.examples import motor
motor.move = motor.set


detector_dictionary = {colmirror_diag.name: {'obj': colmirror_diag, 'elements': [colmirror_diag.stats1.total.name, colmirror_diag.stats2.total.name]},
                       screen_diag.name: {'obj': screen_diag, 'elements': [screen_diag.stats1.total.name, screen_diag.stats2.total.name]},
                       mono_diag.name: {'obj': mono_diag, 'elements': [mono_diag.stats1.total.name, mono_diag.stats2.total.name]},
                       dcr_diag.name: {'obj': dcr_diag, 'elements': [dcr_diag.stats1.total.name, dcr_diag.stats2.total.name]},
                       #pba1.adc1.name: {'obj': pba1.adc1, 'elements': ['pba1_adc1_volt']},
                       pba1.adc3.name: {'obj': pba1.adc3, 'elements': ['pba1_adc3_volt']},
                       pba1.adc4.name: {'obj': pba1.adc4, 'elements': ['pba1_adc4_volt']},
                       pba1.adc5.name: {'obj': pba1.adc5, 'elements': ['pba1_adc5_volt']},
                       pba1.adc6.name: {'obj': pba1.adc6, 'elements': ['pba1_adc6_volt']},
                       pba1.adc7.name: {'obj': pba1.adc7, 'elements': ['pba1_adc7_volt']},
                       pba1.adc8.name: {'obj': pba1.adc8, 'elements': ['pba1_adc8_volt']},
                       pb1.enc1.name: {'obj': pb1.enc1, 'elements': ['pb1_enc1_pos_I']},
                      }

motors_dictionary = {#jj_slits.top.name: {'name': jj_slits.top.name, 'description':jj_slits.top.name, 'object': jj_slits.top},
                    # jj_slits.bottom.name: {'name': jj_slits.bottom.name, 'description':jj_slits.bottom.name, 'object': jj_slits.bottom},
                    # jj_slits.outboard.name: {'name': jj_slits.outboard.name, 'description':jj_slits.outboard.name, 'object': jj_slits.outboard},
                    # jj_slits.inboard.name: {'name': jj_slits.inboard.name, 'description':jj_slits.inboard.name, 'object': jj_slits.inboard},
                     beamstop.horizontal.name: {'name': beamstop.horizontal.name, 'description': beamstop.horizontal.name, 'object':beamstop.horizontal},
                     beamstop.vertical.name: {'name': beamstop.vertical.name, 'description': beamstop.vertical.name, 'object': beamstop.vertical},
                     ip_y_stage.name: {'name': ip_y_stage.name, 'description': ip_y_stage.name, 'object': ip_y_stage},
                     sample_stage1.rotary.name: {'name': sample_stage1.rotary.name, 'description':sample_stage1.rotary.name, 'object':sample_stage1.rotary},
                     sample_stage1.x.name: {'name': sample_stage1.x.name, 'description':sample_stage1.x.name, 'object':sample_stage1.x},
                     sample_stage1.y.name: {'name': sample_stage1.y.name, 'description':sample_stage1.y.name, 'object':sample_stage1.y},
                     sample_stage1.z.name: {'name': sample_stage1.z.name, 'description':sample_stage1.z.name, 'object':sample_stage1.z},
                     sample_stage1.theta.name: {'name': sample_stage1.theta.name, 'description':sample_stage1.theta.name, 'object':sample_stage1.theta},
                     sample_stage1.chi.name: {'name': sample_stage1.chi.name, 'description':sample_stage1.chi.name, 'object':sample_stage1.chi}, 
                    }

shutters_dictionary = {
                       shutter_fe.name: shutter_fe,
                       shutter_ph.name: shutter_ph,
                       shutter_fs.name: shutter_fs,
                       }

sample_stages = [{'x': sample_stage1.x.name, 'y': sample_stage1.y.name}]

print(mono1)

newApp = PyQt5.QtWidgets.QApplication(sys.argv)

xlive_gui = isstools.xlive.XliveGui(plan_funcs=[tscan, tscan_xs3, get_offsets, xs_count],
                                    prep_traj_plan=prep_traj_plan,
                                    diff_plans=[pe_count], 
                                    RE=RE,
                                    db=db, 
                                    accelerator=nsls_ii,
                                    mono=mono1,
                                    sdd = xs,
                                    shutters_dict=shutters_dictionary,
                                    det_dict=detector_dictionary,
                                    aux_plan_funcs ={
                                        'set_reference_foil': set_reference_foil,
                                        'get_reference_foil': get_reference_foil,
                                    },
                                    motors_dict=motors_dictionary,
                                    general_scan_func=general_scan,
                                    sample_stages = sample_stages,
                                    window_title="XLive @QAS/7-BM NSLS-II",
                                   )

sys.stdout = xlive_gui.emitstream_out

def xlive():
    xlive_gui.show()

#sys.stdout = xlive_gui.emitstream_out
#sys.stderr = xlive_gui.emitstream_err

#from isstools.xview import XviewGui
#xview_gui = XviewGui(PB_PULSES_PER_DEGREE)

## jlynch 8/30
#import pyinstrument

#profiler = pyinstrument.Profiler()
#profiler.start()

#print('starting pyinstrument profiler')
## jlynch 8/30

xlive()
