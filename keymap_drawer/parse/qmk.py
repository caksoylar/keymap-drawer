"""Module containing class to parse json-format QMK keymaps."""

import json
import re
from typing import Sequence

from keymap_drawer.config import ParseConfig
from keymap_drawer.keymap import KeymapData, LayoutKey
from keymap_drawer.parse.parse import KeymapParser


class QmkJsonParser(KeymapParser):
    """Parser for json-format QMK keymaps, like Configurator exports or `qmk c2json` outputs."""

    _trans_re = re.compile(r"TRANSPARENT|TRNS|_______")
    _mo_re = re.compile(r"MO\((\d+)\)")
    _tog_re = re.compile(r"(TG|TO|DF)\((\d+)\)")
    _mts_re = re.compile(r"([A-Z_]+)_T\((\S+)\)")
    _mtl_re = re.compile(r"MT\((\S+), *(\S+)\)")
    _lt_re = re.compile(r"LT\((\d+), *(\S+)\)")
    _osm_re = re.compile(r"OSM\(MOD_(\S+)\)")
    _osl_re = re.compile(r"OSL\((\d+)\)")

    def __init__(
        self,
        config: ParseConfig,
        columns: int | None,
        base_keymap: KeymapData | None = None,
        layer_names: list[str] | None = None,
    ):
        super().__init__(config, columns, base_keymap, layer_names)
        self._prefix_re: re.Pattern | None
        if prefixes := self.cfg.qmk_remove_keycode_prefix:
            self._prefix_re = re.compile(r"\b(" + "|".join(re.escape(prefix) for prefix in set(prefixes)) + ")")
        else:
            self._prefix_re = None

    def _str_to_key(  # pylint: disable=too-many-return-statements
        self, key_str: str, current_layer: int, key_positions: Sequence[int]
    ) -> LayoutKey:
        if key_str in self.raw_binding_map:
            return LayoutKey.from_key_spec(self.raw_binding_map[key_str])
        if self.cfg.skip_binding_parsing:
            return LayoutKey(tap=key_str)

        assert self.layer_names is not None

        def mapped(key: str) -> LayoutKey:
            if self._prefix_re is not None:
                key = self._prefix_re.sub("", key)
            return LayoutKey.from_key_spec(self.cfg.qmk_keycode_map.get(key, key.replace("_", " ")))

        if m := self._trans_re.fullmatch(key_str):  # transparent
            return self.trans_key
        if m := self._mo_re.fullmatch(key_str):  # momentary layer
            to_layer = int(m.group(1).strip())
            self.update_layer_activated_from([current_layer], to_layer, key_positions)
            return LayoutKey(tap=self.layer_names[to_layer])
        if m := self._tog_re.fullmatch(key_str):  # toggled layer
            to_layer = int(m.group(2).strip())
            return LayoutKey(tap=self.layer_names[to_layer], hold=self.cfg.toggle_label)
        if m := self._mts_re.fullmatch(key_str):  # short mod-tap syntax
            tap_key = mapped(m.group(2).strip())
            return LayoutKey(tap=tap_key.tap, hold=m.group(1), shifted=tap_key.shifted)
        if m := self._mtl_re.fullmatch(key_str):  # long mod-tap syntax
            tap_key = mapped(m.group(2).strip())
            return LayoutKey(tap=tap_key.tap, hold=m.group(1).strip(), shifted=tap_key.shifted)
        if m := self._lt_re.fullmatch(key_str):  # layer-tap
            to_layer = int(m.group(1).strip())
            self.update_layer_activated_from([current_layer], to_layer, key_positions)
            tap_key = mapped(m.group(2).strip())
            return LayoutKey(tap=tap_key.tap, hold=self.layer_names[to_layer], shifted=tap_key.shifted)
        if m := self._osm_re.fullmatch(key_str):  # one-shot mod
            tap_key = mapped(m.group(1).strip())
            return LayoutKey(tap=tap_key.tap, hold=self.cfg.sticky_label, shifted=tap_key.shifted)
        if m := self._osl_re.fullmatch(key_str):  # one-shot layer
            to_layer = int(m.group(1).strip())
            self.update_layer_activated_from([current_layer], to_layer, key_positions)
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
