# Potential future improvements

These are things I plan to implement if there is demand for it, contributions are also welcome.

## Parse

- VIA/Vial keymap parsing
- Improved ZMK parsing
  - Use `compatible` property values instead of node names
  - Find arbitrarily nested nodes
  - Custom sticky keys parsing
  - Macro parsing for string sending?
- Map ZMK keyboard names (from keymap filename) to physical layout specs

## Draw

- Accept arbitrary `type` values in `LayoutKey` so users can custom define SVG classes
  - Could automatically add `class="LayerName"` for keys on layer and activating keys
- Make `ComboSpec` also respect the `type` in its `key` field, default to `type: combo` if not defined
- Physical layouts in KLE format
  - Maybe consider labeled KLE's like VIA/Vial expects to ensure ordering
- Physical layouts from Ergogen specs
- Encoders
- Add html-based icon specs like KLE
  - Maybe dynamically fetch and embed icon SVGs from [Tabler](https://tablericons.com/)?

## Internal

- Decouple key sizes from `key_w`/`key_h` and use the latter only while drawing
- Find a way to specify any necessary tweaks to YAML representation before parsing
  - This would allow better automation, going from `parse` to `draw` directly for any layout
  - We can already specify display representations for arbitrary keys in config
  - Currently cannot specify combo properties like `align` and `offset` before parsing

## Web UX

- Refactor common parts of `__main__.py` and `app.py`
- Syntax highlighting in text area
- More advanced caching using [experimental primitives](https://docs.streamlit.io/library/advanced-features/experimental-cache-primitives)
