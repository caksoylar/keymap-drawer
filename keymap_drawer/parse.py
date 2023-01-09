"""Module to parse QMK/ZMK keymaps to a simplified KeymapData-like format."""
import sys
import re
import json
from io import StringIO
from abc import ABC

import pyparsing as pp
from pcpp.preprocessor import Preprocessor, OutputDirective, Action


class KeymapParser(ABC):
    def __init__(self, columns: int | None, remove_prefixes: bool):
        self.columns = columns
        self.remove_prefixes = remove_prefixes

    def rearrange_layer(self, layer_keys):
        if self.columns:
            return [layer_keys[i : i + self.columns] for i in range(0, len(layer_keys), self.columns)]
        return layer_keys


class QmkJsonParser(KeymapParser):
    def __init__(self, columns: int | None, remove_prefixes: bool):
        super().__init__(columns, remove_prefixes)

    def parse(self, path) -> dict:
        prefix_re = re.compile(r"\bKC_")
        mo_re = re.compile(r"MO\((\S+)\)")
        mts_re = re.compile(r"([A-Z_]+)_T\((\S+)\)")
        mtl_re = re.compile(r"MT\((\S+),(\S+)\)")
        lt_re = re.compile(r"LT\((\S+),(\S+)\)")

        with open(path, "rb") if path != "-" else sys.stdin as f:
            raw = json.load(f)

        out = {"layout": {}, "layers": {}}
        if "keyboard" in raw:
            out["layout"]["qmk_keyboard"] = raw["keyboard"]
        if "layout" in raw:
            out["layout"]["qmk_layout"] = raw["layout"]

        for ind, layer in enumerate(raw["layers"]):
            parsed_keys = []
            for key in layer:
                if self.remove_prefixes:
                    key = prefix_re.sub("", key)

                if m := mo_re.fullmatch(key):
                    parsed = f"L{m.group(1).strip()}"
                elif m := mts_re.fullmatch(key):
                    parsed = {"t": m.group(2).strip(), "h": m.group(1)}
                elif m := mtl_re.fullmatch(key):
                    parsed = {"t": m.group(2).strip(), "h": m.group(1).strip()}
                elif m := lt_re.fullmatch(key):
                    parsed = {"t": m.group(2).strip(), "h": f"L{m.group(1).strip()}"}
                else:
                    parsed = key

                parsed_keys.append(parsed)

            out["layers"][f"L{ind}"] = {"keys": self.rearrange_layer(parsed_keys)}

        return out


class ZmkKeymapParser(KeymapParser):
    def __init__(self, columns: int | None, remove_prefixes: bool, preprocess: bool):
        super().__init__(columns, remove_prefixes)
        self.preprocess = preprocess
        self._bindings_re = re.compile(r"bindings = <(.*?)>")
        self._keypos_re = re.compile(r"key-positions = <(.*?)>")
        self._layers_re = re.compile(r"layers = <(.*?)>")

    @staticmethod
    def _remove_prefix(binding):
        if binding.startswith("&"):
            binding = binding[1:]
        return re.sub(r"(kp|bt|mt|lt|none|trans) +", "", binding)

    def _get_prepped(self, path):
        clean_prep = re.compile(r"^\s*#.*?$", re.MULTILINE)
        with open(path, "r", encoding="utf-8") if path != "-" else sys.stdin as f:
            if self.preprocess:

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
            return clean_prep.sub("", prepped)

    def _get_combos(self, parsed):
        combo_parents = [node[1] for node in parsed if node[0] == "combos"]
        combo_nodes = [elt for node in combo_parents for elt in node if isinstance(elt, pp.ParseResults)]
        combos = []
        for node in combo_nodes:
            try:
                node_str = " ".join(item for item in node.as_list() if isinstance(item, str))
                binding = self._bindings_re.search(node_str).group(1)
                combos.append(
                    {
                        "k": binding if not self.remove_prefixes else self._remove_prefix(binding),
                        "p": [int(pos) for pos in self._keypos_re.search(node_str).group(1).split()],
                        "l": [int(layer) for layer in self._layers_re.search(node_str).group(1).split()],
                    }
                )
            except Exception:
                continue
        return combos

    def parse(self, path) -> dict:
        prepped = self._get_prepped(path)

        unparsed = "{ " + prepped + " };"
        parsed = (
            pp.nested_expr("{", "};")
            .ignore("//" + pp.SkipTo(pp.lineEnd))
            .ignore(pp.c_style_comment)
            .parse_string(unparsed)[0]
        )
        # print(parsed.dump())
        print(*self._get_combos(parsed), sep="\n")
