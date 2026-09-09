# Data Sources and Acknowledgments

Omniverse Solar System combines astronomical data from several authoritative external sources with project-specific computation and visualization code.

Large external astronomical datasets are **not redistributed** by this repository. Users obtain those files from their original providers and place them in the local `solar-system-data/` directory described in the README.

This document records the primary data sources, their role in the visualization, and important distinctions between authoritative source data and positions calculated by this project.

## Data Overview

The visualization currently combines three primary astronomical data sources:

```text
NASA/JPL SPICE DE440
    -> planetary ephemerides

Minor Planet Center
    -> asteroid osculating orbital elements

NASA Scientific Visualization Studio
    -> static celestial background
```

These sources are used differently and should not be assumed to have equivalent accuracy or computational treatment.

Planetary positions are evaluated directly from the DE440 ephemeris through SPICE.

Asteroid positions are calculated by this project from Minor Planet Center osculating orbital elements using a two-body elliptical propagation model.

The celestial background is a static astronomical visualization aligned with the J2000 celestial reference frame used by the application.

## NASA/JPL SPICE and DE440

Planetary positions are computed using NASA/JPL SPICE data and the SPICE Toolkit maintained by NASA's Navigation and Ancillary Information Facility (NAIF).

The application currently expects:

```text
spice/de440.bsp
spice/naif0012.tls
```

### DE440

`de440.bsp` provides the planetary ephemeris used by the application.

The project evaluates planetary states from the SPICE kernel for the selected simulation time rather than independently propagating planetary orbital elements.

### Leap-Second Kernel

`naif0012.tls` supplies leap-second and time-system information required by SPICE.

### Attribution

NASA/JPL and NAIF provide documentation covering appropriate acknowledgment and use of SPICE resources.

NAIF credit and reference guidance:

https://naif.jpl.nasa.gov/naif/credit.html

SPICE usage rules:

https://naif.jpl.nasa.gov/naif/rules.html

NASA/JPL Solar System Dynamics:

https://ssd.jpl.nasa.gov/

The SPICE kernels are external data files and are not redistributed by this repository.

## International Astronomical Union Minor Planet Center

Asteroid orbital elements are obtained from the International Astronomical Union's Minor Planet Center (MPC).

The project currently expects:

```text
mpc/mpcorb_extended.json
```

This catalog supplies orbital elements used as input to the project's asteroid propagation system.

The application does **not** treat these elements as a precomputed asteroid ephemeris.

Instead, the project independently propagates the osculating elements using its own two-body elliptical orbital model.

Conceptually:

```text
MPC orbital elements
        |
        v
Project orbital model
        |
        v
NVIDIA Warp GPU propagation
        |
        v
Calculated asteroid positions
```

This distinction is important when interpreting the visualization.

The Minor Planet Center provides the source orbital elements, while the time-dependent asteroid positions displayed by the application are calculated by this project.

### MPC Acknowledgment

MPC documentation states that data from its database are freely available to the public and requests acknowledgment of the funding supporting MPC operations and data services.

Suggested acknowledgment:

> Asteroid orbital data are provided by the International Astronomical Union's Minor Planet Center. MPC operations and data services are supported by NASA's Planetary Defense Coordination Office through grant 80NSSC22M0024, administered via a University of Maryland-Smithsonian Astrophysical Observatory subaward.

MPC also notes that some computing equipment is supported in part by the Tamkin Foundation.

MPC documentation:

https://docs.minorplanetcenter.net/mpc-ops-docs/faqs/

The MPC catalog file is not redistributed by this repository.

## NASA Scientific Visualization Studio Deep Star Maps 2020

The celestial background uses:

```text
backgrounds/starmap_2020_16k.exr
```

from NASA Goddard Space Flight Center's Scientific Visualization Studio.

**Deep Star Maps 2020**
Visualization by Ernie Wright
NASA Goddard Space Flight Center
Scientific Visualization Studio
SVS ID 4851
Released September 9, 2020

Source:

https://svs.gsfc.nasa.gov/4851/

The 16K celestial-coordinate EXR is:

```text
16384 x 8192 pixels
```

