from pathlib import Path


def test_status_readout_is_optional_hidden_and_throttled():
    root = Path(__file__).resolve().parents[1]
    source = (
        root
        / "exts"
        / "ronproctor.omniverse_solar_system"
        / "ronproctor"
        / "omniverse_solar_system"
        / "extension.py"
    ).read_text()
    assert '"OMNIVERSE_SOLAR_SYSTEM_STATUS_READOUT", "0"' in source
    assert "self.status_model = ui.SimpleBoolModel(self.status_readout_enabled)" in source
    assert 'ui.Label("Status readout"' in source
    assert "visible=self.status_readout_enabled" in source
    assert "def _on_status_changed" in source
    assert "minimum_interval = 0.25 if self.clock.is_playing else 0.0" in source
    assert "self._status_text = text" in source
    assert 'self._set_status_text("Updating solar-system positions…")' not in source
    assert "ui.Label(self.status_model" not in source
    assert "ui.SimpleStringModel" not in source


def test_extension_uses_independent_display_and_animation_dropdowns():
    root = Path(__file__).resolve().parents[1]
    source = (
        root
        / "exts"
        / "ronproctor.omniverse_solar_system"
        / "ronproctor"
        / "omniverse_solar_system"
        / "extension.py"
    ).read_text()
    assert "DISPLAY_ASTEROID_LIMITS" in source
    assert "DISPLAY_ASTEROID_LABELS" in source
    assert "ANIMATION_BUDGETS" in source
    assert "self.display_combo = ui.ComboBox(" in source
    assert "self.animation_combo = ui.ComboBox(" in source
    assert "OMNIVERSE_SOLAR_SYSTEM_DISPLAY_ASTEROIDS" in source


def test_viewport_uses_independent_scene_views_per_batch():
    root = Path(__file__).resolve().parents[1]
    source = (
        root
        / "exts"
        / "ronproctor.omniverse_solar_system"
        / "ronproctor"
        / "omniverse_solar_system"
        / "viewport_scene.py"
    ).read_text()
    assert "def _create_scene_view" in source
    assert 'self._create_scene_view(f"{kind}.{index}")' in source
    assert "iter_owned_position_batches" in source


def test_extension_hides_default_editor_light_in_session_layer():
    root = Path(__file__).resolve().parents[1]
    source = (
        root
        / "exts"
        / "ronproctor.omniverse_solar_system"
        / "ronproctor"
        / "omniverse_solar_system"
        / "extension.py"
    ).read_text()
    assert 'DEFAULT_LIGHT_PATH = "/Environment/defaultLight"' in source
    assert "stage.GetSessionLayer()" in source
    assert "prim.SetActive(False)" in source
    assert "_restore_default_scene_light" in source


def test_primary_markers_are_filled_screen_space_circles():
    root = Path(__file__).resolve().parents[1]
    source = (
        root
        / "exts"
        / "ronproctor.omniverse_solar_system"
        / "ronproctor"
        / "omniverse_solar_system"
        / "viewport_scene.py"
    ).read_text()
    assert "sc.Arc(" in source
    assert "wireframe=False" in source
    assert "scale_to=sc.Space.SCREEN" in source
    assert "look_at=sc.Transform.LookAt.CAMERA" in source
    assert "self.planet_points" not in source


def test_extension_authors_one_sun_centered_oblique_camera():
    root = Path(__file__).resolve().parents[1]
    source = (
        root
        / "exts"
        / "ronproctor.omniverse_solar_system"
        / "ronproctor"
        / "omniverse_solar_system"
        / "extension.py"
    ).read_text()
    assert "UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)" in source
    assert "OBLIQUE_CAMERA_EYE" in source
    assert "OBLIQUE_CAMERA_TARGET = (0.0, 0.0, 0.0)" in source
    assert "OBLIQUE_CAMERA_FOCUS_DISTANCE" in source
    assert "CreateFocusDistanceAttr().Set(OBLIQUE_CAMERA_FOCUS_DISTANCE)" in source
    assert "def _set_oblique_camera" in source
    assert "SetLookAt" in source
    assert "viewport_api.camera_path = Sdf.Path(CAMERA_PATH)" in source
    assert "CAMERA_PRESETS" not in source
    assert "self.view_combo" not in source
    assert "OMNIVERSE_SOLAR_SYSTEM_START_VIEW" not in source


