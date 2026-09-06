# Data Sources and Acknowledgments

Omniverse Solar System does not redistribute the large external astronomical
datasets used by the application. Users obtain those files from their original
providers and place them in the local `solar-system-data/` directory described
in the README.

## Minor Planet Center (MPC)

Asteroid orbital elements are provided by the International Astronomical Union's
Minor Planet Center (MPC).

MPC documentation states that data from its database are freely available to
the public and asks users to acknowledge the funding that supports MPC
operations and data services.

Suggested acknowledgment:

> Asteroid orbital data are provided by the International Astronomical Union's
> Minor Planet Center. MPC operations and data services are supported by NASA's
> Planetary Defense Coordination Office through grant 80NSSC22M0024,
> administered via a University of Maryland-Smithsonian Astrophysical
> Observatory subaward.

MPC also notes that some computing equipment is supported in part by the Tamkin
Foundation.

MPC documentation:
https://docs.minorplanetcenter.net/mpc-ops-docs/faqs/

This project currently expects the asteroid catalog file:

```text
mpc/mpcorb_extended.json
```

The application propagates MPC osculating orbital elements independently using
a two-body elliptical model. It does not reproduce MPC ephemerides or perform an
N-body close-approach solution.

## NASA/JPL SPICE

Planet positions are computed using NASA/JPL SPICE data and the SPICE Toolkit
provided by NASA's Navigation and Ancillary Information Facility (NAIF).

This project currently expects:

```text
spice/de440.bsp
spice/naif0012.tls
```

`de440.bsp` supplies the planetary ephemeris used by the application.
`naif0012.tls` supplies leap-second/time-system information required by SPICE.

NAIF encourages acknowledgment of SPICE/NAIF resources and the teams that
provide the kernels used in a project.

NAIF credit and reference guidance:
https://naif.jpl.nasa.gov/naif/credit.html

SPICE usage rules:
https://naif.jpl.nasa.gov/naif/rules.html

## NASA Scientific Visualization Studio

The star background uses:

```text
backgrounds/starmap_2020_16k.exr
```

from NASA Goddard Space Flight Center's Scientific Visualization Studio:

**Deep Star Maps 2020**  
Visualization by Ernie Wright  
NASA Scientific Visualization Studio, ID 4851  
Released September 9, 2020

Source:
https://svs.gsfc.nasa.gov/4851/

The 16K celestial-coordinate EXR is 16384 x 8192 pixels. The source map is
centered at right ascension 0h, with right ascension increasing to the left.

NASA SVS states that the map was produced from approximately 1.7 billion stars
using data from Hipparcos-2, Tycho-2, Gaia Data Release 2, and supporting star
catalogs.

The star-map file is not redistributed in this repository.

## NVIDIA Omniverse and Warp

The application is built for NVIDIA Omniverse Kit and uses NVIDIA Warp for
GPU-accelerated asteroid propagation.

Omniverse:
https://developer.nvidia.com/omniverse

Warp:
https://github.com/NVIDIA/warp

The project also uses Fabric/USDRT and the Omniverse Hydra rendering pipeline
for the GPU asteroid visualization path.

## Third-party Python packages

See `requirements.txt` and the package metadata for the licenses and terms of
Python dependencies used by the standalone tools and tests.

`spiceypy` is installed locally for the Kit environment by:

```bash
./scripts/install_kit_dependencies.sh
```

The generated `vendor/` directory is intentionally excluded from Git.

## Accuracy note

The different data sources are not all propagated in the same way.

- Planets are evaluated from the DE440 SPICE ephemeris.
- Asteroids are propagated from MPC osculating elements using the project's
  two-body orbital model.
- The star map is a static J2000 celestial background.

The visualization is intended as a scientific orrery and exploratory
visualization. For precision ephemerides, close approaches, mission analysis,
or other high-accuracy work, use the authoritative source appropriate to the
task, such as JPL Horizons or a suitable N-body ephemeris system.
