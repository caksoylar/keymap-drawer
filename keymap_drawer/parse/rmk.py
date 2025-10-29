"""Parsing for RMK TOML keymap files."""

import logging
import re
try:
    import tomllib
except ImportError:
    # For Python < 3.11, would need to install tomli
    # But since this project requires Python 3.12+, this should not happen
    raise ImportError("tomllib not available - RMK parsing requires Python 3.11+")

from pathlib import Path
from typing import Sequence

from keymap_drawer.keymap import ComboSpec, KeymapData, LayoutKey

from .parse import KeymapParser, ParseError

logger = logging.getLogger(__name__)


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

    def _str_to_key(
        self, binding: str, current_layer: int | None, key_positions: Sequence[int], no_shifted: bool = False
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
            if entry := self.cfg.zmk_keycode_map.get(key):
                return LayoutKey.from_key_spec(entry)
            key, mods = self.parse_modifier_fns(key)
            
            # Map common RMK keycodes to standard ones
            rmk_keycode_map = {
                "Kp0": "KP_0", "Kp1": "KP_1", "Kp2": "KP_2", "Kp3": "KP_3", "Kp4": "KP_4",
                "Kp5": "KP_5", "Kp6": "KP_6", "Kp7": "KP_7", "Kp8": "KP_8", "Kp9": "KP_9",
                "KpEnter": "KP_ENTER", "KpDot": "KP_DOT",
                "KbVolumeDown": "VOL_DN", "KbVolumeUp": "VOL_UP", "KbMute": "MUTE",
                "Dot": ".", "Comma": ",", "Quote": "'", "Backspace": "BSPC",
                "Enter": "RET", "Space": "SPC", "__": "",
            }
            
            display_key = rmk_keycode_map.get(key, key)
            mapped = LayoutKey.from_key_spec(
                self.cfg.zmk_keycode_map.get(display_key, display_key)
            )
            
            if no_shifted:
                mapped.shifted = ""
            if mods:
                mapped.apply_formatter(lambda k: self.format_modified_keys(k, mods))
            return mapped

        # Handle empty/transparent keys
        if not binding or binding == "__":
            return LayoutKey()

        # Parse the binding
        if "(" in binding and binding.endswith(")"):
            # Handle function-style bindings like MT(C, LCtrl) or LT(2, Backspace)
            func_match = re.match(r"(\w+)\((.+)\)", binding)
            if func_match:
                func_name, params = func_match.groups()
                param_list = [p.strip() for p in params.split(",")]
                
                if func_name == "MT" and len(param_list) == 2:
                    # Mod-tap: MT(tap_key, hold_modifier)
                    tap_key = mapped(param_list[0])
                    hold_mod = mapped(param_list[1])
                    return LayoutKey(tap=tap_key.tap, hold=hold_mod.tap, shifted=tap_key.shifted)
                
                elif func_name == "LT" and len(param_list) == 2:
                    # Layer-tap: LT(layer_number, tap_key)
                    try:
                        layer_num = int(param_list[0])
                        tap_key = mapped(param_list[1])
                        
                        if current_layer is not None:
                            self.update_layer_activated_from([current_layer], layer_num, key_positions)
                        
                        return LayoutKey(
                            tap=tap_key.tap,
                            hold=self.layer_legends[layer_num] if layer_num < len(self.layer_legends) else f"L{layer_num}",
                            shifted=tap_key.shifted
                        )
                    except (ValueError, IndexError):
                        pass
                
                elif func_name in ("OSM", "OSL"):
                    # One-shot modifier or layer
                    if len(param_list) == 1:
                        target = mapped(param_list[0])
                        sticky_label = self.cfg.sticky_label if func_name == "OSM" else target.tap
                        return LayoutKey(tap=target.tap, hold=sticky_label)
                
                elif func_name == "SHIFTED" and len(param_list) == 1:
                    # Shifted version of a key
                    base_key = mapped(param_list[0])
                    return LayoutKey(tap=f"S({base_key.tap})")
                
                elif func_name == "WM" and len(param_list) == 2:
                    # Window manager key (Cmd+key on Mac)
                    key, mod = param_list
                    return LayoutKey(tap=f"⌘{mapped(key).tap}")

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
        max_keys = 0
        
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
                raise ParseError(f"Layer '{layer_config['name']}' missing keys")
                
            layer_name = layer_config["name"]
            keys_str = layer_config["keys"].strip()
            
            # Split keys by whitespace and filter out empty strings, but preserve function calls
            raw_keys = keys_str.strip()
            
            # Parse keys more carefully to handle function calls like MT(C, LCtrl)
            key_specs = []
            i = 0
            while i < len(raw_keys):
                if raw_keys[i].isspace():
                    i += 1
                    continue
                    
                # Start of a new key
                start = i
                paren_count = 0
                
                # Find the end of this key spec
                while i < len(raw_keys):
                    if raw_keys[i] == '(':
                        paren_count += 1
                    elif raw_keys[i] == ')':
                        paren_count -= 1
                    elif raw_keys[i].isspace() and paren_count == 0:
                        break
                    i += 1
                
                key_spec = raw_keys[start:i].strip()
                if key_spec:
                    key_specs.append(key_spec)
            
            # Convert to LayoutKey objects
            layer_keys = []
            for i, key_spec in enumerate(key_specs):
                if key_spec == "__":  # Empty key placeholder
                    layer_keys.append(LayoutKey())
                else:
                    layout_key = self._str_to_key(key_spec, layer_names.index(layer_name), [i])
                    layer_keys.append(layout_key)
            
            layers[layer_name] = layer_keys
            max_keys = max(max_keys, len(layer_keys))
        
        # Pad all layers to have the same number of keys
        for layer_name in layers:
            while len(layers[layer_name]) < max_keys:
                layers[layer_name].append(LayoutKey())
            
        return layers

    def _get_combos(self, toml_data: dict, layers: dict[str, list[LayoutKey]]) -> list[ComboSpec]:
        """Extract combos from the TOML data."""
        combos = []
        
        # Look for combo definitions in behavior.combo.combos
        behavior = toml_data.get("behavior", {})
        combo_config = behavior.get("combo", {})
        combo_list = combo_config.get("combos", [])
        
        if not combo_list:
            return combos

        assert self.layer_names is not None

        # Create a mapping from original key specs to positions
        # We need to parse the keys properly to handle function calls
        layer_configs = toml_data.get("layer", [])
        key_spec_to_positions = {}
        
        for layer_config in layer_configs:
            if "keys" not in layer_config:
                continue
            
            keys_str = layer_config["keys"].strip()
            
            # Use the same parsing logic as in _get_layers to handle function calls
            key_specs = []
            i = 0
            while i < len(keys_str):
                if keys_str[i].isspace():
                    i += 1
                    continue
                    
                # Start of a new key
                start = i
                paren_count = 0
                
                # Find the end of this key spec
                while i < len(keys_str):
                    if keys_str[i] == '(':
                        paren_count += 1
                    elif keys_str[i] == ')':
                        paren_count -= 1
                    elif keys_str[i].isspace() and paren_count == 0:
                        break
                    i += 1
                
                key_spec = keys_str[start:i].strip()
                if key_spec:
                    key_specs.append(key_spec)
            
            # Map each key spec to its position(s)
            for pos, key_spec in enumerate(key_specs):
                if key_spec != "__":  # Skip empty placeholders
                    if key_spec not in key_spec_to_positions:
                        key_spec_to_positions[key_spec] = []
                    key_spec_to_positions[key_spec].append(pos)

        # Get the actual number of keys per layer (after padding)
        max_keys = max(len(layer) for layer in layers.values()) if layers else 0

        for combo_data in combo_list:
            if "actions" not in combo_data or "output" not in combo_data:
                logger.warning("Skipping combo with missing 'actions' or 'output'")
                continue
            
            actions = combo_data["actions"]
            output = combo_data["output"]
            
            # Find key positions for the actions
            key_positions = []
            all_actions_found = True
            
            for action in actions:
                # Try exact match with key specs first
                if action in key_spec_to_positions:
                    positions = key_spec_to_positions[action]
                    # Use the first occurrence of this key that's within bounds
                    valid_pos = None
                    for pos in positions:
                        if pos < max_keys and pos not in key_positions:
                            valid_pos = pos
                            break
                    
                    if valid_pos is not None:
                        key_positions.append(valid_pos)
                    else:
                        logger.debug(f"Key spec '{action}' found but no valid positions available")
                        all_actions_found = False
                        break
                else:
                    # Fallback: try to find by comparing with parsed keys in the target layer
                    found_pos = None
                    target_layer = combo_data.get("layer", 0)
                    
                    if target_layer < len(self.layer_names):
                        layer_name = self.layer_names[target_layer]
                        layer_keys = layers.get(layer_name, [])
                        
                        for pos, key in enumerate(layer_keys):
                            # Check various representations of the key
                            if pos >= max_keys:  # Skip if position is out of bounds
                                continue
                                
                            if (key.tap == action or 
                                key.hold == action or
                                str(key).strip() == action.strip()):
                                if pos not in key_positions:
                                    found_pos = pos
                                    break
                    
                    if found_pos is not None:
                        key_positions.append(found_pos)
                    else:
                        logger.debug(f"Could not find position for combo action '{action}'")
                        all_actions_found = False
                        break
            
            # Only create combo if we found positions for ALL actions and have at least 2 keys
            if all_actions_found and len(key_positions) >= 2:
                # Validate that all positions are within bounds
                if all(0 <= pos < max_keys for pos in key_positions):
                    try:
                        parsed_key = self._str_to_key(output, None, [], no_shifted=True)
                        
                        combo = {"k": parsed_key, "p": key_positions}
                        if "layer" in combo_data:
                            layer_idx = combo_data["layer"]
                            if 0 <= layer_idx < len(self.layer_names):
                                combo["l"] = [self.layer_names[layer_idx]]
                        
                        # Apply combo configuration from rmk_combos if specified
                        # Use 'name' field if present, otherwise fall back to 'output'
                        combo_key = combo_data.get("name", output)
                        if combo_name_config := self.cfg.rmk_combos.get(combo_key):
                            combo = combo | ComboSpec.normalize_fields(combo_name_config)
                        
                        combos.append(ComboSpec(**combo))
                    except Exception as err:
                        logger.warning(f'Could not parse combo output "{output}": {err}')
                else:
                    logger.warning(f"Combo has invalid key positions {key_positions} (max keys: {max_keys})")
            else:
                if not all_actions_found:
                    logger.warning(f"Could not find all key positions for combo actions {actions}")
                else:
                    logger.warning(f"Combo needs at least 2 keys but found {len(key_positions)}")

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
                        "columns": cols
                    }
                }
        
        return layout_info

    def _parse(self, in_str: str, file_name: str | None = None) -> tuple[dict, KeymapData]:
        """Parse an RMK TOML keymap and return the layout spec and KeymapData."""
        try:
            toml_data = tomllib.loads(in_str)
        except Exception as err:
            raise ParseError(f"Failed to parse TOML: {err}") from err

        layers = self._get_layers(toml_data)
        layers = self.append_virtual_layers(layers)
        combos = self._get_combos(toml_data, layers)
        layers = self.add_held_keys(layers)

        keymap_data = KeymapData(layers=layers, combos=combos, layout=None, config=None)
        physical_layout = self._get_physical_layout(toml_data)
        
        return physical_layout, keymap_data