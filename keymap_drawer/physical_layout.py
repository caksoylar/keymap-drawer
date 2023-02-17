"""
Module containing classes pertaining to the physical layout of a keyboard,
i.e. a sequence of keys each represented by its coordinates, dimensions
and rotation.
"""
from math import sqrt
from dataclasses import dataclass
from functools import cached_property
from typing import Sequence, Literal

from pydantic import BaseModel, root_validator

from .config import DrawConfig


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

    def __rmul__(self, other: int | float) -> "Point":
        return Point(other * self.x, other * self.y)

    def copy(self) -> "Point":  # pylint: disable=missing-function-docstring
        return Point(self.x, self.y)


@dataclass
class PhysicalKey:
    """
    Represents a physical key, in terms of its center coordinates, width, height,
    rotation angle and the coordinates around which it is rotated.
    """

    pos: Point
    width: float
    height: float
    rotation: float = 0
    rotation_pos: Point | None = None  # pos (key center) by default

    def __post_init__(self):
        if self.rotation_pos is None:
            self.rotation_pos = self.pos  # shallow copy


LayoutType = Literal["ortho", "qmk", "raw"]


class PhysicalLayout(BaseModel):
    """Represents the physical layout of keys on the keyboard, as a sequence of keys."""

    keys: Sequence[PhysicalKey]

    class Config:  # pylint: disable=missing-class-docstring
        keep_untouched = (cached_property,)

    def __len__(self) -> int:
        return len(self.keys)

    @cached_property
    def width(self) -> float:
        """Return overall width of layout."""
        return max(k.pos.x + k.width / 2 for k in self.keys)

    @cached_property
    def height(self) -> float:
        """Return overall height of layout."""
        return max(k.pos.y + k.height / 2 for k in self.keys)

    @cached_property
    def min_width(self) -> float:
        """Return minimum key width in the layout."""
        return min(k.width for k in self.keys)

    @cached_property
    def min_height(self) -> float:
        """Return minimum key height in the layout."""
        return min(k.height for k in self.keys)


def layout_factory(ltype: LayoutType, config: DrawConfig, **kwargs) -> PhysicalLayout:
    """Create and return a physical layout as determined by the ltype argument."""
    match ltype:
        case "ortho":
            return PhysicalLayout(keys=OrthoGenerator(**kwargs).generate(config.key_w, config.key_h, config.split_gap))
        case "qmk":
            return PhysicalLayout(keys=QmkGenerator(**kwargs).generate(config.key_h))
        case "raw":
            return PhysicalLayout(**kwargs)
        case _:
            raise ValueError(f'Physical layout type "{ltype}" is not supported')


class OrthoGenerator(BaseModel):
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


class QmkGenerator(BaseModel):
    """Generator for layouts given by QMK's info.json format."""

    class QmkKey(BaseModel):
        """Model representing each key in QMK's layout definition."""

        x: float
        y: float
        w: float = 1.0
        h: float = 1.0
        r: float = 0
        rx: float | None = None
        ry: float | None = None

    layout: Sequence[QmkKey]

    def generate(self, key_size: float) -> Sequence[PhysicalKey]:
        """Generate a sequence of PhysicalKeys from QmkKeys."""
        x_min = min(k.x for k in self.layout)
        y_min = min(k.y for k in self.layout)
        return [
            PhysicalKey(
                pos=key_size * Point(k.x - x_min + k.w / 2, k.y - y_min + k.h / 2),
                width=key_size * k.w,
                height=key_size * k.h,
                rotation=k.r,
                rotation_pos=None if k.rx is None or k.ry is None else key_size * Point(k.rx - x_min, k.ry - y_min),
            )
            for k in self.layout
        ]
