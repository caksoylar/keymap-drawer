"""Module containing class to parse devicetree format ZMK keymaps."""

import re
from itertools import chain
from pathlib import Path
from typing import Sequence

import yaml
import pyparsing as pp

from keymap_drawer.config import ParseConfig
from keymap_drawer.keymap import ComboSpec, KeymapData, LayoutKey
from keymap_drawer.parse.parse import KeymapParser, ParseError


# fmt: off
_DEFSRC_60 = [
    "grv", "1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "-", "=", "bspc",
    "tab", "q", "w", "e", "r", "t", "y", "u", "i", "o", "p", "[", "]", "\\",
    "caps", "a", "s", "d", "f", "g", "h", "j", "k", "l", ";", "'", "ret",
    "lsft", "z", "x", "c", "v", "b", "n", "m", ",", ".", "/", "rsft",
    "lctl", "lmet", "lalt", "spc", "ralt", "rmet", "cmps", "rctl"
]
# fmt: on
DEFSRC_TO_POS = {key: pos for pos, key in enumerate(_DEFSRC_60)}
PHYSICAL_LAYOUT = {"qmk_keyboard": "1upkeyboards/1up60rgb", "qmk_layout": "LAYOUT_60_ansi"}


class KanataKeymapParser(KeymapParser):
    """Parser for Kanata cfg keymaps, using pyparsing-based parsers."""

    _modifier_fn_to_std = {}

    def __init__(
        self,
        config: ParseConfig,
        columns: int | None,
        base_keymap: KeymapData | None = None,
        layer_names: list[str] | None = None,
    ):
        super().__init__(config, columns, base_keymap, layer_names)
        self.aliases = {}

    @classmethod
    def _parse_cfg(cls, cfg_str: str, file_path: Path | None) -> list[str | pp.ParseResults]:
        parsed = (
            pp.nested_expr("(", ")")
            .ignore(";;" + pp.SkipTo(pp.lineEnd))
            .ignore("#|" + pp.SkipTo("|#"))
            .parse_string("(" + cfg_str + ")")[0]
        )
        if file_path is None:
            return parsed
        includes = [node[1] for node in parsed if isinstance(node, pp.ParseResults) and node[0] == "include"]
        for include in includes[::-1]:
            with open(file_path.parent / Path(include), encoding="utf-8") as f:
                parsed = cls._parse_cfg(f.read, None) + parsed
        return parsed

    @classmethod
    def _element_to_str(cls, elt: str | pp.ParseResults) -> str:
        if isinstance(elt, str):
            return elt
        return "(" + " ".join(cls._element_to_str(sub) for sub in elt) + ")"

    def _str_to_key(  # pylint: disable=too-many-return-statements,too-many-locals
        self, binding: str | pp.ParseResults, current_layer: int | None, key_positions: Sequence[int], no_shifted: bool = False
    ) -> LayoutKey:
        # print(binding)
        if binding in self.raw_binding_map:
            return LayoutKey.from_key_spec(self.raw_binding_map[binding])
        if self.cfg.skip_binding_parsing:
            return LayoutKey(tap=binding)

        def recurse(new_binding):
            return self._str_to_key(new_binding, current_layer, key_positions) 

        orig_binding = binding

        if isinstance(binding, str) and binding.startswith("@"):
            binding = self.aliases.get(binding[1:], binding)

        if isinstance(binding, str):
            if binding in ("_", "‗", "≝"):
                return LayoutKey.from_key_spec(self.cfg.trans_legend)
            if binding in ("XX", "✗", "∅", "•"):
                return LayoutKey()
            if binding.startswith("🔣"):
                return LayoutKey(tap=binding[1:])
            return LayoutKey(tap=binding)

        assert isinstance(binding, pp.ParseResults)

        if binding[0].startswith("tap-hold"):
            tap_key = recurse(binding[3])
            hold_key = recurse(binding[4])
            return LayoutKey(tap=tap_key.tap, hold=hold_key.tap, shifted=tap_key.shifted)
        if binding[0] == "layer-switch":
            return LayoutKey(tap=binding[1], hold=self.cfg.toggle_label)
        if binding[0] in ("layer-while-held", "layer-toggle"):
            return LayoutKey(tap=binding[1])
        if binding[0] in ("unicode", "🔣"):
            return LayoutKey(tap=binding[1])
        if binding[0].startswith("release-"):
            return LayoutKey(tap=binding[1], hold="release")
        if binding[0].startswith("one-shot"):
            l_key = recurse(binding[2])
            return LayoutKey(tap=l_key.tap, hold=self.cfg.sticky_label, shifted=l_key.shifted)
        if binding[0] == "fork":
            main_key = recurse(binding[1])
            alt_key = recurse(binding[2])
            return LayoutKey(tap=main_key.tap, hold=main_key.hold, shifted=alt_key.tap)
        if binding[0] == "multi":
            return LayoutKey(tap=" +".join(recurse(bind).tap for bind in binding[1:]))

        return LayoutKey(tap=self._element_to_str(binding))

    #     assert self.layer_names is not None

    #     def mapped(key: str) -> LayoutKey:
    #         key, mods = self.parse_modifier_fns(key)
    #         if self._prefix_re is not None:
    #             key = self._prefix_re.sub("", key)
    #         mapped = LayoutKey.from_key_spec(
    #             self.cfg.zmk_keycode_map.get(
    #                 key,
    #                 self._numbers_re.sub(r"\3", key)
    #                 .removeprefix("C_")
    #                 .removeprefix("K_")
    #                 .replace("BT_SEL", "BT")
    #                 .replace("_", " "),
    #             )
    #         )
    #         if no_shifted:
    #             mapped.shifted = ""
    #         if mods:
    #             mapped.apply_formatter(lambda key: self.format_modified_keys(key, mods))
    #         return mapped

    #     match binding.split():
    #         case ["&none", *_]:
    #             return LayoutKey()
    #         case ["&trans"]:
    #             return self.trans_key
    #         case [ref, *_] if ref in self.mod_morphs:
    #             tap_key = self._str_to_key(self.mod_morphs[ref][0], current_layer, key_positions)
    #             shifted_key = self._str_to_key(self.mod_morphs[ref][1], current_layer, key_positions)
    #             return LayoutKey(tap=tap_key.tap, hold=tap_key.hold, shifted=shifted_key.tap)
    #         case ["&kp", *pars]:
    #             return mapped(" ".join(pars))
    #         case ["&kt", *pars]:
    #             l_key = mapped(" ".join(pars))
    #             return LayoutKey(tap=l_key.tap, hold=self.cfg.toggle_label, shifted=l_key.shifted)
    #         case [ref, *pars] if ref in self.sticky_keys:
    #             l_key = self._str_to_key(f"{self.sticky_keys[ref][0]} {' '.join(pars)}", current_layer, key_positions)
    #             return LayoutKey(tap=l_key.tap, hold=self.cfg.sticky_label, shifted=l_key.shifted)
    #         case ["&bt", *pars]:
    #             mapped_action = mapped(pars[0])
    #             if len(pars) == 1:
    #                 return mapped_action
    #             return LayoutKey(tap=mapped_action.tap, shifted=mapped_action.shifted, hold=pars[1])
    #         case [("&out" | "&ext_power" | "&rgb_ug"), *pars]:
    #             return LayoutKey(tap=" ".join(pars).replace("_", " "))
    #         case [("&mo" | "&to" | "&tog") as behavior, par]:
    #             if behavior in ("&mo",):
    #                 self.update_layer_activated_from(
    #                     [current_layer] if current_layer is not None else [], int(par), key_positions
    #                 )
    #                 return LayoutKey(tap=self.layer_names[int(par)])
    #             return LayoutKey(tap=self.layer_names[int(par)], hold=self.cfg.toggle_label)
    #         case [ref, hold_par, tap_par] if ref in self.hold_taps:
    #             hold_key = self._str_to_key(f"{self.hold_taps[ref][0]} {hold_par}", current_layer, key_positions)
    #             tap_key = self._str_to_key(f"{self.hold_taps[ref][1]} {tap_par}", current_layer, key_positions)
    #             return LayoutKey(tap=tap_key.tap, hold=hold_key.tap, shifted=tap_key.shifted)
    #         case [ref] | [ref, "0"]:
    #             return LayoutKey(tap=ref)
    #     return LayoutKey(tap=binding)

    # def _get_combos(self, dts: DeviceTree) -> list[ComboSpec]:
    #     return []

    # def _get_physical_layout(self, file_name: str | None, dts: DeviceTree) -> dict:
    #     pass

    def _parse(self, in_str: str, file_name: str | None = None) -> tuple[dict, KeymapData]:
        """
        Parse a ZMK keymap with its content and path and return the layout spec and KeymapData to be dumped to YAML.
        """
        nodes = self._parse_cfg(in_str, Path(file_name))
        defsrc = next(node[1:] for node in nodes if node[0] == "defsrc")

        try:
            defalias = list(chain.from_iterable(node[1:] for node in nodes if node[0] == "defalias"))
            self.aliases = {defalias[k]: defalias[k + 1] for k in range(0, len(defalias), 2)}
        except StopIteration:
            self.aliases = {}

        layer_nodes = {node[1]: node[2:] for node in nodes if node[0] == "deflayer"}
        # print(layer_nodes)
        self.layer_names = list(layer_nodes)

        layers: dict[str, list[LayoutKey]] = {}
        for layer_ind, (layer_name, layer) in enumerate(layer_nodes.items()):
            layers[layer_name] = [""] * len(_DEFSRC_60)
            for src_key, layer_key in zip(defsrc, layer):
                if (key_pos := DEFSRC_TO_POS.get(src_key)) is not None:
                    try:
                        layers[layer_name][key_pos] = self._str_to_key(layer_key, layer_ind, [key_pos])
                    except Exception as err:
                        raise ParseError(
                            f'Could not parse keycode "{layer_key}" in layer "{layer_name}" with exception "{err}"'
                        ) from err

        layers = self.add_held_keys(layers)
        keymap_data = KeymapData(layers=layers, layout=None, config=None)

        return PHYSICAL_LAYOUT, keymap_data
