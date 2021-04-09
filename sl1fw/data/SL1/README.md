# Tilt profiles

- set of all tilt profiles
- values are stored in MC
- see `sl1fw/hardware/tilt.py` to get the names of profiles
- be aware of that `temp` profile is not stored in `*.tilt` file

## Structure of the file

```
[
    [starting_steprate, maximum_steprate, acceleration, deceleration, coil current, stallguard threshold,  coolstep threshold], # homingFast
    [...], # homingSlow
    [...], # moveFast
    [...], # moveSlow
    [...], # layerMoveSlow
    [...], # layerRelease
    [...], # layesMoveFast
    [...]  # reserved2
]
```

# Tune tilt profiles

- set of values for tilt movement while printing
- the movement is split on slow and fast by `limit for fast tilt` parameter
- values are stored in A64
-  tilt down procedure:
    1. set `initial profile` (the number of profile coresponds to TiltProfile(Enum))
    2. go number of `offset steps` [usteps]
    3. wait `offset delay` [ms]
    4. set `finish profile`
    5. split rest of the distence to X `tilt cycles`
    6. wait `tilt delay` between `tilt cycles`
    7. home (`homing cycles` defines number of retries)

## Structure of the file

```
[
    [initial profile, offset steps, offset delay, finish profile, tilt cycles, tilt delay, homing tolerance, homing cycles], # tilt down large fill (area > limit for fast tilt)
    [...], # tilt down small fill (area < limit for fast tilt)
    [...], # tilt up large fill (area > limit for fast tilt)
    [...]  # tilt up small fill (area < limit for fast tilt)
]
```

# Tower profiles

- set of all tower profiles
- values are stored in MC

## Structure of the file

```
[
    [starting_steprate, maximum_steprate, acceleration, deceleration, coil current,  stallguard threshold,  coolstep threshold], # homingFast
    [...], # homingSlow
    [...], # moveFast
    [...], # moveSlow
    [...], # layer
    [...], # layerMove
    [...], # reserved2
    [...]  # resinSensor
]
```
