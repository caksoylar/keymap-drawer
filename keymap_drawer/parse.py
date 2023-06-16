"""Module to parse QMK/ZMK keymaps into KeymapData and then dump them to dict."""
import re
import json
from io import TextIOWrapper
from pathlib import Path
from abc import ABC
from itertools import chain
from typing import Sequence

import yaml

from .keymap import LayoutKey, ComboSpec, KeymapData
from .config import ParseConfig
from .dts import DeviceTree


ZMK_LAYOUTS_PATH = Path(__file__).parent.parent / "resources" / "zmk_keyboard_layouts.yaml"


class KeymapParser(ABC):
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
        self.layer_activated_from: dict[int, set[int]] = {}
        self.trans_key = LayoutKey.from_key_spec(self.cfg.trans_legend)

    def update_layer_activated_from(self, from_layer: int | None, to_layer: int, key_positions: Sequence[int]) -> None:
        """
        Update the data structure that keeps track of what keys were held (i.e. momentary layer keys)
        in order to activate a given layer. Also considers what keys were already being held in order
        to activate the `from_layer` that the `to_layer` is being activated from.

        In order to properly keep track of multiple layer activation sequences, this method needs
        to be called in the order of increasing `to_layer` indices. It also ignores activating lower
        layer indices from higher layers and only considers the first discovered keys.
        """
        # ignore reverse order activations and if we already have a way to get to this layer
        if (from_layer is not None and from_layer >= to_layer) or to_layer in self.layer_activated_from:
            return
        self.layer_activated_from[to_layer] = set(key_positions)  # came here through these key(s)
        # also consider how the layer we are coming from got activated
        if from_layer is not None:
            self.layer_activated_from[to_layer] |= self.layer_activated_from.get(from_layer, set())

    def add_held_keys(self, layers: dict[str, list[LayoutKey]]) -> dict[str, list[LayoutKey]]:
        """Add "held" specifiers to keys that we previously determined were held to activate a given layer."""
        assert self.layer_names is not None
        for layer_index, activating_keys in self.layer_activated_from.items():
            for key_idx in activating_keys:
                key = layers[self.layer_names[layer_index]][key_idx]
                if key == self.trans_key:  # clear legend if it is a transparent key
                    layers[self.layer_names[layer_index]][key_idx] = LayoutKey(type="held")
                else:
                    key.type = "held"
        return layers

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


class QmkJsonParser(KeymapParser):
    """Parser for json-format QMK keymaps, like Configurator exports or `qmk c2json` outputs."""

    _prefix_re = re.compile(r"\bKC_")
    _trans_re = re.compile(r"TRANSPARENT|TRNS|_______")
    _mo_re = re.compile(r"MO\((\d+)\)")
    _mts_re = re.compile(r"([A-Z_]+)_T\((\S+)\)")
    _mtl_re = re.compile(r"MT\((\S+), *(\S+)\)")
    _lt_re = re.compile(r"LT\((\d+), *(\S+)\)")
    _osm_re = re.compile(r"OSM\(MOD_(\S+)\)")
    _osl_re = re.compile(r"OSL\((\d+)\)")

    def _str_to_key(  # pylint: disable=too-many-return-statements
        self, key_str: str, current_layer: int, key_positions: Sequence[int]
    ) -> LayoutKey:
        if key_str in self.cfg.raw_binding_map:
            return LayoutKey.from_key_spec(self.cfg.raw_binding_map[key_str])
        if self.cfg.skip_binding_parsing:
            return LayoutKey(tap=key_str)

        assert self.layer_names is not None

        def mapped(key: str) -> LayoutKey:
            return LayoutKey.from_key_spec(self.cfg.qmk_keycode_map.get(key, key.replace("_", " ")))

        key_str = self._prefix_re.sub("", key_str)

        if m := self._trans_re.fullmatch(key_str):  # transparent
            return self.trans_key
        if m := self._mo_re.fullmatch(key_str):  # momentary layer
            to_layer = int(m.group(1).strip())
            self.update_layer_activated_from(current_layer, to_layer, key_positions)
            return LayoutKey(tap=self.layer_names[to_layer])
        if m := self._mts_re.fullmatch(key_str):  # short mod-tap syntax
            tap_key = mapped(m.group(2).strip())
            return LayoutKey(tap=tap_key.tap, hold=m.group(1), shifted=tap_key.shifted)
        if m := self._mtl_re.fullmatch(key_str):  # long mod-tap syntax
            tap_key = mapped(m.group(2).strip())
            return LayoutKey(tap=tap_key.tap, hold=m.group(1).strip(), shifted=tap_key.shifted)
        if m := self._lt_re.fullmatch(key_str):  # layer-tap
            to_layer = int(m.group(1).strip())
            self.update_layer_activated_from(current_layer, to_layer, key_positions)
            tap_key = mapped(m.group(2).strip())
            return LayoutKey(tap=tap_key.tap, hold=self.layer_names[to_layer], shifted=tap_key.shifted)
        if m := self._osm_re.fullmatch(key_str):  # one-shot mod
            tap_key = mapped(m.group(1).strip())
            return LayoutKey(tap=tap_key.tap, hold=self.cfg.sticky_label, shifted=tap_key.shifted)
        if m := self._osl_re.fullmatch(key_str):  # one-shot layer
            to_layer = int(m.group(1).strip())
            self.update_layer_activated_from(current_layer, to_layer, key_positions)
            return LayoutKey(tap=self.layer_names[to_layer], hold=self.cfg.sticky_label)
        return mapped(key_str)

    def _parse(self, in_str: str, file_name: str | None = None) -> tuple[dict, KeymapData]:
        """
        Parse a JSON keymap with its file content and path (unused), then return the layout spec and KeymapData
        to be dumped to YAML.
        """

        raw = json.loads(in_str)

        layout = {}
        if "keyboard" in raw:
            layout["qmk_keyboard"] = raw["keyboard"]
        if "layout" in raw:
            layout["qmk_layout"] = raw["layout"]

        num_layers = len(raw["layers"])
        if self.layer_names is None:
            self.layer_names = [f"L{ind}" for ind in range(num_layers)]
        else:  # user-provided layer names
            assert (
                l_u := len(self.layer_names)
            ) == num_layers, (
                f"Length of provided layer name list ({l_u}) does not match the number of parsed layers ({num_layers})"
            )

        layers = {
            self.layer_names[ind]: [self._str_to_key(key, ind, [i]) for i, key in enumerate(layer)]
            for ind, layer in enumerate(raw["layers"])
        }

        layers = self.add_held_keys(layers)
        keymap_data = KeymapData(layers=layers, layout=None, config=None)

        return layout, keymap_data


