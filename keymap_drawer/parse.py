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

    def __init__(self, config: ParseConfig, columns: int | None):
        self.cfg = config
        self.columns = columns if columns is not None else 0
        self.layer_names: list[str] | None = None

    def rearrange_layer(self, layer_keys: Sequence[LayoutKey]) -> Sequence[LayoutKey | Sequence[LayoutKey]]:
        """Convert a list of keys to list of list of keys to roughly correspond to rows."""
        if self.columns:
            return [layer_keys[i : i + self.columns] for i in range(0, len(layer_keys), self.columns)]
        return layer_keys

    def _parse(self, in_buf: BinaryIO, file_name: str | None = None):
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
                    return self._parse(f, str(in_arg))
            case _:
                return self._parse(in_arg, file_name)
                # raise ValueError(f"Unknown input argument {in_arg} with type {type(in_arg)} for parsing")


class QmkJsonParser(KeymapParser):
    """Parser for json-format QMK keymaps, like Configurator exports or `qmk c2json` outputs."""

    _prefix_re = re.compile(r"\bKC_")
    _mo_re = re.compile(r"MO\((\S+)\)")
    _mts_re = re.compile(r"([A-Z_]+)_T\((\S+)\)")
    _mtl_re = re.compile(r"MT\((\S+), *(\S+)\)")
    _lt_re = re.compile(r"LT\((\S+), *(\S+)\)")
    _osm_re = re.compile(r"OSM\(MOD_(\S+)\)")
    _osl_re = re.compile(r"OSL\((\S+)\)")

    def _str_to_key(self, key_str: str) -> LayoutKey:  # pylint: disable=too-many-return-statements
        if key_str in self.cfg.raw_binding_map:
            return LayoutKey.from_key_spec(self.cfg.raw_binding_map[key_str])
        if self.cfg.skip_binding_parsing:
            return LayoutKey(tap=key_str)

        def mapped(key: str) -> LayoutKey:
            return LayoutKey.from_key_spec(self.cfg.qmk_keycode_map.get(key, key.replace("_", " ")))

        key_str = self._prefix_re.sub("", key_str)

        if m := self._mo_re.fullmatch(key_str):
            return LayoutKey(tap=f"L{m.group(1).strip()}")
        if m := self._mts_re.fullmatch(key_str):
            tap_key = mapped(m.group(2).strip())
            return LayoutKey(tap=tap_key.tap, hold=m.group(1), shifted=tap_key.shifted)
        if m := self._mtl_re.fullmatch(key_str):
            tap_key = mapped(m.group(2).strip())
            return LayoutKey(tap=tap_key.tap, hold=m.group(1).strip(), shifted=tap_key.shifted)
        if m := self._lt_re.fullmatch(key_str):
            tap_key = mapped(m.group(2).strip())
            return LayoutKey(tap=tap_key.tap, hold=f"L{m.group(1).strip()}", shifted=tap_key.shifted)
        if m := self._osm_re.fullmatch(key_str):
            tap_key = mapped(m.group(1).strip())
            return LayoutKey(tap=tap_key.tap, hold="sticky", shifted=tap_key.shifted)
        if m := self._osl_re.fullmatch(key_str):
            return LayoutKey(tap=f"L{m.group(1).strip()}", hold="sticky")
        return mapped(key_str)

    def _parse(self, in_buf: BinaryIO, file_name: str | None = None) -> dict:
        """Parse a JSON keymap with its file handle and return a dict representation to be dumped to YAML."""

        raw = json.load(in_buf)

        layout = {}
        if "keyboard" in raw:
            layout["qmk_keyboard"] = raw["keyboard"]
        if "layout" in raw:
            layout["qmk_layout"] = raw["layout"]

        keymap_data = KeymapData(
            layers={f"L{ind}": [self._str_to_key(key) for key in layer] for ind, layer in enumerate(raw["layers"])},
            layout=None,
            config=None,
        )

        return {"layout": layout} | keymap_data.dump(self.columns)


class ZmkKeymapParser(KeymapParser):
    """Parser for ZMK devicetree keymaps, using C preprocessor and hacky pyparsing-based parsers."""

    _bindings_re = re.compile(r"(?<!sensor-)bindings = <(.*?)>")
    _keypos_re = re.compile(r"key-positions = <(.*?)>")
    _layers_re = re.compile(r"layers = <(.*?)>")
    _label_re = re.compile(r'label = "(.*?)"')
    _compatible_re = re.compile(r'compatible = "(.*?)"')
    _nodelabel_re = re.compile(r"([\w-]+) *: *([\w-]+) *{")
    _numbers_re = re.compile(r"N(UM(BER)?_)?(\d)")

    def __init__(self, config: ParseConfig, columns: int | None):
        super().__init__(config, columns)
        self.hold_tap_labels = {"&mt", "&lt"}

    def _str_to_key(  # pylint: disable=too-many-return-statements
        self, binding: str, no_shifted: bool = False
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
            case [("&mo" | "&to" | "&tog"), par]:
                return LayoutKey(tap=self.layer_names[int(par)])
            case ["&sl", par]:
                return LayoutKey(tap=self.layer_names[int(par)], hold="sticky")
            case [ref, hold_par, tap_par] if ref in self.hold_tap_labels:
                try:
                    hold = self.layer_names[int(hold_par)]
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
        for name, node in combo_nodes:
            try:
                node_str = " ".join(item for item in node.as_list() if isinstance(item, str))
                binding = self._bindings_re.search(node_str).group(1)  # type: ignore
                combo = {
                    "k": self._str_to_key(binding, no_shifted=True),
                    "p": [int(pos) for pos in self._keypos_re.search(node_str).group(1).split()],  # type: ignore
                }
                if m := self._layers_re.search(node_str):
                    combo["l"] = [self.layer_names[int(layer)] for layer in m.group(1).split()]

                # see if combo had additional properties specified in the config, if so merge them in
                cfg_combo = ComboSpec.normalize_fields(self.cfg.zmk_combos.get(name, {}))
                combos.append(ComboSpec(**(combo | cfg_combo)))
            except (AttributeError, ValueError):
                continue
        return combos

    def _parse(self, in_buf: BinaryIO, file_name: str | None = None) -> dict:
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

        keymap_data = KeymapData(layers=layers, combos=combos, layout=None, config=None)

        if not file_name:
            return keymap_data.dump(self.columns)

        keyboard_name = Path(file_name).stem
        with open(ZMK_LAYOUTS_PATH, "rb") as f:
            keyboard_to_layout_map = yaml.safe_load(f)
        return {"layout": keyboard_to_layout_map.get(keyboard_name)} | keymap_data.dump(self.columns)
