# Potential future improvements

These are things I plan to implement if there is demand for it, contributions are also welcome.

## Parse

- Add shifted values to default `qmk/zmk_keycode_map` and add a `ParseConfig` field
  to omit them if preferred
- Improved ZMK parsing
  - Custom sticky keys parsing
  - Macro parsing for string sending?
- VIA/Vial keymap parsing

## Draw

- Automatically add `class="LayerName"` for layer activating keys
- Physical layouts in KLE format
  - Maybe consider labeled KLE's like VIA/Vial expects to ensure ordering
- Physical layouts from Ergogen specs
- Encoders

## Internal

- Decouple key sizes from `key_w`/`key_h` and use the latter only while drawing

## Web UX

- Syntax highlighting in text area
- Perhaps switch to [NiceGUI](https://github.com/zauberzeug/nicegui)
