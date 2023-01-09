"""Module to parse QMK/ZMK keymaps to a simplified KeymapData-like format."""
import sys
import re
import json
from io import StringIO
from itertools import chain

import pyparsing as pp
from pcpp.preprocessor import Preprocessor, OutputDirective, Action


def parse_qmk_json(path: str, columns: int | None, remove_prefixes: bool) -> dict:
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
            if remove_prefixes:
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

        if columns:
            parsed_keys = [parsed_keys[i:i + columns] for i in range(0, len(parsed_keys), columns)]

        out["layers"][f"L{ind}"] = {"keys": parsed_keys}

    return out


def _remove_zmk_prefix(binding):
    if binding.startswith('&'):
        binding = binding[1:]
    return re.sub(r"(kp|bt|mt|lt|none|trans) +", "", binding)

def _get_zmk_prepped(path, preprocess):
    clean_prep = re.compile(r"^\s*#.*?$", re.MULTILINE)
    with open(path, "r", encoding="utf-8") if path != "-" else sys.stdin as f:
        if preprocess:
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


def _get_zmk_combos(parsed, remove_prefixes):
    bindings_re = re.compile(r"bindings = <(.*?)>")
    keypos_re = re.compile(r"key-positions = <(.*?)>")
    layers_re = re.compile(r"layers = <(.*?)>")

    combo_parents = [node[1] for node in parsed if node[0] == "combos"]
    combo_nodes = [elt for node in combo_parents for elt in node if isinstance(elt, pp.ParseResults)]
    combos = []
    for node in combo_nodes:
        try:
            node_str = " ".join(item for item in node.as_list() if isinstance(item, str))
            binding = bindings_re.search(node_str).group(1)
            combos.append({
                "k": binding if not remove_prefixes else _remove_zmk_prefix(binding),
                "p": [int(pos) for pos in keypos_re.search(node_str).group(1).split()],
                "l": [int(layer) for layer in layers_re.search(node_str).group(1).split()],
            })
        except Exception:
            continue
    return combos


def parse_zmk_keymap(path: str, columns: int | None, remove_prefixes: bool, preprocess: bool):
    prepped = _get_zmk_prepped(path, preprocess)

    unparsed = '{ ' + prepped + ' };'
    parsed = pp.nested_expr('{', '};').ignore("//" + pp.SkipTo(pp.lineEnd)).ignore(pp.c_style_comment).parse_string(unparsed)[0]
    # print(parsed.dump())
    print(*_get_zmk_combos(parsed, remove_prefixes), sep='\n')

