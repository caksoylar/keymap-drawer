# Configuration options

This page details the configuration options available for parsing and drawing, which can be provided to the CLI or can be set in the web UI in the "Configuration" box.
Also see the [customization section](README.md#configuration) in the README for usage.

## Draw Configuration

These settings are nested under the `draw_config` field and applies to `keymap draw` subcommand in the CLI, as well as the conversion from keymap YAML input to SVG in the web app.
In addition to the configuration file, this field can also be set in the [keymap YAML](KEYMAP_SPEC.md#draw_config) which overrides the former.

#### `key_w`, `key_h`

Key dimensions. Non-ortho layouts (e.g. via `qmk_keyboard`) use `key_h` for both width and height, whereas `ortho_layout` and `cols_thumbs_notation` use both.

_Type:_ `float`

_Default:_ `60`, `56`

#### `split_gap`

The gap between two halves of a split keyboard, only used for physical layouts specified via `ortho_layout` and `cols_thumbs_notation`.

_Type:_ `float`

_Default:_ `30`

#### `combo_w`, `combo_h`

Dimensions of combo boxes that are drawn on layer diagrams.

_Type:_ `float`

_Default:_ `28`, `26`

#### `key_rx`, `key_ry`

Curvature of rounded key rectangles, used both for key and combo boxes

_Type:_ `float`

_Default:_ `6`

#### `dark_mode`

Turn on dark mode which applies the CSS overrides in `svg_style_dark` config.
Setting it to `"auto"` enables adapting to the web page or OS light/dark theme setting.

_Type:_ `bool | "auto"`

_Default:_ `false`

#### `n_columns`

Number of layer columns in the output drawing.
For example if this is set to 2, two layers will be shown side-by-side and layers will go right then down.

_Type:_ `int`

_Default:_ `1`

#### `separate_combo_diagrams`

When set, visualize combos using separate mini-layout diagrams rather than drawing them on layers.
This sets the default behavior, which can be overridden by the `draw_separate` field of the [`ComboSpec`](KEYMAP_SPEC.md#combos).

_Type:_ `bool`

_Default:_ `false`

#### `combo_diagrams_scale`

For combos visualized separate from layers, this is the scale factor for the mini-layout used to show their key positions.

_Type:_ `int`

_Default:_ `2`

#### `inner_pad_w`, `inner_pad_h`

The amount of padding between adjacent keys, in two axes.

_Type:_ `float`

_Default:_ `2`, `2`

#### `outer_pad_w`, `outer_pad_h`

Padding amount between layer diagrams, in two axes.

_Type:_ `float`

_Default:_ `30`, `56`

#### `line_spacing`

Spacing between multi-line text in key labels in units of `em`.

_Type:_ `float`

_Default:_ `1.2`

#### `arc_radius`

Radius of the curve for combo dendrons that are drawn from the combo box to the key positions.

_Type:_ `float`

_Default:_ `6`

#### `append_colon_to_layer_header`

Whether to add a colon after layer name while printing the layer header.

_Type:_ `bool`

_Default:_ `true`

#### `small_pad`

Padding from edge of a key representation to top ("shifted"), bottom ("hold"), "left" and "right" legends.

_Type:_ `float`

_Default:_ `2`

#### `legend_rel_x`, `legend_rel_y`

Position of center ("tap") and "left"/"right" key legends relative to the center of the key.
Can be useful to tweak when `draw_key_sides` is used.

_Type:_ `float`

_Default:_ `0`, `0`

#### `draw_key_sides`

Draw "key sides" on key representations, which can be made to look like keycap profiles.
The shape is determined by `key_side_pars`.

_Type:_ `bool`

_Default:_ `false`

#### `key_side_pars`

A mapping of certain field names to their values, characterizing key side drawing. Valid fields:

- **`rel_x`**, **`rel_y`** (type: `float`): Position of internal key rectangle relative to the center of the key. _Default:_ `0`, `4`
- **`rel_w`**, **`rel_y`** (type: `float`): Delta dimension between external key rectangle and internal key rectangle. _Default:_ `12`, `12`
- **`rx`**, **`ry`** (type: `float`): Curvature of the rounded internal key rectangle. _Default:_ `4`, `4`

#### `svg_style`[^1]

[^1]: Excluded from `keymap dump-config` by default, can be modified by manually adding it to the config file.

The CSS used for the SVG styling. This includes font settings, styling of key and combo rectangles and texts within them, along with some tweaks for external SVG glyphs.
Users are encouraged to not change the default value and use `svg_extra_style` to specify overrides instead.

_Type:_ `string`

_Default:_ See [`config.py`](keymap_drawer/config.py)

#### `svg_style_dark`[^1]

The set of CSS overrides that are added when `dark_mode` is enabled, and conditionally added with `@media (prefers-color-scheme: dark)` when it is `"auto"`.

_Type:_ `string`

_Default:_ See [`config.py`](keymap_drawer/config.py)

#### `svg_extra_style`

Extra CSS that will be appended to `svg_style`, enabling augmenting and overriding properties.

_Type:_ `string`

_Default:_ Empty

#### `footer_text`

Footer text that will be displayed at the bottom of the drawing, right aligned.
The value will be placed inside `<text>` tags and can have certain SVG elements in it.

_Type:_ `string`

_Default:_ Empty

#### `shrink_wide_legends`

Shrink font size for legends wider than this many chars, set to 0 to disable.
Ideal value depends on the font size defined in `svg_style`/`svg_extra_style` and width of the boxes.

_Type:_ `int`

_Default:_ `7`

#### `style_layer_activators`

Detect layer names in legends and style them specially: By default they are underlined and
link to the corresponding layer. Styling can be customized using the `layer-activator` CSS class.

_Type:_ `bool`

_Default:_ `true`

#### `glyph_tap_size`, `glyph_hold_size`, `glyph_shifted_size`

Height in `px` for SVG glyphs, in different key fields.

_Type:_ `int`

_Default:_ `14`, `12`, `10`

#### `glyphs`

Mapping of glyph names to be used in key fields to their SVG definitions.

_Type:_ `dict[str, str]`

_Default:_ Empty

#### `glyph_urls`[^1]

Mapping of sources to (possibly templated) URLs for fetching SVG glyphs.
For instance, `$$material:settings$$` will use the value for `material` and replace `{}` in the value with `settings`.

_Type:_ `dict[str, str]`

_Default:_ See [`config.py`](keymap_drawer/config.py)

#### `use_local_cache`[^1]

Use a local filesystem cache on an OS-specific location for downloaded QMK keyboard jsons and SVG glyphs.

_Type:_ `bool`

_Default:_ `true`

## Parse configuration

These settings are nested under the `parse_config` field and applies to `keymap parse` subcommand in the CLI, as well as the conversion from "Parse from..." input forms to the keymap YAML text area in the web app.

#### `preprocess`

Run C preprocessor on ZMK keymaps.

_Type:_ `bool`

_Default:_ `true`

#### `skip_binding_parsing`

Do not do any keycode/binding parsing (except as specified by `raw_binding_map`).

_Type:_ `bool`

_Default:_ `false`

#### `raw_binding_map`

Convert raw keycode/binding strings specified as keys to the representations given by their values.[^2]

[^2]: The value can be a [`LayoutKey` mapping](KEYMAP_SPEC.md#layers) or a string representing the tap legend.

If a conversion was made, shortcut any further processing.
E.g. `{"QK_BOOT": "BOOT", "&bootloader": "BOOT"}`.

_Type:_ `dict[str, str | dict]`

_Default:_ `{}`

#### `sticky_label`

Display text to place in hold field for sticky/one-shot keys.

_Type:_ `str`

_Default:_ `"sticky"`

#### `toggle_label`

Display text to place in hold field for toggled keys.

_Type:_ `str`

_Default:_ `"toggle"`

#### `tap_toggle_label`

Display text to place in hold field for tap-toggle (TT) keys.

_Type:_ `str`

_Default:_ `"tap-toggle"`

#### `trans_legend`

Legend to output for transparent keys.[^2]

_Type:_ `str | dict`

_Default:_ `{"t": "▽", "type": "trans"}`

#### `layer_legend_map`

For layer names specified, replace their representation on keys with the specified string.
The layer names should match the form that they would normally be displayed as, i.e. the
provided names if `keymap parse --layer-names` is used, otherwise the layer names inferred during parsing.

_Type:_ `dict[str, str]`

_Default:_ `{}`

#### `mark_alternate_layer_activators`

Rather than only marking the first sequence of key positions to reach a layer as "held",
mark all of the sequences to reach a given layer. This is disabled by default because it
creates ambiguity: you cannot tell if _all_ the marked keys need to be held down while a
layer is active (which is the default behavior) or _any_ of them (with this option).

The additional keys that are added by enabling this option get the key type "held alternate",
so that you can override their styling in `svg_extra_style` with CSS selector `.held.alternate`.

_Type:_ `bool`

_Default:_ `false`

#### `modifier_fn_map`

Convert modifiers in modifier functions (used in keycodes with built-in modifiers like `LC(V)`
in ZMK or `LCTL(KC_V)` in QMK) to given symbols -- set to `null` to disable the mapping. Valid fields:

- **`left_ctrl`**, **`right_ctrl`**, **`left_shift`**, **`right_shift`**, **`left_alt`**, **`right_alt`**, **`left_gui`**, **`right_gui`** (type: `str`):
  Mapping of each modifier to their corresponding display forms.

  _Default:_ `"Ctl"`, `"Ctl"`, `"Sft"`, `"Sft"`, `"Alt"`, `"AltGr"`, `"Gui"`, `"Gui"`

- **`keycode_combiner`** (type: `str`): Pattern to join modifier functions with the modified keycode, must contain `{mods}` and `{key}`.

  _Default:_ `"{mods}+{key}"`

- **`mod_combiner`** (type: `str`): Pattern to join multiple modifier function strings, must contain `{mod_1}` and `{mod_2}`.

  _Default:_ `"{mod_1}+{mod_2}"`

- **`special_combinations`** (type: `dict[str, str]`): Special look-up for combinations of mods, mod order is ignored. Keys must be modifier names joined by `+`.

  _Default:_ `{"left_ctrl+left_alt+left_gui+left_shift": "Hyper", "left_ctrl+left_alt+left_shift": "Meh"}`

#### `qmk_remove_keycode_prefix`

Remove these prefixes from QMK keycodes before further processing.
Can be augmented with other locale prefixes, e.g. `"DE_"` for German locale headers.

_Type:_ `list[str]`

_Default:_ `["KC_"]`

#### `qmk_keycode_map`

Mapping to convert QMK keycodes to their display forms, applied after removing prefixes in `qmk_remove_keycode_prefix`.[^2]

_Type:_ `dict[str, str | dict]`

_Default:_ See [`config.py`](keymap_drawer/config.py)

#### `zmk_remove_keycode_prefix`

Remove these prefixes from ZMK keycodes before further processing.
Can be augmented with other locale prefixes, e.g. `"DE_"` for German locale headers generated by `zmk-locale-generator`.

_Type:_ `list[str]`

_Default:_ `[]`

#### `zmk_keycode_map`

Mapping to convert ZMK keycodes to their display forms, applied after removing prefixes in `zmk_remove_keycode_prefix`.[^2]

_Type:_ `dict[str, str | dict]`

_Default:_ See [`config.py`](keymap_drawer/config.py)

#### `zmk_combos`

Mapping to augment the output field for parsed combos. The key names are the devicetree node names for
combos in the keymap and the value is a dict containing fields from the [`ComboSpec`](KEYMAP_SPEC.md#combos).

E.g. `{"combo_esc": {"align": "top", "offset": 0.5}}` would add these two fields to the output for combo that has node name `combo_esc`.

_Type:_ `dict[str, dict]`

_Default:_ `{}`

#### `zmk_preamble`

A string to prepend to ZMK keymaps before parsing that can be used to influence the parsed content.
Also used for parsing DTS format physical layouts specified with `--dts-layout`.
The default defines a `KEYMAP_DRAWER` symbol which can be used for checks with preprocessor directives.

_Type:_ `string`

_Default:_ `"#define KEYMAP_DRAWER"`

#### `zmk_additional_includes`

A list of paths to add as search paths to the preprocessor for `#include` directives.
This can be needed if you use Zephyr modules such as [`zmk-helpers`](https://github.com/urob/zmk-helpers/blob/main/docs/keymap_drawer.md) since they require augmenting the search path.
Also used when parsing DTS format physical layouts specified with `--dts-layout`.

_Type:_ `list[str]`

_Default:_ `[]`
