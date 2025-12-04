"""Parsing for RMK TOML keymap files."""

import logging
import re

try:
    import tomllib
except ImportError:
    # For Python < 3.11, would need to install tomli
    # But since this project requires Python 3.12+, this should not happen
    raise ImportError("tomllib not available - RMK parsing requires Python 3.11+")

from typing import Sequence

from keymap_drawer.keymap import ComboSpec, KeymapData, LayoutKey

from .parse import KeymapParser, ParseError

logger = logging.getLogger(__name__)

# Regex pattern to parse RMK key specs: matches identifiers optionally followed by
# balanced parentheses (for function calls like MT(C, LCtrl)), or underscores (for __)
_KEY_SPEC_PATTERN = re.compile(r"\w+(?:\([^)]*\))?|_+")

class RmkKeymapParser(KeymapParser):
    """Parser for RMK TOML keymap files."""

    _modifier_fn_to_std = {
        "LCtrl": ["left_ctrl"],
        "LShift": ["left_shift"],
        "LAlt": ["left_alt"],
        "LGui": ["left_gui"],
        "RCtrl": ["right_ctrl"],
        "RShift": ["right_shift"],
        "RAlt": ["right_alt"],
        "RGui": ["right_gui"],
    }

    def __init__(
        self,
        config,
        columns: int | None,
        base_keymap: KeymapData | None = None,
        layer_names: list[str] | None = None,
        virtual_layers: list[str] | None = None,
    ):
        super().__init__(config, columns, base_keymap, layer_names, virtual_layers)
        self.hold_taps = {"MT": ["&kp", "&kp"], "LT": ["&mo", "&kp"]}
        self._prefix_re: re.Pattern | None
        if prefixes := self.cfg.rmk_remove_keycode_prefix:
            self._prefix_re = re.compile(r"^(" + "|".join(re.escape(prefix) for prefix in set(prefixes)) + ")")
        else:
            self._prefix_re = None

    def _str_to_key(
        self,
        binding: str,
        current_layer: int | None,
        key_positions: Sequence[int],
        no_shifted: bool = False,
    ) -> LayoutKey:
        """Convert an RMK key binding string to a LayoutKey."""
        if binding in self.raw_binding_map:
            return LayoutKey.from_key_spec(self.raw_binding_map[binding])

        if self.cfg.skip_binding_parsing:
            return LayoutKey(tap=binding)

        assert self.layer_names is not None
        assert self.layer_legends is not None

        def mapped(key: str) -> LayoutKey:
            """Map a keycode to a LayoutKey using the configuration."""
            # First, strip any configured prefixes (e.g., "Kc")
            if self._prefix_re is not None:
                key = self._prefix_re.sub("", key)

            # Check keycode map for direct match
            if entry := self.cfg.rmk_keycode_map.get(key):
                return LayoutKey.from_key_spec(entry)

            # Parse modifier functions and check map again
            stripped_key, mods = self.parse_modifier_fns(key)
            result = LayoutKey.from_key_spec(self.cfg.rmk_keycode_map.get(stripped_key, stripped_key))

            if no_shifted:
                result.shifted = ""
            if mods:
                result.apply_formatter(lambda key: self.format_modified_keys(key, mods))
            return result

        # Handle empty/transparent keys
        if not binding or binding == "__":
            return self.trans_key

        # Parse the binding
        if "(" in binding and binding.endswith(")"):
            # Handle function-style bindings like MT(C, LCtrl) or LT(2, Backspace)
            func_match = re.match(r"(\w+)\((.+)\)", binding)
            if func_match:
                func_name, params = func_match.groups()
                param_list = [p.strip() for p in params.split(",")]

                if func_name == "MT" and len(param_list) >= 2:
                    # Mod-tap: MT(tap_key, hold_modifier, <profile_name>)
                    tap_key = mapped(param_list[0])
                    hold_mod = mapped(param_list[1])
                    return LayoutKey(
                        tap=tap_key.tap, hold=hold_mod.tap, shifted=tap_key.shifted
                    )

                elif func_name == "LT" and len(param_list) >= 2:
                    # Layer-tap: LT(layer, tap_key, <profile_name>)
                    try:
                        # Layer can be a number or a layer name
                        layer_ref = param_list[0]
                        try:
                            layer_num = int(layer_ref)
                        except ValueError:
                            # It's a layer name, find its index
                            layer_num = (
                                self.layer_names.index(layer_ref)
                                if layer_ref in self.layer_names
                                else -1
                            )

                        tap_key = mapped(param_list[1])

                        if current_layer is not None and layer_num >= 0:
                            self.update_layer_activated_from(
                                [current_layer], layer_num, key_positions
                            )

                        hold_legend = (
                            self.layer_legends[layer_num]
                            if 0 <= layer_num < len(self.layer_legends)
                            else layer_ref
                        )
                        return LayoutKey(
                            tap=tap_key.tap, hold=hold_legend, shifted=tap_key.shifted
                        )
                    except (ValueError, IndexError):
                        pass

                elif func_name == "TH" and len(param_list) >= 2:
                    # Generic tap-hold: TH(tap_key, hold_key, <profile_name>)
                    tap_key = mapped(param_list[0])
                    hold_key = mapped(param_list[1])
                    return LayoutKey(
                        tap=tap_key.tap, hold=hold_key.tap, shifted=tap_key.shifted
                    )

                elif func_name == "MO" and len(param_list) >= 1:
                    # Momentary layer: MO(layer)
                    try:
                        layer_ref = param_list[0]
                        try:
                            layer_num = int(layer_ref)
                        except ValueError:
                            layer_num = (
                                self.layer_names.index(layer_ref)
                                if layer_ref in self.layer_names
                                else -1
                            )

                        if current_layer is not None and layer_num >= 0:
                            self.update_layer_activated_from(
                                [current_layer], layer_num, key_positions
                            )

                        hold_legend = (
                            self.layer_legends[layer_num]
                            if 0 <= layer_num < len(self.layer_legends)
                            else layer_ref
                        )
                        return LayoutKey(tap=hold_legend)
                    except (ValueError, IndexError):
                        pass

                elif func_name == "LM" and len(param_list) >= 2:
                    # Layer activate with modifier: LM(layer, modifier)
                    try:
                        layer_ref = param_list[0]
                        try:
                            layer_num = int(layer_ref)
                        except ValueError:
                            layer_num = (
                                self.layer_names.index(layer_ref)
                                if layer_ref in self.layer_names
                                else -1
                            )

                        modifier = mapped(param_list[1])

                        if current_layer is not None and layer_num >= 0:
                            self.update_layer_activated_from(
                                [current_layer], layer_num, key_positions
                            )

                        hold_legend = (
                            self.layer_legends[layer_num]
                            if 0 <= layer_num < len(self.layer_legends)
                            else layer_ref
                        )
                        return LayoutKey(tap=hold_legend, hold=modifier.tap)
                    except (ValueError, IndexError):
                        pass

                elif func_name == "DF" and len(param_list) >= 1:
                    # Default layer: DF(layer)
                    layer_ref = param_list[0]
                    try:
                        layer_num = int(layer_ref)
                        layer_legend = (
                            self.layer_legends[layer_num]
                            if 0 <= layer_num < len(self.layer_legends)
                            else layer_ref
                        )
                    except ValueError:
                        layer_legend = layer_ref
                    return LayoutKey(tap=layer_legend, hold="default")

                elif func_name == "TO" and len(param_list) >= 1:
                    # Layer toggle only: TO(layer)
                    layer_ref = param_list[0]
                    try:
                        layer_num = int(layer_ref)
                        layer_legend = (
                            self.layer_legends[layer_num]
                            if 0 <= layer_num < len(self.layer_legends)
                            else layer_ref
                        )
                    except ValueError:
                        layer_legend = layer_ref
                    return LayoutKey(tap=layer_legend, hold="to")

                elif func_name == "TG" and len(param_list) >= 1:
                    # Layer toggle: TG(layer)
                    layer_ref = param_list[0]
                    try:
                        layer_num = int(layer_ref)
                        layer_legend = (
                            self.layer_legends[layer_num]
                            if 0 <= layer_num < len(self.layer_legends)
                            else layer_ref
                        )
                    except ValueError:
                        layer_legend = layer_ref
                    return LayoutKey(tap=layer_legend, hold=self.cfg.toggle_label)

                elif func_name == "TT" and len(param_list) >= 1:
                    # Tap-toggle layer: TT(layer)
                    layer_ref = param_list[0]
                    try:
                        layer_num = int(layer_ref)
                        layer_legend = (
                            self.layer_legends[layer_num]
                            if 0 <= layer_num < len(self.layer_legends)
                            else layer_ref
                        )
                    except ValueError:
                        layer_legend = layer_ref
                    return LayoutKey(tap=layer_legend, hold=self.cfg.tap_toggle_label)

                elif func_name == "OSL" and len(param_list) >= 1:
                    # One-shot layer: OSL(layer)
                    layer_ref = param_list[0]
                    try:
                        layer_num = int(layer_ref)
                        layer_legend = (
                            self.layer_legends[layer_num]
                            if 0 <= layer_num < len(self.layer_legends)
                            else layer_ref
                        )
                    except ValueError:
                        layer_legend = layer_ref
                    return LayoutKey(tap=layer_legend, hold=self.cfg.sticky_label)

                elif func_name == "OSM" and len(param_list) >= 1:
                    # One-shot modifier: OSM(modifier)
                    modifier = mapped(param_list[0])
                    return LayoutKey(tap=modifier.tap, hold=self.cfg.sticky_label)

                elif func_name == "SHIFTED" and len(param_list) == 1:
                    # Shifted version of a key - check keycode map first
                    full_key = f"SHIFTED({param_list[0]})"
                    if entry := self.cfg.rmk_keycode_map.get(full_key):
                        return LayoutKey.from_key_spec(entry)
                    # Fallback to displaying as shifted
                    base_key = mapped(param_list[0])
                    return LayoutKey(tap=f"S({base_key.tap})")

                elif func_name == "WM" and len(param_list) >= 2:
                    # Key with modifier: WM(key, modifier)
                    key = mapped(param_list[0])
                    modifier = param_list[1]
                    # Parse the modifier to get display form
                    mod_key, mods = self.parse_modifier_fns(modifier)
                    if mods:
                        key.apply_formatter(
                            lambda k: self.format_modified_keys(k, mods)
                        )
                    return key

                elif func_name in ("TD", "Morse") and len(param_list) >= 1:
                    # Tap Dance / Morse: TD(n) or Morse(n)
                    return LayoutKey(tap=f"TD{param_list[0]}")

                elif func_name == "Macro" and len(param_list) >= 1:
                    # Macro: Macro(n)
                    return LayoutKey(tap=f"Macro{param_list[0]}")

        # Default: treat as a simple key
        return mapped(binding)

    def _get_layers(self, toml_data: dict) -> dict[str, list[LayoutKey]]:
        """Extract layers from the TOML data."""
        if "layer" not in toml_data:
            raise ParseError("No layers found in RMK keymap")

        layer_configs = toml_data["layer"]
        if not isinstance(layer_configs, list):
            raise ParseError("Layers should be an array of tables")

        layers = {}
        layer_names = []
        num_keys = None

        # First pass: collect layer names and set them
        for layer_config in layer_configs:
            if "name" not in layer_config:
                raise ParseError("Layer missing name")
            layer_names.append(layer_config["name"])

        if self.layer_names is None:
            self.update_layer_names(layer_names)

        # Second pass: process the keys now that layer names are set
        for layer_config in layer_configs:
            if "keys" not in layer_config:
                raise ParseError(f"Layer '{layer_config['name']}' missing `keys` field")

            layer_name = layer_config["name"]
            key_specs = _KEY_SPEC_PATTERN.findall(layer_config["keys"])

            # Validate consistent key count across layers
            if num_keys is None:
                num_keys = len(key_specs)
            elif len(key_specs) != num_keys:
                raise ParseError(
                    f"Layer '{layer_name}' has {len(key_specs)} keys, expected {num_keys}"
                )

            # Convert to LayoutKey objects
            layer_keys = []
            for i, key_spec in enumerate(key_specs):
                if key_spec == "__":  # Empty key placeholder
                    layer_keys.append(LayoutKey())
                else:
                    layout_key = self._str_to_key(
                        key_spec, layer_names.index(layer_name), [i]
                    )
                    layer_keys.append(layout_key)

            layers[layer_name] = layer_keys

        return layers

    def _get_combos(self, toml_data: dict) -> list[ComboSpec]:
        """Extract combos from the TOML data."""
        combos = []

        # Look for combo definitions in behavior.combo.combos
        behavior = toml_data.get("behavior", {})
        combo_config = behavior.get("combo", {})
        combo_list = combo_config.get("combos", [])

        if not combo_list:
            return combos

        assert self.layer_names is not None

        for combo_data in combo_list:
            if "actions" not in combo_data or "output" not in combo_data:
                logger.warning("Skipping combo with missing 'actions' or 'output'")
                continue

            actions = combo_data["actions"]
            output = combo_data["output"]

            # Convert action key specs to LayoutKeys for trigger_keys
            trigger_keys = [
                self._str_to_key(action, None, [], no_shifted=True)
                for action in actions
            ]

            if len(trigger_keys) < 2:
                logger.warning(
                    f"Combo needs at least 2 keys but found {len(trigger_keys)}"
                )
                continue

            try:
                parsed_key = self._str_to_key(output, None, [], no_shifted=True)

                combo: dict = {"k": parsed_key, "tk": trigger_keys}
                if "layer" in combo_data:
                    layer_idx = combo_data["layer"]
                    if 0 <= layer_idx < len(self.layer_names):
                        combo["l"] = [self.layer_names[layer_idx]]

                # Apply combo configuration from rmk_combos if specified
                # Use 'name' field if present, otherwise fall back to 'output'
                combo_key = combo_data.get("name", output)
                if combo_name_config := self.cfg.rmk_combos.get(combo_key):
                    normalized_config = ComboSpec.normalize_fields(combo_name_config.copy())
                    # RMK uses trigger_keys, not key_positions - remove any positions from config
                    normalized_config.pop("p", None)
                    combo |= normalized_config

                combos.append(ComboSpec(**combo))
            except Exception as err:
                logger.warning(f'Could not parse combo output "{output}": {err}')

        return combos

    def _get_physical_layout(self, toml_data: dict) -> dict[str, str]:
        """Extract physical layout information from TOML data."""
        layout_info = {}

        # Try to get layout information from the TOML
        if "layout" in toml_data:
            layout_config = toml_data["layout"]

            if "rows" in layout_config and "cols" in layout_config:
                rows = layout_config["rows"]
                cols = layout_config["cols"]

                # Create an ortho layout specification
                layout_info = {
                    "ortho_layout": {
                        "split": False,  # Default to non-split
                        "rows": rows,
                        "columns": cols,
                    }
                }

        return layout_info

    def _parse(
        self, in_str: str, file_name: str | None = None
    ) -> tuple[dict, KeymapData]:
        """Parse an RMK TOML keymap and return the layout spec and KeymapData."""
        try:
            toml_data = tomllib.loads(in_str)
        except Exception as err:
            raise ParseError(f"Failed to parse TOML: {err}") from err

        layers = self._get_layers(toml_data)
        layers = self.append_virtual_layers(layers)
        combos = self._get_combos(toml_data)
        layers = self.add_held_keys(layers)

        keymap_data = KeymapData(layers=layers, combos=combos, layout=None, config=None)
        physical_layout = self._get_physical_layout(toml_data)

        return physical_layout, keymap_data
