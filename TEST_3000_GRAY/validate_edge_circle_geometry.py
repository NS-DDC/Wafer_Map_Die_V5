"""Small deterministic checks for the circle-crossing EDGE definition."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from USE_LATEST.use_gray_wafer_die_particle import _rect_crosses_circle as gray_crosses
from USE_LATEST.use_manual_grid_wafer_map import _rect_crosses_circle as manual_crosses


CASES = [
    # name, rectangle, expected circle-boundary crossing
    ("inside", (45, 45, 55, 55), False),
    ("cross_center_inside", (95, 45, 105, 55), True),
    # This is the regression case: it crosses, even though its box center is outside.
    ("cross_center_outside", (99, 45, 109, 55), True),
    ("outside", (111, 45, 121, 55), False),
]


def main() -> None:
    for name, rect, expected in CASES:
        gray_actual = gray_crosses(*rect, 50, 50, 50)
        manual_actual = manual_crosses(*rect, 50, 50, 50)
        assert gray_actual == expected, (name, gray_actual, expected)
        assert manual_actual == expected, (name, manual_actual, expected)
    print(f"passed {len(CASES)} circle/rectangle EDGE geometry cases")


if __name__ == "__main__":
    main()
