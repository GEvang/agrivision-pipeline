from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio
from PIL import Image, UnidentifiedImageError


class PreviewService:
    def ensure_preview(self, artifact_path: Path, preview_path: Path) -> Path | None:
        if not artifact_path.exists():
            return None
        preview_path.parent.mkdir(parents=True, exist_ok=True)
        if artifact_path.suffix.lower() in {'.tif', '.tiff'}:
            generated = self._ensure_raster_preview(artifact_path, preview_path)
            if generated is not None:
                return generated

        try:
            with Image.open(artifact_path) as image:
                image.load()
                image.thumbnail((1200, 1200))
                image.convert('RGB').save(preview_path, format='PNG')
            return preview_path
        except (Image.DecompressionBombError, UnidentifiedImageError, OSError):
            return None

    def preview_name_for(self, artifact_path: Path) -> str:
        return f'{artifact_path.stem}_preview.png'

    def _ensure_raster_preview(self, artifact_path: Path, preview_path: Path) -> Path | None:
        try:
            with rasterio.open(artifact_path) as src:
                width, height = self._preview_size(src.width, src.height)
                indexes = [idx for idx in (1, 2, 3) if idx <= src.count]
                if not indexes:
                    return None
                data = src.read(indexes, out_shape=(len(indexes), height, width), masked=True)
        except (OSError, rasterio.errors.RasterioIOError):
            return None

        image = self._normalize_raster(data)
        Image.fromarray(image, mode='RGB').save(preview_path, format='PNG')
        return preview_path

    def _preview_size(self, width: int, height: int) -> tuple[int, int]:
        scale = min(1.0, 1200.0 / float(max(width, height)))
        return max(1, int(round(width * scale))), max(1, int(round(height * scale)))

    def _normalize_raster(self, data: np.ma.MaskedArray) -> np.ndarray:
        arr = np.ma.filled(data.astype('float32'), np.nan)
        if arr.shape[0] == 1:
            arr = np.repeat(arr, 3, axis=0)
        arr = arr[:3]

        out = np.zeros_like(arr, dtype='uint8')
        for idx, band in enumerate(arr):
            valid = np.isfinite(band)
            if not np.any(valid):
                continue
            low, high = np.nanpercentile(band[valid], [2, 98])
            if high <= low:
                low = float(np.nanmin(band[valid]))
                high = float(np.nanmax(band[valid]))
            if high <= low:
                continue
            scaled = np.clip((band - low) / (high - low) * 255.0, 0, 255)
            out[idx] = np.nan_to_num(scaled, nan=0.0).astype('uint8')

        return np.moveaxis(out, 0, -1)
