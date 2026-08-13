from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

BIN_PASS = "pass"
BIN_FAIL = "fail"
BIN_RETEST = "retest"
BIN_RECLASS = "reclass"


def find_wafer_image(dataset_root: str, prefer_classes: list[str] | None = None) -> Path | None:
    root = Path(dataset_root)
    if not root.exists():
        return None
    prefer_classes = prefer_classes or ["Normal", "Edge-Loc", "Edge-Ring"]
    for split in ("train", "valid", "test"):
        for cls in prefer_classes:
            folder = root / split / cls
            if not folder.is_dir():
                continue
            for p in sorted(folder.glob("*")):
                if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".bmp"}:
                    return p
    for p in sorted(root.rglob("*")):
        if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".bmp"}:
            return p
    return None


def image_to_die_bins(
    image_path: Path,
    rows: int = 15,
    cols: int = 15,
) -> list[dict]:
    """
    Convert a wafer-map style image into a circular die grid.
    Defective/highlight pixels map to fail/retest; majority → pass.
    Deterministic numpy thresholding — no random sampling.
    """
    img = Image.open(image_path).convert("L").resize((cols, rows), Image.Resampling.BILINEAR)
    arr = np.asarray(img, dtype=np.float32)

    cx, cy = (cols - 1) / 2.0, (rows - 1) / 2.0
    radius = min(cx, cy) + 0.1

    ys, xs = np.indices((rows, cols))
    dist = np.sqrt((xs - cx) ** 2 + (ys - cy) ** 2)
    mask = dist <= radius
    vals = arr[mask]
    if vals.size == 0:
        return []

    # Robust defect detection: outliers vs wafer median (works for dark or bright defects)
    med = float(np.median(vals))
    mad = float(np.median(np.abs(vals - med))) + 1e-6
    z = np.abs(arr - med) / (1.4826 * mad)

    dies: list[dict] = []
    for y in range(rows):
        for x in range(cols):
            if not mask[y, x]:
                continue
            edge = float(dist[y, x] / radius)
            score = float(z[y, x])
            # Normal maps: sparse outliers only; edge slightly more sensitive
            if score > 4.5 or (edge > 0.9 and score > 3.2):
                bin_name = BIN_FAIL
            elif score > 3.2 or (edge > 0.82 and score > 2.4):
                bin_name = BIN_RETEST
            elif 2.2 < score <= 3.2 and edge > 0.55:
                bin_name = BIN_RECLASS
            else:
                bin_name = BIN_PASS
            dies.append({"x": x, "y": y, "bin": bin_name, "die_id": f"{x},{y}"})
    return dies
