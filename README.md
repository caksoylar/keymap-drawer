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
- Arbitrary physical keyboard layouts (with rotated keys!) supported, along with parametrized ortho layouts
  - Ortho layout generator supports split/non-split ortho layouts with row/column/thumb key counts, MIT/2x2u layouts for non-split, dropped pinky/inner columns
  - Layouts for keyboards supported in QMK can be retrieved from QMK's Keyboards API using keyboard and layout names, similar to QMK Configurator
- Both parsing and drawing are customizable with a config file, see ["Customization" section](#customization)

See [examples folder](examples/) for example inputs and outputs.

## Usage

### Installation

The recommended way to install `keymap-drawer` is through [`pipx`](https://pypa.github.io/pipx/), which sets up an isolated environment and installs the application with a single command:

```sh
pipx install keymap-drawer
```

This will make the `keymap` command available in your `PATH` to use:

```sh
keymap --help
```

Alternatively, you can `pip install` into your favorite `virtualenv` or in your user install directory with `pip install --user keymap-drawer`. Also see the [development](#development) section to install from source.

### Bootstrapping your keymap representation

`parse` subcommand of `keymap` helps to parse an existing QMK or ZMK keymap file into the keymap YAML representation the `draw` command uses to generate SVGs.
`-c`/`--columns` is an optional parameter that specifies the total number of columns in the keymap to better reorganize output layers.

#### QMK

Only json-format QMK keymaps are supported, which can be exported from [QMK Configurator](https://config.qmk.fm/) or converted from `keymap.c` via `qmk c2json`.

```sh
qmk c2json ~/qmk_firmware/keyboards/ferris/keymaps/username/keymap.c | keymap parse -c 10 -q - >sweep_keymap.yaml
```

Due to current limitations of the `keymap.json` format, combos and layer names will not be present in the output.

#### ZMK

ZMK keymaps are parsed by pointing to the `.keymap` file. These will be preprocessed similar to the ZMK build system, so `#define`'s and `#include`s are fully supported.

```sh
keymap parse -c 10 -z ~/zmk-config/config/cradio.keymap >sweep_keymap.yaml
```

Currently combos, hold-taps (including custom ones), layer names and sticky keys (only default `&sk`/`&sl`) can be determined via parsing.
For layer names, `label` property will take precedence over the layer's node name if it is provided.

> **Warning**
>
> Parsing rules currently require that your `keymap` and `combos` nodes be nested one-level deep from the root node and have fixed names. These conditions typically hold for most keymaps by convention.

### Tweaking produced keymap representation

While the parsing step aims to create a decent starting point, you will likely want to make certain tweaks to the produced keymap representation.
Please refer to [the next section on the keymap schema](#keymap-yaml-specification) while making changes:

0. (If starting from a QMK keymap:) Add combo definitions using key position indices.
1. Tweak the display form of parsed keys, e.g, replacing `&bootloader` with `BOOT`. (See [customization section](#customization) to modify parser's behavior.)
2. Add `align` and/or `offset` properties to combos between non-adjacent keys or those 3+ key positions, in order to position them better
3. Add `type` specifiers to certain keys, such as `held` for layer keys used to enter the current layer or `ghost` for optional keys

It might be beneficial to start by `draw`'ing the current representation and iterate over these changes, especially for positioning tricky combos.

### Producing the SVG

Final step is to produce the SVG representation using the `keymap draw` command.
However to do that, we need to specify the physical layout of the keyboard, i.e., how many keys there are, where each key is positioned etc. `keymap-drawer` can figure this information out from a few different sources:

#### QMK `info.json` specification

Each keyboard in the QMK repo has a `info.json` file which specifies physical key locations. Using the keyboard name in the QMK repo, we can fetch this information from the [keyboard metadata API](https://docs.qmk.fm/#/configurator_architecture?id=keyboard-metadata):

```sh
keymap draw -k ferris/sweep sweep_keymap.yaml >sweep_keymap.svg
```

You can also specify a layout macro to use alongside the keyboard name if you don't want to use the default one:

```sh
keymap draw -k crkbd/rev1 -l LAYOUT_split_3x5_3 corne_5col_keymap.yaml >corne_5col_keymap.svg
```

`-j` flag also allows you to pass a local `info.json` file instead of the keyboard name.

> **Note**
>
> If you parsed a QMK keymap, keyboard and layout information will be populated in the keymap YAML already, so you don't need to specify it in the command line.
>
> Hint: You can use the [QMK Configurator](https://config.qmk.fm/) to search for keyboard and layout names, and preview the physical layout.

#### Parametrized ortholinear layouts

You can also specify parameters to automatically generate a split or non-split ortholinear layout, by adding a `layout:` section in the keymap YAML, for example:

```yaml
layout:  # for a Sweep-like layout
    split: true  # split or non-split keyboard
    rows: 3      # number of rows (excluding thumb row if split)
    columns: 5   # number of columns (for each half if split)
    thumbs: 2    # number of thumb keys per side if split, can optionally be "MIT" or "2x2u" for non-split
```

See the following section on keymap specification for other options.

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
