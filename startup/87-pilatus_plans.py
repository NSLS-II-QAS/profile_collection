from xas.file_io import validate_file_exists
import time as ttime
from datetime import datetime
from ophyd.status import SubscriptionStatus



flyer_apb_trigger_pil900k = FlyerAPBwithTrigger(det=apb_stream, pbs=[pb1.enc1], motor=mono1, trigger=apb_trigger_pil900k)


class FlyerPilatus(FlyerAPBwithTrigger):

    def __init__(self, det, pbs, motor, trigger, pilatus_det):
        super().__init__( det, pbs, motor, trigger)
        self.pilatus_det = pilatus_det

    def kickoff(self, traj_duration=None):
        traj_duration = get_traj_duration()
        self.pilatus_det.prepare_to_fly(traj_duration)

        #print_to_gui(f'{self.pilatus_det.name} staging starting', add_timestamp=True, tag='Flyer')
        self.pilatus_det.stage()
        self.pilatus_det.cam.trigger_mode.put('Ext. Enable')
        self.pilatus_det.cam.acquire.put(1)
        st_super = super().kickoff(traj_duration=traj_duration)
        return st_super

    def complete(self):
        st_super = super().complete()
        def callback_pilatus(value, old_value, **kwargs):
            if not isinstance(old_value, (int, str)):
                return False
            print(f'Callback value: {str(old_value)}')
            if int(old_value) == 1 and int(value) == 0:
                self.pilatus_det.complete()
                return True
            else:
                return False

        saving_st = SubscriptionStatus(self.pilatus_det.hdf5.capture, callback_pilatus)
        return st_super & saving_st

    def describe_collect(self):
        dict_super = super().describe_collect()
        dict_pilatus = self.pilatus_det.describe_collect()
        return {**dict_super, **dict_pilatus}

    def collect_asset_docs(self):
        yield from super().collect_asset_docs()
        yield from self.pilatus_det.collect_asset_docs()

    def collect(self):
        self.pilatus_det.unstage()
        yield from super().collect()
        yield from self.pilatus_det.collect()


flyer_pilatus = FlyerPilatus(det=apb_stream, pbs=[pb1.enc1], motor=mono1, trigger=apb_trigger_pil900k, pilatus_det=pilatus_stream)


def execute_trajectory_apb_trigger(name, **metadata):
    md = get_md_for_scan(name,
                         'fly_scan',
                         'execute_trajectory_apb_trigger',
                         'fly_energy_scan_apb_trigger',
                         **metadata)
    yield from bp.fly([flyer_apb_trigger], md=md)


def execute_trajectory_pilatus(name, **metadata):
    md = get_md_for_scan(name,
                         'fly_scan',
                         'execute_trajectory_pilatus',
                         'fly_energy_scan_pilatus3',
                         detector=apb,
                         hutch='b',
                         **metadata)
    md['aux_detector'] = 'pilatus900k'
    yield from bp.fly([flyer_pilatus], md=md)


# See 83-pilatus-callbacks.py for the 'count_pilatus_qas' plan.
# def count_pilatus(sample_name, exposure_time=1, number_of_images=1, delays=0):

#     """
#     Diffraction count plan averaging subframe_count exposures for each frame.

#     Open the specified shutter before bp.count()'ing, close it when the plan ends.

#     Parameters
#     ----------
#     detectors: list
#         list of devices to be bp.count()'d, should include pe1
#     shutter: Device (but a shutter)
#         the shutter to close for background exposures
#     sample_name: str
#         added to the start document with key "sample_name"
#     frame_count: int
#         passed to bp.count(..., num=frame_count)
#     subframe_time: float
#         exposure time for each subframe, total exposure time will be subframe_time*subframe_count
#     subframe_count: int
#         number of exposures to average for each frame

#     Returns
#     -------
#     run start id
#     """

#     yield from bps.mv(shutter, 'Open')
#     yield from bps.mv(pilatus.cam.acquire_time, exposure_time)
#     yield from bps.mv(pilatus.cam.acquire_period, exposure_time + 0.1)

#     yield from bp.count([pilatus], md = {'experiment' : 'diffraction',
#                                          'sample_name' : sample_name,
#                                          'exposure_time' : exposure_time})
