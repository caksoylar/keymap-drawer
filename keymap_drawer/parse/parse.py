"""
Module containing base parser class to parse keymaps into KeymapData and then dump them to dict.
Do not use directly, use QmkJsonParser or ZmkKeymapParser instead.
"""

from abc import ABC
from io import TextIOWrapper
from typing import Sequence

from keymap_drawer.config import ParseConfig
from keymap_drawer.keymap import KeymapData, LayoutKey


class KeymapParser(ABC):  # pylint: disable=too-many-instance-attributes
    """Abstract base class for parsing firmware keymap representations."""

    def __init__(
        self,
        config: ParseConfig,
        columns: int | None,
        base_keymap: KeymapData | None = None,
        layer_names: list[str] | None = None,
    ):
        self.cfg = config
        self.columns = columns if columns is not None else 0
        self.layer_names: list[str] | None = layer_names
        self.base_keymap = base_keymap
        self.layer_activated_from: dict[
            int, set[tuple[int, int]]
        ] = {}  # layer to [layer index, key position] from keys
        self.conditional_layers: dict[int, list[int]] = {}  # then-layer to if-layers mapping
        self.trans_key = LayoutKey.from_key_spec(self.cfg.trans_legend)
        self.raw_binding_map = self.cfg.raw_binding_map.copy()

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
        layer indices from higher layers and only considers the first discovered keys.
        """
        # ignore if we already have a way to get to this layer (unless mark_alternate_layer_activators is set)
        # or if this is a reverse layer order activation
        if (not self.cfg.mark_alternate_layer_activators and to_layer in self.layer_activated_from) or (
            from_layers and any(layer >= to_layer for layer in from_layers)
        ):
            return

        if to_layer not in self.layer_activated_from:
            self.layer_activated_from[to_layer] = set()

        for from_layer in from_layers:
            self.layer_activated_from[to_layer] |= set((from_layer, key_pos) for key_pos in key_positions)

        # also consider how the layer we are coming from got activated
        for from_layer in from_layers:
            self.layer_activated_from[to_layer] |= self.layer_activated_from.get(from_layer, set())

    def add_held_keys(self, layers: dict[str, list[LayoutKey]]) -> dict[str, list[LayoutKey]]:
        """Add "held" specifiers to keys that we previously determined were held to activate a given layer."""
        assert self.layer_names is not None

        # handle conditional layers
        for then_layer, if_layers in sorted(self.conditional_layers.items()):
            self.update_layer_activated_from(if_layers, then_layer, [])

        # assign held keys
        for layer_index, activating_keys in self.layer_activated_from.items():
            for _, key_idx in activating_keys:
                key = layers[self.layer_names[layer_index]][key_idx]
                if key == self.trans_key:  # clear legend if it is a transparent key
                    layers[self.layer_names[layer_index]][key_idx] = LayoutKey(type="held")
                else:
                    key.type = "held"

        return layers

    def fill_trans_keys(self, layers: dict[str, list[LayoutKey]]) -> dict[str, list[LayoutKey]]:
        """Fill in transparent keys with the legend of the key that is underneath."""
        assert self.layer_names is not None

        for layer_name, keys in layers.items():
            layer_idx = self.layer_names.index(layer_name)
            for key_idx, key in enumerate(keys):
                if key == self.trans_key:
                    lower_keys = self._find_lower_keys(layer_idx, key_idx, layers)
                    # usually there should only be one lower key, but if you can get to this layer
                    # that have this key defined, show all of them from multiple different layers
                    if len(lower_keys) > 0:
                        layers[layer_name][key_idx] = LayoutKey(
                            tap="|".join(key.tap for key in lower_keys),
                            hold="|".join(key.hold for key in lower_keys),
                            shifted="|".join(key.shifted for key in lower_keys),
                            type=self.trans_key.type,
                        )
        return layers

    def _find_lower_keys(self, layer: int, key: int, layers: dict[str, list[LayoutKey]]) -> set[LayoutKey]:
        assert self.layer_names is not None

        lower_keys = set()
        activated_from_keys = self.layer_activated_from.get(layer, set())

        for layer_idx, _ in activated_from_keys:
            layer_name = self.layer_names[layer_idx]
            from_layer = layers[layer_name]
            lower_key = from_layer[key]
            if lower_key == self.trans_key:
                lower_keys |= self._find_lower_keys(layer_idx, key, layers)
            else:
                lower_keys.add(lower_key)

        return lower_keys

    def _parse(self, in_str: str, file_name: str | None = None) -> tuple[dict, KeymapData]:
        raise NotImplementedError

    def parse(self, in_buf: TextIOWrapper) -> dict:
        """Wrapper to call parser on a file handle and do post-processing after firmware-specific parsing."""
        layout, keymap_data = self._parse(in_buf.read(), in_buf.name)

        if self.base_keymap is not None:
            keymap_data.rebase(self.base_keymap)

        keymap_dump = keymap_data.dump(self.columns)

        if layout:
            return {"layout": layout} | keymap_dump
        return keymap_dump
