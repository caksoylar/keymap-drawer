# Keymap YAML specification

This page documents the YAML-format keymap representation that is output by `keymap parse` and used by `keymap draw`.

At the root, four fields can be specified which are detailed in respective sections. A typical keymap will have the following structure:

```yaml
layout:      # physical layout specs, optional if used in CLI
  ...
layers:      # ordered mapping of layer name to contents
  layer_1:   # list of (lists of) key specs
    - [Q, W, ...]
    ...
  layer_2:
    ...
combos:      # list of combo specs, optional
  - ...
draw_config: # config overrides for drawing, optional
  - ...
```

## `layout`

This field provides information about the physical layout of the keyboard, i.e., the location and sizes of individual keys.
`keymap-drawer` understands two types of physical layout descriptions:

1. **QMK `info.json` `layout` specification**:
   This is the [official QMK format](https://docs.qmk.fm/#/reference_info_json?id=layout-format) for physical key descriptions
   that every `info.json` file in the QMK firmware repository uses. `keymap-drawer` only uses the `x`, `y`, `r`, `rx` and `ry` fields.
   Note that `keymap-editor` utilizes [the same format](https://github.com/nickcoutsos/keymap-editor/wiki/Defining-keyboard-layouts) for `info.json`.

   QMK spec also lets you specify multiple "layouts" per keyboard corresponding to different layout macros to support physical variations.

   You can create your own physical layout definitions in QMK format to use with `keymap-drawer`, which accepts JSONs with the official schema that
   has layouts listed under the `layout` key, or one that directly consists of a list of key specs as a shortcut. The best way to generate one is to use
   the interactive [Keymap Layout Helper tool](https://nickcoutsos.github.io/keymap-layout-tools/) tool by @nickcoutsos. This web app is useful to
   visualize a given JSON definition, re-order keys using the "Re-order" tool and generate one from scratch from various formats such as KLE or Kicad
   PCBs using the "Import" tool.

   Note that the behavior of the layout helper and `keymap-drawer` differs for rotated keys when omitting `rx`, `ry` parameters --
   `keymap-drawer` assumes rotation around the key center and layout helper assumes rotation around the top left of the key.
   For this reason it is recommended to explicitly specify `rx`, `ry` fields if `r` is specified. You might also want to omit the fields
   besides `x`, `y`, `r`, `rx` and `ry` in your final JSON since they won't be used by `keymap-drawer`.

2. **Parametrized ortholinear layouts**:
   This lets you specify parameters to automatically generate a split or non-split ortholinear layout.

Following physical layout parameters can be specified either in the command line or under this field definition as key-value pairs:

- **`qmk_keyboard`** (equivalent to `-k`/`--qmk-keyboard` on the command line):
  Specifies the keyboard name to use with QMK `info.json` format layout definition, retrieved from following sources in order of preference:
  - `<keyboard>.json` (with `/`'s in `<keyboard>` replaced by `@`) under [`resources/qmk_layouts`](/resources/qmk_layouts/), if it exists
  - [QMK keyboard metadata API](https://docs.qmk.fm/#/configurator_architecture?id=keyboard-metadata) that [QMK Configurator](https://config.qmk.fm) also uses

  _Example:_ `layout: {qmk_keyboard: crkbd/rev1}`
- **`qmk_info_json`** (equivalent to `-j`/`--qmk-info-json` on the command line):
  Specifies the path to a local QMK format `info.json` file to use

  _Example:_ `layout: {qmk_info_json: my_special_layout.json}`
- **`qmk_layout`** (equivalent to `-l`/`--qmk-layout` on the command line):
  Specifies the layout macro to be used for the QMK keyboard, defaults to first one specified if not used --
  should be used alongside one of the above two options

  _Example:_ `layout: {qmk_keyboard: crkbd/rev1, qmk_layout: LAYOUT_split_3x5_3}`
- **`ortho_layout`** (equivalent to `-o`/`--ortho-layout` on the command line):
  Specifies a mapping of parameters to values to generate an ortholinear physical layout, with schema:

  | field name   | type                     | default value | description                                                                                              |
  | ------------ | ------------------------ | ------------- | -------------------------------------------------------------------------------------------------------- |
  | `split`      | `bool`                   | `False`       | whether the layout is a split keyboard or not, affects a few other options below                         |
  | `rows`       | `int`                    | required      | how many rows are in the keyboard, excluding the thumb row if split                                      |
  | `columns`    | `int`                    | required      | how many columns are in the keyboard, only applies to one half if split                                  |
  | `thumbs`     | `int \| "MIT" \| "2x2u"` | `0`           | the number thumb keys per half if split; for non-splits can only take special values `MIT` or `2x2u`[^1] |
  | `drop_pinky` | `bool`                   | `False`       | whether the pinky (outermost) columns have one fewer key, N/A for non-splits                             |
  | `drop_inner` | `bool`                   | `False`       | whether the inner index (innermost) columns have one fewer key, N/A for non-splits                       |

  _Example:_ `layout: {ortho_layout: {split: true, rows: 3, columns: 5, thumbs: 3}}`

[^1]: Corresponding to bottom row arrangements of a single `2u` key, or two neighboring `2u` keys, respectively.

**Hint**: You can use the [QMK Configurator](https://config.qmk.fm/) to search for `qmk_keyboard` and `qmk_layout` values, and preview the physical layout.

> #### ℹ️ CLI+keymap YAML specification
> If these parameters are specified in both command line and under the `layout` section, the former will take precedence.

## `layers`

This field is an ordered mapping of layer names to a list of `LayoutKey` specs that represent the keys on that layer.
A `LayoutKey` can be defined with either a string value or with a mapping with the following fields:

| field name (alias) | type  | default value | description                                                                                                                                                                                                                                                                  |
| ------------------ | ----- | ------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `tap (t)`          | `str` | `""`          | the tap action of a key, drawn on the center of the key; spaces will be converted to line breaks[^2]                                                                                                                                                                         |
| `hold (h)`         | `str` | `""`          | the hold action of a key, drawn on the bottom of the key                                                                                                                                                                                                                     |
| `shifted (s)`      | `str` | `""`          | the "shifted" action of a key, drawn on the top of the key                                                                                                                                                                                                                   |
| `type`             | `str` | `""`          | the styling of the key that corresponds to the [SVG class](keymap_drawer/config.py#L51)[^3]. predefined types are `held` (a red shading to denote held down keys), `ghost` (dashed outline to denote optional keys in a layout), `trans` (lighter text for transparent keys) |

[^2]: You can prevent line breaks by using double spaces `"  "` to denote a single non-breaking space.
[^3]: Text styling can be overridden in the SVG config using the `"tap"`, `"hold"` and `"shifted"` classes if desired.

Using a string value such as `"A"` for a key spec is equivalent to defining a mapping with only the tap field, i.e., `{tap: "A"}`.
It is meant to be used as a shortcut for keys that do not need `hold` or `type` fields.

You can use the special `$$..$$` syntax to refer to custom SVG glyphs in `tap`/`hold`/`shifted` fields, however note that they cannot be used with other text or glyphs inside the same field value.
See the [custom glyphs section](README.md#custom-glyphs) for more information.

`layers` field also flattens any lists that are contained in its value: This allows you to semantically divide keys to "rows," if you prefer to do so.
The two layers in the following example are functionally identical:

```yaml
layers:
  flat_layer: ["7", "8", "9", "4", "5", "6", "1", "2", "3", {t: "0", h: Fn}]
  nested_layer:
    - ["7", "8", "9"]
    - ["4", "5", "6"]
    - ["1", "2", "3"]
    - {t: "0", h: Fn}
```

## `combos`

This is an optional field that contains a list of combo specs, each of which is a mapping that can have the following fields:

| field name (alias)  | type                                              | default value | description                                                                                                                                                                       |
| ------------------- | ------------------------------------------------- | ------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `key_positions (p)` | `list[int]`                                       | required      | list of key indices that trigger the combo[^4]                                                                                                                                    |
| `key (k)`           | `LayoutKey`[^5]                                   | required      | key produced by the combo when triggered, `type` field will be ignored                                                                                                            |
| `layers (l)`        | `list[str]`                                       | `[]`[^6]      | list of layers the combo can trigger on, specified using layer names in `layers` field                                                                                            |
| `align (a)`         | `"mid" \| "top" \| "bottom" \| "left" \| "right"` | `"mid"`       | where to draw the combo: `mid` draws on the mid-point of triggering keys' center coordinates, or to the `top`/`bottom`/`left`/`right` of the triggering keys                      |
| `offset (o)`        | `float`                                           | `0.0`         | additional offset to `top`/`bottom`/`left`/`right` positioning, specified in units of key width/height: useful for combos that would otherwise overlap                            |
| `dendron (d)`       | `null \| bool`                                    | `null`        | whether to draw dendrons going from combo to triggering key coordinates, default is to draw for non-`mid` alignments and draw for `mid` if key coordinates are far from the combo |
| `slide (s)`         | `null \| float (-1 <= val <= 1)`                  | `null`        | slide the combo box along an axis between keys -- can be used for moving `top`/`bottom` combo boxes left/right, `left`/`right` boxes up/down, or `mid` combos between two keys    |
| `arc_scale`         | `float`                                           | `1.0`         | scale the arcs going left/right for `top`/`bottom` or up/down for `left`/`right` aligned combos                                                                                   |
| `type`              | `str`                                             | `""`          | the styling of the key that corresponds to the [SVG class](keymap_drawer/config.py#L51), see `LayoutKey` definition above                                                         |
| `width (w)`         | `float`                                           | `null`        | the width of the combo box (in pixels), defaults to `draw_config.combo_w` if null                                                                                                 |
| `height (h)`        | `float`                                           | `null`        | the height of the combo box (in pixels), defaults to `draw_config.combo_h` if null                                                                                                |
| `rotation (r)`      | `float`                                           | `0.0`         | the rotation of the combo box in degrees -- only applies to the box itself and not any dendrons                                                                                   |

All fields except `key_positions`, `key` and `type` are ignored when `draw_config.separate_combo_diagrams` is used.

[^4]: Key indices start from `0` on the first key position and increase by columns and then rows, corresponding to their ordering in the `layers` field. This matches the `key-positions` property in ZMK combo definitions.
[^5]: Just like for keys in a layer under the `layers` field, `key` field can be specified with a string value as a shortcut, or a mapping (where the `type` field will be ignored).
[^6]: The default value of empty list corresponds to all layers in the keymap, similar to the `layers` property in ZMK.

_Example:_
```yaml
combos:
  - {p: [0, 1], k: Tab, l: [Qwerty]}
  - {p: [1, 2], k: Esc, l: [Qwerty]}
```

## `draw_config`

This optional field lets you override [config parameters](README.md#customization) for SVG drawing.
This way you can specify drawing configuration for a specific layout and store in the keymap specification.
It is a mapping from field names in [`DrawConfig` class](keymap_drawer/config.py) to values.

_Example:_
```yaml
draw_config:
  key_h: 60
  combo_h: 22
  combo_w: 24
```
