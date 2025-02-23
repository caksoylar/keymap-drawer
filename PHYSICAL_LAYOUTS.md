# Physical Layout Specification

`keymap-drawer` uses the "physical" layout of the keyboard you are drawing a keymap for, in order to create a diagram of your keymap.
This physical layout defines the location, size and ordering of the keys on your keyboard.

There are multiple ways to specify physical layouts.
You can use keyboard names for known keyboards, specify a custom layout fully using a data file, or use a parametrized layout generator.

See the [`layout` section](KEYMAP_SPEC.md#layout) in the keymap spec for a summary of options and how to specify them in the keymap YAML or command-line for `keymap draw`.

## Keyboard aliases

You can specify physical layouts using keyboard names, if they are available in the set of sources `keymap-drawer` uses.
Following physical layout parameters can be specified either in the command line or under this field definition as key-value pairs:

- **`qmk_keyboard`** (equivalent to `-k`/`--qmk-keyboard` on the command line):
  Specifies the keyboard name to use with QMK `info.json` format layout definition, retrieved from following sources in order of preference:

  - `<keyboard>.json` (with `/`'s in `<keyboard>` replaced by `@`) under [`resources/extra_layouts`](resources/extra_layouts/), if it exists
  - [QMK keyboard metadata API](https://docs.qmk.fm/#/configurator_architecture?id=keyboard-metadata) that [QMK Configurator](https://config.qmk.fm) also uses

  _Example:_ `layout: {qmk_keyboard: crkbd/rev1}`

- **`zmk_keyboard`** (equivalent to `-z`/`--zmk-keyboard` on the command line):
  Specifies a ZMK keyboard name, which is typically the basename of the keymap file name `<keyboard>.keymap`.
  This value gets converted internally using [a look-up table](resources/zmk_keyboard_layouts.yaml) to a different layout type such as `qmk_keyboard` or `ortho_layout`,
  taking into account `layout_name` field if specified.
  If the value of the field isn't found in the conversion mapping, it will fall back to using `qmk_keyboard` with the same value.

  _Example:_ `layout: {zmk_keyboard: corne}`

**Hint**: You can use the [QMK Configurator](https://config.qmk.fm/) to search for `qmk_keyboard` values and `layout_name`s (see below) you can use with it, and preview the physical layout.

## QMK `info.json` specification

This is the [official QMK format](https://docs.qmk.fm/#/reference_info_json?id=layout-format) for physical key descriptions
that every `info.json` file in the QMK firmware repository uses. `keymap-drawer` only uses the `x`, `y`, `r`, `rx` and `ry` fields.
Note that `keymap-editor` utilizes [the same format](https://github.com/nickcoutsos/keymap-editor/wiki/Defining-keyboard-layouts) for `info.json`.
QMK spec also lets you specify multiple "layouts" per keyboard corresponding to different layout macros to support physical variations.

QMK `info.json`-like physical layout files can be specified either in the command line or under this field definition as a key-value pair:

- **`qmk_info_json`** (equivalent to `-j`/`--qmk-info-json` on the command line):
  Specifies the path to a local QMK format `info.json` file to use (exclusive with `qmk_keyboard`).

  _Example:_ `layout: {qmk_info_json: my_special_layout.json}`

You can create your own physical layout definitions in QMK format to use with `keymap-drawer`, which accepts JSONs with the official schema that
has layouts listed under the `layout` key, or one that directly consists of a list of key specs as a shortcut. The best way to generate one is to use
the interactive [Keymap Layout Helper tool](https://nickcoutsos.github.io/keymap-layout-tools/) tool by @nickcoutsos. This web app is useful to
visualize a given JSON definition, re-order keys using the "Re-order" tool and generate one from scratch from various formats such as KLE or Kicad
PCBs using the "Import" tool.[^1]

[^1]:
    The behavior of the layout helper and `keymap-drawer` differs for rotated keys when omitting `rx`, `ry` parameters --
    `keymap-drawer` assumes rotation around the key center and layout helper assumes rotation around the top left of the key.
    For this reason it is recommended to explicitly specify `rx`, `ry` fields if `r` is specified. You might also want to omit the fields
    besides `x`, `y`, `r`, `rx` and `ry` in your final JSON since they won't be used by `keymap-drawer`.

## ZMK devicetree physical layout specification

This is the [official ZMK format](https://zmk.dev/docs/development/hardware-integration/physical-layouts) for specifying physical layouts,
which are written in devicetree syntax and typically included in keyboard definitions.
It lets you specify multiple "layouts" per keyboard corresponding to different devicetree nodes to support physical variations, similar to QMK format.
The fields to specify each layout are described in the docs linked.

ZMK physical layouts can be specified via either in the command line or under this field definition as key-value pairs:

- **`dts_layout`** (equivalent to `-d`/`--dts-layout` on the command line):
  Specifies the path to a local devicetree file containing ZMK physical layouts.

  _Example:_ `layout: {dts_layout: my_keyboard-layouts.dtsi}`

**Hint**: The physical layout you specify is independent of the firmware that your keymap originates from.
For example, after parsing a ZMK keymap you can specify a layout using `qmk_keyboard`, as long as the physical layout is compatible with
the keymap YAML generated by the parse.

## Layout name

Above physical layout specification (`qmk_keyboard`, `zmk_keyboard`, `qmk_info_json`, `dts_layout`) can define multiple physical layouts at once.
You can choose among the ones they define using the `layout_name` field, such as to select the 5 column variant of a 6 column split keyboard.

- **`layout_name`** (equivalent to `-l`/`--layout-name` on the command line):

  - When used with `qmk_keyboard` or `qmk_info_json`, it specifies the layout macro to be used among the ones defined in the QMK info file.
  - When used with `zmk_keyboard` or `dts_layout`, specifies a ZMK physical layout node label that the keyboard's physical layout definition contains.

  If this isn't specified, the first defined layout macro or physical layout node is used.

  _Example:_ `layout: {zmk_keyboard: corne, layout_name: foostan_corne_5col_layout}`

  _Example:_ `layout: {qmk_keyboard: crkbd/rev1, layout_name: LAYOUT_split_3x5_3}`

## Parametrized ortholinear layout specification

This option lets you specify a set of parameters to automatically generate a split or non-split ortholinear layout.

Following physical layout parameter can be specified either in the command line or under this field definition as a key-value pair:

- **`ortho_layout`** (equivalent to `--ortho-layout` on the command line):
  Specifies a mapping of parameters to values to generate an ortholinear physical layout, with schema:

  | field name   | type                     | default value | description                                                                                              |
  | ------------ | ------------------------ | ------------- | -------------------------------------------------------------------------------------------------------- |
  | `split`      | `bool`                   | `False`       | whether the layout is a split keyboard or not, affects a few other options below                         |
  | `rows`       | `int`                    | required      | how many rows are in the keyboard, excluding the thumb row if split                                      |
  | `columns`    | `int`                    | required      | how many columns are in the keyboard, only applies to one half if split                                  |
  | `thumbs`     | `int \| "MIT" \| "2x2u"` | `0`           | the number thumb keys per half if split; for non-splits can only take special values `MIT` or `2x2u`[^2] |
  | `drop_pinky` | `bool`                   | `False`       | whether the pinky (outermost) columns have one fewer key, N/A for non-splits                             |
  | `drop_inner` | `bool`                   | `False`       | whether the inner index (innermost) columns have one fewer key, N/A for non-splits                       |

  _Example:_ `layout: {ortho_layout: {split: true, rows: 3, columns: 5, thumbs: 3}}`

[^2]: Corresponding to bottom row arrangements of a single `2u` key, or two neighboring `2u` keys, respectively.

## Cols+Thumbs notation specification

Using the "cols+thumbs" notation is another way to generate a layout parametrically, but via a special syntax string that describes the
key counts in each column and thumb cluster of the keyboard. This is more flexible than the `ortho_layout` option
if special MIT/2x2u thumbs aren't needed.

Following physical layout parameter can be specified either in the command line or under this field definition as a key-value pair:

- **`cols_thumbs_notation`** (equivalent to `-n`/`--cols-thumbs-notation` on the command line):
  Specifies a specially formatted string to describe an ortholinear keyboard layout. This string is composed of a number of digits
  corresponding to each column in the keyboard, optionally augmented by a count of thumb keys. This can be repeated to specify
  split keyboards with two or more halves, separated by a space or underscore.

  _Example:_ `layout: {cols_thumbs_notation: 33333+1 2+33332}`

Above example specifies an asymmetric 32 key split keyboard with 3 rows and 5 columns on the left side, and a right-aligned thumb cluster with a single key.
The right half has a left-aligned thumb cluster with two keys, 5 columns with 3 rows but has a key dropped on the last column.

Normally each column will be centered vertically, but you can also add modifier characters after each column count to tweak this:
`v` or `d` (for ↓/"down") pushes the column down by half a key height, and `^` or `u` (for ↑/"up") pushes it up by the same amount.
These modifiers can be repeated to push further.
Similarly, you can use `>` or `r` to push a thumb row right by half a key width, or `<` or `l` to push it left.

As an advanced example, notation `2v333+2> 3+13332^ 33` will result in a physical layout that looks like below:

```
  x x x       x x x x   x x
x x x x     x x x x x   x x
x x x x       x x x     x x
     x x    x x x
```
