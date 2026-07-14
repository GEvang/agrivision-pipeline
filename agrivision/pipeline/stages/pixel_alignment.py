from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from PIL import Image

from agrivision.pipeline.io.paths import resolve_pipeline_paths

VALID_IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".tif", ".tiff")


@dataclass(frozen=True)
class PixelAlignmentResult:
    camera_kind: str
    output_path: Path
    source_path: Path
    x_shift: int
    y_shift: int
    width: int
    height: int


def _first_image(path: Path) -> Path | None:
    if not path.exists():
        return None
    for candidate in sorted(path.iterdir()):
        if candidate.is_file() and candidate.suffix.lower() in VALID_IMAGE_EXTS:
            return candidate
    return None


def _open_as_array(path: Path) -> np.ndarray:
    with Image.open(path) as image:
        image.load()
        if image.mode not in {"RGB", "RGBA", "L", "I;16", "I"}:
            image = image.convert("RGB")
        if image.mode == "RGBA":
            image = image.convert("RGB")
        arr = np.asarray(image)
    if arr.ndim == 2:
        return arr.astype(np.uint8, copy=False)
    if arr.ndim == 3 and arr.shape[2] >= 3:
        return arr[:, :, :3].astype(np.uint8, copy=False)
    return arr.astype(np.uint8, copy=False)


def _grayscale(arr: np.ndarray) -> np.ndarray:
    if arr.ndim == 2:
        return arr.astype(np.float32)
    rgb = arr[:, :, :3].astype(np.float32)
    return 0.2989 * rgb[:, :, 0] + 0.5870 * rgb[:, :, 1] + 0.1140 * rgb[:, :, 2]


def _resize_to(arr: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    width, height = size
    mode = "L" if arr.ndim == 2 else "RGB"
    image = Image.fromarray(arr, mode=mode)
    image = image.resize((width, height), Image.Resampling.BILINEAR)
    return np.asarray(image)


def _phase_correlation_shift(reference: np.ndarray, candidate: np.ndarray) -> tuple[int, int]:
    ref = reference.astype(np.float32)
    cand = candidate.astype(np.float32)
    ref -= ref.mean()
    cand -= cand.mean()
    response = np.fft.ifft2(
        (
            np.fft.fft2(ref)
            * np.conj(np.fft.fft2(cand))
        )
        / (np.abs(np.fft.fft2(ref) * np.conj(np.fft.fft2(cand))) + 1e-6)
    )
    peak_y, peak_x = np.unravel_index(np.argmax(np.abs(response)), response.shape)
    if peak_x > candidate.shape[1] // 2:
        peak_x -= candidate.shape[1]
    if peak_y > candidate.shape[0] // 2:
        peak_y -= candidate.shape[0]
    return int(peak_x), int(peak_y)


def _translate(arr: np.ndarray, x_shift: int, y_shift: int) -> np.ndarray:
    if arr.ndim == 2:
        out = np.zeros_like(arr)
    else:
        out = np.zeros_like(arr)
    src_y0 = max(0, -y_shift)
    src_y1 = min(arr.shape[0], arr.shape[0] - y_shift) if y_shift >= 0 else arr.shape[0]
    dst_y0 = max(0, y_shift)
    dst_y1 = dst_y0 + (src_y1 - src_y0)
    src_x0 = max(0, -x_shift)
    src_x1 = min(arr.shape[1], arr.shape[1] - x_shift) if x_shift >= 0 else arr.shape[1]
    dst_x0 = max(0, x_shift)
    dst_x1 = dst_x0 + (src_x1 - src_x0)
    if src_y1 <= src_y0 or src_x1 <= src_x0:
        return out
    out[dst_y0:dst_y1, dst_x0:dst_x1] = arr[src_y0:src_y1, src_x0:src_x1]
    return out


def _write_tiff(path: Path, arr: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if arr.ndim == 2:
        bands = arr[np.newaxis, :, :]
    else:
        bands = np.moveaxis(arr[:, :, :3], -1, 0)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=bands.shape[1],
        width=bands.shape[2],
        count=bands.shape[0],
        dtype=str(bands.dtype),
    ) as dst:
        dst.write(bands)


def run_pixel_alignment_fallback(
    *,
    workspace_root: Path | None = None,
    config: dict[str, Any] | None = None,
) -> list[PixelAlignmentResult]:
    resolved = resolve_pipeline_paths(workspace_root=workspace_root, config=config)
    sources = {
        "rgb": (_first_image(resolved["images_full_rgb"]), resolved["ortho_rgb"]),
        "mapir": (_first_image(resolved["images_full_mapir"]), resolved["ortho_mapir"]),
        "thermal": (_first_image(resolved["images_full_thermal"]), resolved["ortho_thermal"]),
    }
    available = {kind: pair for kind, pair in sources.items() if pair[0] is not None}
    if not available:
        raise RuntimeError("Pixel alignment fallback could not find any source images.")

    reference_kind = "rgb" if available.get("rgb") else next(iter(available))
    reference_source, _ = available[reference_kind]
    assert reference_source is not None
    reference_arr = _open_as_array(reference_source)
    ref_h, ref_w = reference_arr.shape[:2]
    reference_gray = _grayscale(reference_arr)

    results: list[PixelAlignmentResult] = []
    print(f"[Demo Alignment] Using {reference_kind.upper()} source as pixel-space reference: {reference_source}")

    for camera_kind, (source_path, output_path) in available.items():
        assert source_path is not None
        arr = _open_as_array(source_path)
        resized = _resize_to(arr, (ref_w, ref_h)) if arr.shape[:2] != (ref_h, ref_w) else arr
        x_shift = 0
        y_shift = 0
        if camera_kind != reference_kind:
            candidate_gray = _grayscale(resized)
            x_shift, y_shift = _phase_correlation_shift(reference_gray, candidate_gray)
            resized = _translate(resized, x_shift, y_shift)
        _write_tiff(output_path, resized)
        print(
            f"[Demo Alignment] Wrote fallback {camera_kind.upper()} analysis image to {output_path} "
            f"(source={source_path.name}, shift=({x_shift}, {y_shift}), size={ref_w}x{ref_h})"
        )
        results.append(
            PixelAlignmentResult(
                camera_kind=camera_kind,
                output_path=output_path,
                source_path=source_path,
                x_shift=x_shift,
                y_shift=y_shift,
                width=ref_w,
                height=ref_h,
            )
        )
    return results
