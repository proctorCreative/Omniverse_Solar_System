# Omniverse Solar System

A GPU-accelerated scientific orrery for NVIDIA Omniverse Kit.

Omniverse Solar System visualizes the Sun and nine primary bodies, including Pluto, using NASA/JPL SPICE DE440 ephemerides, together with large populations of asteroids from the International Astronomical Union Minor Planet Center catalog.

Planetary positions are evaluated from SPICE ephemerides, while asteroid orbits are propagated on the GPU using NVIDIA Warp and rendered through Fabric/USDRT as a deformable mesh.

The project is an independent scientific visualization, portfolio, and learning project. It is not an official publication or product of NASA/JPL, the Minor Planet Center, or NVIDIA.

## Project Goals

The project explores how NVIDIA Omniverse can be used for interactive scientific visualization involving very different scales and computational workloads.

The primary goals include:

* Visualizing authoritative planetary ephemeris data in an interactive 3D environment
* Displaying large populations of minor planets
* Exploring GPU-based orbital propagation with NVIDIA Warp
* Exploring Fabric/USDRT for high-performance visualization
* Working with astronomical coordinate systems and large differences in physical scale
* Building interactive time controls for scientific data exploration
* Developing a custom scientific application with NVIDIA Omniverse Kit
* Exploring AI-assisted development for a technically complex visualization project

This is a scientific orrery and exploratory visualization rather than a precision mission-analysis or N-body dynamics application.

## Features

* NASA/JPL SPICE DE440 planetary ephemerides
* Pluto included as the ninth primary displayed body
* Minor Planet Center asteroid orbital data
* GPU asteroid propagation with NVIDIA Warp
* Fabric/USDRT deformable-mesh rendering
* Interactive animation of hundreds of thousands of asteroids
* Full-catalog display controls
* J2000 planetary orbit guides
* NASA/SVS 16K star-map background
* Collision-aware planet labels
* Adjustable planet and asteroid marker sizes
* Forward and reverse time controls
* Persistent Sun-centered oblique camera
* Optional diagnostic status readout
* Adjustable celestial-background exposure

## Architecture

At a high level, the application combines two different approaches to orbital position calculation:

```text
NASA/JPL SPICE DE440
        |
        v
Planetary positions
        |
        +--------------------+
                             |
Minor Planet Center          |
orbital elements             |
        |                    |
        v                    |
Two-body orbital model       |
        |                    |
        v                    |
NVIDIA Warp GPU              |
asteroid propagation         |
        |                    |
        +---------+----------+
                  |
                  v
          Omniverse Kit
                  |
        +---------+---------+
        |         |         |
        v         v         v
     Planets   Asteroids   Orbits
        |         |         |
        +---------+---------+
                  |
                  v
          Fabric / USDRT
                  |
                  v
           Hydra / RTX Viewport
```

This separation is important scientifically.

Planetary positions are obtained from the DE440 ephemeris through SPICE. Asteroid positions are calculated independently from Minor Planet Center osculating orbital elements using the project's two-body propagation model.

The two systems therefore do not have the same accuracy characteristics.

## Coordinate System

Displayed positions use heliocentric equatorial J2000/ICRF coordinates measured in astronomical units (AU).

The visualization uses:

```text
+X = vernal equinox / RA 0h
+Y = RA 6h
+Z = north celestial pole
```

The Sun is located at the origin of the visualization.

Using a consistent astronomical reference frame allows planetary positions, asteroid positions, orbit guides, and the celestial background to share a common spatial convention.

## Planetary Ephemerides

Planet positions are calculated using NASA/JPL SPICE and the DE440 planetary ephemeris.

The application currently expects:

```text
spice/de440.bsp
spice/naif0012.tls
```

`de440.bsp` provides the planetary ephemeris.

`naif0012.tls` provides leap-second and time-system information required by SPICE.

Planetary positions are evaluated for the selected simulation time and converted into the coordinate and scale conventions used by the Omniverse visualization.

## Asteroid Data

Asteroid orbital elements come from the International Astronomical Union Minor Planet Center.

The application currently expects:

```text
mpc/mpcorb_extended.json
```

Rather than requesting individual asteroid ephemerides from an external service, the application propagates the catalog's osculating orbital elements locally.

The current implementation uses a two-body elliptical orbital model.

This makes it practical to animate very large asteroid populations interactively, but it also establishes an important accuracy boundary: these calculated positions should not be treated as replacements for high-precision ephemerides or N-body calculations.

## GPU Asteroid Propagation

Large asteroid populations are propagated using NVIDIA Warp.

The GPU implementation allows orbital calculations for large numbers of objects to be performed in parallel.

The resulting asteroid positions are presented to the Omniverse rendering pipeline through Fabric/USDRT using a deformable-mesh representation.

Conceptually:

```text
MPC orbital elements
        |
        v
GPU-resident orbital state
        |
        v
NVIDIA Warp kernels
        |
        v
GPU-resident positions
        |
        v
Fabric / USDRT
        |
        v
Deformable mesh
        |
        v
Viewport
```

This architecture was developed to reduce unnecessary CPU-side scene updates and explore a more GPU-oriented visualization pipeline for large astronomical datasets.

## Celestial Background

The star background uses the NASA Scientific Visualization Studio's **Deep Star Maps 2020**.

