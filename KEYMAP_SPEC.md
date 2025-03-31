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
  ...
```

## `layout`

This field provides information about the physical layout of the keyboard, i.e., the location and sizes of individual keys.
`keymap-drawer` understands different types of physical layout descriptions, with corresponding sub-fields under the `layout` field.

Following physical layout parameters can be specified either in the command line for `keymap draw` or under this field definition as key-value pairs.
Please see [physical layouts documentation](PHYSICAL_LAYOUTS.md) for details on each option below.

| field name             | CLI argument                  | doc                                                                     | description                                                                                |
| ---------------------- | ----------------------------- | ----------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| `qmk_keyboard`         | `-k`/`--qmk-keyboard`         | [🔗](PHYSICAL_LAYOUTS.md#keyboard-aliases)                              | QMK keyboard name to look up physical layouts for                                          |
| `zmk_keyboard`         | `-z`/`--zmk-keyboard`         | [🔗](PHYSICAL_LAYOUTS.md#keyboard-aliases)                              | ZMK keyboard name to look up physical layouts for                                          |
| `qmk_info_json`        | `-j`/`--qmk-info-json`        | [🔗](PHYSICAL_LAYOUTS.md#qmk-infojson-specification)                    | path to a local json file containing QMK-like physical layout definitions                  |
| `dts_layout`           | `-d`/`--dts-layout`           | [🔗](PHYSICAL_LAYOUTS.md#zmk-devicetree-physical-layout-specification)  | path to a local devicetree file containing ZMK physical layout definitions                 |
| `layout_name`          | `-l`/`--layout-name`          | [🔗](PHYSICAL_LAYOUTS.md#layout-name)                                   | layout name to use among multiple layouts that are provided by one of above specifications |
| `ortho_layout`         | `--ortho-layout`              | [🔗](PHYSICAL_LAYOUTS.md#parametrized-ortholinear-layout-specification) | a set of parameters to automatically generate a split or non-split ortholinear layout      |
| `cols_thumbs_notation` | `-n`/`--cols-thumbs-notation` | [🔗](PHYSICAL_LAYOUTS.md#colsthumbs-notation-specification)             | a specially formatted string to describe an ortholinear keyboard layout                    |

Except for `layout_name`, all other fields are exclusive. `layout_name` is optional; if not specified, the first definition in corresponding layout specification is used.

_Examples:_

- `layout: {qmk_keyboard: crkbd/rev1}`
- `layout: {zmk_keyboard: corne}`
- `layout: {qmk_info_json: my_special_layout.json}`
- `layout: {dts_layout: my_keyboard-layouts.dtsi}`
- `layout: {zmk_keyboard: corne, layout_name: foostan_corne_5col_layout}`
- `layout: {qmk_keyboard: crkbd/rev1, layout_name: LAYOUT_split_3x5_3}`
- `layout: {ortho_layout: {split: true, rows: 3, columns: 5, thumbs: 3}}`
- `layout: {cols_thumbs_notation: 33333+1 2+33332}`

> #### ℹ️ CLI+keymap YAML specification
>
> If the physical layout parameters are specified in both the command line for `keymap draw` and under the `layout` section of keymap YAML, the former will take precedence.

## `layers`

This field is an ordered mapping of layer names to a list of `LayoutKey` specs that represent the keys on that layer.
A `LayoutKey` can be defined with either a string value or with a mapping with the following fields:

| field name | aliases       | type  | default value | description                                                                                                                                                                                                                                                                 |
| ---------- | ------------- | ----- | ------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `tap`      | `t`, `center` | `str` | `""`          | the tap action of a key, drawn on the center of the key; spaces will be converted to line breaks[^3]                                                                                                                                                                        |
| `hold`     | `h`, `bottom` | `str` | `""`          | the hold action of a key, drawn on the bottom of the key                                                                                                                                                                                                                    |
| `shifted`  | `s`, `top`    | `str` | `""`          | the "shifted" action of a key, drawn on the top of the key                                                                                                                                                                                                                  |
| `left`     |               | `str` | `""`          | left legend, drawn on the left-center of the key                                                                                                                                                                                                                            |
| `right`    |               | `str` | `""`          | right legend, drawn on the right-center of the key                                                                                                                                                                                                                          |
| `type`     |               | `str` | `""`          | the styling of the key that corresponds to the [SVG class](CONFIGURATION.md#svg_style)[^4]. predefined types are `held` (a red shading to denote held down keys), `ghost` (dashed outline to denote optional keys in a layout), `trans` (lighter text for transparent keys) |

[^3]: You can prevent line breaks by using double spaces `"  "` to denote a single non-breaking space.

[^4]: Text styling can be overridden in the `svg_extra_style` field under `draw_config` using the `"tap"`, `"hold"`, `"shifted"`, `"left"` and `"right"` CSS classes if desired.

Using a string value such as `"A"` for a key spec is equivalent to defining a mapping with only the tap field, i.e., `{tap: "A"}`.
It is meant to be used as a shortcut for keys that do not need any other fields.

You can use the special `$$..$$` syntax to refer to custom SVG glyphs in `tap`/`hold`/`shifted`/`left`/`right` fields, however note that they cannot be used with other text or glyphs inside the same field value.
See the [custom glyphs section](README.md#custom-glyphs) for more information.

`layers` field also flattens any lists that are contained in its value: This allows you to semantically divide keys to "rows," if you prefer to do so.
The two layers in the following example are functionally identical:

<!-- prettier-ignore -->
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

This is an optional field that contains a list of `ComboSpec`s, each of which is a mapping that can have the following fields:

| field name      | alias | type                                              | default value | description                                                                                                                                                                       |
| --------------- | ----- | ------------------------------------------------- | ------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `key_positions` | `p`   | `list[int]`                                       |               | list of key indices that trigger the combo[^5]                                                                                                                                    |
| `trigger_keys`  | `tk`  | `list[LayoutKey]`[^7]                             |               | list of trigger keys (specified using their legends) that trigger the combo[^6]                                                                                                   |
| `key`           | `k`   | `LayoutKey`[^7]                                   | required      | key produced by the combo when triggered, `LayoutKey`'s `type` field will be combined with the type field of `ComboSpec`                                                          |
| `layers`        | `l`   | `list[str]`                                       | `[]`[^8]      | list of layers the combo can trigger on, specified using layer names in `layers` field                                                                                            |
| `align`         | `a`   | `"mid" \| "top" \| "bottom" \| "left" \| "right"` | `"mid"`       | where to draw the combo: `mid` draws on the mid-point of triggering keys' center coordinates, or to the `top`/`bottom`/`left`/`right` of the triggering keys                      |
| `offset`        | `o`   | `float`                                           | `0.0`         | additional offset to `top`/`bottom`/`left`/`right` positioning, specified in units of key width/height: useful for combos that would otherwise overlap                            |
| `dendron`       | `d`   | `null \| bool`                                    | `null`        | whether to draw dendrons going from combo to triggering key coordinates, default is to draw for non-`mid` alignments and draw for `mid` if key coordinates are far from the combo |
| `slide`         | `s`   | `null \| float (-1 <= val <= 1)`                  | `null`        | slide the combo box along an axis between keys -- can be used for moving `top`/`bottom` combo boxes left/right, `left`/`right` boxes up/down, or `mid` combos between two keys    |
| `arc_scale`     |       | `float`                                           | `1.0`         | scale the arcs going left/right for `top`/`bottom` or up/down for `left`/`right` aligned combos                                                                                   |
| `type`          |       | `str`                                             | `""`          | the styling of the key that corresponds to the [CSS class](CONFIGURATION.md#svg_style), see `LayoutKey` definition above                                                          |
| `width`         | `w`   | `float`                                           | `null`        | the width of the combo box (in pixels), defaults to `draw_config.combo_w` if null                                                                                                 |
| `height`        | `h`   | `float`                                           | `null`        | the height of the combo box (in pixels), defaults to `draw_config.combo_h` if null                                                                                                |
| `rotation`      | `r`   | `float`                                           | `0.0`         | the rotation of the combo box in degrees -- only applies to the box itself and not any dendrons                                                                                   |
| `draw_separate` |       | `null \| bool`                                    | `null`        | whether to draw the combo separate from layers, using a dedicated diagram. defaults to `draw_config.separate_combo_diagrams` if null                                              |
| `hidden`        |       | `bool`                                            | `false`       | do not draw this combo at all -- useful when you have the combo in the parse output but you want to ignore it through your config                                                 |

`key_positions` and `trigger_keys` are exclusive, and exactly one of them must be specified.

All fields except `key_positions`/`trigger_keys`, `key`, `type` and `hidden` are ignored when combo is drawn in a separate diagram using `draw_separate` or `draw_config.separate_combo_diagrams`.

[^5]: Key indices start from `0` on the first key position and increase by columns and then rows, corresponding to their ordering in the `layers` field. This matches the `key-positions` property in ZMK combo definitions.

[^6]: The values in the list will be matched to the `LayoutKey` specs under `layers` to resolve to key positions. First, a full mapping-based match will be performed. If not found, it will try to match to only the `tap` field of each layer key.

[^7]: Just like for keys in a layer under the `layers` field, `key` field can be specified with a string value as a shortcut, or a mapping (where the `type` field will be ignored).

[^8]: The default value of empty list corresponds to all layers in the keymap, similar to the `layers` property in ZMK.

_Example:_

```yaml
combos:
  - { p: [0, 1], k: Tab, l: [Qwerty] }
  - { tk: [J, K], k: Esc, l: [Qwerty] }
```

## `draw_config`

This optional field lets you override [config parameters](README.md#customization) for SVG drawing.
This way you can specify drawing configuration for a specific layout and store in the keymap specification.
It is a mapping from field names in [`DrawConfig` class](CONFIGURATION.md#draw-configuration) to values.

_Example:_

```yaml
draw_config:
  key_h: 60
  combo_h: 22
  combo_w: 24
```
