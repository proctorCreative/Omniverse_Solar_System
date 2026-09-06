"""Omniverse viewport overlay made from shadeless screen-space graphics."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import math

import numpy as np
import omni.ui as ui
from omni.ui import scene as sc
from pxr import Gf

from omniverse_solar_system.constants import PLANET_COLORS
from omniverse_solar_system.engine import PositionSnapshot
from omniverse_solar_system.label_layout import (
    LabelCandidate,
    choose_non_overlapping_labels,
)
from omniverse_solar_system.orbit_visibility import (
    full_orbit_is_projection_safe,
    orbit_max_radius,
)
from omniverse_solar_system.render_batches import (
    iter_owned_position_batches,
    owned_float32_positions,
)


@dataclass
class SceneViewHandle:
    frame: ui.Frame
    scene_view: sc.SceneView


@dataclass
class PointBatch:
    handle: SceneViewHandle
    shape: sc.Points
    start: int
    stop: int
    positions: np.ndarray


@dataclass
class CircularMarker:
    # Keep astronomical translation in world space. Screen-space rescaling must
    # live on a child transform; otherwise Kit rescales the translation matrix.
    position_transform: sc.Transform
    screen_transform: sc.Transform
    shape: sc.Arc


@dataclass
class PlanetLabel:
    name: str
    position_transform: sc.Transform
    screen_transform: sc.Transform
    offset_transform: sc.Transform
    shape: sc.Label
    position: np.ndarray


@dataclass
class OrbitCurve:
    name: str
    shape: sc.Curve
    max_radius: float


class SolarSystemViewportScene:
    """Persistent primary-body scene plus replaceable point-catalog batches."""

    def __init__(
        self,
        viewport_window,
        ext_id: str,
        batch_size: int = 100_000,
        orbit_alpha: float = 0.50,
        orbit_thickness: float = 1.25,
        render_asteroids: bool = True,
        planet_marker_radius: float = 3.25,
        asteroid_point_size: float = 1.0,
        labels_enabled: bool = True,
    ) -> None:
        self.viewport_window = viewport_window
        self.ext_id = ext_id
        self.batch_size = int(batch_size)
        if self.batch_size <= 0:
            raise ValueError("batch_size must be greater than zero")

        self.orbit_alpha = min(1.0, max(0.0, float(orbit_alpha)))
        self.orbit_thickness = max(0.1, float(orbit_thickness))
        self.render_asteroids = bool(render_asteroids)
        self.planet_marker_radius = max(1.0, float(planet_marker_radius))
        self.asteroid_point_size = max(0.25, float(asteroid_point_size))

        self.base_handle: SceneViewHandle | None = None
        self.sun_marker: CircularMarker | None = None
        self.planet_markers: list[CircularMarker] = []
        self.planet_labels: list[PlanetLabel] = []
        self.asteroid_batches: list[PointBatch] = []
        self.orbit_curves: list[OrbitCurve] = []
        self._last_camera_distance: float | None = None
        self._labels_enabled = bool(labels_enabled)
        self.asteroid_count = 0

    def _create_scene_view(self, suffix: str) -> SceneViewHandle:
        frame_id = self.ext_id if suffix == "base" else f"{self.ext_id}.{suffix}"
        frame = self.viewport_window.get_frame(frame_id)
        frame.clear()
        with frame:
            scene_view = sc.SceneView()
            scene_view.cache_draw_buffer = True
            self.viewport_window.viewport_api.add_scene_view(scene_view)
        return SceneViewHandle(frame=frame, scene_view=scene_view)

    def _destroy_handle(self, handle: SceneViewHandle | None) -> None:
        if handle is None:
            return
        scene_view = handle.scene_view
        if self.viewport_window is not None:
            self.viewport_window.viewport_api.remove_scene_view(scene_view)
        scene_view.visible = False
        scene_view.scene.clear()
        handle.frame.clear()

    @staticmethod
    def _points(positions: np.ndarray, *, colors, sizes) -> sc.Points:
        owned = owned_float32_positions(positions)
        try:
            return sc.Points(owned, colors=colors, sizes=sizes)
        except TypeError:
            return sc.Points(owned.tolist(), colors=colors, sizes=sizes)

    @staticmethod
    def _curve(positions: np.ndarray, *, color, thickness: float) -> sc.Curve:
        owned = owned_float32_positions(positions)
        try:
            return sc.Curve(
                owned,
                colors=[color],
                thicknesses=[float(thickness)],
                curve_type=sc.Curve.CurveType.LINEAR,
            )
        except TypeError:
            return sc.Curve(
                owned.tolist(),
                colors=[color],
                thicknesses=[float(thickness)],
                curve_type=sc.Curve.CurveType.LINEAR,
            )

    @staticmethod
    def _translation(position: np.ndarray) -> sc.Matrix44:
        x, y, z = (float(value) for value in position)
        return sc.Matrix44.get_translation_matrix(x, y, z)

    @staticmethod
    def _with_alpha(color, alpha: float):
        red, green, blue = (float(value) for value in color[:3])
        source_alpha = float(color[3]) if len(color) > 3 else 1.0
        return (red, green, blue, min(source_alpha, float(alpha)))

    @classmethod
    def _circular_marker(
        cls,
        position: np.ndarray,
        *,
        color,
        radius: float,
    ) -> CircularMarker:
        position_transform = sc.Transform(transform=cls._translation(position))
        with position_transform:
            screen_transform = sc.Transform(
                scale_to=sc.Space.SCREEN,
                look_at=sc.Transform.LookAt.CAMERA,
            )
            with screen_transform:
                shape = sc.Arc(
                    float(radius),
                    axis=2,
                    begin=0.0,
                    end=math.tau,
                    color=color,
                    tesselation=32,
                    wireframe=False,
                )
        return CircularMarker(position_transform, screen_transform, shape)

    @classmethod
    def _planet_label(
        cls,
        name: str,
        position: np.ndarray,
        *,
        color,
        visible: bool = True,
    ) -> PlanetLabel:
        position_transform = sc.Transform(transform=cls._translation(position))
        with position_transform:
            screen_transform = sc.Transform(
                scale_to=sc.Space.SCREEN,
                look_at=sc.Transform.LookAt.CAMERA,
            )
            with screen_transform:
                # The offset lives below the screen-space transform, so these
                # coordinates behave like pixels rather than astronomical units.
                offset_transform = sc.Transform(
                    transform=sc.Matrix44.get_translation_matrix(7.0, 7.0, 0.0)
                )
                with offset_transform:
                    shape = sc.Label(
                        name,
                        color=cls._with_alpha(color, 0.92),
                        size=13.0,
                        alignment=ui.Alignment.LEFT_CENTER,
                        visible=bool(visible),
                    )
        return PlanetLabel(
            name=name,
            position_transform=position_transform,
            screen_transform=screen_transform,
            offset_transform=offset_transform,
            shape=shape,
            position=np.ascontiguousarray(position, dtype=np.float32),
        )

    def build(
        self,
        snapshot: PositionSnapshot,
        orbit_lines: Mapping[str, np.ndarray],
    ) -> None:
        if self.base_handle is not None:
            raise RuntimeError("Base viewport scene is already built.")

        self.base_handle = self._create_scene_view("base")
        with self.base_handle.scene_view.scene:
            self.sun_marker = self._circular_marker(
                np.zeros(3, dtype=np.float32),
                color=(1.0, 0.88, 0.30, 1.0),
                radius=self.planet_marker_radius * (5.0 / 3.25),
            )

            for index, position in enumerate(snapshot.planet_positions):
                color = PLANET_COLORS[index]
                radius = (
                    self.planet_marker_radius
                    if snapshot.planet_names[index] != "Pluto"
                    else self.planet_marker_radius * (2.75 / 3.25)
                )
                self.planet_markers.append(
                    self._circular_marker(position, color=color, radius=radius)
                )
                self.planet_labels.append(
                    self._planet_label(
                        snapshot.planet_names[index],
                        position,
                        color=color,
                        visible=self._labels_enabled,
                    )
                )

            for index, planet_name in enumerate(snapshot.planet_names):
                points = orbit_lines.get(planet_name)
                if points is None or len(points) == 0:
                    continue
                curve = self._curve(
                    points,
                    color=self._with_alpha(PLANET_COLORS[index], self.orbit_alpha),
                    thickness=self.orbit_thickness,
                )
                self.orbit_curves.append(
                    OrbitCurve(
                        name=planet_name,
                        shape=curve,
                        max_radius=orbit_max_radius(points),
                    )
                )

        self.rebuild_catalog(snapshot)

    def rebuild_catalog(self, snapshot: PositionSnapshot) -> None:
        self._destroy_catalog_views()
        if self.render_asteroids:
            self.asteroid_batches = self._build_batch_views(
                snapshot.asteroid_positions,
                kind="asteroids",
                color=(0.78, 0.80, 0.84, 0.72),
                size=self.asteroid_point_size,
            )
        else:
            self.asteroid_batches = []
        self.asteroid_count = len(snapshot.asteroid_positions) if self.render_asteroids else 0
        self._update_primary_positions(snapshot)
        if self._last_camera_distance is not None:
            self.update_orbit_visibility(self._last_camera_distance)

    def catalog_matches(self, snapshot: PositionSnapshot) -> bool:
        asteroid_matches = (
            self.asteroid_count == len(snapshot.asteroid_positions)
            if self.render_asteroids
            else True
        )
        return asteroid_matches

    def _build_batch_views(
        self,
        positions: np.ndarray,
        *,
        kind: str,
        color,
        size: float,
    ) -> list[PointBatch]:
        batches: list[PointBatch] = []
        for index, (start, stop, owned) in enumerate(
            iter_owned_position_batches(positions, self.batch_size)
        ):
            handle = self._create_scene_view(f"{kind}.{index}")
            with handle.scene_view.scene:
                shape = self._points(owned, colors=[color], sizes=[float(size)])
            batches.append(PointBatch(handle, shape, start, stop, owned))
        return batches

    @staticmethod
    def _assign_positions(batch: PointBatch, positions: np.ndarray) -> None:
        owned = owned_float32_positions(positions)
        batch.positions = owned
        try:
            batch.shape.positions = owned
        except TypeError:
            batch.shape.positions = owned.tolist()

    def _update_primary_positions(self, snapshot: PositionSnapshot) -> None:
        if len(self.planet_markers) != len(snapshot.planet_positions):
            raise RuntimeError("Primary-body count changed; rebuild the viewport scene.")
        for marker, label, position in zip(
            self.planet_markers,
            self.planet_labels,
            snapshot.planet_positions,
        ):
            transform = self._translation(position)
            marker.position_transform.transform = transform
            label.position_transform.transform = transform
            label.position = np.ascontiguousarray(position, dtype=np.float32)

    def update(self, snapshot: PositionSnapshot) -> None:
        if not self.catalog_matches(snapshot):
            raise RuntimeError(
                "Point count changed. Rebuild the catalog views before updating."
            )
        self._update_primary_positions(snapshot)
        if self.render_asteroids:
            self._update_batches(self.asteroid_batches, snapshot.asteroid_positions)

    def _update_batches(self, batches: list[PointBatch], positions: np.ndarray) -> None:
        for batch in batches:
            self._assign_positions(batch, positions[batch.start : batch.stop])

    def set_labels_enabled(self, enabled: bool) -> None:
        self._labels_enabled = bool(enabled)
        if not self._labels_enabled:
            for label in self.planet_labels:
                label.shape.visible = False

    def update_label_visibility(self, viewport_api) -> bool:
        """Project nine labels to pixels and greedily suppress overlaps."""
        if not self.planet_labels:
            return False
        if not self._labels_enabled:
            changed = False
            for label in self.planet_labels:
                if bool(label.shape.visible):
                    label.shape.visible = False
                    changed = True
            return changed

        try:
            width, height = viewport_api.resolution
            world_to_ndc = viewport_api.world_to_ndc
        except Exception:
            return False
        if width <= 0 or height <= 0:
            return False

        candidates: list[LabelCandidate] = []
        for index, label in enumerate(self.planet_labels):
            try:
                ndc = world_to_ndc.Transform(Gf.Vec3d(*map(float, label.position)))
                x_ndc, y_ndc, z_ndc = (float(ndc[0]), float(ndc[1]), float(ndc[2]))
            except Exception:
                continue
            if not all(math.isfinite(value) for value in (x_ndc, y_ndc, z_ndc)):
                continue
            # A generous viewport margin avoids labels popping at the exact edge.
            if abs(x_ndc) > 1.15 or abs(y_ndc) > 1.15:
                continue
            pixel_x = (x_ndc * 0.5 + 0.5) * float(width)
            pixel_y = (0.5 - y_ndc * 0.5) * float(height)
            radial_priority = math.hypot(pixel_x - width * 0.5, pixel_y - height * 0.5)
            candidates.append(
                LabelCandidate(index, label.name, pixel_x, pixel_y, radial_priority)
            )

        visible_indices = choose_non_overlapping_labels(
            candidates,
            viewport_width=float(width),
            viewport_height=float(height),
        )
        changed = False
        for index, label in enumerate(self.planet_labels):
            visible = index in visible_indices
            if bool(label.shape.visible) != visible:
                label.shape.visible = visible
                changed = True
        return changed

    def update_orbit_visibility(self, camera_distance: float) -> bool:
        self._last_camera_distance = float(camera_distance)
        changed = False
        for orbit in self.orbit_curves:
            visible = full_orbit_is_projection_safe(
                self._last_camera_distance,
                orbit.max_radius,
                margin=1.05,
            )
            if bool(orbit.shape.visible) != visible:
                orbit.shape.visible = visible
                changed = True
        return changed

    def _destroy_catalog_views(self) -> None:
        for batch in self.asteroid_batches:
            self._destroy_handle(batch.handle)
        self.asteroid_batches.clear()
        self.asteroid_count = 0

    @property
    def point_batch_count(self) -> int:
        return len(self.asteroid_batches)

    @property
    def visible_orbit_count(self) -> int:
        return sum(bool(orbit.shape.visible) for orbit in self.orbit_curves)

    @property
    def visible_label_count(self) -> int:
        return sum(bool(label.shape.visible) for label in self.planet_labels)

    def destroy(self) -> None:
        self._destroy_catalog_views()
        self._destroy_handle(self.base_handle)
        self.base_handle = None
        self.sun_marker = None
        self.planet_markers.clear()
        self.planet_labels.clear()
        self.orbit_curves.clear()
        self.viewport_window = None
