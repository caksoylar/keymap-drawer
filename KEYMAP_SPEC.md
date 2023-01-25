# Keymap YAML specification

This page documents the YAML-format keymap representation that is output by `keymap parse` and used by `keymap draw`.

At the root, three key values are expected, which are detailed in respective sections. A typical keymap will have the following structure:

```yaml
layout:     # physical layout specs, optional
  ...
layers:     # ordered mapping of layer name to contents
  layer_1:  # list of (lists of) key specs
    - [Q, W, ...]
    ...
  layer_2:
    ...
combos:     # list of combo specs, optional
  - ...
```

## `layout`

This field provides information about the physical layout of the keyboard, i.e., the location and sizes of individual keys.
Following physical layout parameters ([mentioned in the README](README.md#producing-the-svg)) can be specified either in the command line or under this field definition as key-value pairs:

- **`qmk_keyboard`** (equivalent to `-k`/`--qmk-keyboard` on the command line):
  Specifies the path of the keyboard to retrieve from, in the QMK repository
- **`qmk_layout`** (equivalent to `-l`/`--qmk-layout` on the command line):
  Specifies the layout macro to be used for the QMK keyboard, defaults to first one specified if not used
- **`ortho_layout`** (equivalent to `-o`/`--ortho-layout` on the command line):
  Specifies a mapping of parameters to values to generate an ortholinear physical layout, with schema:

  | field name   | required? | default value | description                                                                                              |
  | ------------ | --------- | ------------- | -------------------------------------------------------------------------------------------------------- |
  | `split`      | yes       |               | whether the layout is a split keyboard or not, affects a few other options below                         |
  | `rows`       | yes       |               | how many rows are in the keyboard, excluding the thumb row if split                                      |
  | `columns`    | yes       |               | how many columns are in the keyboard, only applies to one half if split                                  |
  | `thumbs`     | no        | `0`           | the number thumb keys per half if split; for non-splits can only take special values `MIT` or `2x2u`[^1] |
  | `drop_pinky` | no        | `False`       | whether the pinky (outermost) columns have one fewer key, N/A for non-splits                             |
  | `drop_inner` | no        | `False`       | whether the inner index (innermost) columns have one fewer key, N/A for non-splits                       |

[^1]: Corresponding to bottom row arrangements of a single `2u` key, or two neighboring `2u` keys, respectively.

> **Note**
>
> If these parameters are specified in both command line and under the `layout` section, the former will take precedence.

## `layers`

This field is an ordered mapping of layer names to a list of key specs that represent the keys on that layer.
A key spec can be defined with either a string value or with a mapping with the following fields:

| field name (alias) | required? | default value | description                                                                                                                                 |
| ------------------ | --------- | ------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| `tap` (`t`)        | yes       | `""`          | the tap action of a key, drawn on the center of the key                                                                                     |
| `hold` (`h`)       | no        | `""`          | the hold action of a key, drawn on the bottom of the key                                                                                    |
| `type` (`t`)       | no        | `None`        | the styling of the key: `held` adds a red shading to denote held down keys, `ghost` adds a gray shading to denote optional keys in a layout |

Using a string value such as `"A"` for a key spec is equivalent to defining a mapping with only the tap field, i.e., `{tap: "A"}`.
It is meant to be used as a shortcut for keys that do not need `hold` or `type` fields.

`layers` field also flattens any lists that are contained in its value: This allows you to semantically divide keys to "rows," if you prefer to do so.
For instance, the two layers in the following example are functionally identical:

```yaml
layers:
  flat_layer: ["7", "8", "9", "4", "5", "6", "1", "2", "3"]
  nested_layer:
    - ["7", "8", "9"]
    - ["4", "5", "6"]
    - ["1", "2", "3"]
```

## `combos`
