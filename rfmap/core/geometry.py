"""Wall obstacles and segment-intersection tests."""
from dataclasses import dataclass

from rfmap.core.constants import WALL_ATTENUATION


@dataclass
class Obstacle:
    x1: float
    y1: float
    x2: float
    y2: float
    material: str

    @property
    def attenuation_db(self) -> float:
        return WALL_ATTENUATION.get(self.material, 0.0)


def _orient(ax: float, ay: float, bx: float, by: float, cx: float, cy: float) -> float:
    return (by - ay) * (cx - bx) - (bx - ax) * (cy - by)


def _on_segment(ax: float, ay: float, bx: float, by: float, cx: float, cy: float) -> bool:
    return (
        min(ax, bx) <= cx <= max(ax, bx)
        and min(ay, by) <= cy <= max(ay, by)
    )


def segments_intersect(
    x1: float, y1: float, x2: float, y2: float,
    x3: float, y3: float, x4: float, y4: float,
) -> bool:
    o1 = _orient(x1, y1, x2, y2, x3, y3)
    o2 = _orient(x1, y1, x2, y2, x4, y4)
    o3 = _orient(x3, y3, x4, y4, x1, y1)
    o4 = _orient(x3, y3, x4, y4, x2, y2)

    if o1 == 0 and _on_segment(x1, y1, x2, y2, x3, y3):
        return True
    if o2 == 0 and _on_segment(x1, y1, x2, y2, x4, y4):
        return True
    if o3 == 0 and _on_segment(x3, y3, x4, y4, x1, y1):
        return True
    if o4 == 0 and _on_segment(x3, y3, x4, y4, x2, y2):
        return True

    return (o1 > 0) != (o2 > 0) and (o3 > 0) != (o4 > 0)
