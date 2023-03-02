# Potential future improvements

These are things I plan to implement if there is demand for it, contributions are also welcome.

## Parse

- Add shifted values to default `qmk/zmk_keycode_map` and add a `ParseConfig` field
  to omit them if preferred
- Improved ZMK parsing
  - Use `compatible` property values instead of node names
  - Find arbitrarily nested nodes
  - Custom sticky keys parsing
  - Macro parsing for string sending?
- Add a way to customize QMK layer names
  - Maybe apply it for ZMK as well in case parsed names aren't good enough
- Determine held keys from momentarily activated layer positions
  - Can support nested holds as well
- VIA/Vial keymap parsing

## Draw

- Automatically add `class="LayerName"` for keys on layer and activating keys
- Add html-based icon specs like KLE
  - Maybe dynamically fetch and embed icon SVGs from [Tabler](https://tablericons.com/)?
- Physical layouts in KLE format
  - Maybe consider labeled KLE's like VIA/Vial expects to ensure ordering
- Physical layouts from Ergogen specs
- Encoders

## Internal

- Decouple key sizes from `key_w`/`key_h` and use the latter only while drawing
- Find a way to specify any necessary tweaks to YAML representation before parsing
  - This would allow better automation, going from `parse` to `draw` directly for any layout
  - Currently cannot specify combo properties like `align` and `offset` before parsing

## Web UX

- Syntax highlighting in text area
