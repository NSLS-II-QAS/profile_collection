def general_scan_plan(detectors, motor, rel_start, rel_stop, num):
    plan = bp.relative_scan(detectors, motor, rel_start, rel_stop, num)

    if detectors[0].name == 'xs' or detectors[0].name == "pilatus":
        plan = plan
    elif hasattr(detectors[0], 'kickoff'):
        plan = bpp.fly_during_wrapper(plan, detectors)

    yield from plan


def general_scan(detectors, motor, rel_start, rel_stop, num, **kwargs):
    sys.stdout = kwargs.pop('stdout', sys.stdout)
    #print(f'Dets {detectors}')
    #print(f'Motors {motor}')
    print('[General Scan] Starting scan...')
    uid = yield from (general_scan_plan(detectors, motor, rel_start, rel_stop, int(num)))
    print('[General Scan] Done!')
    return uid