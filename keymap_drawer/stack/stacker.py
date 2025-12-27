"""Layer stacking logic for combining multiple keymap layers into one."""

import sys
from typing import Any

from .config import CornerLayers, StackConfig


def get_tap_legend(key: dict | str | None) -> str:
    """Extract tap-only legend string from a key definition.

    Used for corner layers where we only show the tap value.

    Args:
        key: The key definition (str, dict, or None)

    Returns:
        String tap value for the key
    """
    if key is None:
        return ""
    if isinstance(key, str):
        return key
    if isinstance(key, dict):
        if key.get("type") == "trans":
            return ""
        return key.get("t", key.get("tap", ""))
    return str(key)


def get_full_legend(key: dict | str | None) -> dict[str, Any]:
    """Extract complete legend dict (t/s/h/type) from a key definition.

    Used for the center layer where we preserve all display attributes.

    Args:
        key: The key definition (str, dict, or None)

    Returns:
        Dict with available keys: t, s, h, type
    """
    if key is None:
        return {}
    if isinstance(key, str):
        return {"t": key}
    if isinstance(key, dict):
        if key.get("type") == "trans":
            return {}
        result = {}
        tap = key.get("t", key.get("tap", ""))
        if tap:
            result["t"] = tap
        for field in ("s", "h", "type"):
            if field in key:
                result[field] = key[field]
        return result
    return {"t": str(key)}


def _flatten_layer(layer_keys: list) -> list:
    """Flatten nested row lists into a single list of keys.

    Keymap YAML layers can be structured as:
    - Flat list: [key1, key2, key3, ...]
    - Nested rows: [[row1_keys...], [row2_keys...], key3, ...]

    This function normalizes both to a flat list.
    """
    result = []
    for item in layer_keys:
        if isinstance(item, list):
            result.extend(item)
        else:
            result.append(item)
    return result


def _get_layer_keys(layers: dict[str, list], layer_name: str | None, num_keys: int) -> list:
    """Get keys from a layer, with fallback for missing layers."""
    if layer_name is None:
        return [""] * num_keys
    if layer_name not in layers:
        return [""] * num_keys
    return _flatten_layer(layers[layer_name])


def _stack_key(
    key_index: int,
    center_key: Any,
    tl_key: Any,
    tr_key: Any,
    bl_key: Any,
    br_key: Any,
    stack_config: StackConfig,
) -> dict | str:
    """Stack a single key from multiple layers."""
    center_full = get_full_legend(center_key)

    tl = get_tap_legend(tl_key)
    tr = get_tap_legend(tr_key)
    bl = get_tap_legend(bl_key)
    br = get_tap_legend(br_key)

    key_def: dict[str, Any] = {}

    # Center positions (from center layer)
    if center_full.get("t"):
        key_def["t"] = center_full["t"]
    if center_full.get("s"):
        key_def["s"] = center_full["s"]
    if center_full.get("h"):
        key_def["h"] = center_full["h"]
    if center_full.get("type"):
        key_def["type"] = center_full["type"]

    # Filter hidden legends
    if key_def.get("s") in stack_config.hidden_shifted_legends:
        del key_def["s"]
    if key_def.get("h") in stack_config.hidden_held_legends:
        del key_def["h"]

    # Corner positions (filter hidden values)
    hidden_corner_set = set(stack_config.hidden_corner_legends)
    if tl and tl not in hidden_corner_set:
        key_def["tl"] = tl
    if tr and tr not in hidden_corner_set:
        key_def["tr"] = tr
    if bl and bl not in hidden_corner_set:
        key_def["bl"] = bl
    if br and br not in hidden_corner_set:
        key_def["br"] = br

    # Simplify to string if only center tap value
    if len(key_def) == 1 and "t" in key_def:
        return key_def["t"]
    if len(key_def) == 0:
        return ""

    return key_def


def stack_layers(
    keymap: dict[str, Any],
    center_layer: str,
    corner_layers: CornerLayers,
    stack_config: StackConfig | None = None,
) -> dict[str, Any]:
    """Stack multiple layers into a single layer with multi-position legends.

    Each key in the output can show up to 7 positions:
    - center (t): primary layer tap value
    - top-center (s): primary layer shifted value
    - bottom-center (h): primary layer hold value
    - top-left (tl): corner layer 1
    - top-right (tr): corner layer 2
    - bottom-left (bl): corner layer 3
    - bottom-right (br): corner layer 4

    Args:
        keymap: Full keymap dict with 'layers' key
        center_layer: Layer name for center position (primary layer)
        corner_layers: CornerLayers specifying tl/tr/bl/br layer names
        stack_config: Optional StackConfig with hide settings

    Returns:
        New keymap dict with single 'stacked' layer
    """
    if stack_config is None:
        stack_config = StackConfig()

    layers = keymap.get("layers", {})

    if center_layer not in layers:
        print(f"Error: Center layer '{center_layer}' not found in keymap", file=sys.stderr)
        print(f"Available layers: {list(layers.keys())}", file=sys.stderr)
        sys.exit(1)

    center_keys = _flatten_layer(layers[center_layer])
    num_keys = len(center_keys)

    tl_keys = _get_layer_keys(layers, corner_layers.tl, num_keys)
    tr_keys = _get_layer_keys(layers, corner_layers.tr, num_keys)
    bl_keys = _get_layer_keys(layers, corner_layers.bl, num_keys)
    br_keys = _get_layer_keys(layers, corner_layers.br, num_keys)

    stacked_keys = []
    for i in range(num_keys):
        key_def = _stack_key(
            i,
            center_keys[i],
            tl_keys[i] if i < len(tl_keys) else "",
            tr_keys[i] if i < len(tr_keys) else "",
            bl_keys[i] if i < len(bl_keys) else "",
            br_keys[i] if i < len(br_keys) else "",
            stack_config,
        )
        stacked_keys.append(key_def)

    return {
        "layout": keymap.get("layout", {}),
        "layers": {"stacked": stacked_keys},
    }
