"""
Module containing classes pertaining to the physical layout of a keyboard,
i.e. a sequence of keys each represented by its coordinates, dimensions
and rotation.
"""

import json
from dataclasses import dataclass
from functools import cached_property, lru_cache
from math import cos, pi, sin, sqrt
from pathlib import Path
from typing import Literal, Sequence
from urllib.error import HTTPError
from urllib.request import urlopen

from platformdirs import user_cache_dir
from pydantic import BaseModel, root_validator

from .config import DrawConfig

QMK_LAYOUTS_PATH = Path(__file__).parent.parent / "resources" / "qmk_layouts"
QMK_METADATA_URL = "https://keyboards.qmk.fm/v1/keyboards/{keyboard}/info.json"
CACHE_LAYOUTS_PATH = Path(user_cache_dir("keymap-drawer", False)) / "qmk_layouts"


@dataclass(frozen=True)
class Point:
    """Simple class representing a 2d point."""

    x: float
    y: float

    def __add__(self, other: "Point") -> "Point":
        return Point(self.x + other.x, self.y + other.y)

    def __sub__(self, other: "Point") -> "Point":
        return Point(self.x - other.x, self.y - other.y)

    def __abs__(self) -> float:
        return sqrt(self.x**2 + self.y**2)

    def __mul__(self, other: int | float) -> "Point":
        return Point(other * self.x, other * self.y)

    def __rmul__(self, other: int | float) -> "Point":
        return self.__mul__(other)

    def copy(self) -> "Point":  # pylint: disable=missing-function-docstring
        return Point(self.x, self.y)


@dataclass
class PhysicalKey:
    """
    Represents a physical key, in terms of its center coordinates, width, height and
    rotation angle.
    """

    pos: Point
    width: float
    height: float
    rotation: float = 0  # CW if positive
    bounding_width: float = 0.0
    bounding_height: float = 0.0

    @classmethod
    def from_qmk_spec(  # pylint: disable=too-many-arguments
        cls, scale: float, pos: Point, width: float, height: float, rotation: float, rotation_pos: Point
    ) -> "PhysicalKey":
        """
        Create a PhysicalKey from QMK-format key definition. `pos` is the top left corner coordinates,
        `rotation_pos` is the coordinates around which the rectangle is rotated. `scale` maps from `1u` dimensions
        to pixel dimensions.
        During construction of PhysicalKey, uses `rotation_pos` to re-adjust center position.
        """
        center = pos + Point(width / 2, height / 2)
        if rotation:
            center = cls._rotate_point(rotation_pos, center, rotation)

        return cls(scale * center, scale * width, scale * height, rotation)

    def __post_init__(self) -> None:
        if self.rotation:
            # calculate bounding box dimensions
            rotated_corners = [
                self._rotate_point(Point(0, 0), p, self.rotation)
                for p in (Point(0, 0), Point(0, self.height), Point(self.width, 0), Point(self.width, self.height))
            ]
            self.bounding_width = max(p.x for p in rotated_corners) - min(p.x for p in rotated_corners)
            self.bounding_height = max(p.y for p in rotated_corners) - min(p.y for p in rotated_corners)
        else:
            self.bounding_width = self.width
            self.bounding_height = self.height

    @staticmethod
    def _rotate_point(origin: Point, point: Point, angle: float) -> Point:
        angle *= pi / 180
        delta = point - origin
        rotated = Point(
            delta.x * cos(angle) - delta.y * sin(angle),
            delta.x * sin(angle) + delta.y * cos(angle),
        )
        return origin + rotated

    def __add__(self, other: "Point") -> "PhysicalKey":
        return PhysicalKey(
            pos=self.pos + other,
            width=self.width,
            height=self.height,
            rotation=self.rotation,
        )

    def __sub__(self, other: "Point") -> "PhysicalKey":
        return PhysicalKey(
            pos=self.pos - other,
            width=self.width,
            height=self.height,
            rotation=self.rotation,
        )

    def __rmul__(self, other: int | float) -> "PhysicalKey":
        return PhysicalKey(
            pos=self.pos * other,
            width=self.width * other,
            height=self.height * other,
            rotation=self.rotation,
        )


