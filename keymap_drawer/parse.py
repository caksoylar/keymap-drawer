"""Module to parse QMK/ZMK keymaps into KeymapData and then dump them to dict."""
import re
import json
from io import StringIO, TextIOWrapper
from pathlib import Path
from abc import ABC
from itertools import chain
from typing import Sequence, BinaryIO

import yaml
import pyparsing as pp
from pcpp.preprocessor import Preprocessor, OutputDirective, Action  # type: ignore

from .keymap import LayoutKey, ComboSpec, KeymapData
from .config import ParseConfig


ZMK_LAYOUTS_PATH = Path(__file__).parent.parent / "resources" / "zmk_keyboard_layouts.yaml"


class KeymapParser(ABC):
    """Abstract base class for parsing firmware keymap representations."""

    def __init__(self, config: ParseConfig, columns: int | None, base_keymap: KeymapData | None = None):
        self.cfg = config
        self.columns = columns if columns is not None else 0
        self.layer_names: list[str] | None = None
        self.base_keymap = base_keymap
        self.layer_activated_from: dict[int, set[int]] = {}

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
            for key in activating_keys:
                layers[self.layer_names[layer_index]][key].type = "held"
        return layers

    def _parse(self, in_buf: BinaryIO, file_name: str | None = None) -> tuple[dict, KeymapData]:
        raise NotImplementedError

    def parse(self, in_arg: Path | BinaryIO, file_name: str | None = None) -> dict:
        """Wrapper to call parser on a file handle, given a handle or a file path."""
        match in_arg:
            # TODO: Figure out why BinaryIO doesn't match open file handle `_io.BufferedReader` or
            # UploadedFile returned by streamlit's file_uploader widget
            # case BinaryIO():
            #     return self._parse(in_arg)
            case Path():
                with open(in_arg, "rb") as f:
                    layout, keymap_data = self._parse(f, str(in_arg))
            case _:
                # raise ValueError(f"Unknown input argument {in_arg} with type {type(in_arg)} for parsing")
                layout, keymap_data = self._parse(in_arg, file_name)

        if self.base_keymap is not None:
            keymap_data.rebase(self.base_keymap)

        keymap_dump = keymap_data.dump(self.columns)

        if layout:
            return {"layout": layout} | keymap_dump
        return keymap_dump


class QmkJsonParser(KeymapParser):
    """Parser for json-format QMK keymaps, like Configurator exports or `qmk c2json` outputs."""

    _prefix_re = re.compile(r"\bKC_")
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

        def mapped(key: str) -> LayoutKey:
            return LayoutKey.from_key_spec(self.cfg.qmk_keycode_map.get(key, key.replace("_", " ")))

        key_str = self._prefix_re.sub("", key_str)

        if m := self._mo_re.fullmatch(key_str):
            to_layer = int(m.group(1).strip())
            self.update_layer_activated_from(current_layer, to_layer, key_positions)
            return LayoutKey(tap=f"L{to_layer}")
        if m := self._mts_re.fullmatch(key_str):
            tap_key = mapped(m.group(2).strip())
            return LayoutKey(tap=tap_key.tap, hold=m.group(1), shifted=tap_key.shifted)
        if m := self._mtl_re.fullmatch(key_str):
            tap_key = mapped(m.group(2).strip())
            return LayoutKey(tap=tap_key.tap, hold=m.group(1).strip(), shifted=tap_key.shifted)
        if m := self._lt_re.fullmatch(key_str):
            to_layer = int(m.group(1).strip())
            self.update_layer_activated_from(current_layer, to_layer, key_positions)
            tap_key = mapped(m.group(2).strip())
            return LayoutKey(tap=tap_key.tap, hold=f"L{to_layer}", shifted=tap_key.shifted)
        if m := self._osm_re.fullmatch(key_str):
            tap_key = mapped(m.group(1).strip())
            return LayoutKey(tap=tap_key.tap, hold="sticky", shifted=tap_key.shifted)
        if m := self._osl_re.fullmatch(key_str):
            to_layer = int(m.group(1).strip())
            self.update_layer_activated_from(current_layer, to_layer, key_positions)
            return LayoutKey(tap=f"L{to_layer}", hold="sticky")
        return mapped(key_str)

    def _parse(self, in_buf: BinaryIO, file_name: str | None = None) -> tuple[dict, KeymapData]:
        """Parse a JSON keymap with its file handle and return the layout spec and KeymapData to be dumped to YAML."""

        raw = json.load(in_buf)

        layout = {}
        if "keyboard" in raw:
            layout["qmk_keyboard"] = raw["keyboard"]
        if "layout" in raw:
            layout["qmk_layout"] = raw["layout"]

        layers = {}
        self.layer_names = []
        for ind, layer in enumerate(raw["layers"]):
            layer_name = f"L{ind}"
            self.layer_names.append(layer_name)
            layers[layer_name] = [self._str_to_key(key, ind, [i]) for i, key in enumerate(layer)]

        layers = self.add_held_keys(layers)
        keymap_data = KeymapData(layers=layers, layout=None, config=None)

        return layout, keymap_data