def test_camera_transform_updates_stay_in_session_layer():
    root = Path(__file__).resolve().parents[1]
    source = (
        root
        / "exts"
        / "ronproctor.omniverse_solar_system"
        / "ronproctor"
        / "omniverse_solar_system"
        / "extension.py"
    ).read_text()
    assert "with Usd.EditContext(self._stage, self._stage.GetSessionLayer()):" in source
    assert "self._camera_transform_op.Set(view_matrix.GetInverse())" in source


def test_screen_space_marker_does_not_scale_world_translation():
    root = Path(__file__).resolve().parents[1]
    source = (
        root
        / "exts"
        / "ronproctor.omniverse_solar_system"
        / "ronproctor"
        / "omniverse_solar_system"
        / "viewport_scene.py"
    ).read_text()
    assert "position_transform = sc.Transform(transform=cls._translation(position))" in source
    assert "screen_transform = sc.Transform(" in source
    assert "with position_transform:" in source
    assert "with screen_transform:" in source
    assert "marker.position_transform.transform = transform" in source
    assert "label.position_transform.transform = transform" in source
    assert "transform=cls._translation(position),\n            scale_to=sc.Space.SCREEN" not in source


def test_orbit_scene_is_persistent_across_catalog_mode_rebuilds():
    root = Path(__file__).resolve().parents[1]
    extension_source = (
        root
        / "exts"
        / "ronproctor.omniverse_solar_system"
        / "ronproctor"
        / "omniverse_solar_system"
        / "extension.py"
    ).read_text()
    viewport_source = (
        root
        / "exts"
        / "ronproctor.omniverse_solar_system"
        / "ronproctor"
        / "omniverse_solar_system"
        / "viewport_scene.py"
    ).read_text()
    build_section = extension_source.split("def _build_scene", 1)[1].split(
        "def _record_update_frequency", 1
    )[0]
    assert "self.viewport_scene.rebuild_catalog(snapshot)" in build_section
    assert "self.viewport_scene.destroy()" not in build_section
    assert "def rebuild_catalog" in viewport_source
    assert "frame.clear()" in viewport_source


def test_orbit_guides_are_transparent_culled_curves():
    root = Path(__file__).resolve().parents[1]
    extension_source = (
        root
        / "exts"
        / "ronproctor.omniverse_solar_system"
        / "ronproctor"
        / "omniverse_solar_system"
        / "extension.py"
    ).read_text()
    viewport_source = (
        root
        / "exts"
        / "ronproctor.omniverse_solar_system"
        / "ronproctor"
        / "omniverse_solar_system"
        / "viewport_scene.py"
    ).read_text()
    assert "class OrbitCurve" in viewport_source
    assert "self.orbit_curves" in viewport_source
    assert "sc.Curve(" in viewport_source
    assert "update_orbit_visibility" in viewport_source
    assert "full_orbit_is_projection_safe" in viewport_source
    assert "orbit_alpha" in viewport_source
    assert 'OMNIVERSE_SOLAR_SYSTEM_ORBIT_ALPHA", "0.50"' in extension_source
    assert "create_subscription_to_pop" in extension_source


def test_extension_exposes_time_controls_and_clean_dropdowns():
    root = Path(__file__).resolve().parents[1]
    source = (
        root
        / "exts"
        / "ronproctor.omniverse_solar_system"
        / "ronproctor"
        / "omniverse_solar_system"
        / "extension.py"
    ).read_text()
    for label in ("Reverse", "Play / Pause", "Forward", "Now", "Refresh"):
        assert f'ui.Button("{label}"' in source
    assert "SimulationClock" in source
    assert "self.speed_combo = ui.ComboBox(" in source
    assert 'ui.Label("Camera", width=105)' in source
    assert 'ui.Label("Oblique · Sun-centered"' in source
    assert "self.view_combo" not in source
    assert "asteroid_playback_indices" in source
    assert "playback_target_hz" in source