class PhysicalLayout(BaseModel, keep_untouched=(cached_property,)):
    """Represents the physical layout of keys on the keyboard, as a sequence of keys."""

    keys: Sequence[PhysicalKey]

    def __len__(self) -> int:
        return len(self.keys)

    @cached_property
    def width(self) -> float:
        """Return overall width of layout."""
        return max(k.pos.x + k.bounding_width / 2 for k in self.keys)

    @cached_property
    def height(self) -> float:
        """Return overall height of layout."""
        return max(k.pos.y + k.bounding_height / 2 for k in self.keys)

    @cached_property
    def min_width(self) -> float:
        """Return minimum key width in the layout."""
        return min(k.width for k in self.keys)

    @cached_property
    def min_height(self) -> float:
        """Return minimum key height in the layout."""
        return min(k.height for k in self.keys)

    def __add__(self, other: Point) -> "PhysicalLayout":
        return PhysicalLayout(keys=[k + other for k in self.keys])

    def __rmul__(self, other: int | float) -> "PhysicalLayout":
        return PhysicalLayout(keys=[other * k for k in self.keys])


def layout_factory(
    config: DrawConfig,
    qmk_keyboard: str | None = None,
    qmk_info_json: Path | None = None,
    qmk_layout: str | None = None,
    ortho_layout: dict | None = None,
) -> PhysicalLayout:
    """Create and return a physical layout, as determined by the combination of arguments passed."""
    if len([arg for arg in (qmk_keyboard, qmk_info_json, ortho_layout) if arg is not None]) != 1:
        raise ValueError(
            'Please provide exactly one of "qmk_keyboard", "qmk_info_json" or "ortho_layout" specs for physical layout'
        )

    if qmk_keyboard or qmk_info_json:
        if qmk_keyboard:
            qmk_info = _get_qmk_info(qmk_keyboard, config.use_local_cache)
        else:  # qmk_info_json
            assert qmk_info_json is not None
            with open(qmk_info_json, "rb") as f:
                qmk_info = json.load(f)

        if isinstance(qmk_info, list):
            assert qmk_layout is None, "Cannot use qmk_layout with a list-format QMK spec"
            layout = qmk_info  # shortcut for list-only representation
        elif qmk_layout is None:
            layout = next(iter(qmk_info["layouts"].values()))["layout"]  # take the first layout in map
        else:
            assert qmk_layout in qmk_info["layouts"], (
                f'Could not find layout "{qmk_layout}" in QMK info.json, '
                f'available options are: {list(qmk_info["layouts"])}'
            )
            layout = qmk_info["layouts"][qmk_layout]["layout"]

        keys = QmkLayout(layout=layout).generate(config.key_h)
    else:  # ortho_layout
        assert ortho_layout is not None
        keys = OrthoLayout(**ortho_layout).generate(config.key_w, config.key_h, config.split_gap)
    return PhysicalLayout(keys=keys)


