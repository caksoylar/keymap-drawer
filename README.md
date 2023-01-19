# `keymap-drawer`

Parse QMK & ZMK keymaps and draw them in SVG format, with support for visualizing hold-taps and combos.

(example SVG here)

## Features

- Draw keymap representations consisting of multiple layers, hold-tap keys and combos
  - Uses an intuitive and human-readable YAML format for specifying the keymap
  - Non-adjacent or 3+ key combos can be visualized by specifying its positioning relative to the keys, with automatically drawn dendrons to keys
- Bootstrap the YAML representation by automatically parsing QMK or ZMK keymap files
  - QMK keymaps are supported in json format as emitted by QMK Configurator and `qmk c2json` (and thus it is not possible to parse combos at the moment)
  - ZMK formats are parsed from devicetree `.keymap` files with preprocessor applied, with full support for parsing combos and hold-taps
- Arbitrary physical keyboard layouts (with rotated keys!) supported, along with parameterized ortho layouts
  - Ortho layout generator supports split/non-split ortho layouts with row/column/thumb key counts, MIT/2x2u layouts for non-split, dropped pinky/inner columns
  - Layouts for keyboards supported in QMK can be retrieved from QMK's Keyboards API using keyboard and layout names, similar to QMK Configurator
- Both parsing and drawing are customizable with a config file, see "Customization" section

See [examples folder](./examples/) for example YAML's with output SVGs.

## Usage

## Customization

## Development

This project requires Python 3.10+ and uses [`poetry`](https://python-poetry.org/) for packaging and development.

To get started with development, clone this repo, then initialize it:

## TODO