def test_extension_hides_grid_and_exposes_label_toggle():
    root = Path(__file__).resolve().parents[1]
    extension_source = (
        root
        / "exts"
        / "ronproctor.omniverse_solar_system"
        / "ronproctor"
        / "omniverse_solar_system"
        / "extension.py"
    ).read_text()
    viewport_source = (
        root
        / "exts"
        / "ronproctor.omniverse_solar_system"
        / "ronproctor"
        / "omniverse_solar_system"
        / "viewport_scene.py"
    ).read_text()
    assert '"toggle_grid_visibility"' in extension_source
    assert "self.grid_model = ui.SimpleBoolModel(False)" in extension_source
    assert "self.labels_model = ui.SimpleBoolModel(self.labels_enabled)" in extension_source
    assert "sc.Label(" in viewport_source
    assert "update_label_visibility" in viewport_source
    assert "choose_non_overlapping_labels" in viewport_source



def test_version_27_uses_zero_copy_deformable_mesh_path():
    root = Path(__file__).resolve().parents[1]
    extension_source = (
        root / "exts" / "ronproctor.omniverse_solar_system" / "ronproctor"
        / "omniverse_solar_system" / "extension.py"
    ).read_text()
    gpu_source = (
        root / "exts" / "ronproctor.omniverse_solar_system" / "ronproctor"
        / "omniverse_solar_system" / "gpu_asteroids.py"
    ).read_text()
    assert "GpuAsteroidRenderer" in extension_source
    assert "compute_primary_snapshot" in extension_source
    assert "render_asteroids=not self.gpu_active" in extension_source
    assert "UsdGeom.Mesh.Define" in gpu_source
    assert 'require_prim_type="Mesh"' in gpu_source
    assert "Deformable" in gpu_source
    assert "RtUsd.Access.ReadWrite" in gpu_source
    assert "wp.fabricarrayarray" in gpu_source
    assert "self._bind_writable_points()" in gpu_source
    assert "_propagate_elliptic_asteroid_mesh" in gpu_source
    assert "VERTICES_PER_ASTEROID = 3" in gpu_source
    assert "--/app/useFabricSceneDelegate=1" in gpu_source


def test_version_2_1_removes_comets_and_allows_full_catalog_playback():
    root = Path(__file__).resolve().parents[1]
    extension_source = (
        root / "exts" / "ronproctor.omniverse_solar_system" / "ronproctor" / "omniverse_solar_system" / "extension.py"
    ).read_text()
    viewport_source = (
        root / "exts" / "ronproctor.omniverse_solar_system" / "ronproctor" / "omniverse_solar_system" / "viewport_scene.py"
    ).read_text()
    engine_source = (root / "src" / "omniverse_solar_system" / "engine.py").read_text()
    assert '"Full catalog",\n)\nPLAYBACK_RATE_MAGNITUDES' in extension_source
    assert "ANIMATION_BUDGETS: tuple[int | None, ...]" in extension_source
    assert "return available if budget is None" in extension_source
    assert "comet" not in extension_source.lower()
    assert "comet" not in viewport_source.lower()
    assert "comet" not in engine_source.lower()


def test_gpu_renderer_writes_camera_facing_triangle_vertices_in_fabric():
    root = Path(__file__).resolve().parents[1]
    source = (
        root / "exts" / "ronproctor.omniverse_solar_system" / "ronproctor"
        / "omniverse_solar_system" / "gpu_asteroids.py"
    ).read_text()
    assert 'attrib="points"' in source
    assert "points[0, vertex_base]" in source
    assert "points[0, vertex_base + 1]" in source
    assert "points[0, vertex_base + 2]" in source
    assert "camera_right" in source
    assert "camera_up" in source
    assert "Degenerate inactive triangles" in source
    assert "wp.synchronize_device" in source


