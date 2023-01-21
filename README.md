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
- Both parsing and drawing are customizable with a config file, see ["Customization" section](#customization)

See [examples folder](examples/) for example inputs and outputs.

## Usage

## Keymap YAML specification

## Customization

Both parsing and drawing can be customized using a configuration file passed to the `keymap` executable.
This allows you to, for instance, change the default keycode-to-symbol mappings while parsing, or change font sizes, colors etc. while drawing the SVG.

Start by dumping the default configuration settings to a file:

```sh
keymap dump-config >my_config.yaml
```

Then, edit the file to change the settings, referring to comments in [config.py](keymap_drawer/config.py).
You can then pass this file to either `draw` and `parse` subcommands with the `-c`/`--config` argument (note the location before the subcommand):

```sh
keymap -c my_config.yaml parse [...] >my_keymap.yaml
keymap -c my_config.yaml draw [...] my_keymap.yaml >my_keymap.svg
```

Since configuration classes are [Pydantic settings](https://docs.pydantic.dev/usage/settings/) they can also be overridden by environment variables with a `KEYMAP_` prefix:

```sh
KEYMAP_raw_binding_map='{"&bootloader": "BOOT"}' keymap parse -z zmk-config/config/cradio.keymap >cradio.yaml
```

## Development

This project requires Python 3.10+ and uses [`poetry`](https://python-poetry.org/) for packaging.

To get started, install `poetry`, clone this repo, then install dependencies with `poetry`:

```sh
git clone https://github.com/caksoylar/keymap-drawer.git
cd keymap-drawer
poetry install  # --with dev,lsp optional dependencies
```

`poetry shell` will activate a virtual environment with `keymap_drawer` in Python path and `keymap` executable available.
Changes in the source code will be reflected.

## Related projects

- [The original `keymap`](https://github.com/callum-oakley/keymap/)
- [Keymapviz](https://github.com/yskoht/keymapviz)
- [@nickcoutsos's ZMK keymap editor](https://github.com/nickcoutsos/keymap-editor)
- [@leiserfg's ZMK parser](https://github.com/leiserfg/zmk-config/tree/master/parser)
- [@jbarr21's ZMK parser](https://github.com/jbarr21/zmk-config/tree/main/parser)
