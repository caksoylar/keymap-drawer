# Stacked Layer Example

This example demonstrates the `stack-layers` command to combine multiple keyboard layers into a single diagram with corner legends.

## Files

- `ferris_sweep.yaml` - Parsed keymap with multiple layers (colemak_dh, qwerty, num, nav, fun, sys, etc.)
- `stacked.yaml` - Output from stack-layers with corner legends populated
- `config.yaml` - Configuration with corner legend styling and `corner_hide` filtering

## Generate Stacked SVG

Stack layers and draw in a single pipeline:

```bash
keymap -c config.yaml stack-layers --center colemak_dh --tl fun --tr sys --bl num --br nav ferris_sweep.yaml | keymap -c config.yaml draw -k "ferris/sweep" - -o stacked.svg
```

Or as separate steps:

```bash
# 1. Stack layers into intermediate YAML (pass config for corner_hide filtering)
keymap -c config.yaml stack-layers --center colemak_dh --tl fun --tr sys --bl num --br nav ferris_sweep.yaml -o stacked.yaml

# 2. Draw the stacked keymap (pass config for styling)
keymap -c config.yaml draw -k "ferris/sweep" stacked.yaml -o stacked.svg
```

**Important:** Pass `-c config.yaml` to both `stack-layers` and `draw`:
- `stack-layers` uses `stack_config.corner_hide` to filter out unwanted corner values
- `draw` uses `draw_config.svg_extra_style` for corner legend colors and styling

## Layer Positions

The `stack-layers` command places layers in corner positions:

| Position | Flag | Layer | Color |
|----------|------|-------|-------|
| Center | `--center` | colemak_dh | (base) |
| Top-Left | `--tl` | fun | Red (#F93827) |
| Top-Right | `--tr` | sys | Blue (#2563EB) |
| Bottom-Left | `--bl` | num | Green (#16A34A) |
| Bottom-Right | `--br` | nav | Orange (#FF9D23) |

## Configuration Notes

The `config.yaml` includes:

- **Corner legend styling** - CSS rules for `text.tl`, `text.tr`, `text.bl`, `text.br` with colors and proper text alignment
- **`corner_hide` list** - Filters out common modifiers (⇧, ⌃, ⌥, ⌘) and other values from corner positions to reduce clutter
