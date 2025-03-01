"""
Module containing base parser class to parse keymaps into KeymapData and then dump them to dict.
Do not use directly, use QmkJsonParser or ZmkKeymapParser instead.
"""

import logging
import re
from abc import ABC
from io import TextIOWrapper
from typing import Sequence

from keymap_drawer.config import ParseConfig
from keymap_drawer.keymap import KeymapData, LayoutKey

logger = logging.getLogger(__name__)


class ParseError(Exception):
    """Error type for exceptions that happen during keymap parsing."""


class KeymapParser(ABC):  # pylint: disable=too-many-instance-attributes
    """Abstract base class for parsing firmware keymap representations."""

    _modifier_fn_to_std: dict[str, list[str]]
    _modifier_fn_re: re.Pattern | None = None

    def __init__(
        self,
        config: ParseConfig,
        columns: int | None,
        base_keymap: KeymapData | None = None,
        layer_names: list[str] | None = None,
        virtual_layers: list[str] | None = None,
    ):
        self.cfg = config
        self.columns = columns if columns is not None else 0
        self.layer_names: list[str] | None = layer_names
        self.layer_legends: list[str] | None = None
        self.virtual_layers = virtual_layers if virtual_layers is not None else []
        if layer_names is not None:
            self._update_layer_legends()
        self.base_keymap = base_keymap
        self.layer_activated_from: dict[int, set[tuple[int, bool]]] = {}  # layer to key positions + alternate flags
        self.conditional_layers: dict[int, list[int]] = {}  # then-layer to if-layers mapping
        self.trans_key = LayoutKey.from_key_spec(self.cfg.trans_legend)
        self.raw_binding_map = self.cfg.raw_binding_map.copy()
        if self._modifier_fn_re is None:
            self._modifier_fn_re = re.compile(
                "(" + "|".join(re.escape(mod) for mod in self._modifier_fn_to_std) + r") *\( *(.*) *\)"
            )
        if (mod_map := self.cfg.modifier_fn_map) is not None:
            self._mod_combs_lookup = {
                frozenset(mods.split("+")): val for mods, val in mod_map.special_combinations.items()
            }

    def parse_modifier_fns(self, keycode: str) -> tuple[str, list[str]]:
        """
        Strip potential modifier functions from the keycode then return a tuple of the keycode and the modifiers.
        """
        if self.cfg.modifier_fn_map is None:
            return keycode, []

        def strip_modifiers(keycode: str, current_mods: list[str] | None = None) -> tuple[str, list[str]]:
            assert self._modifier_fn_re is not None

            if current_mods is None:
                current_mods = []
            if not (m := self._modifier_fn_re.fullmatch(keycode)):
                return keycode, current_mods
            return strip_modifiers(m.group(2), current_mods + self._modifier_fn_to_std[m.group(1)])

        return strip_modifiers(keycode)

    def format_modified_keys(self, key_str: str, modifiers: list[str]) -> str:
        """
        Format the combination of modifier functions and modified keycode into their display form,
        as configured by parse_config.modifier_fn_map.
        """
        if self.cfg.modifier_fn_map is None or not modifiers:
            return key_str

        if (combo_str := self._mod_combs_lookup.get(frozenset(modifiers))) is not None:
            fns_str = combo_str
        else:
            fn_map = self.cfg.modifier_fn_map.dict()
            assert all(
                mod in fn_map for mod in modifiers
            ), f"Not all modifier functions in {modifiers} have a corresponding mapping in parse_config.modifier_fn_map"
            fns_str = fn_map[modifiers[0]]
            for mod in modifiers[1:]:
                fns_str = self.cfg.modifier_fn_map.mod_combiner.format(mod_1=fns_str, mod_2=fn_map[mod])
        return self.cfg.modifier_fn_map.keycode_combiner.format(mods=fns_str, key=key_str)

    def update_layer_names(self, names: list[str]) -> None:
        """Update layer names to given list, then update legends."""
        assert self.layer_names is None  # make sure they weren't preset
        self.layer_names = names
        logger.debug("updated layer names: %s", self.layer_names)

        self._update_layer_legends()

    def _update_layer_legends(self) -> None:
        """Create layer legends from layer_legend_map in parse_config and inferred/provided layer names."""
        assert self.layer_names is not None
        for name in self.cfg.layer_legend_map:
            if name not in self.layer_names + self.virtual_layers:
                logger.warning('layer name "%s" in parse_config.layer_legend_map not found in keymap layers', name)

        self.layer_legends = [
            self.cfg.layer_legend_map.get(name, name) for name in self.layer_names + self.virtual_layers
        ]
        logger.debug("updated layer legends: %s", self.layer_legends)

    def update_layer_activated_from(
        self, from_layers: Sequence[int], to_layer: int, key_positions: Sequence[int]
    ) -> None:
        """
        Update the data structure that keeps track of what keys were held (i.e. momentary layer keys)
        in order to activate a given layer. Also considers what keys were already being held in order
        to activate the `from_layers` that the `to_layer` is being activated from.

        `from_layers` can be empty (e.g. for combos) or have multiple elements (for conditional layers).

        In order to properly keep track of multiple layer activation sequences, this method needs
        to be called in the order of increasing `to_layer` indices. It also ignores activating lower
        layer indices from higher layers.
        """
        # ignore if this is a reverse layer order activation
        if from_layers and any(layer >= to_layer for layer in from_layers):
            return

        # ignore if we already have a way to get to this layer (unless mark_alternate_layer_activators is set)
        is_alternate = False
        if to_layer in self.layer_activated_from:
            if self.cfg.mark_alternate_layer_activators:
                is_alternate = True
            else:
                return
        else:
            self.layer_activated_from[to_layer] = set()
        self.layer_activated_from[to_layer] |= {
            (k, is_alternate) for k in key_positions
        }  # came here through these key(s)

        # also consider how the layer we are coming from got activated
        for from_layer in from_layers:
            self.layer_activated_from[to_layer] |= {
                (k, is_alternate) for k, _ in self.layer_activated_from.get(from_layer, set())
            }

    def add_held_keys(self, layers: dict[str, list[LayoutKey]]) -> dict[str, list[LayoutKey]]:
        """Add "held" specifiers to keys that we previously determined were held to activate a given layer."""
        assert self.layer_names is not None

        # handle conditional layers
        for then_layer, if_layers in sorted(self.conditional_layers.items()):
            self.update_layer_activated_from(if_layers, then_layer, [])

        logger.debug("layers activated from key positions: %s", self.layer_activated_from)

        # assign held keys
        for layer_index, activating_keys in self.layer_activated_from.items():
            for key_idx, is_alternate in activating_keys:
                key = layers[self.layer_names[layer_index]][key_idx]
                if is_alternate and "held" in key.type:  # do not override primary held with alternate
                    continue

                key_type = "held alternate" if is_alternate else "held"
                if key == self.trans_key:  # clear legend if it is a transparent key
                    layers[self.layer_names[layer_index]][key_idx] = LayoutKey(type=key_type)
                else:
                    key.type = key_type

        return layers

    def append_virtual_layers(self, layers: dict[str, list[LayoutKey]]) -> dict[str, list[LayoutKey]]:
        """Add blank "virtual" layers at the end of the keymap, for use in later visualization."""
        layer_length = max(
            (len(layer) for layer in layers.values()), default=0
        )  # should all be equal, but that's validated later
        return layers | {name: [LayoutKey() for _ in range(layer_length)] for name in self.virtual_layers}

    def _parse(self, in_str: str, file_name: str | None = None) -> tuple[dict, KeymapData]:
        raise NotImplementedError

    def parse(self, in_buf: TextIOWrapper) -> dict:
        """Wrapper to call parser on a file handle and do post-processing after firmware-specific parsing."""
        layout, keymap_data = self._parse(in_buf.read(), in_buf.name)
        logger.debug("inferred physical layout: %s", layout)

        if self.base_keymap is not None:
            keymap_data.rebase(self.base_keymap)

        keymap_dump = keymap_data.dump(self.columns)

        if layout:
            return {"layout": layout} | keymap_dump
        return keymap_dump
