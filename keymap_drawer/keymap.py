from itertools import chain
from typing import Literal, Sequence, Mapping, Union

from pydantic import BaseModel, validator, root_validator

from .physical_layout import layout_factory, PhysicalLayout


class LayoutKey(BaseModel):
    tap: str
    hold: str = ""
    type: Literal[None, "held", "combo", "ghost"] = None

    @classmethod
    def from_key_spec(cls, key_spec: Union[str, "LayoutKey", None]) -> "LayoutKey":
        if key_spec is None:
            return cls(tap="")
        if isinstance(key_spec, str):
            return cls(tap=key_spec)
        return key_spec


class ComboSpec(BaseModel):
    positions: Sequence[int]
    key: LayoutKey
    layers: Sequence[str] = []

    @validator("key", pre=True)
    def get_key(cls, val) -> LayoutKey:
        return LayoutKey.from_key_spec(val)


class Layer(BaseModel):
    keys: Sequence[LayoutKey]
    combos: Sequence[ComboSpec] = []

    @validator("keys", pre=True)
    def parse_keys(cls, vals) -> Sequence[LayoutKey]:
        return [
            LayoutKey.from_key_spec(val)
            for val in chain.from_iterable(
                v if isinstance(v, Sequence) and not isinstance(v, str) else [v] for v in vals
            )
        ]


class KeymapData(BaseModel):
    layout: PhysicalLayout
    layers: Mapping[str, Layer]
    combos: Sequence[ComboSpec] = []

    @validator("layout", pre=True)
    def create_layout(cls, val) -> PhysicalLayout:
        assert "ltype" in val, 'Specifying a layout type key "ltype" is mandatory under "layout"'
        return layout_factory(**val)

    @root_validator(skip_on_failure=True)
    def assign_combos_to_layers(cls, vals):
        for combo in vals["combos"]:
            for layer in combo.layers if combo.layers else vals["layers"]:
                vals["layers"][layer].combos.append(combo)
        return vals

    @root_validator(skip_on_failure=True)
    def check_combo_pos(cls, vals):
        for layer in vals["layers"].values():
            for combo in layer.combos:
                assert len(combo.positions) == 2, "Cannot have more than two positions for combo"
                assert all(
                    pos < len(vals["layout"]) for pos in combo.positions
                ), "Combo positions exceed number of keys"
        return vals

    @root_validator(skip_on_failure=True)
    def check_dimensions(cls, vals):
        for name, layer in vals["layers"].items():
            assert len(layer.keys) == len(
                vals["layout"]
            ), f"Number of keys do not match layout specification in layer {name}"
        return vals
