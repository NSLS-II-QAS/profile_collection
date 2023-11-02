import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp


def fly_scan_with_apb(name: str, comment: str, n_cycles: int = 1, delay: float = 0, hutch_c: bool = False, **kwargs):
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
    print(f'Hutch C is {hutch_c}')
    sys.stdout = kwargs.pop('stdout', sys.stdout)
    uids = []

    if hutch_c:
        _execute_trajectory = execute_trajectory_apb_c
        flyer = flyer_apb_c
    else:
        _execute_trajectory = execute_trajectory_apb
        flyer = flyer_apb

    def plan():
        for indx in range(int(n_cycles)):
            name_n = '{} {:04d}'.format(name, indx + 1)
            yield from prep_traj_plan()
            print(f'Trajectory preparation complete at {print_now()}')
            uid = (yield from _execute_trajectory(name_n, comment=comment))
            uids.append(uid)
            print(f'Trajectory is complete {print_now()}')
            yield from bps.sleep(float(delay))
        return uids

    def final_plan():
        yield from bps.mv(flyer.motor.stop_trajectory, "1")
        det_acquiring_status = (yield from bps.rd(flyer.det.acquiring))
        if det_acquiring_status == 1:  # acquiring
            yield from bps.stop(flyer)

    RE.md['experiment'] = ''
    return (yield from bpp.finalize_wrapper(plan(), final_plan))


def fly_scan_with_apb_trigger(name: str, comment: str, n_cycles: int = 1, delay: float = 0, autofoil :bool= False, **kwargs):
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
    if autofoil:
        current_element = getattr(mono1, f'traj{int(mono1.lut_number_rbv.get())}').elem.get()
        try:
            yield from set_reference_foil(current_element)
        except:
            pass

    for indx in range(int(n_cycles)):
        name_n = '{} {:04d}'.format(name, indx + 1)
        yield from prep_traj_plan()
        print(f'Trajectory preparation complete at {print_now()}')
        #yield from shutter_fs.open_plan()
        uid = (yield from execute_trajectory_apb_trigger(name_n, comment=comment))
        uids.append(uid)
        #yield from shutter_fs.close_plan()
        print(f'Trajectory is complete {print_now()}')
        yield from bps.sleep(float(delay))

    RE.md['experiment'] = ''
    return uids


def fly_scan_with_xs3(name: str, comment: str, n_cycles: int = 1, delay: float = 0, autofoil :bool= False, **kwargs):
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
    if autofoil:
    #if True:
        current_element = getattr(mono1, f'traj{int(mono1.lut_number_rbv.get())}').elem.get()
        try:
            yield from set_reference_foil(current_element)
        except:
            pass

    for indx in range(int(n_cycles)):
        name_n = '{} {:04d}'.format(name, indx + 1)
        yield from prep_traj_plan()
        print(f'Trajectory preparation complete at {print_now()}')
        #TODO add qas shutter
        #yield from shutter_fs.open_plan()
        uid = (yield from execute_trajectory_xs(name_n, comment=comment))
        uids.append(uid)
        #yield from shutter_fs.close_plan()
        print(f'Trajectory is complete {print_now()}')
        yield from bps.sleep(float(delay))

    RE.md['experiment'] = ''
    return uids


def fly_scan_with_pilatus(name: str, comment: str, n_cycles: int = 1, delay: float = 0, autofoil :bool= False, **kwargs):
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
    if autofoil:
    #if True:
        current_element = getattr(mono1, f'traj{int(mono1.lut_number_rbv.get())}').elem.get()
        try:
            yield from set_reference_foil(current_element)
        except:
            pass

    for indx in range(int(n_cycles)):
        name_n = '{} {:04d}'.format(name, indx + 1)
        yield from prep_traj_plan()
        print(f'Trajectory preparation complete at {print_now()}')
        #TODO add qas shutter
        #yield from shutter_fs.open_plan()
        uid = (yield from execute_trajectory_pilatus(name_n, comment=comment))
        uids.append(uid)
        #yield from shutter_fs.close_plan()
        print(f'Trajectory is complete {print_now()}')
        yield from bps.sleep(float(delay))

    RE.md['experiment'] = ''
    return uids