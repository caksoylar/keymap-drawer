"""
Module with classes that define the keymap representation, with multiple layers
containing key and combo specifications, paired with the physical keyboard layout.
"""

from collections import defaultdict
from functools import partial
from itertools import chain
from typing import Callable, Iterable, Literal

from pydantic import AliasChoices, BaseModel, Field, field_validator, model_serializer, model_validator

from keymap_drawer.config import Config
from keymap_drawer.physical_layout import PhysicalLayout, PhysicalLayoutGenerator


class LayoutKey(BaseModel, populate_by_name=True, coerce_numbers_to_str=True, extra="forbid"):
    """
    Represents a binding in the keymap, which has a tap property by default and
    can optionally have hold or shifted properties, left or right labels, or be "held" or be a "ghost" key.
    """

    tap: str = Field(validation_alias=AliasChoices("center", "t"), serialization_alias="t", default="")
    hold: str = Field(validation_alias=AliasChoices("bottom", "h"), serialization_alias="h", default="")
    shifted: str = Field(validation_alias=AliasChoices("shifted", "s"), serialization_alias="s", default="")
    left: str = ""
    right: str = ""

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

    @model_serializer
    def serialize_model(self) -> str | dict[str, str]:
        """Custom serializer to output string-only for simple legends."""
        if self.hold or self.shifted or self.left or self.right or self.type:
            return {
                k: v
                for k, v in (
                    ("t", self.tap),
                    ("h", self.hold),
                    ("s", self.shifted),
                    ("left", self.left),
                    ("right", self.right),
                    ("type", self.type),
                )
                if v
            }
        return self.tap

    def full_serializer(self) -> dict[str, str]:
        """Custom serializer that always outputs a dict."""
        return {k: v for k in ("tap", "hold", "shifted", "left", "right", "type") if (v := getattr(self, k))}

    def apply_formatter(self, formatter: Callable[[str], str]) -> None:
        """Add a formatter function (str -> str) to all non-empty fields."""
        if self.tap:
            self.tap = formatter(self.tap)
        if self.hold:
            self.hold = formatter(self.hold)
        if self.shifted:
            self.shifted = formatter(self.shifted)
        if self.left:
            self.left = formatter(self.left)
        if self.right:
            self.right = formatter(self.right)


class ComboSpec(BaseModel, populate_by_name=True, extra="forbid"):
    """
    Represents a combo in the keymap, with the trigger positions, activated binding (key)
    and layers that it is present on.
    """

    key_positions: list[int] = Field(alias="p", default=[])
    trigger_keys: list[LayoutKey] = Field(alias="tk", default=[])
    key: LayoutKey = Field(alias="k")
    layers: list[str] = Field(alias="l", default=[])
    align: Literal["mid", "top", "bottom", "left", "right"] = Field(alias="a", default="mid")
    offset: float = Field(alias="o", default=0.0)
    dendron: bool | None = Field(alias="d", default=None)
    slide: float | None = Field(alias="s", default=None, ge=-1.0, le=1.0)
    arc_scale: float = 1.0
    type: str = ""
    width: float | None = Field(alias="w", default=None)
    height: float | None = Field(alias="h", default=None)
    rotation: float = Field(alias="r", default=0.0)
    draw_separate: bool | None = None
    hidden: bool = False

    @classmethod
    def normalize_fields(cls, spec_dict: dict) -> dict:
        """Normalize spec_dict so that each field uses its alias and key is parsed to LayoutKey."""
        for name, field in cls.model_fields.items():
            if name in spec_dict:
                spec_dict[field.alias or name] = spec_dict.pop(name)
        if key_spec := spec_dict.get("k"):
            spec_dict["k"] = LayoutKey.from_key_spec(key_spec)
        return spec_dict

    @model_validator(mode="after")
    def validate_trigger_spec(self):
        """Make sure either positions or trigger keys are specified."""
        assert (not self.key_positions and self.trigger_keys) or (
            self.key_positions and not self.trigger_keys
        ), "Need to specify exactly one of `key_positions` or `trigger_keys` for combo"
        return self

    @field_validator("key", mode="before")
    @classmethod
    def get_key(cls, val) -> LayoutKey:
        """Parse each key from its key spec."""
        return val if isinstance(val, LayoutKey) else LayoutKey.from_key_spec(val)

    @field_validator("trigger_keys", mode="before")
    @classmethod
    def get_trigger_keys(cls, val) -> list[LayoutKey]:
        """Parse each trigger key from its key spec."""
        return [item if isinstance(item, LayoutKey) else LayoutKey.from_key_spec(item) for item in val]

    @field_validator("key_positions")
    @classmethod
    def validate_positions(cls, val) -> list[str]:
        """Make sure each combo has at least two positions."""
        assert not val or len(val) >= 2, f"Need at least two key positions for combo but got {val}"
        return val

    @field_validator("key_positions")
    @classmethod
    def validate_trigger_keys(cls, val) -> list[str]:
        """Make sure each combo has at least two trigger keys."""
        assert not val or len(val) >= 2, f"Need at least two trigger keys for combo but got {val}"
        return val


