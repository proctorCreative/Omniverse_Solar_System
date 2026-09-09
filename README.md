# Omniverse Solar System

A GPU-accelerated scientific orrery for NVIDIA Omniverse Kit.

Omniverse Solar System renders the Sun and nine primary planets, including Pluto,
using NASA/JPL SPICE DE440 ephemerides, along with large populations from the
Minor Planet Center asteroid catalog.

Asteroids are propagated on the GPU using NVIDIA Warp and rendered through
Fabric/USDRT as a zero-copy deformable mesh.

All displayed positions use heliocentric equatorial J2000/ICRF coordinates in AU:

- +Z = north celestial pole
- +X = vernal equinox / RA 0h
- +Y = RA 6h

## Credits and Data Sources

### This software depends on Omniverse and source code provided by NVIDIA Corporation.

Some sources are absent because they were based on NVIDIA-provided templates and the license forbids redistribution.

NVIDIA Omniverse/Kit and Warp are dependencies governed by their respective NVIDIA terms and are not licensed by the MIT license.

Planetary ephemerides:
NASA/JPL SPICE
https://ssd.jpl.nasa.gov/planets/orbits.html

Asteroid orbital data:
International Astronomical Union Minor Planet Center (MPC)
https://data.minorplanetcenter.net/data

Star background:
Deep Star Maps 2020
NASA Scientific Visualization Studio
https://svs.gsfc.nasa.gov/4851/

## Features

- SPICE DE440 planetary ephemerides
- Pluto included as the ninth primary planet
- MPC asteroid orbital data
- GPU asteroid propagation with NVIDIA Warp
- Fabric/USDRT deformable-mesh rendering
- Interactive animation of hundreds of thousands of asteroids
- Full-catalog display controls
- J2000 planetary orbit guides
- NASA/SVS 16K star-map background
- Collision-aware planet labels
- Adjustable planet and asteroid marker sizes
- Time controls with forward and reverse playback
- Persistent Sun-centered oblique camera
- Optional diagnostic status readout
- Adjustable background exposure

Kit SDK **110.1.3 or newer in the PB 26h1 line** is recommended for the
verified zero-copy deformable-mesh path.

## Data layout

Large astronomical datasets are not included in this repository.

Create a shared data directory with this structure:

```text
solar-system-data/
├── backgrounds/
│   └── starmap_2020_16k.exr
├── mpc/
│   └── mpcorb_extended.json
└── spice/
    ├── de440.bsp
    └── naif0012.tls
```

The application can discover a sibling `solar-system-data` directory, or you can
create a `RawData` symlink inside the project:

```bash
ln -s /path/to/solar-system-data RawData
```

You can also set explicit paths with environment variables.

## Install

Clone the repository:

```bash
git clone <repository-url>
cd Omniverse_Solar_System
```

Create a Python environment for the standalone tools and tests:

```bash
python3 -m venv .venv
source .venv/bin/activate

python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
```

Install `spiceypy` into the project-local Kit dependency directory:

```bash
KIT_PYTHON=/path/to/kit-sdk/python.sh \
  ./scripts/install_kit_dependencies.sh
```

Build the asteroid cache:

```bash
python3 scripts/build_cache.py
```

Run the standalone tests:

```bash
python3 -m pytest -q
```

## Launch

Set `KIT_ROOT` to your NVIDIA Omniverse Kit SDK installation:

```bash
KIT_ROOT=/path/to/kit-sdk \
  ./launch.sh
```

To capture the console output:

```bash
KIT_ROOT=/path/to/kit-sdk \
  ./launch.sh 2>&1 | tee omniverse-solar-system.log
```

## Controls

- **Asteroids** selects the displayed population.
- **During playback** selects the active animated population.
- **Speed** selects the simulation time rate.
- **Reverse**, **Play / Pause**, **Forward**, and **Now** control simulation time.
- **Planet dots** and **Asteroid dots** control marker size.
- **Planet labels** enables collision-aware labels.
- **Viewport grid** toggles the viewport grid.
- **Status readout** shows or hides detailed diagnostics.
- **Star background** enables the NASA/SVS star-map background.
- **Exposure** adjusts background brightness.

The camera remains in a single interactive oblique view centered initially on
the Sun. Manual zoom and orbit are preserved while other controls change.

## Environment overrides

```text
OMNIVERSE_SOLAR_SYSTEM_RAW_DATA
OMNIVERSE_SOLAR_SYSTEM_CACHE
OMNIVERSE_SOLAR_SYSTEM_DISPLAY_ASTEROIDS
OMNIVERSE_SOLAR_SYSTEM_ANIMATION_BUDGET
OMNIVERSE_SOLAR_SYSTEM_PLAYBACK_RATE
OMNIVERSE_SOLAR_SYSTEM_PLAYBACK_HZ
OMNIVERSE_SOLAR_SYSTEM_PLANET_LABELS
OMNIVERSE_SOLAR_SYSTEM_PLANET_PIXELS
OMNIVERSE_SOLAR_SYSTEM_ASTEROID_PIXELS
OMNIVERSE_SOLAR_SYSTEM_ORBIT_ALPHA
OMNIVERSE_SOLAR_SYSTEM_ORBIT_THICKNESS
OMNIVERSE_SOLAR_SYSTEM_STATUS_READOUT
OMNIVERSE_SOLAR_SYSTEM_STARMAP
OMNIVERSE_SOLAR_SYSTEM_STARMAP_ENABLED
OMNIVERSE_SOLAR_SYSTEM_STARMAP_EXPOSURE
```

## Accuracy boundary

Planet positions come from DE440 through SPICE.

Asteroids are independently propagated as two-body elliptical orbits from MPC
osculating elements. This is appropriate for a positional orrery and time
exploration, but it is not a replacement for JPL Horizons or an N-body
close-approach calculation.

## Data sources and acknowledgments

This project uses data and software from:

- NASA/JPL SPICE
- International Astronomical Union Minor Planet Center
- NASA Scientific Visualization Studio
- NVIDIA Omniverse
- NVIDIA Warp

See `DATA.md` for detailed attribution and data-source notes.

## License

Source code is released under the MIT License unless otherwise noted.

External datasets are not redistributed by this repository and remain subject
to their respective providers' terms and attribution requirements.