class ZmkKeymapParser(KeymapParser):
    """Parser for ZMK devicetree keymaps, using C preprocessor and hacky pyparsing-based parsers."""

    _numbers_re = re.compile(r"N(UM(BER)?_)?(\d)")

    def __init__(
        self,
        config: ParseConfig,
        columns: int | None,
        base_keymap: KeymapData | None = None,
        layer_names: list[str] | None = None,
    ):
        super().__init__(config, columns, base_keymap, layer_names)
        self.hold_tap_labels = {"&mt": ["&kp", "&kp"], "&lt": ["&mo", "&kp"]}
        self.mod_morph_labels: dict[str, list[str]] = {}

    def _str_to_key(  # pylint: disable=too-many-return-statements,too-many-locals
        self, binding: str, current_layer: int | None, key_positions: Sequence[int], no_shifted: bool = False
    ) -> LayoutKey:
        if binding in self.cfg.raw_binding_map:
            return LayoutKey.from_key_spec(self.cfg.raw_binding_map[binding])
        if self.cfg.skip_binding_parsing:
            return LayoutKey(tap=binding)

        assert self.layer_names is not None

        def mapped(key: str) -> LayoutKey:
            mapped = LayoutKey.from_key_spec(
                self.cfg.zmk_keycode_map.get(
                    key, self._numbers_re.sub(r"\3", key).removeprefix("C_").removeprefix("K_").replace("_", " ")
                )
            )
            if no_shifted:
                mapped.shifted = ""
            return mapped

        match binding.split():
            case ["&none", *_]:
                return LayoutKey()
            case ["&trans"]:
                return self.trans_key
            case [ref, *_] if ref in self.mod_morph_labels:
                tap_key = self._str_to_key(self.mod_morph_labels[ref][0], current_layer, key_positions)
                shifted_key = self._str_to_key(self.mod_morph_labels[ref][1], current_layer, key_positions)
                return LayoutKey(tap=tap_key.tap, hold=tap_key.hold, shifted=shifted_key.tap)
            case ["&kp", par]:
                return mapped(par)
            case ["&sk", par]:
                l_key = mapped(par)
                return LayoutKey(tap=l_key.tap, hold=self.cfg.sticky_label, shifted=l_key.shifted)
            case [("&out" | "&bt" | "&ext_power" | "&rgb_ug"), *pars]:
                return LayoutKey(tap=" ".join(pars).replace("_", " ").replace(" SEL ", " "))
            case [("&mo" | "&to" | "&tog" | "&sl") as behavior, par]:
                if behavior in ("&mo", "&sl"):
                    self.update_layer_activated_from(current_layer, int(par), key_positions)
                return LayoutKey(
                    tap=self.layer_names[int(par)], hold=self.cfg.sticky_label if behavior == "&sl" else ""
                )
            case [ref, hold_par, tap_par] if ref in self.hold_tap_labels:
                hold_key = self._str_to_key(f"{self.hold_tap_labels[ref][0]} {hold_par}", current_layer, key_positions)
                tap_key = self._str_to_key(f"{self.hold_tap_labels[ref][1]} {tap_par}", current_layer, key_positions)
                return LayoutKey(tap=tap_key.tap, hold=hold_key.tap, shifted=tap_key.shifted)
            case [ref] | [ref, "0"]:
                return LayoutKey(tap=ref)
        return LayoutKey(tap=binding)

    def _update_behavior_labels(self, dts: DeviceTree) -> None:
        def get_behavior_bindings(compatible_value: str, n_bindings: int) -> dict[str, list[str]]:
            out = {}
            for node in dts.get_compatible_nodes(compatible_value):
                if not (bindings := node.get_phandle_array("(?<!sensor-)bindings")):
                    raise RuntimeError(f'Cannot parse bindings for behavior "{node.name}"')
                if node.label is None:
                    raise RuntimeError(f'Cannot find label for behavior "{node.name}"')
                out[f"&{node.label}"] = bindings[:n_bindings]
            return out

        self.hold_tap_labels |= get_behavior_bindings("zmk,behavior-hold-tap", 2)
        self.mod_morph_labels |= get_behavior_bindings("zmk,behavior-mod-morph", 2)

    def _get_layers(self, dts: DeviceTree) -> dict[str, list[LayoutKey]]:
        if not (layer_parents := dts.get_compatible_nodes("zmk,keymap")):
            raise RuntimeError('Could not find any keymap nodes with "zmk,keymap" compatible property')

        layer_nodes = [node for parent in layer_parents for node in parent.children]
        if self.layer_names is None:
            self.layer_names = [
                node.get_string("label") or node.name.removeprefix("layer_").removesuffix("_layer")
                for node in layer_nodes
            ]
        else:
            assert (l_u := len(self.layer_names)) == (
                l_p := len(layer_nodes)
            ), f"Length of provided layer name list ({l_u}) does not match the number of parsed layers ({l_p})"

        layers = {}
        for layer_ind, node in enumerate(layer_nodes):
            if bindings := node.get_phandle_array(r"(?<!sensor-)bindings"):
                layers[self.layer_names[layer_ind]] = [
                    self._str_to_key(binding, layer_ind, [i]) for i, binding in enumerate(bindings)
                ]
            else:
                raise RuntimeError(f'Could not parse `bindings` property under layer node "{node.name}"')
        return layers

    def _get_combos(self, dts: DeviceTree) -> list[ComboSpec]:
        assert self.layer_names is not None
        if not (combo_parents := dts.get_compatible_nodes("zmk,combos")):
            return []
        combo_nodes = chain.from_iterable(parent.children for parent in combo_parents)

        combos = []
        for node in combo_nodes:
            if not (bindings := node.get_phandle_array("bindings")):
                raise RuntimeError(f'Could not parse `bindings` for combo node "{node.name}"')
            if not (key_pos_strs := node.get_array("key-positions")):
                raise RuntimeError(f'Could not parse `key-positions` for combo node "{node.name}"')

            key_pos = [int(pos) for pos in key_pos_strs]
            combo = {
                "k": self._str_to_key(bindings[0], None, key_pos, no_shifted=True),  # ignore current layer for combos
                "p": key_pos,
            }
            if layers := node.get_array("layers"):
                combo["l"] = [self.layer_names[int(layer)] for layer in layers]

            # see if combo had additional properties specified in the config, if so merge them in
            cfg_combo = ComboSpec.normalize_fields(self.cfg.zmk_combos.get(node.name, {}))
            combos.append(ComboSpec(**(combo | cfg_combo)))
        return combos

    def _parse(self, in_str: str, file_name: str | None = None) -> tuple[dict, KeymapData]:
        """
        Parse a ZMK keymap with its content and path and return the layout spec and KeymapData to be dumped to YAML.
        """
        dts = DeviceTree(in_str, file_name, self.cfg.preprocess)
        self._update_behavior_labels(dts)
        layers = self._get_layers(dts)
        combos = self._get_combos(dts)
        layers = self.add_held_keys(layers)

        keymap_data = KeymapData(layers=layers, combos=combos, layout=None, config=None)

        if not file_name:
            return {}, keymap_data

        keyboard_name = Path(file_name).stem
        with open(ZMK_LAYOUTS_PATH, "rb") as f:
            keyboard_to_layout_map = yaml.safe_load(f)
        return keyboard_to_layout_map.get(keyboard_name), keymap_data
