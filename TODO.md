# Potential future improvements

These are things I plan to implement if there is demand for it, or would welcome contributions on.

## Parse

- VIA/Vial keymap parsing
- Improved ZMK parsing
  - Use `compatible` property values instead of node names
  - Find arbitrarily nested nodes
  - Custom sticky keys parsing
  - Macro parsing for string sending?

## Draw

- Physical layouts in KLE format
  - Maybe consider labeled KLE's like VIA/Vial expects

## Internal

- Decouple key sizes from `key_w`/`key_h` and use the latter only while drawing
- Find a way to specify any necessary tweaks to YAML representation before parsing
  - This would allow better automation, going from `parse` to `draw` directly for any layout
  - We can already specify display representations for arbitrary keys in config
  - Currently cannot specify combo properties like `align` and `offset` before parsing
