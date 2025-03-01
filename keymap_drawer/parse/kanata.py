"""Module containing class to parse devicetree format ZMK keymaps."""

import json
import logging
from itertools import chain, islice
from pathlib import Path
from typing import Iterable, Sequence

import pyparsing as pp

from keymap_drawer.config import ParseConfig
from keymap_drawer.keymap import ComboSpec, KeymapData, LayoutKey
from keymap_drawer.parse.parse import KeymapParser, ParseError

logger = logging.getLogger(__name__)

DEFSRC_CLASSES = Path(__file__).parent.parent.parent / "resources" / "kanata" / "defsrc_classes.json"
PHYSICAL_LAYOUTS = Path(__file__).parent.parent.parent / "resources" / "kanata" / "layout_srcs.json"


def _get_canonical_defsrc_lookup() -> dict[str, str]:
    with open(DEFSRC_CLASSES, "rb") as f:
        data = json.load(f)
    return {other: defsrc_class[0] for defsrc_class in data for other in defsrc_class}


def _get_layouts() -> list[dict]:
    with open(PHYSICAL_LAYOUTS, "rb") as f:
        layouts = json.load(f)
    for layout in layouts:
        layout["defsrc_index"] = set(layout["defsrc"])
    return layouts


class KanataKeymapParser(KeymapParser):
    """Parser for Kanata cfg keymaps, using pyparsing-based parsers."""

    _modifier_fn_to_std = {}
    _available_layouts: list[dict] = _get_layouts()
    _canonical_defsrcs: dict[str, str] = _get_canonical_defsrc_lookup()

    def __init__(
        self,
        config: ParseConfig,
        columns: int | None,
        base_keymap: KeymapData | None = None,
        layer_names: list[str] | None = None,
        virtual_layers: list[str] | None = None,
    ):
        super().__init__(config, columns, base_keymap, layer_names)
        self.aliases: dict[str, str | pp.ParseResults] = {}
        self.vars: dict[str, str | pp.ParseResults] = {}
        self.physical_layout: dict | None = None
        self.defsrc_indices: list[int] | None = None
        self.defsrc_to_pos: dict[str, int] | None = None

    @classmethod
    def _parse_cfg(cls, cfg_str: str, file_path: Path | None) -> list[pp.ParseResults]:
        parsed = (
            pp.nested_expr("(", ")")
            .ignore(";;" + pp.SkipTo(pp.lineEnd))
            .ignore("#|" + pp.SkipTo("|#"))
            .parse_string("(" + cfg_str + ")")[0]
        )
        if file_path is None:
            return parsed
        includes = [node[1] for node in parsed if isinstance(node, pp.ParseResults) and node[0] == "include"]
        logger.debug("found include files: %s", includes)
        for include in includes[::-1]:
            with open(file_path.parent / Path(include), encoding="utf-8") as f:
                parsed = cls._parse_cfg(f.read(), None) + parsed
        return parsed

    @classmethod
    def _element_to_str(cls, elt: str | pp.ParseResults) -> str:
        if isinstance(elt, str):
            return elt
        return "(" + " ".join(cls._element_to_str(sub) for sub in elt) + ")"

    @classmethod
    def _canonicalize_defsrc(cls, val: str) -> str:
        if (canonical := cls._canonical_defsrcs.get(val)) is not None:
            return canonical
        raise ValueError(f'Unknown defsrc item "{val}"!')

    def _find_physical_layout(self, defsrc: list[str], extra_defsrc: Iterable[str] | None = None) -> None:
        canonical = [self._canonicalize_defsrc(val) for val in defsrc]
        extra = [] if extra_defsrc is None else [self._canonicalize_defsrc(val) for val in extra_defsrc]

        for layout in self._available_layouts:
            if all(val in layout["defsrc_index"] for val in (canonical + extra)):
                self.defsrc_to_pos = {key: pos for pos, key in enumerate(layout["defsrc"])}
                self.defsrc_indices = [self.defsrc_to_pos[val] for val in canonical]
                self.physical_layout = layout["physical_layout"]
                return

        logger.debug("missing: %s", set(canonical + extra) - self._available_layouts[-1]["defsrc_index"])
        raise ValueError("Cannot find a physical layout that contains all items in defsrc")

    def _get_aliases_vars(self, nodes: list[pp.ParseResults]) -> None:
        try:
            defalias = list(chain.from_iterable(node[1:] for node in nodes if node[0] == "defalias"))
            self.aliases = {defalias[k]: defalias[k + 1] for k in range(0, len(defalias), 2)}
            logger.debug("found aliases: %s", {k: self._element_to_str(v) for k, v in self.aliases.items()})
        except StopIteration:
            pass

        try:
            defvar = list(chain.from_iterable(node[1:] for node in nodes if node[0] == "defvar"))
            self.vars = {defvar[k]: defvar[k + 1] for k in range(0, len(defvar), 2)}
            logger.debug("found vars: %s", {k: self._element_to_str(v) for k, v in self.vars.items()})
        except StopIteration:
            pass

    def _str_to_key(  # pylint: disable=too-many-return-statements,too-many-locals,too-many-branches
        self,
        binding: str | pp.ParseResults,
        current_layer: int | None,
        key_positions: Sequence[int],
    ) -> LayoutKey:
        binding_str = self._element_to_str(binding)
        if binding_str in self.raw_binding_map:
            return LayoutKey.from_key_spec(self.raw_binding_map[binding_str])
        if self.cfg.skip_binding_parsing:
            return LayoutKey(tap=binding_str)

        def recurse(new_binding):
            return self._str_to_key(new_binding, current_layer, key_positions)

        if isinstance(binding, str) and binding.startswith("@"):
            binding = self.aliases.get(binding[1:], binding)
        if isinstance(binding, str) and binding.startswith("$"):
            binding = self.vars.get(binding[1:], binding)

        if isinstance(binding, str):
            if binding in ("_", "‗", "≝"):
                return LayoutKey.from_key_spec(self.cfg.trans_legend)
            if binding in ("XX", "✗", "∅", "•"):
                return LayoutKey()
            if binding.startswith("🔣"):
                return LayoutKey(tap=binding[1:])
            return LayoutKey(tap=binding)

        assert isinstance(binding, pp.ParseResults)
        assert self.layer_names is not None

        if binding[0].startswith("tap-hold"):
            tap_key = recurse(binding[3])
            hold_key = recurse(binding[4])
            return LayoutKey(tap=tap_key.tap, hold=hold_key.tap, shifted=tap_key.shifted)
        if binding[0] == "layer-switch":
            return LayoutKey(tap=binding[1], hold=self.cfg.toggle_label)
        if binding[0] in ("layer-while-held", "layer-toggle"):
            self.update_layer_activated_from(
                [current_layer] if current_layer is not None else [], self.layer_names.index(binding[1]), key_positions
            )
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
            return LayoutKey(tap="+".join(recurse(bind).tap for bind in binding[1:]))
        if binding[0] == "macro":
            return LayoutKey(tap="macro " + "  ".join(recurse(bind).tap for bind in binding[1:]))

        return LayoutKey(tap=binding_str)

    def _get_layers(self, nodes: list[pp.ParseResults]) -> dict[str, list[LayoutKey]]:
        assert self.defsrc_indices is not None
        assert self.defsrc_to_pos is not None

        layer_nodes = {node[1]: node[2:] for node in nodes if node[0] == "deflayer"}
        self.update_layer_names(list(layer_nodes))

        layers: dict[str, list[LayoutKey]] = {}
        for layer_ind, (layer_name, layer) in enumerate(layer_nodes.items()):
            layers[layer_name] = [LayoutKey() for _ in range(len(self.defsrc_to_pos))]
            for key_pos, layer_key in zip(self.defsrc_indices, layer):
                try:
                    layers[layer_name][key_pos] = self._str_to_key(layer_key, layer_ind, [key_pos])
                except Exception as err:
                    raise ParseError(
                        f'Could not parse keycode "{layer_key}" in layer "{layer_name}" with exception "{err}"'
                    ) from err
        return layers

    @staticmethod
    def _get_raw_combo_nodes(nodes: list[pp.ParseResults]) -> list[tuple[(str | pp.ParseResults), ...]]:
        try:
            chords_node = next(node[1:] for node in nodes if node[0] in ("defchordsv2", "defchordsv2-experimental"))
        except StopIteration:
            return []

        def batched(iterable, n):
            it = iter(iterable)
            while batch := tuple(islice(it, n)):
                yield batch

        return list(batched(chords_node, 5))

    def _get_combos(self, raw_combo_nodes: list[tuple[(str | pp.ParseResults), ...]]) -> list[ComboSpec]:
        assert self.layer_names is not None
        assert self.defsrc_to_pos is not None

        combos = []
        for combo_def in raw_combo_nodes:
            pos_node, action_node, _, _, disabled_layers_node = combo_def

            key_pos = [self.defsrc_to_pos.get(self._canonicalize_defsrc(val)) for val in pos_node]
            assert all(pos is not None for pos in key_pos)

            try:
                parsed_key = self._str_to_key(action_node, None, key_pos)  # type: ignore
            except Exception as err:
                raise ParseError(
                    f'Could not parse binding "{self._element_to_str(action_node)}" in combo node "{combo_def}" with exception "{err}"'
                ) from err

            combo = {"k": parsed_key, "p": key_pos}
            if disabled_layers := list(disabled_layers_node):
                combo["l"] = [name for name in self.layer_names if name not in disabled_layers]
            combos.append(ComboSpec(**combo))
        return combos

    def _parse(self, in_str: str, file_name: str | None = None) -> tuple[dict, KeymapData]:
        """
        Parse a ZMK keymap with its content and path and return the layout spec and KeymapData to be dumped to YAML.
        """
        nodes = self._parse_cfg(in_str, Path(file_name) if file_name else None)

        if any(node[1:] for node in nodes if node[0] == "deflayermap"):
            logger.warning("deflayermap is not currently supported")

        if any(node[1:] for node in nodes if node[0] == "deflocalkeys"):
            logger.warning("deflocalkeys is not currently supported")

        defsrc = next(node[1:] for node in nodes if node[0] == "defsrc")
        raw_combo_nodes = self._get_raw_combo_nodes(nodes)

        self._find_physical_layout(defsrc, set(pos for combo_def in raw_combo_nodes for pos in combo_def[0]))
        assert self.physical_layout is not None

        self._get_aliases_vars(nodes)

        layers = self._get_layers(nodes)
        layers = self.append_virtual_layers(layers)
        combos = self._get_combos(raw_combo_nodes)
        layers = self.add_held_keys(layers)
        keymap_data = KeymapData(layers=layers, combos=combos, layout=None, config=None)

        return self.physical_layout, keymap_data
