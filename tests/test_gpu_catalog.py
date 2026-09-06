import numpy as np

from omniverse_solar_system.catalog import OrbitalCatalog
from omniverse_solar_system.frames import ecliptic_j2000_to_equatorial_j2000
from omniverse_solar_system.gpu_catalog import evaluate_packed_cpu, pack_gpu_asteroids
from omniverse_solar_system.propagation import propagate_catalog


def _catalog() -> OrbitalCatalog:
    arrays = {
        "a": np.array([1.0, 2.5, np.nan, 4.0]),
        "e": np.array([0.0, 0.2, 1.1, 0.5]),
        "inc": np.array([0.0, 0.1, 0.2, 0.4]),
        "node": np.array([0.0, 0.3, 0.4, 0.8]),
        "argp": np.array([0.0, 0.5, 0.6, 1.0]),
        "m0": np.array([0.0, 1.2, np.nan, 2.0]),
        "n": np.array([np.nan, 0.004, np.nan, 0.002]),
        "epoch": np.array([2451545.0, 2451545.0, np.nan, 2451545.0]),
        "tp": np.array([np.nan, np.nan, 2451545.0, np.nan]),
        "q": np.array([1.0, 2.0, 1.0, 2.0]),
        "h": np.array([8.0, 4.0, 2.0, 10.0], dtype=np.float32),
    }
    return OrbitalCatalog("asteroids", arrays, {"count": 4})


def test_gpu_packer_filters_non_elliptical_records_and_preserves_order():
    packed = pack_gpu_asteroids(_catalog(), np.array([2, 1, 3, 0]))
    assert packed.source_indices.tolist() == [1, 3, 0]
    assert packed.count == 3
    assert packed.semi_major_axis.dtype == np.float32
    assert packed.basis_p_j2000.shape == (3, 3)
    assert packed.basis_q_j2000.flags.c_contiguous


def test_gpu_reference_matches_scientific_cpu_propagator():
    catalog = _catalog()
    indices = np.array([1, 3, 0])
    packed = pack_gpu_asteroids(catalog, indices)
    jd = 2452545.25
    gpu_reference = evaluate_packed_cpu(packed, jd)
    ecliptic, finite = propagate_catalog(catalog, jd, indices=indices)
    assert finite.all()
    expected = ecliptic_j2000_to_equatorial_j2000(ecliptic).astype(np.float32)
    np.testing.assert_allclose(gpu_reference, expected, rtol=2.0e-5, atol=2.0e-5)


def test_packed_apoapsis_bounds_all_selected_orbits():
    packed = pack_gpu_asteroids(_catalog(), np.array([0, 1, 3]))
    expected = np.max(
        packed.semi_major_axis * (1.0 + packed.eccentricity)
    )
    assert np.isclose(packed.max_apoapsis_au, expected)


def test_circular_reference_stays_exactly_on_semimajor_axis():
    arrays = {
        "a": np.array([2.5]),
        "e": np.array([0.0]),
        "inc": np.array([0.0]),
        "node": np.array([0.0]),
        "argp": np.array([0.0]),
        "m0": np.array([0.0]),
        "n": np.array([0.004]),
        "epoch": np.array([2451545.0]),
        "tp": np.array([np.nan]),
        "q": np.array([2.5]),
        "h": np.array([8.0], dtype=np.float32),
    }
    packed = pack_gpu_asteroids(
        OrbitalCatalog("asteroids", arrays, {"count": 1}), np.array([0])
    )
    positions = evaluate_packed_cpu(packed, 2451545.0 + 1000.0)
    radius = np.linalg.norm(positions[0])
    assert np.isclose(radius, 2.5, rtol=1.0e-6, atol=1.0e-6)


def test_gpu_packer_preserves_named_element_values_without_vector_repacking():
    catalog = _catalog()
    packed = pack_gpu_asteroids(catalog, np.array([1]))
    assert packed.count == 1
    assert packed.semi_major_axis[0] == np.float32(catalog["a"][1])
    assert packed.eccentricity[0] == np.float32(catalog["e"][1])
    assert packed.mean_anomaly_epoch[0] == np.float32(catalog["m0"][1])
    assert packed.mean_motion[0] == np.float32(catalog["n"][1])
    assert packed.epoch_jd[0] == np.float32(catalog["epoch"][1])
