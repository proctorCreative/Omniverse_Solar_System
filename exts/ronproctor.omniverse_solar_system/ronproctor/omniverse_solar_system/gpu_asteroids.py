"""GPU-resident asteroid propagation using generation-safe deformable meshes.

One tiny camera-facing triangle represents each asteroid. Orbital elements stay in
persistent Warp CUDA arrays. Mesh growth is handled by creating a new generation
at a unique USD path, waiting until Fabric exposes the exact expected vertex count,
then swapping renderers only after the new generation has completed a verified GPU
update. This prevents a larger CUDA launch from ever writing into an older, smaller
Fabric buffer.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from time import perf_counter

import carb.settings
import numpy as np
import omni.kit.app
import omni.usd
from pxr import Gf, Sdf, Usd, UsdGeom, UsdShade, Vt
import warp as wp
from usdrt import Gf as RtGf
from usdrt import Rt
from usdrt import Sdf as RtSdf
from usdrt import Usd as RtUsd

from omniverse_solar_system.gpu_catalog import PackedGpuAsteroids


GPU_ASTEROID_PATH_PREFIX = "/OmniverseSolarSystem/GPUAsteroids_G"
GPU_MATERIAL_PATH_PREFIX = "/OmniverseSolarSystem/Materials/Asteroids_G"
TARGET_ATTR_PREFIX = "solar:gpuAsteroidMeshTarget_g"
DEVICE = "cuda:0"
VERTICES_PER_ASTEROID = 3
_TWO_PI = 2.0 * math.pi
_PI = math.pi
_SQRT3_OVER_2 = 0.8660254037844386


class GpuRendererFatalError(RuntimeError):
    """A CUDA fault that requires Kit to be restarted."""


def _cuda_error_is_fatal(exc: BaseException) -> bool:
    text = f"{type(exc).__name__}: {exc}".lower()
    return any(
        token in text
        for token in (
            "cudaerrorillegaladdress",
            "illegal memory access",
            "cuda error 700",
            "error 700",
            "context is destroyed",
            "launch failed",
        )
    )


def _pxr_vec3f_array(values: np.ndarray) -> Vt.Vec3fArray:
    array = np.ascontiguousarray(values, dtype=np.float32)
    from_numpy = getattr(Vt.Vec3fArray, "FromNumpy", None)
    if from_numpy is not None:
        return from_numpy(array)
    return Vt.Vec3fArray(
        [Gf.Vec3f(float(x), float(y), float(z)) for x, y, z in array]
    )


def _pxr_int_array(values: np.ndarray) -> Vt.IntArray:
    array = np.ascontiguousarray(values, dtype=np.int32)
    from_numpy = getattr(Vt.IntArray, "FromNumpy", None)
    if from_numpy is not None:
        return from_numpy(array)
    return Vt.IntArray([int(value) for value in array])


@wp.kernel(enable_backward=False)
def _propagate_elliptic_asteroid_mesh(
    semi_major_axis: wp.array(dtype=wp.float32),
    eccentricity: wp.array(dtype=wp.float32),
    mean_anomaly_epoch: wp.array(dtype=wp.float32),
    mean_motion: wp.array(dtype=wp.float32),
    epoch_jd: wp.array(dtype=wp.float32),
    basis_p: wp.array(dtype=wp.vec3f),
    basis_q: wp.array(dtype=wp.vec3f),
    points: wp.fabricarrayarray(dtype=wp.vec3f),
    jd: wp.float32,
    active_count: wp.int32,
    resident_count: wp.int32,
    vertex_capacity: wp.int32,
    marker_scale: wp.float32,
    camera_position: wp.vec3f,
    camera_forward: wp.vec3f,
    camera_right: wp.vec3f,
    camera_up: wp.vec3f,
):
    asteroid_id = wp.tid()
    if asteroid_id >= resident_count:
        return

    vertex_base = asteroid_id * VERTICES_PER_ASTEROID
    if vertex_base < 0 or vertex_base + 2 >= vertex_capacity:
        return

    if asteroid_id >= active_count:
        # Degenerate inactive triangles have zero area and therefore generate no
        # fragments, while preserving one fixed topology for the resident mesh.
        hidden = wp.vec3f(0.0, 0.0, 0.0)
        points[0, vertex_base] = hidden
        points[0, vertex_base + 1] = hidden
        points[0, vertex_base + 2] = hidden
        return

    a = semi_major_axis[asteroid_id]
    e = eccentricity[asteroid_id]
    mean = mean_anomaly_epoch[asteroid_id] + mean_motion[asteroid_id] * (
        jd - epoch_jd[asteroid_id]
    )
    mean = mean - wp.float32(_TWO_PI) * wp.floor(
        (mean + wp.float32(_PI)) / wp.float32(_TWO_PI)
    )

    estimate = mean
    if e >= wp.float32(0.8):
        sign_value = wp.float32(1.0)
        if wp.sin(mean) < wp.float32(0.0):
            sign_value = wp.float32(-1.0)
        estimate = mean + sign_value * wp.float32(0.85) * e

    for _iteration in range(12):
        estimate = estimate - (
            estimate - e * wp.sin(estimate) - mean
        ) / (wp.float32(1.0) - e * wp.cos(estimate))

    x_pf = a * (wp.cos(estimate) - e)
    y_pf = a * wp.sqrt(
        wp.max(wp.float32(0.0), wp.float32(1.0) - e * e)
    ) * wp.sin(estimate)
    center = basis_p[asteroid_id] * x_pf + basis_q[asteroid_id] * y_pf

    depth = wp.dot(center - camera_position, camera_forward)
    radius = marker_scale * wp.max(depth, wp.float32(0.0))
    points[0, vertex_base] = center + camera_up * radius
    points[0, vertex_base + 1] = center + (
        camera_right * wp.float32(-_SQRT3_OVER_2)
        + camera_up * wp.float32(-0.5)
    ) * radius
    points[0, vertex_base + 2] = center + (
        camera_right * wp.float32(_SQRT3_OVER_2)
        + camera_up * wp.float32(-0.5)
    ) * radius


@dataclass(frozen=True)
class GpuUpdateStats:
    launch_seconds: float
    active_count: int
    resident_count: int
    triangle_count: int
    vertex_count: int
    marker_scale_per_au: float
    generation: int


class GpuAsteroidRenderer:
    """One generation-specific deformable mesh updated directly by Warp CUDA."""

    def __init__(
        self,
        packed: PackedGpuAsteroids,
        *,
        generation: int,
        color: tuple[float, float, float] = (0.82, 0.84, 0.88),
        opacity: float = 0.78,
    ) -> None:
        if not wp.is_cuda_available():
            raise RuntimeError("CUDA is unavailable to NVIDIA Warp")
        if not bool(
            carb.settings.get_settings().get_as_bool("/app/useFabricSceneDelegate")
        ):
            raise RuntimeError(
                "Fabric Scene Delegate is disabled. Launch Kit with "
                "--/app/useFabricSceneDelegate=1"
            )
        wp.init()
        self.generation = max(1, int(generation))
        suffix = f"{self.generation:06d}"
        self.mesh_path_string = f"{GPU_ASTEROID_PATH_PREFIX}{suffix}"
        self.material_path_string = f"{GPU_MATERIAL_PATH_PREFIX}{suffix}"
        self.target_attr = f"{TARGET_ATTR_PREFIX}{suffix}"
        self.packed = packed
        self.count = int(packed.count)
        self.vertex_count = self.count * VERTICES_PER_ASTEROID
        self.bound_vertex_count = 0
        self.color = tuple(float(value) for value in color)
        self.opacity = float(opacity)
        self.usd_stage = omni.usd.get_context().get_stage()
        if self.usd_stage is None:
            raise RuntimeError("No active USD stage")
        self.rt_stage = None
        self.rt_prim = None
        self.selection = None
        self.fabric_points = None
        self.failed = False
        self._create_cuda_inputs()
        self._create_usd_mesh()

    def _create_cuda_inputs(self) -> None:
        with wp.ScopedDevice(DEVICE):
            self.a_cuda = wp.array(
                self.packed.semi_major_axis, dtype=wp.float32, device=DEVICE
            )
            self.e_cuda = wp.array(
                self.packed.eccentricity, dtype=wp.float32, device=DEVICE
            )
            self.m0_cuda = wp.array(
                self.packed.mean_anomaly_epoch, dtype=wp.float32, device=DEVICE
            )
            self.n_cuda = wp.array(
                self.packed.mean_motion, dtype=wp.float32, device=DEVICE
            )
            self.epoch_cuda = wp.array(
                self.packed.epoch_jd, dtype=wp.float32, device=DEVICE
            )
            self.basis_p_cuda = wp.array(
                self.packed.basis_p_j2000, dtype=wp.vec3f, device=DEVICE
            )
            self.basis_q_cuda = wp.array(
                self.packed.basis_q_j2000, dtype=wp.vec3f, device=DEVICE
            )

    def _create_usd_mesh(self) -> None:
        path = Sdf.Path(self.mesh_path_string)
        material_path = Sdf.Path(self.material_path_string)
        radius = max(100.0, self.packed.max_apoapsis_au * 1.10)
        zero_points = np.zeros((self.vertex_count, 3), dtype=np.float32)
        face_counts = np.full(self.count, VERTICES_PER_ASTEROID, dtype=np.int32)
        face_indices = np.arange(self.vertex_count, dtype=np.int32)

        with Usd.EditContext(self.usd_stage, self.usd_stage.GetSessionLayer()):
            if self.usd_stage.GetPrimAtPath(path).IsValid():
                self.usd_stage.RemovePrim(path)
            if self.usd_stage.GetPrimAtPath(material_path).IsValid():
                self.usd_stage.RemovePrim(material_path)

            mesh = UsdGeom.Mesh.Define(self.usd_stage, path)
            mesh.CreatePointsAttr().Set(_pxr_vec3f_array(zero_points))
            mesh.CreateFaceVertexCountsAttr().Set(_pxr_int_array(face_counts))
            mesh.CreateFaceVertexIndicesAttr().Set(_pxr_int_array(face_indices))
            mesh.CreateSubdivisionSchemeAttr().Set(UsdGeom.Tokens.none)
            mesh.CreateDoubleSidedAttr().Set(True)
            mesh.CreateExtentAttr().Set(
                Vt.Vec3fArray(
                    [
                        Gf.Vec3f(-radius, -radius, -radius),
                        Gf.Vec3f(radius, radius, radius),
                    ]
                )
            )
            mesh.GetPrim().CreateAttribute(
                self.target_attr, Sdf.ValueTypeNames.Int, custom=True
            ).Set(self.generation)

            primvars = UsdGeom.PrimvarsAPI(mesh.GetPrim())
            primvars.CreatePrimvar(
                "displayColor",
                Sdf.ValueTypeNames.Color3fArray,
                UsdGeom.Tokens.constant,
            ).Set(Vt.Vec3fArray([Gf.Vec3f(*self.color)]))
            primvars.CreatePrimvar(
                "displayOpacity",
                Sdf.ValueTypeNames.FloatArray,
                UsdGeom.Tokens.constant,
            ).Set(Vt.FloatArray([self.opacity]))

            material = UsdShade.Material.Define(self.usd_stage, material_path)
            shader = UsdShade.Shader.Define(
                self.usd_stage, material_path.AppendChild("PreviewSurface")
            )
            shader.CreateIdAttr("UsdPreviewSurface")
            shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(
                Gf.Vec3f(*self.color)
            )
            shader.CreateInput("emissiveColor", Sdf.ValueTypeNames.Color3f).Set(
                Gf.Vec3f(*self.color)
            )
            shader.CreateInput("opacity", Sdf.ValueTypeNames.Float).Set(self.opacity)
            shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(1.0)
            shader.CreateOutput("surface", Sdf.ValueTypeNames.Token)
            material.CreateSurfaceOutput().ConnectToSource(
                shader.ConnectableAPI(), "surface"
            )
            UsdShade.MaterialBindingAPI.Apply(mesh.GetPrim()).Bind(material)

    async def bind_fabric(self, max_frames: int = 600) -> None:
        """Wait for this exact generation and its exact vertex capacity in Fabric."""
        app = omni.kit.app.get_app()
        stage_id = omni.usd.get_context().get_stage_id()
        self.rt_stage = RtUsd.Stage.Attach(stage_id)
        path = RtSdf.Path(self.mesh_path_string)
        last_observed = -1
        for _ in range(max_frames):
            prim = self.rt_stage.GetPrimAtPath(path)
            if prim.IsValid() and prim.GetTypeName() == "Mesh":
                points_attr = prim.GetAttribute("points")
                if points_attr.IsValid():
                    try:
                        observed = len(points_attr.Get())
                    except Exception:
                        observed = -1
                    last_observed = observed
                    if observed == self.vertex_count:
                        self.rt_prim = prim
                        self.bound_vertex_count = observed
                        break
            await app.next_update_async()
        if self.rt_prim is None or not self.rt_prim.IsValid():
            raise RuntimeError(
                f"{self.mesh_path_string} did not expose the expected "
                f"{self.vertex_count:,} Fabric vertices after {max_frames} frames "
                f"(last observed {last_observed:,})"
            )

        if not self.rt_prim.HasAttribute("Deformable"):
            self.rt_prim.CreateAttribute(
                "Deformable", RtSdf.ValueTypeNames.PrimTypeTag, True
            )
        radius = max(100.0, self.packed.max_apoapsis_au * 1.10)
        Rt.Boundable(self.rt_prim).CreateWorldExtentAttr().Set(
            RtGf.Range3d(
                RtGf.Vec3d(-radius, -radius, -radius),
                RtGf.Vec3d(radius, radius, radius),
            )
        )
        identity = RtGf.Matrix4d(1.0)
        xform = Rt.Xformable(self.rt_prim)
        xform.CreateFabricHierarchyLocalMatrixAttr().Set(identity)
        xform.CreateFabricHierarchyWorldMatrixAttr().Set(identity)
        self._bind_writable_points()

    def _bind_writable_points(self) -> None:
        if self.rt_stage is None:
            raise RuntimeError("Fabric stage is not attached")
        # Release the previous Python wrappers before creating the fresh ReadWrite
        # access that signals Fabric change tracking for this frame.
        self.fabric_points = None
        self.selection = None
        self.selection = self.rt_stage.SelectPrims(
            require_attrs=[
                (
                    RtSdf.ValueTypeNames.Point3fArray,
                    "points",
                    RtUsd.Access.ReadWrite,
                ),
                (RtSdf.ValueTypeNames.Int, self.target_attr, RtUsd.Access.Read),
            ],
            require_prim_type="Mesh",
            device=DEVICE,
        )
        selected = int(self.selection.GetCount())
        if selected != 1:
            raise RuntimeError(
                f"Expected one tagged GPU asteroid Mesh generation {self.generation}; "
                f"selected {selected}"
            )
        with wp.ScopedDevice(DEVICE):
            self.fabric_points = wp.fabricarrayarray(
                data=self.selection, attrib="points"
            )

    def update(
        self,
        jd: float,
        active_count: int,
        marker_scale_per_au: float,
        camera_position: tuple[float, float, float],
        camera_forward: tuple[float, float, float],
        camera_right: tuple[float, float, float],
        camera_up: tuple[float, float, float],
        *,
        synchronize: bool = True,
    ) -> GpuUpdateStats:
        if self.failed:
            raise GpuRendererFatalError(
                "GPU asteroid renderer is disabled after a CUDA fault; restart Kit"
            )
        if self.count == 0:
            return GpuUpdateStats(
                0.0, 0, 0, 0, 0, float(marker_scale_per_au), self.generation
            )
        if self.bound_vertex_count != self.vertex_count:
            raise RuntimeError(
                f"Generation {self.generation} capacity mismatch: expected "
                f"{self.vertex_count:,} vertices, bound {self.bound_vertex_count:,}"
            )

        active = max(0, min(int(active_count), self.count))
        marker_scale = max(0.0, float(marker_scale_per_au))
        started = perf_counter()
        try:
            # Reacquiring ReadWrite access every update is intentional: in Kit
            # 110.1.3 this records a fresh Fabric change-tracking event before CUDA.
            self._bind_writable_points()
            with wp.ScopedDevice(DEVICE):
                wp.launch(
                    kernel=_propagate_elliptic_asteroid_mesh,
                    dim=self.count,
                    inputs=[
                        self.a_cuda,
                        self.e_cuda,
                        self.m0_cuda,
                        self.n_cuda,
                        self.epoch_cuda,
                        self.basis_p_cuda,
                        self.basis_q_cuda,
                        self.fabric_points,
                        np.float32(jd),
                        np.int32(active),
                        np.int32(self.count),
                        np.int32(self.bound_vertex_count),
                        np.float32(marker_scale),
                        wp.vec3f(*camera_position),
                        wp.vec3f(*camera_forward),
                        wp.vec3f(*camera_right),
                        wp.vec3f(*camera_up),
                    ],
                    device=DEVICE,
                )
                if synchronize:
                    wp.synchronize_device(DEVICE)
        except Exception as exc:
            if _cuda_error_is_fatal(exc):
                self.failed = True
                raise GpuRendererFatalError(
                    "CUDA illegal-memory fault detected. The CUDA context is no "
                    "longer safe; close and restart Kit."
                ) from exc
            raise

        return GpuUpdateStats(
            launch_seconds=perf_counter() - started,
            active_count=active,
            resident_count=self.count,
            triangle_count=self.count,
            vertex_count=self.vertex_count,
            marker_scale_per_au=marker_scale,
            generation=self.generation,
        )

    def destroy(self) -> None:
        self.fabric_points = None
        self.selection = None
        self.rt_prim = None
        self.rt_stage = None
        for name in (
            "a_cuda",
            "e_cuda",
            "m0_cuda",
            "n_cuda",
            "epoch_cuda",
            "basis_p_cuda",
            "basis_q_cuda",
        ):
            setattr(self, name, None)
        if self.usd_stage is not None:
            with Usd.EditContext(self.usd_stage, self.usd_stage.GetSessionLayer()):
                for path_string in (
                    self.mesh_path_string,
                    self.material_path_string,
                ):
                    path = Sdf.Path(path_string)
                    if self.usd_stage.GetPrimAtPath(path).IsValid():
                        self.usd_stage.RemovePrim(path)
        self.usd_stage = None
