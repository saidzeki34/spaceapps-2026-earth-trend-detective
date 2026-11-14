"""Versioned conservative quality rules; rejected raw values remain in source columns."""
import numpy as np

NVE_QUALITY_POLICY = "controlled-2-3-corrections-0-1-4-11-v1"
MODIS_QUALITY_POLICY = "basic-0-1-flags-0-1-2-3-4-7-clear-coverage-ge-0.5-v1"
MODIS_REJECT_BITS = sum(1 << bit for bit in (0, 1, 2, 3, 4, 7))


def nve_valid(value, quality, correction):
    return (value is not None and np.isfinite(value) and value >= 0
            and quality in (2, 3) and correction in (0, 1, 4, 11))


def modis_valid(value, basic_qa, flags):
    return (np.isfinite(value) and 0 <= value <= 100 and basic_qa in (0, 1)
            and flags is not None and int(flags) & MODIS_REJECT_BITS == 0)


def aggregate_modis_pixels(values, areas, valid, minimum_coverage=.5):
    """Reference calculation for deterministic spatial contract tests."""
    values, areas, valid = np.asarray(values), np.asarray(areas), np.asarray(valid, dtype=bool)
    if not np.isfinite(areas).all() or (areas <= 0).any():
        raise ValueError("Pixel intersection areas must be finite and positive.")
    valid = valid & np.isfinite(values)
    total = float(areas.sum())
    accepted = float(areas[valid].sum())
    coverage = accepted / total if total else 0.
    value = float(np.sum(values[valid] * areas[valid]) / accepted) if accepted else None
    return (value if coverage >= minimum_coverage else None), coverage
