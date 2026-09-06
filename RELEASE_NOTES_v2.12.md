# Omniverse Solar System v2.12

## Control-panel readout

- Adds a **Status readout** checkbox.
- The detailed diagnostics are hidden by default.
- Status data continues to be collected while hidden, but no label repaint occurs.
- When shown during playback, the label is throttled to four repaints per second
  and held at a fixed height to prevent control-panel layout strobing.
- Fatal CUDA and playback errors bypass the throttle when the readout is visible.

## Camera interaction

- Removes the equatorial/ecliptic/oblique view dropdown.
- Uses one oblique, Sun-centered project camera.
- The camera transform is authored only once at startup, so changing unrelated
  controls no longer resets interactive zoom, orbit, or pan state.
- Authors the camera focus distance to the Sun to give the Kit camera manipulator
  a Sun-centered initial center of interest.

## Marker defaults

- Planet dots now default to **X-Large** (5 px).
- `OMNIVERSE_SOLAR_SYSTEM_PLANET_PIXELS` still overrides the default.

The generation-safe zero-copy Fabric asteroid renderer and corrected J2000 star
background are unchanged from v2.11.
