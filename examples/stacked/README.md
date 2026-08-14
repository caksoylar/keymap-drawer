# Stacked Layer Example

Example files for the `stack-layers` command. See [STACKED.md](../../STACKED.md) for full documentation.

## Files

- `ferris_sweep.yaml` - Parsed keymap with multiple layers
- `config.yaml` - Configuration with corner styling and filtering

## Commands

```bash
# Stack and draw
keymap -c config.yaml stack-layers --center colemak_dh --tl fun --tr sys --bl num --br nav \
  ferris_sweep.yaml | keymap -c config.yaml draw -k "ferris/sweep" - -o stacked.svg

# With combos stacked
keymap -c config.yaml stack-layers --center colemak_dh --tl fun --tr sys --bl num --br nav \
  ferris_sweep.yaml --include-combos colemak_dh nav num -o stacked.yaml
keymap -c config.yaml draw -k "ferris/sweep" stacked.yaml -o stacked.svg

# With combos as separate layer (--separate-combo-layer flag)
keymap -c config.yaml stack-layers --center colemak_dh --tl fun --tr sys --bl num --br nav \
  ferris_sweep.yaml --include-combos colemak_dh nav num --separate-combo-layer -o stacked.yaml
keymap -c config.yaml draw -k "ferris/sweep" stacked.yaml -o stacked.svg
```