The application expects:

```text
backgrounds/starmap_2020_16k.exr
```

The map is a 16384 × 8192 celestial-coordinate image derived from astronomical catalogs including Gaia DR2.

The star map provides visual context for the J2000 astronomical coordinate frame.

The source star-map file is not redistributed in this repository.

## Data Layout

Large external astronomical datasets are intentionally not included in the repository.

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

The application can discover a sibling `solar-system-data` directory.

Alternatively, create a `RawData` symbolic link inside the project:

```bash
ln -s /path/to/solar-system-data RawData
```

Explicit data paths can also be configured using environment variables.

See `DATA.md` for source information, attribution, and additional data notes.

## Installation

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

Install `spiceypy` into the project-local Kit dependency directory using the Python environment supplied with the Kit SDK:

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

## NVIDIA Omniverse Kit

This project requires an appropriate NVIDIA Omniverse Kit development environment.

Kit SDK **110.1.3 or newer in the PB 26h1 line** is recommended for the zero-copy deformable-mesh path used and tested during development.

NVIDIA Omniverse, Kit, Warp, Fabric/USDRT, and other NVIDIA-provided software components are external dependencies and remain governed by their applicable NVIDIA terms.

The MIT license for this repository does not relicense NVIDIA software or other third-party components.

## Launch

Set `KIT_ROOT` to the NVIDIA Omniverse Kit SDK installation:

```bash
KIT_ROOT=/path/to/kit-sdk \
  ./launch.sh
```

To capture console output:

```bash
KIT_ROOT=/path/to/kit-sdk \
  ./launch.sh 2>&1 | tee omniverse-solar-system.log
```

## Controls

The application provides interactive controls for exploring the visualization.

* **Asteroids** selects the displayed asteroid population.
* **During playback** selects the population actively animated during time playback.
* **Speed** controls the simulation time rate.
* **Reverse**, **Play / Pause**, **Forward**, and **Now** control simulation time.
* **Planet dots** adjusts planet marker size.
* **Asteroid dots** adjusts asteroid marker size.
* **Planet labels** enables collision-aware labels.
* **Viewport grid** toggles the viewport grid.
* **Status readout** shows or hides diagnostic information.
* **Star background** enables the NASA/SVS celestial background.
* **Exposure** adjusts background brightness.

The camera begins in a Sun-centered oblique view. Manual camera zoom and orbit are preserved while other visualization controls change.

## Environment Overrides

The application recognizes the following environment variables:

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

## Scientific Accuracy Boundary

The application deliberately combines authoritative ephemeris data with an approximate high-throughput asteroid propagation model.

### Planets

Planetary positions are evaluated from NASA/JPL DE440 through SPICE.

### Asteroids

Asteroids are independently propagated from Minor Planet Center osculating orbital elements using a two-body elliptical model.

This approach is useful for a positional orrery, visualization of large-scale solar-system structure, and interactive exploration through time.

It is **not** a replacement for:

* JPL Horizons
* N-body orbital integration
* Close-approach calculations
* Spacecraft navigation
* Mission analysis
* Precision astrometry

For applications requiring authoritative or high-precision positions, use the appropriate source system for that task.

## External Data and Software

This project uses data or software from:

* NASA/JPL SPICE and DE440
* International Astronomical Union Minor Planet Center
* NASA Goddard Scientific Visualization Studio
* ESA/Gaia/DPAC and other source catalogs represented in the star map
* NVIDIA Omniverse
* NVIDIA Kit
* NVIDIA Warp
* Fabric/USDRT
* Python open-source packages listed in `requirements.txt`

Large external astronomical datasets are not redistributed by this repository.

See [`DATA.md`](DATA.md) for detailed provenance and attribution information.

## Development Approach

This project was developed as an independent scientific visualization, portfolio, and learning project.

I directed the project goals, visualization design, astronomical requirements, coordinate conventions, interaction design, testing, evaluation of results, performance goals, and technical direction.

ChatGPT and Codex were used extensively as implementation collaborators for software development.

Their use included assistance with:

* Python implementation
* NVIDIA Omniverse API exploration
* NVIDIA Warp implementation
* Fabric/USDRT experimentation
* SPICE integration
* Orbital-model implementation
* Debugging
* Performance investigation
* Refactoring
* Testing
* Documentation
* Evaluation of alternative technical approaches

I reviewed and tested the resulting system throughout development and used the project to build a practical understanding of the technologies and architectural choices involved.

The project should therefore be understood both as a scientific visualization project and as an exploration of AI-assisted technical development.

## License

Original project source code is released under the MIT License unless otherwise noted.

The MIT license applies to project-specific material for which the project author has the right to grant that license. It does not relicense NVIDIA software, astronomical datasets, or other third-party material.

External datasets are not redistributed by this repository and remain subject to their respective providers' terms and attribution requirements.

See [`LICENSE`](LICENSE) for the software license and [`DATA.md`](DATA.md) for data provenance and third-party acknowledgments.

## Status

Active prototype / portfolio project.

The current implementation demonstrates an interactive GPU-accelerated scientific orrery and provides a platform for continued exploration of Omniverse, OpenUSD, GPU scientific visualization, astronomical data integration, and large-scale solar-system visualization.
