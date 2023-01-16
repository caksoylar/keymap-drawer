"""Module to parse QMK/ZMK keymaps to a simplified KeymapData-like format."""
import sys
import re
import json
from io import StringIO
from abc import ABC
from itertools import chain

import pyparsing as pp
from pcpp.preprocessor import Preprocessor, OutputDirective, Action  # type: ignore

from .keymap import Layer, ComboSpec, KeymapData
from .config import ParseConfig


class KeymapParser(ABC):
    """Abstract base class for parsing firmware keymap representations."""

    def __init__(self, config: ParseConfig, columns: int | None):
        self.cfg = config
        self.columns = columns
        self.layer_names: list[str] | None = None
        self._dict_args = {"exclude_defaults": True, "exclude_unset": True, "by_alias": True}

    def rearrange_layer(self, layer_keys: list) -> list:
        """Convert a list of keys to list of list of keys to roughly correspond to rows."""
        if self.columns:
            return [layer_keys[i : i + self.columns] for i in range(0, len(layer_keys), self.columns)]
        return layer_keys


class QmkJsonParser(KeymapParser):
    """Parser for json-format QMK keymaps, like Configurator exports or `qmk c2json` outputs."""

    _prefix_re = re.compile(r"\bKC_")
    _mo_re = re.compile(r"MO\((\S+)\)")
    _mts_re = re.compile(r"([A-Z_]+)_T\((\S+)\)")
    _mtl_re = re.compile(r"MT\((\S+), *(\S+)\)")
    _lt_re = re.compile(r"LT\((\S+), *(\S+)\)")

    def _str_to_key_spec(self, key_str: str) -> str | dict:
        if self.cfg.skip_binding_parsing:
            return key_str

        key_str = self._prefix_re.sub("", key_str)

        if m := self._mo_re.fullmatch(key_str):
            return f"L{m.group(1).strip()}"
        if m := self._mts_re.fullmatch(key_str):
            return {"t": m.group(2).strip(), "h": m.group(1)}
        if m := self._mtl_re.fullmatch(key_str):
            return {"t": m.group(2).strip(), "h": m.group(1).strip()}
        if m := self._lt_re.fullmatch(key_str):
            return {"t": m.group(2).strip(), "h": f"L{m.group(1).strip()}"}
        return key_str

    def parse(self, path: str) -> dict:
        """Parse a JSON keymap with its file path and return a dict representation to be dumped to YAML."""

        with open(path, "rb") if path != "-" else sys.stdin.buffer as f:
            raw = json.load(f)

        layout = {}
        if "keyboard" in raw:
            layout["qmk_keyboard"] = raw["keyboard"]
        if "layout" in raw:
            layout["qmk_layout"] = raw["layout"]

        layers = {}
        for ind, layer in enumerate(raw["layers"]):
            layer = Layer(keys=[self._str_to_key_spec(key) for key in layer]).dict(**self._dict_args)
            layers[f"L{ind}"] = {"keys": self.rearrange_layer(layer["keys"])}

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

    def _str_to_key_spec(self, binding: str) -> str | dict:  # pylint: disable=too-many-return-statements
        if self.cfg.skip_binding_parsing:
            return binding
        match binding.split():
            case ["&none"] | ["&trans"]:
                return ""
            case [ref]:
                return ref
            case ["&kp", par]:
                return self._numbers_re.sub(r"\3", par).removeprefix("C_").removeprefix("K_").replace("_", " ")
            case ["&sk", par]:
                return {"t": par, "h": "sticky"}
            case [("&out" | "&bt"), *pars]:
                return " ".join(pars).replace("_", " ")
            case [("&mo" | "&to" | "&tog"), par]:
                return self.layer_names[int(par)]
            case ["&sl", par]:
                return {"t": self.layer_names[int(par)], "h": "sticky"}
            case [ref, hold_par, tap_par] if ref in self.hold_tap_labels:
                try:
                    hold_par = self.layer_names[int(hold_par)]
                except (ValueError, IndexError):
                    pass
                return {"t": tap_par, "h": hold_par}
        return binding

    def _get_prepped(self, path: str) -> str:
        with open(path, "r", encoding="utf-8") if path != "-" else sys.stdin as f:
            if self.cfg.preprocess:

                def include_handler(*args):
                    raise OutputDirective(Action.IgnoreAndPassThrough)

                preprocessor = Preprocessor()
                preprocessor.line_directive = None
                preprocessor.on_include_not_found = include_handler
                preprocessor.parse(f)
                with StringIO() as f_out:
                    preprocessor.write(f_out)
                    prepped = f_out.getvalue()
            else:
                prepped = f.read()
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

    def _update_hold_tap_labels(self, parsed: list[pp.ParseResults]) -> None:
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

    def _get_layers(self, parsed: list[pp.ParseResults]) -> dict[str, Layer]:
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
                layers[layer_name] = Layer(
                    keys=[
                        self._str_to_key_spec("&" + stripped)
                        for binding in self._bindings_re.search(node_str).group(1).split("&")  # type: ignore
                        if (stripped := binding.strip().removeprefix("&"))
                    ]
                )
            except AttributeError:
                continue
        return layers

    def _get_combos(self, parsed: list[pp.ParseResults]) -> list[ComboSpec]:
        assert self.layer_names is not None
        combo_parents = chain.from_iterable(self._find_nodes_with_name(node, "combos") for node in parsed)
        combo_nodes = chain.from_iterable(self._find_nodes_with_name(node) for _, node in combo_parents)

        combos = []
        for _, node in combo_nodes:
            try:
                node_str = " ".join(item for item in node.as_list() if isinstance(item, str))
                binding = self._bindings_re.search(node_str).group(1)  # type: ignore
                combo = {
                    "k": self._str_to_key_spec(binding),
                    "p": [int(pos) for pos in self._keypos_re.search(node_str).group(1).split()],  # type: ignore
                }
                if m := self._layers_re.search(node_str):
                    combo["l"] = [self.layer_names[int(layer)] for layer in m.group(1).split()]  # type: ignore
                combos.append(ComboSpec(**combo))
            except (AttributeError, ValueError):
                continue
        return combos

    def parse(self, path: str) -> dict:
        """Parse a ZMK keymap with its file path and return a dict representation to be dumped to YAML."""
        prepped = self._get_prepped(path)
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

        layers = KeymapData.assign_combos_to_layers({"layers": layers, "combos": combos})["layers"]
        layers_dict = {name: layer.dict(**self._dict_args) for name, layer in layers.items()}
        for name, layer in layers_dict.items():
            layer["keys"] = self.rearrange_layer(layer["keys"])

        return {"layers": layers_dict}
