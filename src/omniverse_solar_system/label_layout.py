"""Small, dependency-free screen-space label collision helpers."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable


@dataclass(frozen=True)
class LabelCandidate:
    index: int
    name: str
    x: float
    y: float
    priority: float


@dataclass(frozen=True)
class LabelBox:
    left: float
    top: float
    right: float
    bottom: float


def estimated_label_box(
    candidate: LabelCandidate,
    *,
    character_width: float = 7.5,
    height: float = 16.0,
    offset_x: float = 8.0,
    offset_y: float = -8.0,
    padding: float = 5.0,
) -> LabelBox:
    """Estimate a left-anchored label rectangle in viewport pixels."""
    width = max(28.0, len(candidate.name) * character_width)
    left = candidate.x + offset_x - padding
    top = candidate.y + offset_y - height * 0.5 - padding
    return LabelBox(
        left=left,
        top=top,
        right=left + width + 2.0 * padding,
        bottom=top + height + 2.0 * padding,
    )


def boxes_overlap(a: LabelBox, b: LabelBox) -> bool:
    return not (
        a.right <= b.left
        or b.right <= a.left
        or a.bottom <= b.top
        or b.bottom <= a.top
    )


def choose_non_overlapping_labels(
    candidates: Iterable[LabelCandidate],
    *,
    viewport_width: float,
    viewport_height: float,
) -> set[int]:
    """Greedily retain high-priority labels that fit and do not overlap.

    Priority is normally the planet's projected distance from the Sun. This
    preserves readable outer labels when inner planets collapse into a small
    screen-space cluster.
    """
    accepted: list[LabelBox] = []
    visible: set[int] = set()
    ordered = sorted(candidates, key=lambda item: (item.priority, item.index), reverse=True)
    for candidate in ordered:
        if not (math.isfinite(candidate.x) and math.isfinite(candidate.y)):
            continue
        box = estimated_label_box(candidate)
        if (
            box.right < 0.0
            or box.bottom < 0.0
            or box.left > viewport_width
            or box.top > viewport_height
        ):
            continue
        if any(boxes_overlap(box, prior) for prior in accepted):
            continue
        accepted.append(box)
        visible.add(candidate.index)
    return visible
