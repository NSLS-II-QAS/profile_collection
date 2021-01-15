import inspect
import bluesky.plans as bp
import bluesky.plan_stubs as bps
from bluesky.plan_patterns import spiral_square_pattern
import os, sys
from bluesky.utils import FailedStatus





def fly_scan_with_apb(name: str, comment: str, n_cycles: int = 1, delay: float = 0, **kwargs):
    '''
    Trajectory Scan - Runs the monochromator along the trajectory that is previously loaded in the controller N times
    Parameters
    ----------
    name : str
        Name of the scan - it will be stored in the metadata
    n_cycles : int (default = 1)
        Number of times to run the scan automatically
    delay : float (default = 0)
        Delay in seconds between scans
    Returns
    -------
    uid : list(str)
        Lists containing the unique ids of the scans
    '''
    sys.stdout = kwargs.pop('stdout', sys.stdout)
    uids = []

    for indx in range(int(n_cycles)):
        name_n = '{} {:04d}'.format(name, indx + 1)
        yield from prep_traj_plan()
        print(f'Trajectory preparation complete at {print_now()}')
        uid = (yield from execute_trajectory_apb(name_n, comment=comment))
        uids.append(uid)
        print(f'Trajectory is complete {print_now()}')
        yield from bps.sleep(float(delay))
    return uids