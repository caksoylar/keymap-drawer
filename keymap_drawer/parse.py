"""Module to parse QMK/ZMK keymaps to a simplified KeymapData-like format."""
import sys
import re
import json
from io import StringIO, TextIOWrapper
from abc import ABC
from itertools import chain
from typing import Sequence, BinaryIO

import pyparsing as pp
from pcpp.preprocessor import Preprocessor, OutputDirective, Action  # type: ignore

from .keymap import LayoutKey, ComboSpec
from .config import ParseConfig


class KeymapParser(ABC):
    """Abstract base class for parsing firmware keymap representations."""

    def __init__(self, config: ParseConfig, columns: int | None):
        self.cfg = config
        self.columns = columns
        self.layer_names: list[str] | None = None
        self._dict_args = {"exclude_defaults": True, "exclude_unset": True, "by_alias": True}

    def rearrange_layer(self, layer_keys: Sequence[LayoutKey]) -> Sequence[LayoutKey | Sequence[LayoutKey]]:
        """Convert a list of keys to list of list of keys to roughly correspond to rows."""
        if self.columns:
            return [layer_keys[i : i + self.columns] for i in range(0, len(layer_keys), self.columns)]
        return layer_keys

    def _parse(self, in_buf: BinaryIO):
        raise NotImplementedError

    def parse(self, in_arg: str | BinaryIO) -> dict:
        """Wrapper to call parser on a file handle, given a handle or a file path."""
        match in_arg:
            # TODO: Figure out why BinaryIO doesn't match open file handle `_io.BufferedReader` or
            # UploadedFile returned by streamlit's file_uploader widget
            # case BinaryIO():
            #     return self._parse(in_arg)
            case str():
                with open(in_arg, "rb") if in_arg != "-" else sys.stdin.buffer as f:
                    return self._parse(f)
            case _:
                return self._parse(in_arg)
                # raise ValueError(f"Unknown input argument {in_arg} with type {type(in_arg)} for parsing")


class QmkJsonParser(KeymapParser):
    """Parser for json-format QMK keymaps, like Configurator exports or `qmk c2json` outputs."""

    _prefix_re = re.compile(r"\bKC_")
    _mo_re = re.compile(r"MO\((\S+)\)")
    _mts_re = re.compile(r"([A-Z_]+)_T\((\S+)\)")
    _mtl_re = re.compile(r"MT\((\S+), *(\S+)\)")
    _lt_re = re.compile(r"LT\((\S+), *(\S+)\)")

    def _str_to_key(self, key_str: str) -> LayoutKey:  # pylint: disable=too-many-return-statements
        if key_str in self.cfg.raw_binding_map:
            return LayoutKey.from_key_spec(self.cfg.raw_binding_map[key_str])
        if self.cfg.skip_binding_parsing:
            return LayoutKey(tap=key_str)

        def mapped(key: str) -> str:
            return self.cfg.qmk_keycode_map.get(key, key)

        key_str = self._prefix_re.sub("", key_str)

        if m := self._mo_re.fullmatch(key_str):
            return LayoutKey(tap=f"L{m.group(1).strip()}")
        if m := self._mts_re.fullmatch(key_str):
            return LayoutKey(tap=mapped(m.group(2).strip()), hold=m.group(1))
        if m := self._mtl_re.fullmatch(key_str):
            return LayoutKey(tap=mapped(m.group(2).strip()), hold=m.group(1).strip())
        if m := self._lt_re.fullmatch(key_str):
            return LayoutKey(tap=mapped(m.group(2).strip()), hold=f"L{m.group(1).strip()}")
        return LayoutKey(tap=mapped(key_str))

    def _parse(self, in_buf: BinaryIO) -> dict:
        """Parse a JSON keymap with its file handle and return a dict representation to be dumped to YAML."""

        raw = json.load(in_buf)

        layout = {}
        if "keyboard" in raw:
            layout["qmk_keyboard"] = raw["keyboard"]
        if "layout" in raw:
            layout["qmk_layout"] = raw["layout"]

        layers = {
            f"L{ind}": self.rearrange_layer([self._str_to_key(key).dict(**self._dict_args) for key in layer])
            for ind, layer in enumerate(raw["layers"])
        }

        return {"layout": layout, "layers": layers}


