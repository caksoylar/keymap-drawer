"""
Module with classes that define the keymap representation, with multiple layers
containing key and combo specifications, paired with the physical keyboard layout.
"""
from itertools import chain
from typing import Literal, Sequence, Mapping

from pydantic import BaseModel, Field, validator, root_validator

from .physical_layout import layout_factory, PhysicalLayout
from .config import DrawConfig


class LayoutKey(BaseModel):
    """
    Represents a binding in the keymap, which has a tap property by default and
    can optionally have a hold property, or be "held", be a "ghost" key, or be a combo.
    """

    tap: str = Field(alias="t")
    hold: str = Field(default="", alias="h")
    type: Literal[None, "held", "ghost"] = None

    class Config:  # pylint: disable=missing-class-docstring
        allow_population_by_field_name = True

    @classmethod
    def from_key_spec(cls, key_spec: dict | str | int | None) -> "LayoutKey":
        """Derive full params from a string/int (for tap), a full spec or null (empty key)."""
        match key_spec:
            case dict():
                return cls(**key_spec)
            case str():
                return cls(tap=key_spec)
            case int():
                return cls(tap=str(key_spec))
            case None:
                return cls(tap="")
        raise ValueError(f'Invalid key specification "{key_spec}", provide a dict, string or null')

    def dict(self, *args, **kwargs):
        dict_repr = super().dict(*args, **kwargs)
        if set(dict_repr.keys()).issubset({"t", "tap"}):
            return dict_repr.get("t") or dict_repr.get("tap", "")
        return dict_repr


class ComboSpec(BaseModel):
    """
    Represents a combo in the keymap, with the trigger positions, activated binding (key)
    and layers that it is present on.
    """

    key_positions: Sequence[int] = Field(alias="p")
    key: LayoutKey = Field(alias="k")
    layers: Sequence[str] = Field(alias="l", default=[])
    align: Literal["mid", "top", "bottom", "left", "right"] = Field(alias="a", default="mid")
    offset: float = Field(alias="o", default=0.0)
    dendron: bool | None = Field(alias="d", default=None)

    class Config:  # pylint: disable=missing-class-docstring
        allow_population_by_field_name = True

    @validator("key", pre=True)
    def get_key(cls, val) -> LayoutKey:
        """Parse each key from its key spec."""
        return val if isinstance(val, LayoutKey) else LayoutKey.from_key_spec(val)


class KeymapData(BaseModel):
    """Represents all data pertaining to a keymap, including layers, combos and physical layout."""

    layout: PhysicalLayout
    layers: Mapping[str, Sequence[LayoutKey]]
    combos: Sequence[ComboSpec] = []
    config: DrawConfig

    def get_combos_per_layer(self) -> dict[str, list[ComboSpec]]:
        """Return a mapping of layer names to combos that are present on that layer."""
        out: dict[str, list[ComboSpec]] = {layer_name: [] for layer_name in self.layers}
        for combo in self.combos:
            for layer_name in combo.layers if combo.layers else self.layers:
                out[layer_name].append(combo)
        return out

    @validator("layers", pre=True)
    def parse_layers(cls, val) -> Mapping[str, Sequence[LayoutKey]]:
        """Parse each key on layer from its key spec, flattening the spec if it contains sublists."""
        return {
            layer_name: [
                val if isinstance(val, LayoutKey) else LayoutKey.from_key_spec(val)
                for val in chain.from_iterable(
                    v if isinstance(v, Sequence) and not isinstance(v, str) else [v] for v in keys
                )
            ]
            for layer_name, keys in val.items()
        }

    @root_validator(pre=True, skip_on_failure=True)
    def create_layout(cls, vals):
        """Create layout with type given by ltype."""
        assert "ltype" in vals["layout"], 'Specifying a layout type key "ltype" is mandatory under "layout"'
        vals["layout"] = layout_factory(config=vals["config"], **vals["layout"])
        return vals

    @root_validator(skip_on_failure=True)
    def check_combos(cls, vals):
        """Validate combo positions are legitimate ones we can draw."""
        for combo in vals["combos"]:
            assert all(
                pos < len(vals["layout"]) for pos in combo.key_positions
            ), f"Combo positions exceed number of keys for combo '{combo}'"
            assert not combo.layers or all(
                l in vals["layers"] for l in combo.layers
            ), f"One of the layer names for combo '{combo}' is not found in the layer definitions"
        return vals

    @root_validator(skip_on_failure=True)
    def check_dimensions(cls, vals):
        """Validate that physical layout and layers have the same number of keys."""
        for name, layer in vals["layers"].items():
            assert len(layer) == len(
                vals["layout"]
            ), f"Number of keys do not match layout specification in layer {name}"
        return vals