def test_v23_has_robust_boolean_models_and_dot_size_controls():
    root = Path(__file__).resolve().parents[1]
    extension_source = (
        root / "exts" / "ronproctor.omniverse_solar_system" / "ronproctor" / "omniverse_solar_system" / "extension.py"
    ).read_text()
    viewport_source = (
        root / "exts" / "ronproctor.omniverse_solar_system" / "ronproctor" / "omniverse_solar_system" / "viewport_scene.py"
    ).read_text()
    assert "def _bool_model_value" in extension_source
    assert "self.labels_enabled = _bool_model_value(model)" in extension_source
    assert "PLANET_DOT_SIZES" in extension_source
    assert "ASTEROID_DOT_SIZES" in extension_source
    assert "self.planet_size_combo = ui.ComboBox(" in extension_source
    assert "self.asteroid_size_combo = ui.ComboBox(" in extension_source
    assert "planet_marker_radius=self.planet_marker_radius" in extension_source
    assert "asteroid_point_size=self.asteroid_dot_pixels" in extension_source
    assert "self.planet_marker_radius" in viewport_source
    assert "self.asteroid_point_size" in viewport_source


def test_version_27_reacquires_writable_fabric_access_every_update():
    root = Path(__file__).resolve().parents[1]
    gpu_source = (
        root / "exts" / "ronproctor.omniverse_solar_system" / "ronproctor"
        / "omniverse_solar_system" / "gpu_asteroids.py"
    ).read_text()
    extension_source = (
        root / "exts" / "ronproctor.omniverse_solar_system" / "ronproctor"
        / "omniverse_solar_system" / "extension.py"
    ).read_text()
    assert "async def bind_fabric" in gpu_source
    assert "CreateWorldExtentAttr" in gpu_source
    assert "CreateFabricHierarchyLocalMatrixAttr" in gpu_source
    assert "CreateFabricHierarchyWorldMatrixAttr" in gpu_source
    assert "self._bind_writable_points()" in gpu_source
    assert "RtUsd.Access.ReadWrite" in gpu_source
    assert "TARGET_ATTR" in gpu_source
    assert "await new_renderer.bind_fabric()" in extension_source
    assert "GPU/Fabric deformable mesh" in extension_source


def test_label_checkbox_rebuilds_cached_primary_scene_immediately():
    root = Path(__file__).resolve().parents[1]
    extension_source = (
        root
        / "exts"
        / "ronproctor.omniverse_solar_system"
        / "ronproctor"
        / "omniverse_solar_system"
        / "extension.py"
    ).read_text()
    viewport_source = (
        root
        / "exts"
        / "ronproctor.omniverse_solar_system"
        / "ronproctor"
        / "omniverse_solar_system"
        / "viewport_scene.py"
    ).read_text()
    handler = extension_source.split("def _on_labels_changed", 1)[1].split(
        "def _on_grid_changed", 1
    )[0]
    assert "self.viewport_scene.destroy()" in handler
    assert "self.viewport_scene = None" in handler
    assert "self._wake()" in handler
    assert "labels_enabled: bool = True" in viewport_source
    assert "visible=bool(visible)" in viewport_source


def test_camera_changes_refresh_gpu_billboards_while_paused():
    root = Path(__file__).resolve().parents[1]
    source = (
        root / "exts" / "ronproctor.omniverse_solar_system" / "ronproctor"
        / "omniverse_solar_system" / "extension.py"
    ).read_text()
    assert "def _camera_state_signature" in source
    assert "self.gpu_active and not self.clock.is_playing" in source
    assert "self._last_gpu_camera_signature" in source
    assert "self._wake()" in source


def test_release_uses_omniverse_solar_system_identity_only():
    root = Path(__file__).resolve().parents[1]
    text = "\n".join(
        path.read_text(errors="ignore")
        for path in root.rglob("*")
        if path.is_file() and path.suffix in {".py", ".md", ".toml", ".txt", ".sh"}
    ).lower()
    legacy_name = "chat" + "gpt"
    legacy_vendor = "open" + "ai"
    assert legacy_name not in text
    assert legacy_vendor not in text
    assert "ronproctor.omniverse_solar_system" in text
    assert "/omniversesolarsystem" in text


