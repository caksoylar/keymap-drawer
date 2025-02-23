<h1 align="center">
  <img alt="keymap-drawer logo" src="https://caksoylar.github.io/keymap-drawer/logo.svg" max-width="100%"/>
</h1>

[![PyPI version](https://img.shields.io/pypi/v/keymap-drawer.svg)](https://pypi.org/project/keymap-drawer/)

Parse QMK & ZMK keymaps and draw them in vector graphics (SVG) format, with support for visualizing hold-taps and combos that are commonly used with smaller keyboards.

Available as a [command-line tool](#command-line-tool-installation) or a [web application](https://caksoylar.github.io/keymap-drawer).

<div align="center">
  <a href="examples/showcase.yaml">
    <img alt="Example keymap visualization" src="https://caksoylar.github.io/keymap-drawer/showcase.svg"/>
  </a>
</div>

## Features

- Draw keymap representations consisting of multiple layers, hold-tap keys and combos
  - Uses a human-editable YAML format for specifying the keymap
  - Non-adjacent or 3+ key combos can be visualized by specifying its positioning relative to the keys, with automatically drawn dendrons to keys
  - Alternatively, output a separate diagram per combo if you have tricky key position combinations
- Bootstrap the YAML representation by automatically parsing QMK or ZMK keymap files
- Arbitrary physical keyboard layouts (with rotated keys!) supported, along with parametrized ortho layouts
- Both parsing and drawing are customizable with a config file, see ["Customization" section](#customization)
- Custom glyph support: render custom SVG icons and not just unicode text

See examples in [the live web demo](https://caksoylar.github.io/keymap-drawer) for example inputs and outputs.

Compared to to visual editors like [KLE](http://www.keyboard-layout-editor.com/), `keymap-drawer` takes a more programmatic approach.
It also decouples the physical keyboard layout from the keymap (i.e., layer and combo definitions) and provides the tooling to bootstrap it quickly from existing firmware configuration.

## Usage

### Try it as a web application

You can try the keymap parsing and drawing functionalities with a [Streamlit](https://streamlit.io) web application available at <https://caksoylar.github.io/keymap-drawer>.
Below instructions mostly apply for the web interface, where subcommands and option flags are mapped to different widgets in the UX.

### Command-line tool installation

The recommended way to install `keymap-drawer` is through [pipx](https://pipx.pypa.io), which sets up an isolated environment and installs the application with a single command:

```sh
pipx install keymap-drawer
```

This will make the `keymap` command available in your `PATH` to use:

```sh
keymap --help
```

Alternatively, you can `pip install keymap-drawer` in a virtual environment or install into your user install directory with `pip install --user keymap-drawer`.
See [the development section](#development) for instructions to install from source.

> #### ℹ️ Windows command-line issues
>
> If you are running on Windows, using the `-o`/`--output` parameter to save command outputs to files is recommended instead of redirecting stdout.
> Otherwise you might run into text encoding issues related to unicode characters in YAMLs and SVGs.

### Bootstrapping your keymap representation

**`keymap parse`** command helps to parse an existing QMK or ZMK keymap file into the keymap YAML representation the `draw` command uses to generate SVGs.
`-c`/`--columns` is an optional parameter that specifies the total number of columns in the keymap to better reorganize output layers.

- **QMK**: Only json-format keymaps are supported, which can be exported from [QMK Configurator](https://config.qmk.fm/), converted from `keymap.c` via [`qmk c2json`](https://docs.qmk.fm/#/cli_commands?id=qmk-c2json), or from a VIA backup json via [`qmk via2json`](https://docs.qmk.fm/#/cli_commands?id=qmk-via2json):

  ```sh
  # from keymap.c
  qmk c2json ~/qmk_firmware/keyboards/ferris/keymaps/username/keymap.c | keymap parse -c 10 -q - >sweep_keymap.yaml

  # from VIA backup
  qmk via2json -kb ferris/sweep sweep_via_backup.json | keymap parse -c 10 -q - >sweep_keymap.yaml
  ```

  Due to current limitations of the `keymap.json` format, combos and `#define`'d layer names will not be present in the parsing output.
  However you can manually specify layer names using the layer names parameter, e.g. `keymap parse --layer-names Base Sym Nav ...`.

- **ZMK**: `.keymap` files are used for parsing. These will be preprocessed similar to the ZMK build system, so `#define`'s and `#include`s will be expanded.

  ```sh
  keymap parse -c 10 -z ~/zmk-config/config/cradio.keymap >sweep_keymap.yaml
  ```

  Currently combos, hold-taps, mod-morphs, sticky keys and layer names can be determined via parsing.
  For layer names, the value of the `display-name` property will take precedence over the layer's node name if provided.

As an alternative to parsing, you can also check out the [examples](examples/) to find a layout similar to yours to use as a starting point.

### Tweaking the produced keymap representation

While the parsing step aims to create a decent starting point, you will likely want to make certain tweaks to the produced keymap representation.
Please refer to [the keymap schema specification](KEYMAP_SPEC.md) while making changes:

0. (If starting from a QMK keymap) Add combo definitions using key position indices.
1. Tweak the display form of parsed keys, e.g., replacing `&bootloader` with `BOOT`. (See [the customization section](#customization) to modify parser's behavior.)
2. If you have combos between non-adjacent keys or 3+ key positions, add `align` and/or `offset` properties in order to position them better
3. Add or modify `type` specifiers for certain keys, like `"ghost"` for keys optional to the layout

It might be beneficial to start by `draw`'ing the current representation and iterate over these changes, especially for tweaking combo positioning.

> #### ℹ️ Preserving manual modifications
>
> If you need to re-parse a firmware file after it was changed, you can provide the previous parse output that you tweaked to the
> parse command via `keymap parse -b old_keymap.yaml ... >new_keymap.yaml` and the tool will try to preserve your manual tweaks.

### Producing the SVG

Final step is to produce the SVG representation using the **`keymap draw`** command.
However to do that, we need to specify the _physical_ layout of the keyboard, i.e., how many keys there are, where each key is positioned etc.

If you produced your keymap YAML through `keymap parse`, it will have tried to guess the proper layout in the `layout` field of your keymap.
If you like you can tweak the field value according to the [spec](KEYMAP_SPEC.md#layout), then finally call the draw command:

```sh
keymap draw sweep_keymap.yaml >sweep_keymap.ortho.svg
```

And you are done! You can view the output SVG on your browser or use a tool like [CairoSVG](https://cairosvg.org/) or [Inkscape](https://inkscape.org/) to convert to a different format.

> #### ℹ️ Specifying layouts in the CLI
>
> If you like you can override the layout specification on the command line.
> For instance you can provide a QMK keyboard name with `-k`/`--qmk-keyboard` and layout with `-l`/`--layout-name`,
> or an ortho layout with `--ortho-layout` (using YAML syntax for the value) or `-n`/`--cols-thumbs-notation`.
> See `keymap draw --help` for details.

## Customization

Both parsing and drawing can be customized using a configuration file passed to the `keymap` executable.
This allows you to, for instance, change the default keycode-to-symbol mappings while parsing, or change font sizes, colors etc. while drawing the SVG.

Start by dumping the default configuration settings to a file:

```sh
keymap dump-config >my_config.yaml
```

Then, edit the file to change the settings, referring to [CONFIGURATION.md](CONFIGURATION.md). You can delete from the file the settings you don't want to change.

You can then pass this file to either `draw` and `parse` subcommands with the `-c`/`--config` argument (note the location before the subcommand):

```sh
keymap -c my_config.yaml parse [...] >my_keymap.yaml
keymap -c my_config.yaml draw [...] my_keymap.yaml >my_keymap.svg
```

Since configuration classes are [Pydantic settings](https://docs.pydantic.dev/usage/settings/) they can also be overridden by environment variables with a `KEYMAP_` prefix:

```sh
KEYMAP_raw_binding_map='{"&bootloader": "BOOT"}' keymap parse -z zmk-config/config/cradio.keymap >cradio.yaml
```

Drawing parameters that are specified in the `draw_config` field can also be overridden in [the keymap YAML](KEYMAP_SPEC.md#draw_config).
Using this you can preserve your style customizations along with your keymap in a single file.

## Custom SVG Glyphs

`keymap-drawer` can also use SVG glyphs for legends, in addition to plain or unicode text. The easiest way to do this is
to use the `$$source:id$$` notation [certain `source`s](CONFIGURATION.md#glyph_urls), which will automatically fetch
the SVGs from a given remote `source`, e.g. using `$$mdi:volume-mute$$` will insert the
[mute icon from Material Design Icons](https://pictogrammers.com/library/mdi/icon/volume-mute/).
The following `source` values are currently supported:

- `mdi`: [Pictogrammers Material Design Icons](https://pictogrammers.com/library/mdi/) (use icon name as `id`)
- `mdil`: [Pictogrammers Material Design Icons Light](https://pictogrammers.com/library/mdil/) (use icon name as `id`)
- `material`: [Google Material Symbols](https://fonts.google.com/icons) (use value in "Android" tab as `id`)
- `tabler`: [Tabler Icons](https://tabler.io/icons) ("Outline" style, use icon name as `id`)
- `phosphor`: [Phosphor Icons](https://phosphoricons.com) (use `<weight>/<name>` as `id`, e.g. `$$phosphor:bold/lock$$`)

Fetched SVGs will be [cached by default](CONFIGURATION.md#use_local_cache) to speed up future runs.

The height of the SVG is bound by the config properties `glyph_{tap,hold,shifted}_size` and width will maintain the aspect ratio.
To allow for customization, glyphs are assigned CSS classes `glyph` and `<glyph_name>`.
SVG glyphs currently cannot be used alongside other text in the same legend field.

Instead of automatically fetching them from remote sources, you can also define custom SVG blocks under `draw_config`.
After a glyph is defined this way it can be used in key fields via the glyph name surrounded by `$$`, e.g. `$$vol_up$$`.
The provided SVG must specify a `viewBox`, given that positional or dimensional properties will be calculated by `keymap-drawer`:

```yaml
draw_config:
  # specify the size to bound the vertical dimension of your glyph, below are defaults
  glyph_tap_size: 14
  glyph_hold_size: 12
  glyph_shifted_size: 10
  glyphs: # mapping of glyph name to be used to svg definition
    vol_up: |
      <svg viewBox="2 3 34 33">
        <path style="stroke: black; fill: black;" d="M23.41,25.25a1,1,0,0,1-.54-1.85,6.21,6.21,0,0,0-.19-10.65,1,1,0,1,1,1-1.73,8.21,8.21,0,0,1,.24,14.06A1,1,0,0,1,23.41,25.25Z"/>
        <path style="stroke: black; fill: black;" d="M25.62,31.18a1,1,0,0,1-.45-1.89A12.44,12.44,0,0,0,25,6.89a1,1,0,1,1,.87-1.8,14.44,14.44,0,0,1,.24,26A1,1,0,0,1,25.62,31.18Z"/>
        <path style="stroke: black; fill: black;" d="M18.33,4,9.07,12h-6a1,1,0,0,0-1,1v9.92a1,1,0,0,0,1,1H8.88l9.46,8.24A1,1,0,0,0,20,31.43V4.72A1,1,0,0,0,18.33,4Z"/>
      </svg>
layers:
  Media:
    - ["", "$$vol_up$$", "", "", ""]
```

## Setting up an automated drawing workflow

If you use a [ZMK config repo](https://zmk.dev/docs/user-setup), you can set up an automated workflow that parses and draws your keymaps, then commits the YAML parse outputs and produced SVGs to your repo.
To do that you can add a new workflow to your repo at `.github/workflows/draw-keymaps.yml` that refers to the reusable `keymap-drawer` [workflow](.github/workflows/draw-zmk.yml):

<!-- prettier-ignore -->
```yaml
# Example for using the keymap-drawer ZMK user config workflow
name: Draw ZMK keymaps
on:
  workflow_dispatch:  # can be triggered manually
  push:               # automatically run on changes to following paths
    paths:
      - "config/*.keymap"
      - "config/*.dtsi"
      - "keymap_drawer.config.yaml"
      # - 'boards/*/*/*.keymap'

jobs:
  draw:
    uses: caksoylar/keymap-drawer/.github/workflows/draw-zmk.yml@main
    permissions:
      contents: write  # allow workflow to commit to the repo
    with:
      keymap_patterns: "config/*.keymap"        # path to the keymaps to parse
      config_path: "keymap_drawer.config.yaml"  # config file, ignored if not exists
      output_folder: "keymap-drawer"            # path to save produced SVG and keymap YAML files
      parse_args: ""  # map of extra args to pass to `keymap parse`, e.g. "corne:'-l Def Lwr Rse' cradio:''"
      draw_args: ""   # map of extra args to pass to `keymap draw`, e.g. "corne:'-k corne_rotated' cradio:'-k paroxysm'"
```

### Modifying the workflow-generated commit

The workflow will add the generated SVG and keymap representation YAML files to the `output_folder`, and generate a new commit with commit message "keymap-drawer render" by default. You can modify this commit message with the `commit_message` input param, e.g.:

```yaml
jobs:
  draw:
    uses: caksoylar/keymap-drawer/.github/workflows/draw-zmk.yml@main
    with:
      # Use the triggering commit's message, prepending the "[Draw]" tag
      commit_message: "[Draw] ${{ github.event.head_commit.message }}"
      # …other inputs
```

Alternatively, you can choose to amend the triggering commit instead of generating a new one by using the `amend_commit: true` option. In this case the triggering commit's message will be used by default, and the `commit_message` input will be ignored. E.g.:

```yaml
jobs:
  draw:
    uses: caksoylar/keymap-drawer/.github/workflows/draw-zmk.yml@main
    with:
      amend_commit: true
      # …other inputs
```

> #### ⚠️ Rewriting history
>
> You should understand the implications of rewriting history if you amend a commit that has already been published. See [remarks](https://git-scm.com/docs/git-rebase#_recovering_from_upstream_rebase) in `git-rebase` documentation.

## Community

Below are a few tools and example usages from the community that might be inspirational, whether they are doing unique things with styling, configuration or legends used, or integrate `keymap-drawer` into other workflows.

### Tools

- [YellowAfterlife's Vial To Keymap Drawer](https://yal-tools.github.io/vial-to-keymap-drawer/): Parser to convert Vial .vil files to keymap YAMLs
- [jbarr21's `keymap-display`](https://github.com/jbarr21/keymap-display): Uses a [converter script](https://github.com/jbarr21/keymap-display/blob/main/scripts/json2yaml) to convert QMK `keymap.c` to a keymap YAML
- [hnaderi's fork](https://github.com/hnaderi/keymap-drawer): Contains an example [Dockerfile](https://github.com/hnaderi/keymap-drawer/blob/main/Dockerfile) and publishes unofficial [Docker images](https://github.com/hnaderi/keymap-drawer/blob/main/README.md#using-docker)

### Examples

- [minusfive's ZMK config](https://github.com/minusfive/zmk-config): Uses an [extensive config file](https://github.com/minusfive/zmk-config/blob/main/keymap-drawer/config.yaml) for great results out of the automated drawing workflow, with plenty of SVG glyphs
- [SethMilliken's ZMK config](https://github.com/SethMilliken/zmk-config): Another config using the automated workflow with a [nice configuration](https://github.com/SethMilliken/zmk-config/blob/main/keymap_drawer.config.yaml) and SVG glyphs
- [englmaxi's ZMK config](https://github.com/englmaxi/zmk-config): Using key sides setting and CSS tricks to position multiple SVG glyphs in one key
- [casuanoob's keymap](https://github.com/casuanoob/zmk-config-bkb): Many useful unicode and SVG glyphs in the [keymap YAML](https://github.com/casuanoob/zmk-config-bkb/blob/master/assets/split34_keymap_zmk.yaml)
- [rafaelromao's keymap](https://github.com/rafaelromao/keyboards#diagram): Advanced keymap with many glyphs and a Inkscape-based PNG conversion command
- [possumvibes's keymap](https://github.com/possumvibes/keyboard-layout): Separate layer and combo diagrams
- [infused-kim's ZMK config](https://github.com/infused-kim/zmk-config): Defines a script to [tweak the keymap](https://github.com/infused-kim/zmk-config/blob/main/keymap_img/keymap_img_adjuster.py) between parsing and drawing
- [crides's Fissure write-up](https://github.com/crides/fissure): Custom physical layout with non-square keys and unique SVG styling

If you use `keymap-drawer`, tag your Github repo with the [`keymap-drawer` topic](https://github.com/topics/keymap-drawer) and it will show up for anyone else searching for it!

## Development

This project requires Python 3.10+ and uses [Poetry](https://python-poetry.org/) for packaging.

To get started, [install Poetry](https://python-poetry.org/docs/#installation), clone this repo, then install dependencies with the `poetry` command:

```sh
git clone https://github.com/caksoylar/keymap-drawer.git
cd keymap-drawer
poetry install  # -E dev -E lsp (optional dependencies)
```

Activate a virtual environment with the `keymap_drawer` module in Python path and `keymap` executable available by running the output of `poetry env activate`.
Changes you make in the source code will be reflected when using the module or the command.

If you prefer not to use Poetry, you can get an editable install with `pip install --editable .` inside the `keymap-drawer` folder.

The source code for the Streamlit app lives in the [`keymap-drawer-web`](https://github.com/caksoylar/keymap-drawer-web) repo.

## Questions? Feedback?

If you have any questions on usage or feedback for new or existing features, please check out the [Discussions tab](https://github.com/caksoylar/keymap-drawer/discussions) and feel free to create a new one!

## Related projects

- [@nickcoutsos's ZMK keymap editor](https://github.com/nickcoutsos/keymap-editor)
- [The original `keymap`](https://github.com/callum-oakley/keymap/)
- [@jbarr21's keymap parser](https://github.com/jbarr21/keymap-display)
- [@leiserfg's ZMK parser](https://github.com/leiserfg/zmk-config/tree/master/parser)
- [Keymapviz](https://github.com/yskoht/keymapviz)
