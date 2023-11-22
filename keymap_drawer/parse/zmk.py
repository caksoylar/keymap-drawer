"""Module containing class to parse devicetree format ZMK keymaps."""

import re
from itertools import chain
from pathlib import Path
from typing import Sequence

import yaml

from keymap_drawer.config import ParseConfig
from keymap_drawer.keymap import ComboSpec, KeymapData, LayoutKey
from keymap_drawer.parse.dts import DeviceTree
from keymap_drawer.parse.parse import KeymapParser

ZMK_LAYOUTS_PATH = Path(__file__).parent.parent.parent / "resources" / "zmk_keyboard_layouts.yaml"


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
        self.hold_taps = {"&mt": ["&kp", "&kp"], "&lt": ["&mo", "&kp"]}
        self.mod_morphs = {"&gresc": ["&kp ESC", "&kp GRAVE"]}
        self.sticky_keys = {"&sk": ["&kp"], "&sl": ["&mo"]}
        self._prefix_re: re.Pattern | None
        if prefixes := self.cfg.zmk_remove_keycode_prefix:
            self._prefix_re = re.compile(r"\b(" + "|".join(re.escape(prefix) for prefix in set(prefixes)) + ")")
        else:
            self._prefix_re = None

    def _update_raw_binding_map(self, dts: DeviceTree) -> None:
        raw_keys = list(self.raw_binding_map.keys())
        prep_keys = dts.preprocess_extra_data("\n".join(raw_keys)).splitlines()
        assert len(raw_keys) == len(
            prep_keys
        ), "Keys in parse_config.raw_binding_map did not preprocess properly, please check for issues"
        for old, new in zip(raw_keys, prep_keys):
            if new != old:
                self.raw_binding_map[new] = self.raw_binding_map[old]
                del self.raw_binding_map[old]

    def _str_to_key(  # pylint: disable=too-many-return-statements,too-many-locals
        self, binding: str, current_layer: int | None, key_positions: Sequence[int], no_shifted: bool = False
    ) -> LayoutKey:
        if binding in self.raw_binding_map:
            return LayoutKey.from_key_spec(self.raw_binding_map[binding])
        if self.cfg.skip_binding_parsing:
            return LayoutKey(tap=binding)

        assert self.layer_names is not None

        def mapped(key: str) -> LayoutKey:
            if self._prefix_re is not None:
                key = self._prefix_re.sub("", key)
            mapped = LayoutKey.from_key_spec(
                self.cfg.zmk_keycode_map.get(
                    key,
                    self._numbers_re.sub(r"\3", key)
                    .removeprefix("C_")
                    .removeprefix("K_")
                    .replace("BT_SEL", "BT")
                    .replace("_", " "),
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
            case [ref, *_] if ref in self.mod_morphs:
                tap_key = self._str_to_key(self.mod_morphs[ref][0], current_layer, key_positions)
                shifted_key = self._str_to_key(self.mod_morphs[ref][1], current_layer, key_positions)
                return LayoutKey(tap=tap_key.tap, hold=tap_key.hold, shifted=shifted_key.tap)
            case ["&kp", *pars]:
                return mapped(" ".join(pars))
            case ["&kt", *pars]:
                l_key = mapped(" ".join(pars))
                return LayoutKey(tap=l_key.tap, hold=self.cfg.toggle_label, shifted=l_key.shifted)
            case [ref, *pars] if ref in self.sticky_keys:
                l_key = self._str_to_key(f"{self.sticky_keys[ref][0]} {' '.join(pars)}", current_layer, key_positions)
                return LayoutKey(tap=l_key.tap, hold=self.cfg.sticky_label, shifted=l_key.shifted)
            case ["&bt", *pars]:
                mapped_action = mapped(pars[0])
                if len(pars) == 1:
                    return mapped_action
                return LayoutKey(tap=mapped_action.tap, shifted=mapped_action.shifted, hold=pars[1])
            case [("&out" | "&ext_power" | "&rgb_ug"), *pars]:
                return LayoutKey(tap=" ".join(pars).replace("_", " "))
            case [("&mo" | "&to" | "&tog") as behavior, par]:
                if behavior in ("&mo",):
                    self.update_layer_activated_from(
                        [current_layer] if current_layer is not None else [], int(par), key_positions
                    )
                    return LayoutKey(tap=self.layer_names[int(par)])
                return LayoutKey(tap=self.layer_names[int(par)], hold=self.cfg.toggle_label)
            case [ref, hold_par, tap_par] if ref in self.hold_taps:
                hold_key = self._str_to_key(f"{self.hold_taps[ref][0]} {hold_par}", current_layer, key_positions)
                tap_key = self._str_to_key(f"{self.hold_taps[ref][1]} {tap_par}", current_layer, key_positions)
                return LayoutKey(tap=tap_key.tap, hold=hold_key.tap, shifted=tap_key.shifted)
            case [ref] | [ref, "0"]:
                return LayoutKey(tap=ref)
        return LayoutKey(tap=binding)

    def _update_behaviors(self, dts: DeviceTree) -> None:
        def get_behavior_bindings(compatible_value: str, n_bindings: int) -> dict[str, list[str]]:
            out = {}
            for node in dts.get_compatible_nodes(compatible_value):
                if not (bindings := node.get_phandle_array("(?<!sensor-)bindings")):
                    raise RuntimeError(f'Cannot parse bindings for behavior "{node.name}"')
                if node.label is None:
                    raise RuntimeError(f'Cannot find label for behavior "{node.name}"')
                out[f"&{node.label}"] = bindings[:n_bindings]
            return out

        self.hold_taps |= get_behavior_bindings("zmk,behavior-hold-tap", 2)
        self.mod_morphs |= get_behavior_bindings("zmk,behavior-mod-morph", 2)
        self.sticky_keys |= get_behavior_bindings("zmk,behavior-sticky-key", 1)

    def _update_conditional_layers(self, dts: DeviceTree) -> None:
        cl_parents = dts.get_compatible_nodes("zmk,conditional-layers")
        cl_nodes = [node for parent in cl_parents for node in parent.children]
        for node in cl_nodes:
            if not (then_layer_val := node.get_array("then-layer")):
                raise RuntimeError(f'Could not parse `then-layer` for conditional layer node "{node.name}"')
            if not (if_layers := node.get_array("if-layers")):
                raise RuntimeError(f'Could not parse `if-layers` for conditional layer node "{node.name}"')
            self.conditional_layers[int(then_layer_val[0])] = [int(val) for val in if_layers]

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

    def _get_physical_layout(self, file_name: str | None, dts: DeviceTree) -> dict:
        if not file_name:
            return {}

        keyboard_name = Path(file_name).stem
        with open(ZMK_LAYOUTS_PATH, "rb") as f:
            keyboard_to_layout_map = yaml.safe_load(f)

        if (keyboard_layouts := keyboard_to_layout_map.get(keyboard_name)) is None:
            return {}

        # if no chosen set, use first transform as the default
        if (transform := dts.get_chosen_property("zmk,matrix_transform")) is None:
            return next(iter(keyboard_layouts.values()))

        return keyboard_layouts.get(transform, {})

    def _parse(self, in_str: str, file_name: str | None = None) -> tuple[dict, KeymapData]:
        """
        Parse a ZMK keymap with its content and path and return the layout spec and KeymapData to be dumped to YAML.
        """
        dts = DeviceTree(in_str, file_name, self.cfg.preprocess, add_define="KEYMAP_DRAWER")

        if self.cfg.preprocess and self.raw_binding_map:
            self._update_raw_binding_map(dts)

        self._update_behaviors(dts)
        self._update_conditional_layers(dts)
        layers = self._get_layers(dts)
        combos = self._get_combos(dts)
        layers = self.add_held_keys(layers)

        keymap_data = KeymapData(layers=layers, combos=combos, layout=None, config=None)

        return self._get_physical_layout(file_name, dts), keymap_data
