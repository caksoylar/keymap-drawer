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

  | field name (alias) | required? | default value | description                                                                                              |
  | ------------------ | --------- | ------------- | -------------------------------------------------------------------------------------------------------- |
  | `split`            | yes       |               | whether the layout is a split keyboard or not, affects a few other options below                         |
  | `rows`             | yes       |               | how many rows are in the keyboard, excluding the thumb row if split                                      |
  | `columns`          | yes       |               | how many columns are in the keyboard, only applies to one half if split                                  |
  | `thumbs`           | no        | `0`           | the number thumb keys per half if split; for non-splits can only take special values `MIT` or `2x2u`[^1] |
  | `drop_pinky`       | no        | False         | whether the pinky (outermost) columns have one fewer key, N/A for non-splits                             |
  | `drop_inner`       | no        | False         | whether the inner index (innermost) columns have one fewer key, N/A for non-splits                       |

[^1]: Corresponding to bottom row arrangements of a single `2u` key, or two neighboring `2u` keys, respectively.

> **Note**
>
> If these parameters are specified in both command line and under the `layout` section, the former will take precedence.

## `layers`

## `combos`
