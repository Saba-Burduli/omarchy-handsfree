"""Geometry for the numbered mouse grid (say a number to zoom into a cell)."""

from __future__ import annotations

Rect = tuple[float, float, float, float]  # x, y, width, height


def split(rect: Rect, n: int) -> list[Rect]:
    """n x n cells numbered row by row, left to right (cell 1 is top-left)."""
    x, y, w, h = rect
    cw, ch = w / n, h / n
    return [(x + col * cw, y + row * ch, cw, ch) for row in range(n) for col in range(n)]


def around(point: tuple[float, float], span: float, bounds: Rect) -> Rect:
    """A span x span square centred on point, shifted to stay inside bounds."""
    bx, by, bw, bh = bounds
    w, h = min(span, bw), min(span, bh)
    x = min(max(point[0] - w / 2, bx), bx + bw - w)
    y = min(max(point[1] - h / 2, by), by + bh - h)
    return (x, y, w, h)


def center(rect: Rect) -> tuple[float, float]:
    x, y, w, h = rect
    return (x + w / 2, y + h / 2)
