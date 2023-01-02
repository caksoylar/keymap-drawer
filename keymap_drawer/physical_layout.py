"""
Module containing classes pertaining to the physical layout of a keyboard,
i.e. a sequence of keys each represented by its coordinates, dimensions
and rotation.
"""
from functools import cached_property
from typing import Sequence, Literal

from pydantic import BaseModel, root_validator

from .style import KEY_W, KEY_H, SPLIT_GAP


class PhysicalKey(BaseModel):
    """Represents a physical key, in terms of its center coordinates, width, height and rotation."""

    x_pos: float
    y_pos: float
    width: float = KEY_W
    height: float = KEY_H
    rotation: float = 0


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
        return max(k.x_pos + k.width / 2 for k in self.keys)

    @cached_property
    def height(self) -> float:
        """Return overall height of layout."""
        return max(k.y_pos + k.height / 2 for k in self.keys)


def layout_factory(ltype: LayoutType, **kwargs) -> PhysicalLayout:
    """Create and return a physical layout as determined by the ltype argument."""
    match ltype:
        case "ortho":
            return PhysicalLayout(keys=OrthoGenerator(**kwargs).generate())
        case "qmk":
            return PhysicalLayout(keys=QmkGenerator(**kwargs).generate())
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

    split: bool
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

    def generate(self) -> Sequence[PhysicalKey]:
        """Generate a list of PhysicalKeys from given ortho specifications."""
        nrows = self.rows
        if not isinstance(self.thumbs, int):
            nrows -= 1
        ncols = self.columns

        keys: list[PhysicalKey] = []

        def create_row(x: float, y: float, ncols: int = ncols) -> list[PhysicalKey]:
            row_keys = []
            for _ in range(ncols):
                row_keys.append(PhysicalKey(x_pos=x + KEY_W / 2, y_pos=y + KEY_H / 2))
                x += KEY_W
            return row_keys

        x, y = 0.0, 0.0
        for row in range(nrows):
            row_keys = create_row(x, y)
            if self.split:
                row_keys += create_row(x + ncols * KEY_W + SPLIT_GAP, y)

            drop_cols = [0, -1] * self.drop_pinky + [
                len(row_keys) // 2 - 1,
                len(row_keys) // 2,
            ] * self.drop_inner
            for col in reversed(drop_cols):
                if row < nrows - 1:
                    row_keys[col].y_pos += KEY_H / 2
                else:
                    row_keys.pop(col)

            keys.extend(row_keys)
            y += KEY_H

        if not self.thumbs:
            return keys

        if isinstance(self.thumbs, int):  # implies split
            keys += create_row((ncols - self.thumbs) * KEY_W, y, self.thumbs)
            keys += create_row(ncols * KEY_W + SPLIT_GAP, y, self.thumbs)
        elif self.thumbs == "MIT":
            keys += create_row(0.0, y, ncols // 2 - 1)
            keys.append(PhysicalKey(x_pos=(ncols / 2) * KEY_W, y_pos=y + KEY_H / 2, width=2 * KEY_W))
            keys += create_row((ncols / 2 + 1) * KEY_W, y, ncols // 2 - 1)
        else:  # "2x2u"
            keys += create_row(0.0, y, ncols // 2 - 2)
            keys.append(PhysicalKey(x_pos=(ncols / 2 - 1) * KEY_W, y_pos=y + KEY_H / 2, width=2 * KEY_W))
            keys.append(PhysicalKey(x_pos=(ncols / 2 + 1) * KEY_W, y_pos=y + KEY_H / 2, width=2 * KEY_W))
            keys += create_row((ncols / 2 + 2) * KEY_W, y, ncols // 2 - 2)

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

    layout: Sequence[QmkKey]

    def generate(self) -> Sequence[PhysicalKey]:
        """Generate a sequence of PhysicalKeys from QmkKeys."""
        return [
            PhysicalKey(
                x_pos=KEY_H * (k.x + k.w / 2),
                y_pos=KEY_H * (k.y + k.h / 2),
                width=KEY_H * k.w,
                height=KEY_H * k.h,
                rotation=k.r,
            )
            for k in self.layout
        ]