class KeymapData(BaseModel):
    """Represents all data pertaining to a keymap, including layers, combos and physical layout."""

    layers: dict[str, list[LayoutKey]]
    combos: list[ComboSpec] = []

    # None-values only for use while parsing, i.e. no-layout mode
    layout: PhysicalLayout | None = None
    config: Config | None = None

    def _resolve_key_positions_from_trigger_keys(self, combo: ComboSpec) -> None:
        assert combo.trigger_keys
        for layer in combo.layers if combo.layers else list(self.layers):
            # try full legend match
            matches = [
                next(
                    (ind for ind, layer_key in enumerate(self.layers[layer]) if key == layer_key),
                    None,
                )
                for key in combo.trigger_keys
            ]
            if all(ind is not None for ind in matches):
                combo.key_positions = matches  # type: ignore
                return

            # try matching by only tap legend
            matches = [
                next(
                    (ind for ind, layer_key in enumerate(self.layers[layer]) if key == LayoutKey(tap=layer_key.tap)),
                    None,
                )
                for key in combo.trigger_keys
            ]
            if all(ind is not None for ind in matches):
                combo.key_positions = matches  # type: ignore
                return

        raise ValueError(f'Cannot find matching key positions in the layers for trigger keys "{combo.trigger_keys}"')

    def get_combos_per_layer(self, layers: Iterable[str] | None = None) -> dict[str, list[ComboSpec]]:
        """Return a mapping of layer names to combos that are present on that layer, if they aren't drawn separately."""
        assert self.config is not None
        if layers is None:
            layers = self.layers

        out: dict[str, list[ComboSpec]] = {layer_name: [] for layer_name in layers}
        for combo in self.combos:
            if combo.draw_separate or (combo.draw_separate is None and self.config.draw_config.separate_combo_diagrams):
                continue
            for layer_name in combo.layers if combo.layers else layers:
                if layer_name in layers:
                    out[layer_name].append(combo)
        return out

    def get_separate_combos(self) -> list[ComboSpec]:
        """Return a list of combos that are meant to be drawn separately."""
        assert self.config is not None
        return [
            combo
            for combo in self.combos
            if combo.draw_separate or (combo.draw_separate is None and self.config.draw_config.separate_combo_diagrams)
        ]

    def dump(self, num_cols: int = 0) -> dict:
        """Returns a dict-valued dump of the keymap representation."""
        dump = self.model_dump(exclude_defaults=True, exclude_unset=True, by_alias=True)
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
                layer = [base_key.model_copy(update=key.full_serializer()) for base_key, key in zip(base_layer, layer)]
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
                key = combo.key.model_copy(deep=True)
                combo = best_match.model_copy(
                    update=combo.model_dump(exclude={"key"}, exclude_unset=True, exclude_defaults=True)
                )
                combo.key = key

            new_combos.append(combo)
        self.combos = new_combos

    @field_validator("layers", mode="before")
    @classmethod
    def parse_layers(cls, val) -> dict[str, list[LayoutKey]]:
        """Parse each key on layer from its key spec, flattening the spec if it contains sublists."""
        assert val, "No layers found"
        return {
            layer_name: [
                val if isinstance(val, LayoutKey) else LayoutKey.from_key_spec(val)
                for val in chain.from_iterable(
                    v if isinstance(v, list) and not isinstance(v, str) else [v] for v in keys
                )
            ]
            for layer_name, keys in val.items()
        }

    @model_validator(mode="before")
    @classmethod
    def create_layout(cls, vals):
        """Create layout with type given by layout param."""
        if vals["layout"] is None:  # ignore for no-layout mode
            return vals
        if isinstance(vals["layout"], PhysicalLayout):  # already provided a valid object
            return vals
        vals["layout"] = PhysicalLayoutGenerator(config=vals["config"], **vals["layout"]).generate()
        return vals

    @model_validator(mode="after")
    def check_combos(self):
        """Resolve trigger keys if specified then validate combo positions are legitimate ones we can draw."""
        for combo in self.combos:
            if combo.trigger_keys:
                self._resolve_key_positions_from_trigger_keys(combo)

            assert self.layout is None or all(
                pos < len(self.layout) for pos in combo.key_positions
            ), f"Combo positions ({combo.key_positions}) exceed number of keys ({len(self.layout)}) for combo '{combo}'"
            assert not combo.layers or all(
                l in self.layers for l in combo.layers
            ), f"One of the layer names for combo '{combo}' is not found in the layer definitions"
        return self

    @model_validator(mode="after")
    def check_dimensions(self):
        """Validate that physical layout and layers have the same number of keys."""
        if self.layout is None:  # only check self-consistency for no-layout mode
            if len(set(len(layer) for layer in self.layers.values())) != 1:
                counts = {layer_name: len(layer) for layer_name, layer in self.layers.items()}
                raise AssertionError(f"Number of keys differ between layers. Key counts found: {counts}")
            return self
        for name, layer in self.layers.items():
            assert len(layer) == len(self.layout), (
                f'Number of keys on layer "{name}" ({len(layer)}) does not match physical layout '
                f"specification ({len(self.layout)})"
            )
        return self
