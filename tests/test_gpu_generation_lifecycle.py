from pathlib import Path


def _gpu_source() -> str:
    root = Path(__file__).resolve().parents[1]
    return (
        root
        / "exts"
        / "ronproctor.omniverse_solar_system"
        / "ronproctor"
        / "omniverse_solar_system"
        / "gpu_asteroids.py"
    ).read_text()


def _extension_source() -> str:
    root = Path(__file__).resolve().parents[1]
    return (
        root
        / "exts"
        / "ronproctor.omniverse_solar_system"
        / "ronproctor"
        / "omniverse_solar_system"
        / "extension.py"
    ).read_text()


def test_gpu_mesh_uses_generation_specific_paths_and_marker_attributes():
    source = _gpu_source()
    assert 'GPU_ASTEROID_PATH_PREFIX = "/OmniverseSolarSystem/GPUAsteroids_G"' in source
    assert 'TARGET_ATTR_PREFIX = "solar:gpuAsteroidMeshTarget_g"' in source
    assert 'self.mesh_path_string = f"{GPU_ASTEROID_PATH_PREFIX}{suffix}"' in source
    assert 'self.target_attr = f"{TARGET_ATTR_PREFIX}{suffix}"' in source


def test_fabric_binding_waits_for_exact_vertex_capacity():
    source = _gpu_source()
    assert "observed == self.vertex_count" in source
    assert "self.bound_vertex_count = observed" in source
    assert "capacity mismatch" in source


def test_kernel_guards_resident_and_vertex_capacity():
    source = _gpu_source()
    assert "resident_count: wp.int32" in source
    assert "vertex_capacity: wp.int32" in source
    assert "if asteroid_id >= resident_count:" in source
    assert "if vertex_base < 0 or vertex_base + 2 >= vertex_capacity:" in source


def test_extension_uses_grow_only_generation_swap():
    source = _extension_source()
    assert "GPU meshes are grow-only" in source
    assert "desired <= self._gpu_resident_count" in source
    assert "next_generation = self._gpu_generation + 1" in source
    assert "Swap only after the new, uniquely tagged generation" in source
    assert "self._destroy_renderer_instance(old_renderer)" in source


def test_selected_display_count_controls_active_gpu_population():
    source = _extension_source()
    assert "displayed = min(self._display_asteroid_count(), self._gpu_resident_count)" in source
    assert "self._effective_animation_count(displayed)" in source


def test_cuda_fatal_error_requires_restart_instead_of_cpu_fallback():
    gpu_source = _gpu_source()
    extension_source = _extension_source()
    assert "class GpuRendererFatalError" in gpu_source
    assert "CUDA illegal-memory fault detected" in gpu_source
    assert "CUDA context invalid — close and restart Kit" in extension_source