class OrthoLayout(BaseModel):
    """
    Generator for a physical layout representing an ortholinear keyboard, as specified by
    its number of rows, columns, thumb keys and whether it is split or not. If split,
    row/column number represents the size of one half. Thumb keys can only be used if split.
    """

    split: bool = False
    rows: int
    columns: int
    thumbs: int | Literal["MIT", "2x2u"] = 0
    drop_pinky: bool = False
    drop_inner: bool = False

    @root_validator
    def check_thumbs(cls, vals):
        """Check that the number of thumb keys is specified correctly."""
        thumbs = vals["thumbs"]
        if thumbs:
            if isinstance(thumbs, int):
                assert thumbs <= vals["columns"], "Number of thumbs should not be greater than columns"
                assert vals["split"], "Cannot process non-split layout with thumb keys"
            else:
                assert not vals["split"], "Non-integer thumb specs (MIT/2x2u) can only be used with non-split layout"
                assert thumbs in (
                    "MIT",
                    "2x2u",
                ), 'Only "MIT" or "2x2u" supported for "thumbs" for non-splits'
                assert vals["columns"] % 2 == 0, "Cannot use MIT or 2x2u bottom row layout with odd number of columns"
        return vals

    @root_validator
    def check_drops(cls, vals):
        """Check that drop_pinky or drop_index are only used with split layouts."""
        if vals["drop_pinky"] or vals["drop_inner"]:
            assert vals["split"], '"drop_*" properties can only be used with split layouts'
        return vals

    def generate(self, key_w: float, key_h: float, split_gap: float) -> Sequence[PhysicalKey]:
        """Generate a list of PhysicalKeys from given ortho specifications."""
        nrows = self.rows
        if not isinstance(self.thumbs, int):
            nrows -= 1
        ncols = self.columns

        keys: list[PhysicalKey] = []

        def create_row(x: float, y: float, ncols: int = ncols) -> list[PhysicalKey]:
            row_keys = []
            for _ in range(ncols):
                row_keys.append(PhysicalKey(pos=Point(x + key_w / 2, y + key_h / 2), width=key_w, height=key_h))
                x += key_w
            return row_keys

        x, y = 0.0, 0.0
        for row in range(nrows):
            row_keys = create_row(x, y)
            if self.split:
                row_keys += create_row(x + ncols * key_w + split_gap, y)

            drop_cols = [0, -1] * self.drop_pinky + [
                len(row_keys) // 2 - 1,
                len(row_keys) // 2,
            ] * self.drop_inner
            for col in reversed(drop_cols):
                if row < nrows - 1:
                    row_keys[col].pos += Point(0, key_h / 2)
                else:
                    row_keys.pop(col)

            keys.extend(row_keys)
            y += key_h

        if not self.thumbs:
            return keys

        match self.thumbs:
            case int():  # implies split
                keys += create_row((ncols - self.thumbs) * key_w, y, self.thumbs)
                keys += create_row(ncols * key_w + split_gap, y, self.thumbs)
            case "MIT":
                keys += create_row(0.0, y, ncols // 2 - 1)
                keys.append(PhysicalKey(pos=Point((ncols / 2) * key_w, y + key_h / 2), width=2 * key_w, height=key_h))
                keys += create_row((ncols / 2 + 1) * key_w, y, ncols // 2 - 1)
            case "2x2u":
                keys += create_row(0.0, y, ncols // 2 - 2)
                keys.append(
                    PhysicalKey(pos=Point((ncols / 2 - 1) * key_w, y + key_h / 2), width=2 * key_w, height=key_h)
                )
                keys.append(
                    PhysicalKey(pos=Point((ncols / 2 + 1) * key_w, y + key_h / 2), width=2 * key_w, height=key_h)
                )
                keys += create_row((ncols / 2 + 2) * key_w, y, ncols // 2 - 2)
            case _:
                raise ValueError("Unknown thumbs value in ortho layout")

        return keys


class QmkLayout(BaseModel):
    """Generator for layouts given by QMK's info.json format."""

    class QmkKey(BaseModel):
        """Model representing each key in QMK's layout definition."""

        x: float  # coordinates of top-left corner
        y: float
        w: float = 1.0
        h: float = 1.0
        r: float = 0  # assume CW rotation around rx, ry (defaults to x, y), after translation to x, y
        rx: float | None = None
        ry: float | None = None

    layout: Sequence[QmkKey]

    def generate(self, key_size: float) -> Sequence[PhysicalKey]:
        """Generate a sequence of PhysicalKeys from QmkKeys."""
        min_pt = Point(min(k.x for k in self.layout), min(k.y for k in self.layout))
        return [
            PhysicalKey.from_qmk_spec(
                scale=key_size,
                pos=Point(k.x, k.y) - min_pt,
                width=k.w,
                height=k.h,
                rotation=k.r,
                rotation_pos=Point(k.x if k.rx is None else k.rx, k.y if k.ry is None else k.ry) - min_pt,
            )
            for k in self.layout
        ]


@lru_cache(maxsize=128)
def _get_qmk_info(qmk_keyboard: str, use_local_cache: bool = False):
    """
    Get a QMK info.json file from either self-maintained folder of layouts,
    local file cache if enabled, or from QMK keyboards metadata API.
    """
    local_path = QMK_LAYOUTS_PATH / f"{qmk_keyboard.replace('/', '@')}.json"
    cache_path = CACHE_LAYOUTS_PATH / f"{qmk_keyboard.replace('/', '@')}.json"

    if local_path.is_file():
        with open(local_path, "rb") as f:
            return json.load(f)

    if use_local_cache and cache_path.is_file():
        with open(cache_path, "rb") as f:
            return json.load(f)

    try:
        with urlopen(QMK_METADATA_URL.format(keyboard=qmk_keyboard)) as f:
            info = json.load(f)["keyboards"][qmk_keyboard]
        if use_local_cache:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            with open(cache_path, "w", encoding="utf-8") as f_out:
                json.dump({"layouts": info["layouts"]}, f_out)
        return info
    except HTTPError as exc:
        raise ValueError(
            f"QMK keyboard '{qmk_keyboard}' not found, please make sure you specify an existing keyboard "
            "(hint: check from https://config.qmk.fm)"
        ) from exc
