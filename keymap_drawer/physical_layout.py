from abc import ABC
from typing import Sequence

from pydantic import BaseModel, root_validator


class PhysicalKey(BaseModel):
    x_pos: float
    y_pos: float
    width: float = KEY_W
    height: float = KEY_H
    rotation: float = 0


class PhysicalLayout(ABC):
    _keys: Sequence[PhysicalKey]

    def __getitem__(self, i):
        return self._keys[i]

    def __len__(self):
        return len(self._keys)


class DefaultLayout(PhysicalLayout, BaseModel):
    split: bool
    rows: int
    columns: int
    thumbs: int = 0

    @root_validator
    def check_thumbs(cls, vals):
        if vals["thumbs"]:
            assert vals["thumbs"] <= vals["columns"], "Number of thumbs should not be greater than columns"
            assert vals["split"], "Cannot process non-split keyboard with thumb keys"
        return vals

    @property
    def total_keys(self):
        total = self.rows * self.columns
        if self.thumbs:
            total += self.thumbs
        if self.split:
            total *= 2
        return total

    @property
    def total_cols(self):
        return 2 * self.columns if self.split else self.columns

    def pos_to_col(self, pos: int):
        col = pos % self.total_cols
        if pos >= self.rows * self.total_cols and self.thumbs:
            col += self.columns - self.thumbs
        return col

    def pos_to_row(self, pos: int):
        return pos // self.total_cols
