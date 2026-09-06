"""Kit extension lifecycle, GPU asteroid controls, labels, and controllable time."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import math
import os
from pathlib import Path
import sys
from time import perf_counter

import carb.settings
import omni.ext
import omni.kit.actions.core
import omni.kit.app
import omni.ui as ui
import omni.usd
from omni.kit.viewport.utility import get_active_viewport_window
from pxr import Gf, Sdf, Usd, UsdGeom, UsdLux

PROJECT_ROOT = Path(__file__).resolve().parents[4]
for extra in (PROJECT_ROOT / "vendor", PROJECT_ROOT / "src"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

from omniverse_solar_system.constants import PLANET_TARGETS  # noqa: E402
from omniverse_solar_system.engine import SolarSystemEngine  # noqa: E402
from omniverse_solar_system.paths import resolve_starmap_path  # noqa: E402
from omniverse_solar_system.simulation_clock import (  # noqa: E402
    SimulationClock,
    format_playback_rate,
)
from omniverse_solar_system.time_utils import datetime_to_jd  # noqa: E402
from .viewport_scene import SolarSystemViewportScene  # noqa: E402


DEFAULT_LIGHT_PATH = "/Environment/defaultLight"
CAMERA_ROOT_PATH = "/OmniverseSolarSystem"
CAMERA_PATH = f"{CAMERA_ROOT_PATH}/Camera"
STARMAP_DOME_PATH = f"{CAMERA_ROOT_PATH}/Environment/StarMap"
RTX_BACKGROUND_SOURCE_SETTING = "/rtx/background/source/type"
RTX_SHOW_LIGHTS_SETTING = "/rtx/raytracing/showLights"
RTX_TEXTURE_REQUEST_BUDGET_SETTING = (
    "/rtx-transient/resourcemanager/texturestreaming/streamingBudgetMB"
)

# NASA's map is a linear half-float EXR.  Use a conventional HDRI DomeLight
# intensity so its sparse stars remain visible after RTX tone mapping while the
# exposure presets retain useful adjustment range.
STARMAP_INTENSITY = 1000.0
STARMAP_EXPOSURES = (-4.0, -2.0, 0.0, 2.0)
STARMAP_EXPOSURE_LABELS = ("Very dim", "Dim", "Normal", "Bright")

# v2.11 correction applied to the Environment parent after the v2.10 DomeLight
# Euler transform. It rotates the observed v2.10 sky basis as follows:
#   RA 0h: -Y -> +X
#   RA 6h: -Z -> +Y
#   north: +X -> +Z
# Gf matrices use row-vector convention, so each of the first three rows is
# the transformed direction of the corresponding +X, +Y, or +Z basis vector.
STARMAP_J2000_CORRECTION = Gf.Matrix4d(
    0.0, 0.0, 1.0, 0.0,
   -1.0, 0.0, 0.0, 0.0,
    0.0,-1.0, 0.0, 0.0,
    0.0, 0.0, 0.0, 1.0,
)

DISPLAY_ASTEROID_LIMITS: tuple[int | None, ...] = (
    0,
    10_000,
    25_000,
    50_000,
    100_000,
    250_000,
    500_000,
    1_000_000,
    None,
)
DISPLAY_ASTEROID_LABELS = (
    "None",
    "10,000",
    "25,000",
    "50,000",
    "100,000",
    "250,000",
    "500,000",
    "1,000,000",
    "Full catalog",
)
ANIMATION_BUDGETS: tuple[int | None, ...] = (
    0,
    10_000,
    25_000,
    50_000,
    100_000,
    250_000,
    500_000,
    1_000_000,
    None,
)
ANIMATION_BUDGET_LABELS = (
    "None",
    "10,000",
    "25,000",
    "50,000",
    "100,000",
    "250,000",
    "500,000",
    "1,000,000",
    "Full catalog",
)
PLAYBACK_RATE_MAGNITUDES = (
    3_600.0,
    86_400.0,
    864_000.0,
    8_640_000.0,
)
PLAYBACK_RATE_LABELS = (
    "1 hour / second",
    "1 day / second",
    "10 days / second",
    "100 days / second",
)

OBLIQUE_CAMERA_EYE = (65.0, -85.0, 55.0)
OBLIQUE_CAMERA_TARGET = (0.0, 0.0, 0.0)
OBLIQUE_CAMERA_UP = (0.0, 0.0, 1.0)
OBLIQUE_CAMERA_FOCUS_DISTANCE = math.sqrt(
    sum(
        (eye - target) ** 2
        for eye, target in zip(OBLIQUE_CAMERA_EYE, OBLIQUE_CAMERA_TARGET)
    )
)

PLANET_DOT_SIZES = (2.5, 3.25, 4.0, 5.0, 6.5)
PLANET_DOT_LABELS = ("Small", "Medium", "Large", "X-Large", "Huge")
ASTEROID_DOT_SIZES = (0.75, 1.0, 1.25, 1.5, 2.0, 3.0)
ASTEROID_DOT_LABELS = ("0.75 px", "1.0 px", "1.25 px", "1.5 px", "2.0 px", "3.0 px")


def _nearest_index(values: tuple[int | float, ...], requested: int | float) -> int:
    return min(range(len(values)), key=lambda index: abs(values[index] - requested))


def _combo_index(item_model) -> int:
    value = item_model.get_item_value_model().as_int
    return int(value() if callable(value) else value)


def _bool_model_value(model) -> bool:
    """Read Kit boolean models across property- and method-style APIs."""
    for name in ("get_value_as_bool", "as_bool"):
        value = getattr(model, name, None)
        if value is None:
            continue
        return bool(value() if callable(value) else value)
    value = getattr(model, "as_int", 0)
    return bool(value() if callable(value) else value)


def _visibility_result(result) -> bool | None:
    """Extract the post-toggle visibility state returned by viewport actions."""
    if isinstance(result, bool):
        return result
    if isinstance(result, int):
        return bool(result)
    if isinstance(result, dict):
        for key in ("visible", "enabled", "state", "guide/grid"):
            if key in result:
                value = result[key]
                if isinstance(value, (bool, int)):
                    return bool(value)
    if isinstance(result, (tuple, list)):
        for value in reversed(result):
            state = _visibility_result(value)
            if state is not None:
                return state
    return None


def _parse_display_limit(value: str) -> int | None:
    normalized = value.strip().lower().replace(",", "")
    if normalized in {"full", "all", "none-limit"}:
        return None
    return max(0, int(normalized))


def _parse_animation_budget(value: str) -> int | None:
    normalized = value.strip().lower().replace(",", "")
    if normalized in {"full", "all", "catalog"}:
        return None
    return max(0, int(normalized))


def _legacy_start_limit() -> int | None:
    mode = os.environ.get("OMNIVERSE_SOLAR_SYSTEM_START_MODE", "").strip().lower()
    return {"planets": 0, "100k": 100_000, "full": None}.get(mode, 100_000)


class SolarSystemExtension(omni.ext.IExt):
    def on_startup(self, ext_id: str) -> None:
        self.ext_id = ext_id
        self.engine: SolarSystemEngine | None = None
        self.viewport_scene: SolarSystemViewportScene | None = None
        self.viewport_window = None
        self.task: asyncio.Task | None = None
        self._stopping = False
        self._refresh_event = asyncio.Event()
        self._rebuild_requested = False
        self._orbit_lines = None
        self._camera_update_sub = None
        self._last_view_poll = 0.0
        self._last_gpu_camera_signature = None
        self._last_gpu_camera_wake = 0.0
        self._playback_indices_cache: dict[tuple[int, int | None], object] = {}
        self._last_update_completed_at: float | None = None
        self._actual_update_hz = 0.0

        self.gpu_requested = os.environ.get(
            "OMNIVERSE_SOLAR_SYSTEM_GPU_ASTEROIDS", "1"
        ).strip().lower() not in {"0", "false", "off", "no"}
        self.gpu_active = False
        self.gpu_renderer = None
        self._gpu_rebuild_requested = self.gpu_requested
        self._gpu_failure: str | None = None
        self._gpu_active_count = 0
        self._gpu_launch_seconds = 0.0
        self._gpu_resident_count = 0
        self._gpu_triangle_count = 0
        self._gpu_vertex_count = 0
        self._gpu_generation = 0
        self._gpu_fatal_error: str | None = None

        self._stage = None
        self._previous_up_axis = None
        self._previous_camera_path = None
        self._camera_transform_op = None
        self._default_light_stage = None
        self._default_light_was_active = False
        self._starmap_dome = None
        self._starmap_loaded = False
        self._starmap_error: str | None = None
        self._previous_background_source = None
        self._previous_show_lights = None
        self._previous_texture_request_budget = None
        self._background_source_changed = False
        self._grid_visible: bool | None = None
        self._syncing_grid_model = False

        self.batch_size = max(
            1,
            int(os.environ.get("OMNIVERSE_SOLAR_SYSTEM_BATCH_SIZE", "100000")),
        )
        default_playback_hz = "60" if self.gpu_requested else "30"
        self.playback_target_hz = max(
            1.0,
            float(os.environ.get("OMNIVERSE_SOLAR_SYSTEM_PLAYBACK_HZ", default_playback_hz)),
        )
        self.orbit_samples = max(
            64,
            int(os.environ.get("OMNIVERSE_SOLAR_SYSTEM_ORBIT_SAMPLES", "1024")),
        )
        self.orbit_alpha = min(
            1.0,
            max(
                0.0,
                float(os.environ.get("OMNIVERSE_SOLAR_SYSTEM_ORBIT_ALPHA", "0.50")),
            ),
        )
        self.orbit_thickness = max(
            0.1,
            float(os.environ.get("OMNIVERSE_SOLAR_SYSTEM_ORBIT_THICKNESS", "1.25")),
        )
        requested_planet_pixels = float(
            os.environ.get("OMNIVERSE_SOLAR_SYSTEM_PLANET_PIXELS", "5.0")
        )
        self.planet_size_index = _nearest_index(PLANET_DOT_SIZES, requested_planet_pixels)
        requested_asteroid_pixels = float(
            os.environ.get("OMNIVERSE_SOLAR_SYSTEM_ASTEROID_PIXELS", "1.25")
        )
        self.asteroid_size_index = _nearest_index(
            ASTEROID_DOT_SIZES, requested_asteroid_pixels
        )

        raw_display_limit = os.environ.get("OMNIVERSE_SOLAR_SYSTEM_DISPLAY_ASTEROIDS")
        requested_display = (
            _parse_display_limit(raw_display_limit)
            if raw_display_limit is not None
            else _legacy_start_limit()
        )
        if requested_display is None:
            self.display_index = len(DISPLAY_ASTEROID_LIMITS) - 1
        else:
            finite_limits = tuple(value for value in DISPLAY_ASTEROID_LIMITS if value is not None)
            nearest_value = finite_limits[_nearest_index(finite_limits, requested_display)]
            self.display_index = DISPLAY_ASTEROID_LIMITS.index(nearest_value)

        requested_rate = float(
            os.environ.get("OMNIVERSE_SOLAR_SYSTEM_PLAYBACK_RATE", "86400")
        )
        self.speed_index = _nearest_index(PLAYBACK_RATE_MAGNITUDES, abs(requested_rate))
        self.play_direction = -1 if requested_rate < 0.0 else 1
        requested_budget = _parse_animation_budget(
            os.environ.get("OMNIVERSE_SOLAR_SYSTEM_ANIMATION_BUDGET", "25000")
        )
        if requested_budget is None:
            self.budget_index = len(ANIMATION_BUDGETS) - 1
        else:
            finite_budgets = tuple(
                value for value in ANIMATION_BUDGETS if value is not None
            )
            nearest_budget = finite_budgets[
                _nearest_index(finite_budgets, requested_budget)
            ]
            self.budget_index = ANIMATION_BUDGETS.index(nearest_budget)
        self.status_readout_enabled = os.environ.get(
            "OMNIVERSE_SOLAR_SYSTEM_STATUS_READOUT", "0"
        ).strip().lower() not in {"0", "false", "off", "no"}
        self._status_text = "Starting…"
        self._last_status_label_update = 0.0
        self.labels_enabled = os.environ.get(
            "OMNIVERSE_SOLAR_SYSTEM_PLANET_LABELS", "1"
        ).strip().lower() not in {"0", "false", "off", "no"}
        self.starmap_enabled = os.environ.get(
            "OMNIVERSE_SOLAR_SYSTEM_STARMAP_ENABLED", "1"
        ).strip().lower() not in {"0", "false", "off", "no"}
        requested_starmap_exposure = float(
            os.environ.get("OMNIVERSE_SOLAR_SYSTEM_STARMAP_EXPOSURE", "0")
        )
        self.starmap_exposure_index = _nearest_index(
            STARMAP_EXPOSURES, requested_starmap_exposure
        )
        self.starmap_path = resolve_starmap_path(PROJECT_ROOT)
        self.clock = SimulationClock.paused_at(datetime.now(timezone.utc))

        self.window = ui.Window("Solar System Orrery", width=560, height=385)
        self.status_label = None
        self.display_combo = None
        self.animation_combo = None
        self.speed_combo = None
        self.planet_size_combo = None
        self.asteroid_size_combo = None
        self.starmap_exposure_combo = None
        self.labels_model = ui.SimpleBoolModel(self.labels_enabled)
        self.grid_model = ui.SimpleBoolModel(False)
        self.status_model = ui.SimpleBoolModel(self.status_readout_enabled)
        self.starmap_model = ui.SimpleBoolModel(self.starmap_enabled)

        with self.window.frame:
            with ui.VStack(spacing=8):
                ui.Label("J2000 planets + MPC asteroids")
                self.status_label = ui.Label(
                    "Starting…",
                    height=96,
                    word_wrap=True,
                    visible=self.status_readout_enabled,
                )

                with ui.HStack(height=30, spacing=6):
                    ui.Label("Asteroids", width=72)
                    self.display_combo = ui.ComboBox(
                        self.display_index,
                        *DISPLAY_ASTEROID_LABELS,
                        width=ui.Fraction(1),
                    )
                    ui.Label("During playback", width=105)
                    self.animation_combo = ui.ComboBox(
                        self.budget_index,
                        *ANIMATION_BUDGET_LABELS,
                        width=ui.Fraction(1),
                    )

                with ui.HStack(height=30, spacing=6):
                    ui.Label("Speed", width=72)
                    self.speed_combo = ui.ComboBox(
                        self.speed_index,
                        *PLAYBACK_RATE_LABELS,
                        width=ui.Fraction(1),
                    )
                    ui.Label("Camera", width=105)
                    ui.Label("Oblique · Sun-centered", width=ui.Fraction(1))

                with ui.HStack(height=30, spacing=6):
                    ui.Label("Planet dots", width=72)
                    self.planet_size_combo = ui.ComboBox(
                        self.planet_size_index,
                        *PLANET_DOT_LABELS,
                        width=ui.Fraction(1),
                    )
                    ui.Label("Asteroid dots", width=105)
                    self.asteroid_size_combo = ui.ComboBox(
                        self.asteroid_size_index,
                        *ASTEROID_DOT_LABELS,
                        width=ui.Fraction(1),
                    )

                with ui.HStack(height=30, spacing=6):
                    ui.Button("Reverse", clicked_fn=self._play_reverse)
                    ui.Button("Play / Pause", clicked_fn=self._toggle_pause)
                    ui.Button("Forward", clicked_fn=self._play_forward)
                    ui.Button("Now", clicked_fn=self._reset_to_now)
                    ui.Button("Refresh", clicked_fn=self._request_refresh)

                with ui.HStack(height=24, spacing=8):
                    ui.CheckBox(model=self.labels_model, width=20)
                    ui.Label("Planet labels", width=110)
                    ui.CheckBox(model=self.grid_model, width=20)
                    ui.Label("Viewport grid", width=110)
                    ui.CheckBox(model=self.status_model, width=20)
                    ui.Label("Status readout", width=110)
                    ui.Spacer()

                with ui.HStack(height=30, spacing=8):
                    ui.CheckBox(model=self.starmap_model, width=20)
                    ui.Label("Star background", width=110)
                    ui.Label("Exposure", width=62)
                    self.starmap_exposure_combo = ui.ComboBox(
                        self.starmap_exposure_index,
                        *STARMAP_EXPOSURE_LABELS,
                        width=ui.Fraction(1),
                    )

        self.display_combo.model.add_item_changed_fn(self._on_display_changed)
        self.animation_combo.model.add_item_changed_fn(self._on_animation_changed)
        self.speed_combo.model.add_item_changed_fn(self._on_speed_changed)
        self.planet_size_combo.model.add_item_changed_fn(self._on_planet_size_changed)
        self.asteroid_size_combo.model.add_item_changed_fn(self._on_asteroid_size_changed)
        self.starmap_exposure_combo.model.add_item_changed_fn(
            self._on_starmap_exposure_changed
        )
        self.labels_model.add_value_changed_fn(self._on_labels_changed)
        self.grid_model.add_value_changed_fn(self._on_grid_changed)
        self.status_model.add_value_changed_fn(self._on_status_changed)
        self.starmap_model.add_value_changed_fn(self._on_starmap_changed)

        self._camera_update_sub = (
            omni.kit.app.get_app()
            .get_update_event_stream()
            .create_subscription_to_pop(
                self._on_app_update,
                name="Omniverse Solar System view-dependent overlays",
            )
        )
        self.task = asyncio.ensure_future(self._run())

    @property
    def display_asteroid_limit(self) -> int | None:
        return DISPLAY_ASTEROID_LIMITS[self.display_index]

    @property
    def animation_budget(self) -> int | None:
        return ANIMATION_BUDGETS[self.budget_index]

    @property
    def playback_rate_magnitude(self) -> float:
        return PLAYBACK_RATE_MAGNITUDES[self.speed_index]

    @property
    def planet_marker_radius(self) -> float:
        return PLANET_DOT_SIZES[self.planet_size_index]

    @property
    def asteroid_dot_pixels(self) -> float:
        return ASTEROID_DOT_SIZES[self.asteroid_size_index]

    @property
    def starmap_exposure(self) -> float:
        return STARMAP_EXPOSURES[self.starmap_exposure_index]

    def _wake(self, *, rebuild: bool = False) -> None:
        if rebuild:
            self._rebuild_requested = True
        self._refresh_event.set()

    def _request_refresh(self) -> None:
        self._wake()

    def _on_display_changed(self, item_model, _item) -> None:
        index = max(0, min(_combo_index(item_model), len(DISPLAY_ASTEROID_LIMITS) - 1))
        if index == self.display_index:
            return
        self.display_index = index
        self._set_status_text("Changing displayed asteroid population…")
        if self.gpu_requested:
            desired = self._display_asteroid_count()
            # GPU meshes are grow-only. Selecting a smaller population only changes
            # active_count; selecting a larger population builds a new generation.
            if self.gpu_renderer is None or desired > self._gpu_resident_count:
                self._gpu_rebuild_requested = True
            self._wake()
        else:
            self._wake(rebuild=True)

    def _on_animation_changed(self, item_model, _item) -> None:
        index = max(0, min(_combo_index(item_model), len(ANIMATION_BUDGETS) - 1))
        if index == self.budget_index:
            return
        self.budget_index = index
        self._wake(rebuild=self.clock.is_playing and not self.gpu_active)

    def _on_speed_changed(self, item_model, _item) -> None:
        index = max(0, min(_combo_index(item_model), len(PLAYBACK_RATE_MAGNITUDES) - 1))
        if index == self.speed_index:
            return
        self.speed_index = index
        if self.clock.is_playing:
            self.clock.set_rate(self.play_direction * self.playback_rate_magnitude)
        self._wake()

    def _on_planet_size_changed(self, item_model, _item) -> None:
        index = max(0, min(_combo_index(item_model), len(PLANET_DOT_SIZES) - 1))
        if index == self.planet_size_index:
            return
        self.planet_size_index = index
        # Nine markers are cheap to rebuild, and rebuilding avoids relying on
        # version-specific mutability of omni.ui.scene.Arc.radius.
        if self.viewport_scene is not None:
            self.viewport_scene.destroy()
            self.viewport_scene = None
        self._wake()

    def _on_asteroid_size_changed(self, item_model, _item) -> None:
        index = max(0, min(_combo_index(item_model), len(ASTEROID_DOT_SIZES) - 1))
        if index == self.asteroid_size_index:
            return
        self.asteroid_size_index = index
        if self.viewport_scene is not None:
            self.viewport_scene.asteroid_point_size = self.asteroid_dot_pixels
        self._wake(rebuild=not self.gpu_active)

    def _on_labels_changed(self, model) -> None:
        self.labels_enabled = _bool_model_value(model)
        # Kit 110.1 updates the Python-visible ``visible`` property immediately,
        # but a cached SceneView draw buffer may not be rebuilt until another
        # shape changes. Rebuilding the nine-body overlay is cheap and makes the
        # checkbox deterministic without touching the GPU asteroid prim.
        if self.viewport_scene is not None:
            self.viewport_scene.destroy()
            self.viewport_scene = None
        self._wake()

    def _on_grid_changed(self, model) -> None:
        if self._syncing_grid_model:
            return
        self._set_grid_visible(_bool_model_value(model))

    def _on_status_changed(self, model) -> None:
        self.status_readout_enabled = _bool_model_value(model)
        if self.status_label is not None:
            self.status_label.visible = self.status_readout_enabled
        if self.status_readout_enabled:
            self._set_status_text(self._status_text, force=True)

    def _on_starmap_changed(self, model) -> None:
        self.starmap_enabled = _bool_model_value(model)
        self._apply_starmap_state()
        if self.starmap_enabled and self._starmap_error:
            self._set_status_text(self._starmap_error)
        self._wake()

    def _on_starmap_exposure_changed(self, item_model, _item) -> None:
        index = max(0, min(_combo_index(item_model), len(STARMAP_EXPOSURES) - 1))
        if index == self.starmap_exposure_index:
            return
        self.starmap_exposure_index = index
        self._apply_starmap_state()
        self._wake()

    def _set_playback_rate(self, rate: float) -> None:
        was_playing = self.clock.is_playing
        self.clock.set_rate(rate)
        is_playing = self.clock.is_playing
        if rate != 0.0:
            self.play_direction = -1 if rate < 0.0 else 1
        if was_playing != is_playing:
            if not self.gpu_active:
                self._rebuild_requested = True
            self._last_update_completed_at = None
            self._actual_update_hz = 0.0
        self._wake()

    def _play_reverse(self) -> None:
        self._set_playback_rate(-self.playback_rate_magnitude)

    def _play_forward(self) -> None:
        self._set_playback_rate(self.playback_rate_magnitude)

    def _toggle_pause(self) -> None:
        if self.clock.is_playing:
            self._set_playback_rate(0.0)
        else:
            self._set_playback_rate(self.play_direction * self.playback_rate_magnitude)

    def _reset_to_now(self) -> None:
        was_playing = self.clock.is_playing
        self.clock.reset_to_now(datetime.now(timezone.utc))
        if was_playing and not self.gpu_active:
            self._rebuild_requested = True
        self._last_update_completed_at = None
        self._actual_update_hz = 0.0
        self._wake()

    def _execute_viewport_action(self, action_id: str, **kwargs):
        action = omni.kit.actions.core.get_action_registry().get_action(
            "omni.kit.viewport.actions", action_id
        )
        if not action:
            print(f"[Omniverse Solar System] Viewport action unavailable: {action_id}")
            return None
        return action.execute(**kwargs)

    def _sync_grid_checkbox(self, visible: bool) -> None:
        model = self.grid_model
        if model is None or _bool_model_value(model) == bool(visible):
            return
        self._syncing_grid_model = True
        try:
            model.set_value(bool(visible))
        finally:
            self._syncing_grid_model = False

    def _set_grid_visible(self, visible: bool) -> None:
        """Set grid visibility directly: checked means on, unchecked means off.

        The viewport action accepts an explicit ``visible`` argument.  Using it
        avoids inferring the editor's remembered initial state from a toggle and
        keeps the checkbox semantics deterministic across sessions.
        """
        desired = bool(visible)
        viewport_api = (
            self.viewport_window.viewport_api
            if self.viewport_window is not None
            else None
        )
        kwargs = {"visible": desired}
        if viewport_api is not None:
            kwargs["viewport_api"] = viewport_api

        try:
            result = self._execute_viewport_action(
                "toggle_grid_visibility", **kwargs
            )
            state = _visibility_result(result)
            actual = desired if state is None else bool(state)
        except TypeError:
            # Compatibility fallback for older action implementations which did
            # not accept keyword arguments.  Avoid an unnecessary toggle when our
            # tracked state already matches the request.
            if self._grid_visible is None or self._grid_visible != desired:
                result = self._execute_viewport_action("toggle_grid_visibility")
                state = _visibility_result(result)
                actual = desired if state is None else bool(state)
            else:
                actual = desired

        self._grid_visible = actual
        self._sync_grid_checkbox(actual)

    def _restore_grid_visibility(self) -> None:
        # Grid state is an explicit user-facing application control.  Leave the
        # last selected state in place rather than applying another blind toggle
        # during extension shutdown.
        return

    def _hide_light_gizmos(self) -> None:
        """Hide viewport light icons without disabling rendered stage lights."""
        viewport_api = (
            self.viewport_window.viewport_api
            if self.viewport_window is not None
            else None
        )
        kwargs = {"visible": False}
        if viewport_api is not None:
            kwargs["viewport_api"] = viewport_api
        try:
            self._execute_viewport_action("toggle_light_visibility", **kwargs)
        except TypeError:
            # Kit 110.1 supports explicit visibility. Do not use a blind-toggle
            # fallback because it could turn icons on in a viewport where the
            # user had already hidden them.
            print(
                "[Omniverse Solar System] Could not explicitly hide light "
                "gizmos with this viewport-actions version."
            )

    async def _in_worker(self, func, *args):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, func, *args)

    async def _wait_for_viewport(self):
        while not self._stopping:
            viewport = get_active_viewport_window()
            if viewport is not None:
                return viewport
            await omni.kit.app.get_app().next_update_async()
        return None

    async def _wait_for_stage(self):
        context = omni.usd.get_context()
        while not self._stopping:
            stage = context.get_stage()
            if stage is not None:
                return stage
            await omni.kit.app.get_app().next_update_async()
        return None

    @staticmethod
    def _path_string(path) -> str:
        return getattr(path, "pathString", str(path))

    def _configure_stage_and_camera(self, stage, viewport_window) -> None:
        self._stage = stage
        self.viewport_window = viewport_window
        self._previous_up_axis = UsdGeom.GetStageUpAxis(stage)
        self._previous_camera_path = viewport_window.viewport_api.camera_path

        with Usd.EditContext(stage, stage.GetSessionLayer()):
            UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
            UsdGeom.Xform.Define(stage, CAMERA_ROOT_PATH)
            camera = UsdGeom.Camera.Define(stage, CAMERA_PATH)
            camera.CreateProjectionAttr().Set(UsdGeom.Tokens.perspective)
            camera.CreateHorizontalApertureAttr().Set(36.0)
            camera.CreateVerticalApertureAttr().Set(20.25)
            camera.CreateFocalLengthAttr().Set(24.0)
            camera.CreateFocusDistanceAttr().Set(OBLIQUE_CAMERA_FOCUS_DISTANCE)
            camera.CreateClippingRangeAttr().Set(Gf.Vec2f(0.01, 10_000.0))
            xformable = UsdGeom.Xformable(camera.GetPrim())
            xformable.ClearXformOpOrder()
            self._camera_transform_op = xformable.AddTransformOp()

        self._set_oblique_camera()
        print(
            "[Omniverse Solar System] Rendering frame J2000: "
            "+Z=NCP, +X=vernal equinox; stage is Z-up"
        )

    def _set_oblique_camera(self) -> None:
        """Install the one project camera without resetting it during UI changes.

        The USD focus distance is authored to the Sun so Kit's camera manipulator
        starts with a Sun-centered center of interest.  Because v2.12 no longer
        switches camera presets, interactive zoom and orbit state are left intact.
        """
        if self._camera_transform_op is None or self.viewport_window is None:
            return
        view_matrix = Gf.Matrix4d(1.0)
        view_matrix.SetLookAt(
            Gf.Vec3d(*OBLIQUE_CAMERA_EYE),
            Gf.Vec3d(*OBLIQUE_CAMERA_TARGET),
            Gf.Vec3d(*OBLIQUE_CAMERA_UP),
        )
        if self._stage is None:
            return
        with Usd.EditContext(self._stage, self._stage.GetSessionLayer()):
            self._camera_transform_op.Set(view_matrix.GetInverse())
            camera = UsdGeom.Camera(self._stage.GetPrimAtPath(CAMERA_PATH))
            camera.CreateFocusDistanceAttr().Set(OBLIQUE_CAMERA_FOCUS_DISTANCE)
        self.viewport_window.viewport_api.camera_path = Sdf.Path(CAMERA_PATH)
        self._update_view_dependent_visibility(force=True)

    def _configure_starmap(self) -> None:
        """Author the shared 16K EXR as a session-layer DomeLight background."""
        stage = self._stage
        if stage is None:
            return

        # The NASA map is already plate-carree J2000: north at the top, RA 0h
        # at image center, and RA increasing left. OpenEXR lat-long maps use
        # local +Y as north and local +Z as longitude zero. The v2.10 Euler op
        # produced a renderer-visible basis with north at +X, RA 0h at -Y, and
        # RA 6h at -Z. Apply an explicit parent matrix so the visible result is
        # the orrery convention: north +Z, RA 0h +X, and RA 6h +Y.
        with Usd.EditContext(stage, stage.GetSessionLayer()):
            environment = UsdGeom.Xform.Define(
                stage, f"{CAMERA_ROOT_PATH}/Environment"
            )
            environment_xform = UsdGeom.Xformable(environment.GetPrim())
            environment_xform.ClearXformOpOrder()
            environment_xform.AddTransformOp().Set(STARMAP_J2000_CORRECTION)
            dome = UsdLux.DomeLight.Define(stage, STARMAP_DOME_PATH)
            dome.CreateTextureFileAttr().Set(Sdf.AssetPath(str(self.starmap_path)))
            dome.CreateTextureFormatAttr().Set(UsdLux.Tokens.latlong)
            dome.CreateIntensityAttr().Set(STARMAP_INTENSITY)
            dome.CreateExposureAttr().Set(float(self.starmap_exposure))
            dome.CreateColorAttr().Set(Gf.Vec3f(1.0, 1.0, 1.0))
            # Keep standard DomeLight contribution enabled.  The planets and
            # asteroid markers are shadeless/emissive, so this does not alter
            # their appearance, while it avoids renderer paths that suppress a
            # DomeLight whose diffuse and specular multipliers are both zero.
            dome.CreateDiffuseAttr().Set(1.0)
            dome.CreateSpecularAttr().Set(1.0)
            dome.GetPrim().CreateAttribute(
                "visibleInPrimaryRay", Sdf.ValueTypeNames.Bool
            ).Set(True)
            xformable = UsdGeom.Xformable(dome.GetPrim())
            xformable.ClearXformOpOrder()
            xformable.AddRotateXYZOp().Set(Gf.Vec3f(90.0, 0.0, 90.0))

        self._starmap_dome = dome
        self._apply_starmap_state()

    def _set_rtx_background_to_dome(self) -> None:
        if self._background_source_changed:
            return
        try:
            settings = carb.settings.get_settings()
            self._previous_background_source = settings.get(
                RTX_BACKGROUND_SOURCE_SETTING
            )
            self._previous_show_lights = settings.get(RTX_SHOW_LIGHTS_SETTING)
            self._previous_texture_request_budget = settings.get(
                RTX_TEXTURE_REQUEST_BUDGET_SETTING
            )

            # 0 = use the rendered DomeLight as the background.  Force primary-ray
            # light visibility because editor profiles can remember a global
            # Force Disable state even when the DomeLight prim itself is visible.
            settings.set_int(RTX_BACKGROUND_SOURCE_SETTING, 0)
            settings.set_int(RTX_SHOW_LIGHTS_SETTING, 1)

            # The 16K half-float EXR is larger than RTX's default 200 MB
            # per-request streaming budget.  A 1 GB request ceiling allows its
            # largest mip to arrive without disabling texture streaming globally.
            current_budget = self._previous_texture_request_budget
            if current_budget is None or int(current_budget) < 1024:
                settings.set_int(RTX_TEXTURE_REQUEST_BUDGET_SETTING, 1024)
            self._background_source_changed = True
        except Exception as exc:
            print(
                "[Omniverse Solar System] Could not configure RTX star background "
                f"settings: {exc}"
            )

    @staticmethod
    def _restore_setting(settings, path: str, previous) -> None:
        if previous is None:
            destroy_item = getattr(settings, "destroy_item", None)
            if destroy_item is not None:
                destroy_item(path)
        else:
            settings.set(path, previous)

    def _restore_rtx_background_source(self) -> None:
        if not self._background_source_changed:
            return
        try:
            settings = carb.settings.get_settings()
            self._restore_setting(
                settings, RTX_BACKGROUND_SOURCE_SETTING, self._previous_background_source
            )
            self._restore_setting(
                settings, RTX_SHOW_LIGHTS_SETTING, self._previous_show_lights
            )
            self._restore_setting(
                settings,
                RTX_TEXTURE_REQUEST_BUDGET_SETTING,
                self._previous_texture_request_budget,
            )
        except Exception as exc:
            print(
                "[Omniverse Solar System] Background-setting restore warning: "
                f"{exc}"
            )
        self._previous_background_source = None
        self._previous_show_lights = None
        self._previous_texture_request_budget = None
        self._background_source_changed = False

    def _apply_starmap_state(self) -> None:
        stage = self._stage
        dome = self._starmap_dome
        if stage is None or dome is None:
            return

        path_exists = self.starmap_path.is_file()
        enabled = bool(self.starmap_enabled and path_exists)
        self._starmap_loaded = enabled
        self._starmap_error = None
        if self.starmap_enabled and not path_exists:
            self._starmap_error = (
                "Star background not found. Expected:\n"
                f"{self.starmap_path}"
            )

        with Usd.EditContext(stage, stage.GetSessionLayer()):
            prim = dome.GetPrim()
            if not prim.IsValid():
                self._starmap_loaded = False
                self._starmap_error = "Star background DomeLight prim is invalid."
                return
            # Reactivate before editing in case the checkbox previously disabled it.
            prim.SetActive(True)
            dome.CreateTextureFileAttr().Set(Sdf.AssetPath(str(self.starmap_path)))
            dome.CreateTextureFormatAttr().Set(UsdLux.Tokens.latlong)
            dome.CreateIntensityAttr().Set(STARMAP_INTENSITY)
            dome.CreateExposureAttr().Set(float(self.starmap_exposure))
            dome.CreateColorAttr().Set(Gf.Vec3f(1.0, 1.0, 1.0))
            dome.CreateDiffuseAttr().Set(1.0)
            dome.CreateSpecularAttr().Set(1.0)
            prim.CreateAttribute(
                "visibleInPrimaryRay", Sdf.ValueTypeNames.Bool
            ).Set(True)
            prim.SetActive(enabled)

        if enabled:
            self._set_rtx_background_to_dome()
            # Re-author the texture after the RTX visibility/background settings
            # change so Hydra receives a fresh DomeLight texture dirtiness event.
            with Usd.EditContext(stage, stage.GetSessionLayer()):
                dome.CreateTextureFileAttr().Set(
                    Sdf.AssetPath(str(self.starmap_path))
                )
                prim.GetAttribute("visibleInPrimaryRay").Set(True)
            print(
                "[Omniverse Solar System] Star background enabled: "
                f"{self.starmap_path} (intensity {STARMAP_INTENSITY:g}, "
                f"exposure {self.starmap_exposure:+g} EV)"
            )
        else:
            self._restore_rtx_background_source()
            if self._starmap_error:
                print(f"[Omniverse Solar System] {self._starmap_error}")

    async def _hide_default_scene_light(self) -> None:
        context = omni.usd.get_context()
        for _ in range(120):
            if self._stopping:
                return
            stage = context.get_stage()
            if stage is not None:
                prim = stage.GetPrimAtPath(DEFAULT_LIGHT_PATH)
                if prim.IsValid():
                    self._default_light_stage = stage
                    self._default_light_was_active = bool(prim.IsActive())
                    if self._default_light_was_active:
                        with Usd.EditContext(stage, stage.GetSessionLayer()):
                            prim.SetActive(False)
                        print(
                            f"[Omniverse Solar System] Hid editor light {DEFAULT_LIGHT_PATH}"
                        )
                    return
            await omni.kit.app.get_app().next_update_async()

    def _restore_default_scene_light(self) -> None:
        stage = self._default_light_stage
        if stage is None or not self._default_light_was_active:
            return
        prim = stage.GetPrimAtPath(DEFAULT_LIGHT_PATH)
        if prim.IsValid():
            with Usd.EditContext(stage, stage.GetSessionLayer()):
                prim.SetActive(True)
        self._default_light_stage = None
        self._default_light_was_active = False

    def _restore_stage_and_camera(self) -> None:
        stage = self._stage
        viewport_window = self.viewport_window
        if stage is None:
            return
        if viewport_window is not None and self._previous_camera_path is not None:
            current = self._path_string(viewport_window.viewport_api.camera_path)
            if current == CAMERA_PATH:
                viewport_window.viewport_api.camera_path = self._previous_camera_path
        with Usd.EditContext(stage, stage.GetSessionLayer()):
            if stage.GetPrimAtPath(CAMERA_ROOT_PATH).IsValid():
                stage.RemovePrim(CAMERA_ROOT_PATH)
            if self._previous_up_axis is not None:
                UsdGeom.SetStageUpAxis(stage, self._previous_up_axis)
        self._camera_transform_op = None
        self._previous_camera_path = None
        self._previous_up_axis = None
        self._stage = None
        self.viewport_window = None

    async def _asteroid_indices_for_playback(self, static_limit: int | None):
        # CPU fallback path retained as a scientific reference implementation.
        effective_total = self.engine.asteroids.count if static_limit is None else static_limit
        budget = self.animation_budget
        count = effective_total if budget is None else min(budget, effective_total)
        key = (count, static_limit)
        indices = self._playback_indices_cache.get(key)
        if indices is None:
            indices = await self._in_worker(
                self.engine.asteroid_playback_indices,
                count,
                static_limit,
            )
            self._playback_indices_cache[key] = indices
        return indices

    def _display_asteroid_count(self) -> int:
        total = self.engine.asteroids.count if self.engine else 0
        limit = self.display_asteroid_limit
        return total if limit is None else min(int(limit), total)

    def _effective_animation_count(self, available_count: int | None = None) -> int:
        available = (
            self._display_asteroid_count()
            if available_count is None
            else max(0, int(available_count))
        )
        budget = self.animation_budget
        return available if budget is None else min(int(budget), available)

    @staticmethod
    def _destroy_renderer_instance(renderer) -> None:
        if renderer is None:
            return
        try:
            renderer.destroy()
        except Exception as exc:
            print(f"[Omniverse Solar System] GPU cleanup warning: {exc}")

    def _destroy_gpu_renderer(self) -> None:
        self._destroy_renderer_instance(self.gpu_renderer)
        self.gpu_renderer = None
        self._gpu_active_count = 0
        self._gpu_resident_count = 0
        self._gpu_triangle_count = 0
        self._gpu_vertex_count = 0

    def _fall_back_to_cpu(self, exc: Exception) -> None:
        self._gpu_failure = f"{type(exc).__name__}: {exc}"
        print(f"[Omniverse Solar System] GPU asteroid fallback: {self._gpu_failure}")
        self._destroy_gpu_renderer()
        self.gpu_active = False
        self.gpu_requested = False
        self._gpu_rebuild_requested = False
        if self.viewport_scene is not None:
            self.viewport_scene.destroy()
            self.viewport_scene = None
        self._rebuild_requested = True
        self.playback_target_hz = min(self.playback_target_hz, 30.0)

    async def _rebuild_gpu_renderer(self, *, initial_jd: float | None = None) -> float:
        if not self.gpu_requested or self._gpu_fatal_error:
            return 0.0
        desired = self._display_asteroid_count()
        if self.gpu_renderer is not None and desired <= self._gpu_resident_count:
            # Grow-only resident capacity: smaller display choices are handled by
            # active_count and never rebuild or shrink the Fabric mesh.
            self._gpu_rebuild_requested = False
            return 0.0

        started = perf_counter()
        old_renderer = self.gpu_renderer
        new_renderer = None
        next_generation = self._gpu_generation + 1
        try:
            self._set_status_text(
                f"Packing {desired:,} GPU asteroids for generation {next_generation}…"
            )
            packed = await self._in_worker(self.engine.pack_gpu_asteroids, desired)
            if packed.count:
                from .gpu_asteroids import GpuAsteroidRenderer

                self._set_status_text(
                    f"Creating generation {next_generation} with "
                    f"{packed.count:,} asteroids…"
                )
                new_renderer = GpuAsteroidRenderer(
                    packed,
                    generation=next_generation,
                )
                await new_renderer.bind_fabric()
                jd = initial_jd
                if jd is None:
                    jd = datetime_to_jd(self.clock.current())
                displayed = min(desired, packed.count)
                active = (
                    self._effective_animation_count(displayed)
                    if self.clock.is_playing
                    else displayed
                )
                camera_position, camera_forward, camera_right, camera_up = (
                    self._camera_billboard_frame()
                )
                stats = new_renderer.update(
                    jd,
                    active,
                    self._gpu_marker_scale_per_au(),
                    camera_position,
                    camera_forward,
                    camera_right,
                    camera_up,
                    synchronize=True,
                )

                # Swap only after the new, uniquely tagged generation has bound the
                # exact expected vertex capacity and completed one synchronized GPU
                # update. The old generation remains valid until this point.
                self.gpu_renderer = new_renderer
                new_renderer = None
                self._gpu_generation = stats.generation
                self._gpu_resident_count = stats.resident_count
                self._gpu_active_count = stats.active_count
                self._gpu_launch_seconds = stats.launch_seconds
                self._gpu_triangle_count = stats.triangle_count
                self._gpu_vertex_count = stats.vertex_count
                self.gpu_active = True
                self._gpu_failure = None
                self._gpu_rebuild_requested = False
                self._destroy_renderer_instance(old_renderer)
                print(
                    f"[Omniverse Solar System] GPU/Fabric generation "
                    f"{self._gpu_generation}: {self._gpu_resident_count:,} resident"
                )
            else:
                # A zero-object display does not need a resident mesh. Preserve an
                # existing larger generation for instant later reuse when possible.
                self.gpu_active = old_renderer is not None
                self._gpu_rebuild_requested = False
        except Exception as exc:
            self._destroy_renderer_instance(new_renderer)
            self._gpu_failure = f"{type(exc).__name__}: {exc}"
            print(
                f"[Omniverse Solar System] GPU generation {next_generation} "
                f"failed: {self._gpu_failure}"
            )
            if type(exc).__name__ == "GpuRendererFatalError":
                self._gpu_fatal_error = str(exc)
                self.clock.pause()
                self._gpu_rebuild_requested = False
            elif old_renderer is not None:
                # A non-CUDA grow failure must not throw away the known-good mesh.
                self.gpu_renderer = old_renderer
                self.gpu_active = True
                self._gpu_rebuild_requested = False
            else:
                self._fall_back_to_cpu(exc)
        return perf_counter() - started

    def _gpu_marker_scale_per_au(self) -> float:
        """Return triangle circumradius per unit camera depth for pixel sizing."""
        height = 720.0
        if self.viewport_window is not None:
            try:
                _width, viewport_height = self.viewport_window.viewport_api.resolution
                height = max(1.0, float(viewport_height))
            except Exception:
                pass
        vertical_fov = math.radians(45.0)
        if self._stage is not None and self.viewport_window is not None:
            try:
                camera_prim = self._stage.GetPrimAtPath(
                    self.viewport_window.viewport_api.camera_path
                )
                camera = UsdGeom.Camera(camera_prim)
                focal = float(camera.GetFocalLengthAttr().Get())
                aperture = float(camera.GetVerticalApertureAttr().Get())
                if focal > 0.0 and aperture > 0.0:
                    vertical_fov = 2.0 * math.atan(aperture / (2.0 * focal))
            except Exception:
                pass
        pixel_diameter = max(0.25, self.asteroid_dot_pixels)
        # An equilateral triangle's top-to-bottom span is 1.5 circumradii.
        # Scale each asteroid by its camera-space depth in the GPU kernel.
        return (
            2.0 * math.tan(vertical_fov * 0.5) / height
            * pixel_diameter / 1.5
        )

    def _camera_billboard_frame(self):
        """Return camera position and normalized forward/right/up world vectors."""
        stage = self._stage
        viewport_window = self.viewport_window
        if stage is None or viewport_window is None:
            return (
                (0.0, 0.0, 100.0),
                (0.0, 0.0, -1.0),
                (1.0, 0.0, 0.0),
                (0.0, 1.0, 0.0),
            )
        try:
            camera_prim = stage.GetPrimAtPath(viewport_window.viewport_api.camera_path)
            world = UsdGeom.Xformable(camera_prim).ComputeLocalToWorldTransform(
                Usd.TimeCode.Default()
            )
            position = world.ExtractTranslation()
            forward = world.TransformDir(Gf.Vec3d(0.0, 0.0, -1.0)).GetNormalized()
            right = world.TransformDir(Gf.Vec3d(1.0, 0.0, 0.0)).GetNormalized()
            up = world.TransformDir(Gf.Vec3d(0.0, 1.0, 0.0)).GetNormalized()
            return tuple(
                (float(vector[0]), float(vector[1]), float(vector[2]))
                for vector in (position, forward, right, up)
            )
        except Exception:
            return (
                (0.0, 0.0, 100.0),
                (0.0, 0.0, -1.0),
                (1.0, 0.0, 0.0),
                (0.0, 1.0, 0.0),
            )

    def _camera_billboard_axes(
        self,
    ) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
        _position, _forward, right, up = self._camera_billboard_frame()
        return right, up

    def _update_gpu_asteroids(self, jd: float) -> float:
        if self._gpu_fatal_error:
            return 0.0
        if not self.gpu_active or self.gpu_renderer is None:
            self._gpu_active_count = 0
            return 0.0
        displayed = min(self._display_asteroid_count(), self._gpu_resident_count)
        active = (
            self._effective_animation_count(displayed)
            if self.clock.is_playing
            else displayed
        )
        camera_position, camera_forward, camera_right, camera_up = (
            self._camera_billboard_frame()
        )
        try:
            stats = self.gpu_renderer.update(
                jd,
                active,
                self._gpu_marker_scale_per_au(),
                camera_position,
                camera_forward,
                camera_right,
                camera_up,
                synchronize=True,
            )
        except Exception as exc:
            if type(exc).__name__ == "GpuRendererFatalError":
                self._gpu_fatal_error = str(exc)
                self.clock.pause()
            raise
        self._gpu_active_count = stats.active_count
        self._gpu_launch_seconds = stats.launch_seconds
        self._gpu_triangle_count = stats.triangle_count
        self._gpu_vertex_count = stats.vertex_count
        self._gpu_generation = stats.generation
        return stats.launch_seconds

    async def _compute_snapshot(self):
        when = self.clock.current()
        started = perf_counter()
        if self.gpu_active:
            snapshot = await self._in_worker(
                self.engine.compute_primary_snapshot,
                when,
            )
        else:
            asteroid_limit = self.display_asteroid_limit
            # The legacy SceneView path is intentionally safety-capped because
            # its native buffer rebuilds were the source of the 500k crash.
            cpu_static_cap = max(
                0,
                int(os.environ.get("OMNIVERSE_SOLAR_SYSTEM_CPU_FALLBACK_MAX", "250000")),
            )
            if asteroid_limit is None:
                asteroid_limit = min(cpu_static_cap, self.engine.asteroids.count)
            else:
                asteroid_limit = min(int(asteroid_limit), cpu_static_cap)
            asteroid_indices = None
            if self.clock.is_playing and asteroid_limit != 0:
                cpu_animation_cap = max(
                    0,
                    int(
                        os.environ.get(
                            "OMNIVERSE_SOLAR_SYSTEM_CPU_FALLBACK_ANIMATION_MAX",
                            "100000",
                        )
                    ),
                )
                requested_budget = self.animation_budget
                effective_budget = (
                    min(asteroid_limit, cpu_animation_cap)
                    if requested_budget is None
                    else min(int(requested_budget), cpu_animation_cap)
                )
                key = (effective_budget, asteroid_limit)
                asteroid_indices = self._playback_indices_cache.get(key)
                if asteroid_indices is None:
                    asteroid_indices = await self._in_worker(
                        self.engine.asteroid_playback_indices,
                        effective_budget,
                        asteroid_limit,
                    )
                    self._playback_indices_cache[key] = asteroid_indices
                asteroid_limit = None
            snapshot = await self._in_worker(
                self.engine.compute_snapshot,
                when,
                asteroid_limit,
                asteroid_indices,
            )
        return snapshot, perf_counter() - started

    def _build_scene(self, viewport, snapshot) -> float:
        started = perf_counter()
        if self.viewport_scene is None:
            self.viewport_scene = SolarSystemViewportScene(
                viewport,
                self.ext_id,
                batch_size=self.batch_size,
                orbit_alpha=self.orbit_alpha,
                orbit_thickness=self.orbit_thickness,
                render_asteroids=not self.gpu_active,
                planet_marker_radius=self.planet_marker_radius,
                asteroid_point_size=self.asteroid_dot_pixels,
                labels_enabled=self.labels_enabled,
            )
            self.viewport_scene.build(snapshot, self._orbit_lines)
        else:
            self.viewport_scene.rebuild_catalog(snapshot)
        self.viewport_scene.set_labels_enabled(self.labels_enabled)
        self._update_view_dependent_visibility(force=True)
        return perf_counter() - started

    def _camera_distance_from_origin(self) -> float | None:
        stage = self._stage
        viewport_window = self.viewport_window
        if stage is None or viewport_window is None:
            return None
        camera_prim = stage.GetPrimAtPath(viewport_window.viewport_api.camera_path)
        if not camera_prim.IsValid():
            return None
        world = UsdGeom.Xformable(camera_prim).ComputeLocalToWorldTransform(
            Usd.TimeCode.Default()
        )
        return float(world.ExtractTranslation().GetLength())

    def _update_view_dependent_visibility(self, *, force: bool = False) -> None:
        scene = self.viewport_scene
        viewport_window = self.viewport_window
        if scene is None or viewport_window is None:
            return
        now = perf_counter()
        if not force and now - self._last_view_poll < 0.10:
            return
        self._last_view_poll = now
        camera_distance = self._camera_distance_from_origin()
        if camera_distance is not None:
            scene.update_orbit_visibility(camera_distance)
        scene.update_label_visibility(viewport_window.viewport_api)

    def _camera_state_signature(self):
        stage = self._stage
        viewport_window = self.viewport_window
        if stage is None or viewport_window is None:
            return None
        try:
            camera_prim = stage.GetPrimAtPath(viewport_window.viewport_api.camera_path)
            world = UsdGeom.Xformable(camera_prim).ComputeLocalToWorldTransform(
                Usd.TimeCode.Default()
            )
            position = world.ExtractTranslation()
            right, up = self._camera_billboard_axes()
            values = (
                float(position[0]), float(position[1]), float(position[2]),
                *right, *up,
            )
            return tuple(round(value, 5) for value in values)
        except Exception:
            return None

    def _on_app_update(self, _event) -> None:
        if self._stopping:
            return
        self._update_view_dependent_visibility()
        # The asteroid triangles are camera-facing geometry. While simulation time
        # is paused, refresh them only when the camera actually changes, capped at
        # 30 Hz so interactive orbiting and zooming stay smooth.
        if self.gpu_active and not self.clock.is_playing:
            now = perf_counter()
            if now - self._last_gpu_camera_wake >= (1.0 / 30.0):
                signature = self._camera_state_signature()
                if signature is not None and signature != self._last_gpu_camera_signature:
                    self._last_gpu_camera_signature = signature
                    self._last_gpu_camera_wake = now
                    self._wake()

    def _record_update_frequency(self) -> None:
        completed = perf_counter()
        if self.clock.is_playing and self._last_update_completed_at is not None:
            elapsed = completed - self._last_update_completed_at
            if elapsed > 0.0:
                instantaneous = 1.0 / elapsed
                if self._actual_update_hz == 0.0:
                    self._actual_update_hz = instantaneous
                else:
                    self._actual_update_hz = (
                        0.80 * self._actual_update_hz + 0.20 * instantaneous
                    )
        elif not self.clock.is_playing:
            self._actual_update_hz = 0.0
        self._last_update_completed_at = completed

    async def _update_once(self, viewport) -> None:
        if self._gpu_fatal_error:
            self.clock.pause()
            self._set_status_text(
                "CUDA context invalid — close and restart Kit.\n"
                f"{self._gpu_fatal_error}",
                force=True,
            )
            return
        gpu_rebuild_seconds = 0.0
        if self._gpu_rebuild_requested:
            gpu_rebuild_seconds = await self._rebuild_gpu_renderer()
        snapshot, compute_seconds = await self._compute_snapshot()
        started = perf_counter()
        needs_rebuild = (
            self._rebuild_requested
            or self.viewport_scene is None
            or not self.viewport_scene.catalog_matches(snapshot)
        )
        if needs_rebuild:
            upload_seconds = self._build_scene(viewport, snapshot)
            self._rebuild_requested = False
        else:
            self.viewport_scene.update(snapshot)
            self._update_view_dependent_visibility(force=True)
            upload_seconds = perf_counter() - started
        gpu_seconds = self._update_gpu_asteroids(snapshot.jd_utc)
        self._record_update_frequency()
        self._set_status(
            snapshot,
            compute_seconds,
            upload_seconds,
            gpu_seconds,
            gpu_rebuild_seconds,
        )

    async def _wait_until_next_update(self, deadline: float | None) -> None:
        if deadline is None:
            await self._refresh_event.wait()
            self._refresh_event.clear()
            return
        timeout = max(0.0, deadline - perf_counter())
        try:
            await asyncio.wait_for(self._refresh_event.wait(), timeout=timeout)
            self._refresh_event.clear()
        except asyncio.TimeoutError:
            pass

    async def _run(self) -> None:
        try:
            self._set_status_text("Loading memory-mapped caches…")
            self.engine = await self._in_worker(SolarSystemEngine, PROJECT_ROOT)
            self.starmap_path = resolve_starmap_path(
                PROJECT_ROOT,
                raw_data_root=self.engine.raw_data_root,
            )
            viewport = await self._wait_for_viewport()
            stage = await self._wait_for_stage()
            if viewport is None or stage is None:
                return

            self._configure_stage_and_camera(stage, viewport)
            self._configure_starmap()
            self._hide_light_gizmos()
            self._set_grid_visible(False)
            await self._hide_default_scene_light()

            gpu_rebuild_seconds = 0.0
            if self._gpu_rebuild_requested:
                gpu_rebuild_seconds = await self._rebuild_gpu_renderer()
            self._set_status_text("Computing initial view…")
            snapshot, compute_seconds = await self._compute_snapshot()
            self._orbit_lines = await self._in_worker(
                self.engine.compute_orbit_lines,
                snapshot.when_utc,
                self.orbit_samples,
            )
            upload_seconds = self._build_scene(viewport, snapshot)
            gpu_seconds = self._update_gpu_asteroids(snapshot.jd_utc)
            self._rebuild_requested = False
            self._record_update_frequency()
            self._set_status(
                snapshot,
                compute_seconds,
                upload_seconds,
                gpu_seconds,
                gpu_rebuild_seconds,
            )

            next_deadline: float | None = None
            while not self._stopping:
                if self.clock.is_playing:
                    if next_deadline is None:
                        next_deadline = perf_counter()
                else:
                    next_deadline = None

                await self._wait_until_next_update(next_deadline)
                if self._stopping:
                    break

                try:
                    await self._update_once(viewport)
                except Exception as exc:
                    self.clock.pause()
                    self._rebuild_requested = True
                    self._set_status_text(
                        f"Playback paused: {type(exc).__name__}: {exc}\n"
                        "Press Now to return to the current epoch.",
                        force=True,
                    )
                    print(f"[Omniverse Solar System] {type(exc).__name__}: {exc}")
                    next_deadline = None
                    continue

                if self.clock.is_playing:
                    interval = 1.0 / self.playback_target_hz
                    now = perf_counter()
                    base = next_deadline if next_deadline is not None else now
                    next_deadline = max(base + interval, now)
                else:
                    next_deadline = None
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            self._set_status_text(
                f"Error: {type(exc).__name__}: {exc}", force=True
            )
            print(f"[Omniverse Solar System] {type(exc).__name__}: {exc}")

    def _set_status_text(self, text: str, *, force: bool = False) -> None:
        """Store diagnostics continuously but repaint the optional label sparingly."""
        self._status_text = text
        label = self.status_label
        if label is None or not self.status_readout_enabled:
            return
        now = perf_counter()
        minimum_interval = 0.25 if self.clock.is_playing else 0.0
        if (
            not force
            and minimum_interval > 0.0
            and now - self._last_status_label_update < minimum_interval
        ):
            return
        label.text = text
        self._last_status_label_update = now

    def _set_status(
        self,
        snapshot,
        compute_seconds: float,
        upload_seconds: float,
        gpu_seconds: float = 0.0,
        gpu_rebuild_seconds: float = 0.0,
    ) -> None:
        timestamp = snapshot.when_utc.strftime("%Y-%m-%d %H:%M:%S UTC")
        total_asteroids = self.engine.asteroids.count if self.engine else 0
        batches = self.viewport_scene.point_batch_count if self.viewport_scene else 0
        visible_orbits = self.viewport_scene.visible_orbit_count if self.viewport_scene else 0
        visible_labels = self.viewport_scene.visible_label_count if self.viewport_scene else 0
        state = format_playback_rate(self.clock.rate)
        update_text = (
            f"{self._actual_update_hz:.1f} updates/s" if self.clock.is_playing else "paused"
        )
        selected_display = DISPLAY_ASTEROID_LABELS[self.display_index]
        selected_animation = ANIMATION_BUDGET_LABELS[self.budget_index]
        gpu_display_available = (
            min(self._display_asteroid_count(), self._gpu_resident_count)
            if self.gpu_active
            else None
        )
        effective_animation = self._effective_animation_count(gpu_display_available)
        if self.gpu_active:
            rendered_asteroids = self._gpu_active_count
            backend = f"GPU/Fabric deformable mesh · generation {self._gpu_generation}"
            asteroid_detail = (
                f"{rendered_asteroids:,} active / {self._gpu_resident_count:,} resident · "
                f"{self._gpu_triangle_count:,} triangles / {self._gpu_vertex_count:,} vertices"
            )
            timing_detail = (
                f"CPU {compute_seconds:.3f}s · Fabric submit {gpu_seconds * 1000.0:.2f}ms"
            )
            if gpu_rebuild_seconds > 0.0:
                timing_detail += f" · rebuild {gpu_rebuild_seconds:.2f}s"
        else:
            rendered_asteroids = len(snapshot.asteroid_positions)
            backend = "CPU fallback"
            asteroid_detail = f"{rendered_asteroids:,}/{total_asteroids:,} rendered"
            timing_detail = f"compute {compute_seconds:.3f}s · upload {upload_seconds:.3f}s"
        failure_line = (
            f"\nGPU fallback reason: {self._gpu_failure}"
            if self._gpu_failure
            else ""
        )
        if self._starmap_loaded:
            background_detail = (
                f"stars {STARMAP_EXPOSURE_LABELS[self.starmap_exposure_index].lower()}"
            )
        elif self._starmap_error:
            background_detail = "stars missing"
        else:
            background_detail = "stars off"
        self._set_status_text(
            f"{timestamp} · {state} · {update_text}\n"
            f"asteroids: {selected_display} · playback: {selected_animation} "
            f"(effective {effective_animation:,}) · camera: oblique\n"
            f"{len(PLANET_TARGETS)} planets · {asteroid_detail} · "
            f"dots {self.planet_marker_radius:g}px/{self.asteroid_dot_pixels:g}px\n"
            f"{backend} · J2000 Z-up · {background_detail} · "
            f"{visible_orbits}/{len(PLANET_TARGETS)} orbits · "
            f"{visible_labels}/{len(PLANET_TARGETS)} labels · {timing_detail} · "
            f"{batches} UI point batches{failure_line}"
        )

    def on_shutdown(self) -> None:
        self._stopping = True
        if hasattr(self, "_refresh_event"):
            self._refresh_event.set()
        if self.task is not None:
            self.task.cancel()
            self.task = None
        self._camera_update_sub = None
        self._destroy_gpu_renderer()
        if self.viewport_scene is not None:
            self.viewport_scene.destroy()
            self.viewport_scene = None
        if self.engine is not None:
            self.engine.close()
            self.engine = None
        self._restore_grid_visibility()
        self._restore_default_scene_light()
        self._restore_rtx_background_source()
        self._restore_stage_and_camera()
        self.status_label = None
        self.display_combo = None
        self.animation_combo = None
        self.speed_combo = None
        self.planet_size_combo = None
        self.asteroid_size_combo = None
        self.starmap_exposure_combo = None
        self.labels_model = None
        self.grid_model = None
        self.status_model = None
        self.starmap_model = None
        self._starmap_dome = None
        if getattr(self, "window", None) is not None:
            self.window.destroy()
            self.window = None
