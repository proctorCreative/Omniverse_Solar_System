from pathlib import Path

from omniverse_solar_system.paths import resolve_cache_root, resolve_raw_data_root


def make_raw_data(path: Path) -> Path:
    raw = path / "RawData"
    (raw / "mpc").mkdir(parents=True)
    (raw / "spice").mkdir(parents=True)
    return raw


def test_direct_raw_data(tmp_path: Path) -> None:
    project = tmp_path / "Omniverse_Solar_System"
    project.mkdir()
    expected = make_raw_data(project)
    assert resolve_raw_data_root(project) == expected.resolve()


def test_versioned_sibling_layout(tmp_path: Path) -> None:
    expected = make_raw_data(tmp_path / "Omniverse_Solar_System")
    project = tmp_path / "Omniverse_Solar_System_v0.1" / "Omniverse_Solar_System"
    project.mkdir(parents=True)
    assert resolve_raw_data_root(project) == expected.resolve()


def test_explicit_project_or_raw_data(tmp_path: Path) -> None:
    data_project = tmp_path / "data-project"
    expected = make_raw_data(data_project)
    other_project = tmp_path / "code"
    other_project.mkdir()
    assert resolve_raw_data_root(other_project, data_project) == expected.resolve()
    assert resolve_raw_data_root(other_project, expected) == expected.resolve()


def test_cache_defaults_to_code_project(tmp_path: Path) -> None:
    project = tmp_path / "code"
    assert resolve_cache_root(project) == (project / "Cache").resolve()


def test_canonical_solar_system_data_sibling(tmp_path: Path) -> None:
    expected = tmp_path / "solar-system-data"
    (expected / "mpc").mkdir(parents=True)
    (expected / "spice").mkdir(parents=True)
    project = tmp_path / "Omniverse_Solar_System_v2.7" / "Omniverse_Solar_System"
    project.mkdir(parents=True)
    assert resolve_raw_data_root(project) == expected.resolve()


def test_starmap_resolves_from_canonical_raw_data(tmp_path: Path) -> None:
    from omniverse_solar_system.paths import resolve_starmap_path

    project = tmp_path / "Omniverse_Solar_System"
    project.mkdir()
    raw = tmp_path / "solar-system-data"
    expected = raw / "backgrounds" / "starmap_2020_16k.exr"
    expected.parent.mkdir(parents=True)
    expected.write_bytes(b"EXR")
    assert resolve_starmap_path(project, raw_data_root=raw) == expected.resolve()


def test_starmap_environment_override(tmp_path: Path, monkeypatch) -> None:
    from omniverse_solar_system.paths import STARMAP_ENV, resolve_starmap_path

    project = tmp_path / "Omniverse_Solar_System"
    project.mkdir()
    expected = tmp_path / "custom-stars.exr"
    expected.write_bytes(b"EXR")
    monkeypatch.setenv(STARMAP_ENV, str(expected))
    assert resolve_starmap_path(project) == expected.resolve()


def test_starmap_missing_reports_highest_priority_expected_path(
    tmp_path: Path, monkeypatch
) -> None:
    from omniverse_solar_system.paths import STARMAP_ENV, resolve_starmap_path

    project = tmp_path / "Omniverse_Solar_System"
    project.mkdir()
    expected = tmp_path / "missing.exr"
    monkeypatch.setenv(STARMAP_ENV, str(expected))
    assert resolve_starmap_path(project) == expected.resolve()
