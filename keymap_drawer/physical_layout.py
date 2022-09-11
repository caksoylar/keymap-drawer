from abc import ABC
from functools import cached_property
from typing import Sequence, ClassVar, Literal

from pydantic import BaseModel, validator, root_validator

KEY_W = 55
KEY_H = 50
KEY_RX = 6
KEY_RY = 6
INNER_PAD_W = 2
INNER_PAD_H = 2
KEYSPACE_W = KEY_W + 2 * INNER_PAD_W
KEYSPACE_H = KEY_H + 2 * INNER_PAD_H


class PhysicalKey(BaseModel):
    x_pos: float
    y_pos: float
    width: float = KEY_W
    height: float = KEY_H
    rotation: float = 0


LayoutType = Literal["ortho", "raw"]


class PhysicalLayout(BaseModel, ABC):
    keys: Sequence[PhysicalKey]
    ltype: ClassVar[LayoutType]

    class Config:
        arbitrary_types_allowed = True
        keep_untouched = (cached_property,)

    def __getitem__(self, i):
        return self.keys[i]

    def __len__(self):
        return len(self.keys)

    @cached_property
    def width(self):
        return max(k.x_pos + k.width for k in self.keys)

    @cached_property
    def height(self):
        return max(k.y_pos + k.height for k in self.keys)


def layout_factory(ltype: Literal, **kwargs) -> PhysicalLayout:
    match ltype:
        case "ortho":
            return OrthoLayout(**kwargs)
        case "raw":
            return RawLayout(**kwargs)
        case _:
            raise ValueError(f'Physical layout type "{ltype}" is not supported')


class RawLayout(PhysicalLayout):
    ltype: ClassVar[LayoutType] = "raw"

    @validator("keys", pre=True, each_item=True, check_fields=False)
    def parse_keys(cls, val):
        return PhysicalKey(**val)


class OrthoLayout(PhysicalLayout):
    split: bool
    rows: int
    columns: int
    thumbs: int = 0
    ltype: ClassVar[LayoutType] = "ortho"

    @root_validator
    def check_thumbs(cls, vals):
        if vals["thumbs"]:
            assert (
                vals["thumbs"] <= vals["columns"]
            ), "Number of thumbs should not be greater than columns"
            assert vals["split"], "Cannot process non-split keyboard with thumb keys"
        return vals

    @root_validator(pre=True, skip_on_failure=True)
    def create_ortho_layout(cls, vals):
        nrows = vals["rows"]
        ncols = vals["columns"]
        nthumbs = vals["thumbs"]
        keys = []

        def create_row(x: float, y: float, ncols: int = ncols) -> None:
            for _ in range(ncols):
                keys.append(PhysicalKey(x_pos=x, y_pos=y))
                x += KEYSPACE_W

        def create_block(x: float, y: float) -> None:
            for _ in range(nrows):
                create_row(x, y)
                y += KEYSPACE_H

        create_block(0.0, 0.0)
        if vals["split"]:
            create_block(ncols * KEYSPACE_W + KEY_W / 2, 0.0)
        if nthumbs:
            create_row((ncols - nthumbs) * KEYSPACE_W, nrows * KEYSPACE_H, nthumbs)
            create_row(ncols * KEYSPACE_W + KEY_W / 2, nrows * KEYSPACE_H, nthumbs)

        return vals | {"keys": keys}