class ZmkKeymapParser(KeymapParser):
    """Parser for ZMK devicetree keymaps, using C preprocessor and hacky pyparsing-based parsers."""

    _bindings_re = re.compile(r"bindings = <(.*?)>")
    _keypos_re = re.compile(r"key-positions = <(.*?)>")
    _layers_re = re.compile(r"layers = <(.*?)>")
    _label_re = re.compile(r'label = "(.*?)"')
    _compatible_re = re.compile(r'compatible = "(.*?)"')
    _nodelabel_re = re.compile(r"([\w-]+) *: *([\w-]+) *{")
    _numbers_re = re.compile(r"N(UM(BER)?_)?(\d)")

    def __init__(self, config: ParseConfig, columns: int | None):
        super().__init__(config, columns)
        self.hold_tap_labels = {"&mt", "&lt"}

    def _str_to_key(self, binding: str) -> LayoutKey:  # pylint: disable=too-many-return-statements
        if binding in self.cfg.raw_binding_map:
            return LayoutKey.from_key_spec(self.cfg.raw_binding_map[binding])
        if self.cfg.skip_binding_parsing:
            return LayoutKey(tap=binding)

        def mapped(key: str) -> str:
            if key in self.cfg.zmk_keycode_map:
                return self.cfg.zmk_keycode_map[key]
            return self._numbers_re.sub(r"\3", key).removeprefix("C_").removeprefix("K_").replace("_", " ")

        match binding.split():
            case ["&none"] | ["&trans"]:
                return LayoutKey(tap="")
            case [ref]:
                return LayoutKey(tap=ref)
            case ["&kp", par]:
                return LayoutKey(tap=mapped(par))
            case ["&sk", par]:
                return LayoutKey(tap=mapped(par), hold="sticky")
            case [("&out" | "&bt" | "&ext_power" | "&rgb_ug"), *pars]:
                return LayoutKey(tap=" ".join(pars).replace("_", " ").replace(" SEL ", " "))
            case [("&mo" | "&to" | "&tog"), par]:
                return LayoutKey(tap=self.layer_names[int(par)])
            case ["&sl", par]:
                return LayoutKey(tap=self.layer_names[int(par)], hold="sticky")
            case [ref, hold_par, tap_par] if ref in self.hold_tap_labels:
                try:
                    hold_par = self.layer_names[int(hold_par)]
                except (ValueError, IndexError):  # not a layer-tap, so maybe a keycode?
                    hold_par = mapped(hold_par)
                return LayoutKey(tap=mapped(tap_par), hold=hold_par)
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
                and (node_name is None or elt_p == node_name)
                and isinstance(elt_n, pp.ParseResults)
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
        for layer_name, node_str in zip(self.layer_names, layer_nodes.values()):
            try:
                layers[layer_name] = [
                    self._str_to_key("&" + stripped)
                    for binding in self._bindings_re.search(node_str).group(1).split("&")  # type: ignore
                    if (stripped := binding.strip().removeprefix("&"))
                ]
            except AttributeError:
                continue
        return layers

    def _get_combos(self, parsed: Sequence[pp.ParseResults]) -> list[ComboSpec]:
        assert self.layer_names is not None
        combo_parents = chain.from_iterable(self._find_nodes_with_name(node, "combos") for node in parsed)
        combo_nodes = chain.from_iterable(self._find_nodes_with_name(node) for _, node in combo_parents)

        combos = []
        for _, node in combo_nodes:
            try:
                node_str = " ".join(item for item in node.as_list() if isinstance(item, str))
                binding = self._bindings_re.search(node_str).group(1)  # type: ignore
                combo = {
                    "k": self._str_to_key(binding),
                    "p": [int(pos) for pos in self._keypos_re.search(node_str).group(1).split()],  # type: ignore
                }
                if m := self._layers_re.search(node_str):
                    combo["l"] = [self.layer_names[int(layer)] for layer in m.group(1).split()]
                combos.append(ComboSpec(**combo))
            except (AttributeError, ValueError):
                continue
        return combos

    def _parse(self, in_buf: BinaryIO) -> dict:
        """Parse a ZMK keymap with its file handle and return a dict representation to be dumped to YAML."""
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

        out = {
            "layers": {
                name: self.rearrange_layer([key.dict(**self._dict_args) for key in layer])
                for name, layer in layers.items()
            }
        }
        if combos:
            out["combos"] = [combo.dict(**self._dict_args) for combo in combos]  # type: ignore
        return out
