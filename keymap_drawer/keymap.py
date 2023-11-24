"""
Module with classes that define the keymap representation, with multiple layers
containing key and combo specifications, paired with the physical keyboard layout.
"""
from collections import defaultdict
from functools import partial
from itertools import chain
from typing import Iterable, Literal, Mapping, Sequence

from pydantic import BaseModel, Field, root_validator, validator

from .config import DrawConfig
from .physical_layout import PhysicalLayout, layout_factory


class LayoutKey(BaseModel, allow_population_by_field_name=True):
    """
    Represents a binding in the keymap, which has a tap property by default and
    can optionally have hold or shifted properties, or be "held" or be a "ghost" key.
    """

    tap: str = Field(alias="t", default="")
    hold: str = Field(alias="h", default="")
    shifted: str = Field(alias="s", default="")
    type: str = ""  # pre-defined types: "held" | "ghost"

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
                return cls()
        raise ValueError(f'Invalid key specification "{key_spec}", provide a dict, string or null')

    def dict(self, *args, no_tapstr: bool = False, **kwargs):
        dict_repr = super().dict(*args, **kwargs)
        if no_tapstr or not set(dict_repr.keys()).issubset({"t", "tap"}):
            return dict_repr
        return dict_repr.get("t") or dict_repr.get("tap", "")


class ComboSpec(BaseModel, allow_population_by_field_name=True):
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
    slide: float | None = Field(alias="s", default=None)
    arc_scale: float = 1.0
    type: str = ""
    width: float | None = Field(alias="w", default=None)
    height: float | None = Field(alias="h", default=None)
    rotation: float = Field(alias="r", default=0.0)

    @classmethod
    def normalize_fields(cls, spec_dict: dict) -> dict:
        """Normalize spec_dict so that each field uses its alias and key is parsed to LayoutKey."""
        for name, field in cls.__fields__.items():
            if name in spec_dict:
                spec_dict[field.alias] = spec_dict.pop(name)
        if key_spec := spec_dict.get("k"):
            spec_dict["k"] = LayoutKey.from_key_spec(key_spec)
        return spec_dict

    @validator("key", pre=True)
    def get_key(cls, val) -> LayoutKey:
        """Parse each key from its key spec."""
        return val if isinstance(val, LayoutKey) else LayoutKey.from_key_spec(val)

    @validator("key_positions")
    def validate_positions(cls, val) -> Sequence[str]:
        """Make sure each combo has at least two positions."""
        assert len(val) >= 2, f"Need at least two key positions for combo but got {val}"
        return val

    @validator("slide")
    def validate_slide(cls, val) -> float:
        """Ensure slide is between -1 and 1."""
        if val is not None:
            assert -1.0 <= val <= 1.0, f"Slide value needs to be in [-1, 1] but got {val}"
        return val


class KeymapData(BaseModel):
    """Represents all data pertaining to a keymap, including layers, combos and physical layout."""

    layers: Mapping[str, Sequence[LayoutKey]]
    combos: Sequence[ComboSpec] = []

    # None-values only for use while parsing, i.e. no-layout mode
    layout: PhysicalLayout | None
    config: DrawConfig | None

    def get_combos_per_layer(self, layers: Iterable[str] | None = None) -> dict[str, list[ComboSpec]]:
        """Return a mapping of layer names to combos that are present on that layer."""
        if layers is None:
            layers = self.layers

        out: dict[str, list[ComboSpec]] = {layer_name: [] for layer_name in layers}
        for combo in self.combos:
            for layer_name in combo.layers if combo.layers else layers:
                if layer_name in layers:
                    out[layer_name].append(combo)
        return out

    def dump(self, num_cols: int = 0) -> dict:
        """Returns a dict-valued dump of the keymap representation."""
        dump = self.dict(exclude_defaults=True, exclude_unset=True, by_alias=True)
        if num_cols > 0:
            dump["layers"] = {
                name: [layer_keys[i : i + num_cols] for i in range(0, len(layer_keys), num_cols)]
                for name, layer_keys in dump["layers"].items()
            }
        return dump

    def rebase(self, base: "KeymapData") -> None:
        """
        Rebase a keymap on a "base" one: This mostly preserves the fields with the fields from
        the keymap, however for layers and combos it inherits fields from base that are not
        specified in the new keymap. For example this can be used to take an old keymap and update
        with a new parse output, while keeping manual additions like held keys and combo positioning.

        For layers, it uses a base key on each position when the layer with the same name exists in base.
        For combos, it uses `key_positions` and `layers` properties to associate old and new ones.
        """
        new_layers = {}
        for name, layer in self.layers.items():
            if base_layer := base.layers.get(name):
                assert len(base_layer) == len(
                    layer
                ), f'Cannot update from base keymap because layer lengths for "{name}" do not match'
                layer = [
                    base_key.copy(update=key.dict(exclude_unset=True, exclude_defaults=True, no_tapstr=True))
                    for base_key, key in zip(base_layer, layer)
                ]
            new_layers[name] = layer
        self.layers = new_layers

        base_combos_map = defaultdict(list)  # for faster lookup by key_positions
        for combo in base.combos:
            base_combos_map[tuple(sorted(combo.key_positions))].append(combo)

        def combo_matcher(combo: ComboSpec, ref_layers: set[str]) -> int:
            return len(ref_layers & set(combo.layers))

        new_combos = []
        for combo in self.combos:
            layers = set(combo.layers)

            # find all matching combos in base by key_positions, then use the one with the most layer overlap
            if base_matches := base_combos_map.get(tuple(sorted(combo.key_positions))):
                best_match = max(base_matches, key=partial(combo_matcher, ref_layers=layers))

                # need to handle key separately because update doesn't support nested models
                # https://github.com/pydantic/pydantic/issues/4177
                key = combo.key.copy(deep=True)
                combo = best_match.copy(update=combo.dict(exclude={"key"}, exclude_unset=True, exclude_defaults=True))
                combo.key = key

            new_combos.append(combo)
        self.combos = new_combos

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
        if vals["layout"] is None:  # ignore for no-layout mode
            return vals
        vals["layout"] = layout_factory(config=vals["config"], **vals["layout"])
        return vals

    @root_validator(skip_on_failure=True)
    def check_combos(cls, vals):
        """Validate combo positions are legitimate ones we can draw."""
        for combo in vals["combos"]:
            assert vals["layout"] is None or all(
                pos < len(vals["layout"]) for pos in combo.key_positions
            ), f"Combo positions exceed number of keys for combo '{combo}'"
            assert not combo.layers or all(
                l in vals["layers"] for l in combo.layers
            ), f"One of the layer names for combo '{combo}' is not found in the layer definitions"
        return vals

    @root_validator(skip_on_failure=True)
    def check_dimensions(cls, vals):
        """Validate that physical layout and layers have the same number of keys."""
        if vals["layout"] is None:  # ignore for no-layout mode
            return vals
        for name, layer in vals["layers"].items():
            assert len(layer) == len(vals["layout"]), (
                f'Number of keys on layer "{name}" ({len(layer)}) does not match physical layout '
                f'specification ({len(vals["layout"])})'
            )
        return vals