The source map is centered at right ascension 0h, with right ascension increasing toward the left in the source image.

NASA SVS describes the visualization as being generated from approximately 1.7 billion stars using astronomical catalogs including:

* Gaia Data Release 2
* Hipparcos-2
* Tycho-2
* Additional supporting stellar catalogs

Gaia mission data are provided by ESA/Gaia/DPAC.

The star map is used as a static celestial reference background. It is not dynamically recomputed as simulation time changes.

The original star-map file is not redistributed by this repository.

## Coordinate Reference Frame

The application uses heliocentric equatorial J2000/ICRF coordinates for displayed solar-system positions.

The visualization convention is:

```text
+X = vernal equinox / RA 0h
+Y = RA 6h
+Z = north celestial pole
```

Distances are represented in astronomical units (AU).

The Sun is placed at the visualization origin.

Planetary positions, calculated asteroid positions, orbit guides, and the celestial background are organized around this common astronomical reference convention.

## NVIDIA Omniverse and Warp

NVIDIA Omniverse and NVIDIA Warp are software dependencies rather than astronomical data sources.

The application is built for NVIDIA Omniverse Kit and uses NVIDIA Warp for GPU-accelerated asteroid propagation.

NVIDIA Omniverse:

https://developer.nvidia.com/omniverse

NVIDIA Warp:

https://github.com/NVIDIA/warp

The project also uses Fabric/USDRT and the Omniverse Hydra rendering pipeline for the GPU asteroid visualization path.

NVIDIA software and components remain governed by their applicable NVIDIA license terms and are not relicensed by this repository's MIT license.

## SPICE Python Interface

The Python interface to SPICE is provided through `spiceypy`.

The project installs `spiceypy` locally for the Kit environment using:

```bash
./scripts/install_kit_dependencies.sh
```

The resulting generated dependency directory is intentionally excluded from Git.

`spiceypy` is an external open-source project and remains governed by its own license.

## Other Third-Party Python Packages

Additional Python dependencies used by the standalone tools, preprocessing workflow, and tests are listed in:

```text
requirements.txt
```

These packages are external software dependencies and remain subject to their respective licenses.

Generated dependency directories and local Python environments are intentionally excluded from the repository.

## Local Data Layout

The expected external data directory is:

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

These files should be obtained from their original providers.

The repository's `.gitignore` is configured to prevent the primary external astronomical datasets and generated dependency directories from being unintentionally committed.

## Scientific Accuracy Boundary

The different astronomical sources used by this project are not all evaluated in the same way.

### Planets

Planetary positions are evaluated from the NASA/JPL DE440 ephemeris through SPICE.

### Asteroids

Asteroid positions are calculated from Minor Planet Center osculating orbital elements using the project's two-body elliptical propagation model.

The model does not perform a full N-body integration and does not reproduce authoritative MPC or JPL ephemerides.

### Celestial Background

The NASA SVS star map is a static celestial background used to provide astronomical context for the visualization.

It is not a dynamic stellar-propagation system.

## Appropriate Use

The visualization is intended as a scientific orrery, exploratory visualization, and technical demonstration.

It is useful for:

* Exploring large-scale solar-system structure
* Visualizing planetary and asteroid populations
* Exploring motion through simulation time
* Demonstrating GPU scientific visualization techniques
* Studying the integration of astronomical data with NVIDIA Omniverse

It should **not** be used as the authoritative source for:

* Spacecraft navigation
* Mission-critical trajectory planning
* Precision astrometry
* N-body close-approach calculations
* Planetary-defense calculations
* Other applications requiring validated high-precision ephemerides

For precision work, use the authoritative data system appropriate to the task, such as NASA/JPL Horizons, SPICE with appropriate kernels and methodology, or a suitable N-body ephemeris system.

## Redistribution

The large astronomical datasets described in this document are not redistributed by this repository.

Users should obtain them from their original providers and comply with the applicable attribution, licensing, and usage requirements.

The project's MIT license applies only to original project material for which the project author has the right to grant that license. It does not relicense external astronomical data, NVIDIA software, or other third-party components.

See [`LICENSE`](LICENSE) for the project software license and [`README.md`](README.md) for installation and application information.