class ZmkKeymapParser(KeymapParser):
    """Parser for ZMK devicetree keymaps, using C preprocessor and hacky pyparsing-based parsers."""

    _bindings_re = re.compile(r"(?<!sensor-)bindings = <(.*?)>")
    _keypos_re = re.compile(r"key-positions = <(.*?)>")
    _layers_re = re.compile(r"layers = <(.*?)>")
    _label_re = re.compile(r'label = "(.*?)"')
    _compatible_re = re.compile(r'compatible = "(.*?)"')
    _nodelabel_re = re.compile(r"([\w-]+) *: *([\w-]+) *{")
    _numbers_re = re.compile(r"N(UM(BER)?_)?(\d)")

    def __init__(self, config: ParseConfig, columns: int | None, base_keymap: KeymapData | None = None):
        super().__init__(config, columns, base_keymap)
        self.hold_tap_labels = {"&mt", "&lt"}

    def _str_to_key(  # pylint: disable=too-many-return-statements
        self, binding: str, current_layer: int | None, key_positions: Sequence[int], no_shifted: bool = False
    ) -> LayoutKey:
        if binding in self.cfg.raw_binding_map:
            return LayoutKey.from_key_spec(self.cfg.raw_binding_map[binding])
        if self.cfg.skip_binding_parsing:
            return LayoutKey(tap=binding)

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
            case ["&none"] | ["&trans"]:
                return LayoutKey()
            case [ref]:
                return LayoutKey(tap=ref)
            case ["&kp", par]:
                return mapped(par)
            case ["&sk", par]:
                l_key = mapped(par)
                return LayoutKey(tap=l_key.tap, hold="sticky", shifted=l_key.shifted)
            case [("&out" | "&bt" | "&ext_power" | "&rgb_ug"), *pars]:
                return LayoutKey(tap=" ".join(pars).replace("_", " ").replace(" SEL ", " "))
            case [("&mo" | "&to" | "&tog" | "&sl") as behavior, par]:
                if behavior in ("&mo", "&sl"):
                    self.update_layer_activated_from(current_layer, int(par), key_positions)
                return LayoutKey(tap=self.layer_names[int(par)], hold="sticky" if behavior == "&sl" else "")
            case [ref, hold_par, tap_par] if ref in self.hold_tap_labels:
                try:
                    hold = self.layer_names[int(hold_par)]
                    self.update_layer_activated_from(current_layer, int(hold_par), key_positions)
                except (ValueError, IndexError):  # not a layer-tap, so maybe a keycode?
                    hold = mapped(hold_par).tap
                tap_key = mapped(tap_par)
                return LayoutKey(tap=tap_key.tap, hold=hold, shifted=tap_key.shifted)
        return LayoutKey(tap=binding)

    def _get_prepped(self, in_buf: BinaryIO) -> str:
        wrapper = TextIOWrapper(in_buf, encoding="utf-8")
        if self.cfg.preprocess:

            def include_handler(*args):
                raise OutputDirective(Action.IgnoreAndPassThrough)

            preprocessor = Preprocessor()
            preprocessor.line_directive = None
            preprocessor.on_include_not_found = include_handler
            preprocessor.parse(wrapper)
            with StringIO() as f_out:
                preprocessor.write(f_out)
                prepped = f_out.getvalue()
        else:
            prepped = wrapper.read()
        return re.sub(r"^\s*#.*?$", "", prepped)

    def _find_nodes_with_name(
        self, parsed: pp.ParseResults, node_name: str | None = None
    ) -> list[tuple[str, pp.ParseResults]]:
        found_nodes = []
        for elt_p, elt_n in zip(parsed[:-1], parsed[1:]):
            if (
                isinstance(elt_p, str)
                and isinstance(elt_n, pp.ParseResults)
                and (node_name is None or elt_p.rsplit(":", maxsplit=1)[-1] == node_name)
            ):
                found_nodes.append((elt_p, elt_n))
        return found_nodes

    def _update_hold_tap_labels(self, parsed: Sequence[pp.ParseResults]) -> None:
        behavior_parents = chain.from_iterable(self._find_nodes_with_name(node, "behaviors") for node in parsed)
        behavior_nodes = {
            node_name: " ".join(item for item in node.as_list() if isinstance(item, str))
            for node_name, node in chain.from_iterable(self._find_nodes_with_name(node) for _, node in behavior_parents)
        }
        for name, node_str in behavior_nodes.items():
            if ":" not in name:
                continue
            if (m := self._compatible_re.search(node_str)) and m.group(1) == "zmk,behavior-hold-tap":
                self.hold_tap_labels.add("&" + name.split(":", 1)[0])

    def _get_layers(self, parsed: Sequence[pp.ParseResults]) -> dict[str, list[LayoutKey]]:
        layer_parents = chain.from_iterable(self._find_nodes_with_name(node, "keymap") for node in parsed)
        layer_nodes = {
            node_name: " ".join(item for item in node.as_list() if isinstance(item, str))
            for node_name, node in chain.from_iterable(self._find_nodes_with_name(node) for _, node in layer_parents)
        }
        self.layer_names: list[str] = [
            m.group(1) if (m := self._label_re.search(node_str)) else node_name
            for node_name, node_str in layer_nodes.items()
        ]
        layers = {}
        for layer_ind, node_str in enumerate(layer_nodes.values()):
            layer_name = self.layer_names[layer_ind]
            try:
                key_strs = [
                    f"&{stripped}"
                    for binding in self._bindings_re.search(node_str).group(1).split("&")  # type: ignore
                    if (stripped := binding.strip().removeprefix("&"))
                ]
                layers[layer_name] = [self._str_to_key(binding, layer_ind, [i]) for i, binding in enumerate(key_strs)]
            except AttributeError:
                continue
        return layers

    def _get_combos(self, parsed: Sequence[pp.ParseResults]) -> list[ComboSpec]:
        assert self.layer_names is not None
        combo_parents = chain.from_iterable(self._find_nodes_with_name(node, "combos") for node in parsed)
        combo_nodes = chain.from_iterable(self._find_nodes_with_name(node) for _, node in combo_parents)

        combos = []
        for name, node in combo_nodes:
            try:
                node_str = " ".join(item for item in node.as_list() if isinstance(item, str))
                binding = self._bindings_re.search(node_str).group(1)  # type: ignore
                key_pos = [int(pos) for pos in self._keypos_re.search(node_str).group(1).split()]  # type: ignore
                combo = {
                    "k": self._str_to_key(binding, None, key_pos, no_shifted=True),  # ignore current layer for combos
                    "p": key_pos,
                }
                if m := self._layers_re.search(node_str):
                    combo["l"] = [self.layer_names[int(layer)] for layer in m.group(1).split()]

                # see if combo had additional properties specified in the config, if so merge them in
                cfg_combo = ComboSpec.normalize_fields(self.cfg.zmk_combos.get(name, {}))
                combos.append(ComboSpec(**(combo | cfg_combo)))
            except (AttributeError, ValueError):
                continue
        return combos

    def _parse(self, in_buf: BinaryIO, file_name: str | None = None) -> tuple[dict, KeymapData]:
        """Parse a ZMK keymap with its file handle and return the layout spec and KeymapData to be dumped to YAML."""
        prepped = self._get_prepped(in_buf)
        parsed = [
            node
            for node in (
                pp.nested_expr("{", "};")
                .ignore("//" + pp.SkipTo(pp.lineEnd))
                .ignore(pp.c_style_comment)
                .parse_string("{ " + self._nodelabel_re.sub(r"\1:\2 {", prepped) + " };")[0]
            )
            if isinstance(node, pp.ParseResults)
        ]
        self._update_hold_tap_labels(parsed)
        layers = self._get_layers(parsed)
        combos = self._get_combos(parsed)
        layers = self.add_held_keys(layers)

        keymap_data = KeymapData(layers=layers, combos=combos, layout=None, config=None)

        if not file_name:
            return {}, keymap_data

        keyboard_name = Path(file_name).stem
        with open(ZMK_LAYOUTS_PATH, "rb") as f:
            keyboard_to_layout_map = yaml.safe_load(f)
        return keyboard_to_layout_map.get(keyboard_name), keymap_data