def test_extension_authors_configurable_starmap_dome_background():
    root = Path(__file__).resolve().parents[1]
    source = (
        root
        / "exts"
        / "ronproctor.omniverse_solar_system"
        / "ronproctor"
        / "omniverse_solar_system"
        / "extension.py"
    ).read_text()
    assert "UsdLux.DomeLight.Define" in source
    assert "CreateTextureFileAttr" in source
    assert "UsdLux.Tokens.latlong" in source
    assert 'STARMAP_DOME_PATH = f"{CAMERA_ROOT_PATH}/Environment/StarMap"' in source
    assert "starmap_2020_16k.exr" not in source  # resolved by the shared paths module
    assert 'ui.Label("Star background"' in source
    assert "self.starmap_model.add_value_changed_fn" in source
    assert "OMNIVERSE_SOLAR_SYSTEM_STARMAP_ENABLED" in source
    assert "OMNIVERSE_SOLAR_SYSTEM_STARMAP_EXPOSURE" in source
    assert "STARMAP_J2000_CORRECTION = Gf.Matrix4d" in source
    assert "environment_xform.AddTransformOp().Set(STARMAP_J2000_CORRECTION)" in source
    assert "Gf.Vec3f(90.0, 0.0, 90.0)" in source


def test_version_210_sets_grid_visibility_explicitly():
    root = Path(__file__).resolve().parents[1]
    source = (
        root
        / "exts"
        / "ronproctor.omniverse_solar_system"
        / "ronproctor"
        / "omniverse_solar_system"
        / "extension.py"
    ).read_text()
    handler = source.split("def _set_grid_visible", 1)[1].split(
        "async def _in_worker", 1
    )[0]
    assert 'kwargs = {"visible": desired}' in handler
    assert 'kwargs["viewport_api"] = viewport_api' in handler
    assert '"toggle_grid_visibility", **kwargs' in handler
    assert "self._sync_grid_checkbox(actual)" in handler


def test_version_210_hardens_starmap_visibility_and_streaming():
    root = Path(__file__).resolve().parents[1]
    source = (
        root
        / "exts"
        / "ronproctor.omniverse_solar_system"
        / "ronproctor"
        / "omniverse_solar_system"
        / "extension.py"
    ).read_text()
    assert 'RTX_SHOW_LIGHTS_SETTING = "/rtx/raytracing/showLights"' in source
    assert "RTX_TEXTURE_REQUEST_BUDGET_SETTING" in source
    assert "STARMAP_INTENSITY = 1000.0" in source
    assert '"visibleInPrimaryRay", Sdf.ValueTypeNames.Bool' in source
    assert "settings.set_int(RTX_SHOW_LIGHTS_SETTING, 1)" in source
    assert "settings.set_int(RTX_TEXTURE_REQUEST_BUDGET_SETTING, 1024)" in source
    assert "dome.CreateDiffuseAttr().Set(1.0)" in source
    assert "dome.CreateSpecularAttr().Set(1.0)" in source
    assert 'prim.GetAttribute("visibleInPrimaryRay").Set(True)' in source


def test_version_211_corrects_starmap_basis_and_hides_light_gizmos():
    root = Path(__file__).resolve().parents[1]
    source = (
        root
        / "exts"
        / "ronproctor.omniverse_solar_system"
        / "ronproctor"
        / "omniverse_solar_system"
        / "extension.py"
    ).read_text()
    assert "STARMAP_J2000_CORRECTION = Gf.Matrix4d" in source
    assert "RA 0h: -Y -> +X" in source
    assert "RA 6h: -Z -> +Y" in source
    assert "north: +X -> +Z" in source
    assert "environment_xform.AddTransformOp().Set(STARMAP_J2000_CORRECTION)" in source
    assert "def _hide_light_gizmos" in source
    assert 'kwargs = {"visible": False}' in source
    assert '"toggle_light_visibility", **kwargs' in source
    assert "self._hide_light_gizmos()" in source


def test_version_212_defaults_to_xlarge_planet_dots():
    root = Path(__file__).resolve().parents[1]
    source = (
        root
        / "exts"
        / "ronproctor.omniverse_solar_system"
        / "ronproctor"
        / "omniverse_solar_system"
        / "extension.py"
    ).read_text()
    assert 'OMNIVERSE_SOLAR_SYSTEM_PLANET_PIXELS", "5.0"' in source
    assert 'PLANET_DOT_LABELS = ("Small", "Medium", "Large", "X-Large", "Huge")' in source

