"""
Module containing configuration related to styling of produced SVG and other drawing options,
keycode converters for parsing.
"""

from textwrap import dedent
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class DrawConfig(BaseSettings, env_prefix="KEYMAP_", extra="ignore"):
    """Configuration related to SVG drawing, including key sizes, padding amounts, combo drawing settings etc."""

    class KeySidePars(BaseModel):
        """Parameters of key side drawing for `draw_key_sides` config."""

        # position of internal key rectangle relative to the center of the key
        rel_x: float = 0
        rel_y: float = 4
        # delta dimension between external key rectangle and internal key rectangle
        rel_w: float = 12
        rel_h: float = 12
        # curvature of rounded internal key rectangle
        rx: float = 4
        ry: float = 4

    # key dimensions, non-ortho layouts use key_h for width as well
    key_w: float = 60
    key_h: float = 56

    # gap between two halves for ortho layout generator
    split_gap: float = key_w / 2

    # combo box dimensions
    combo_w: float = key_w / 2 - 2
    combo_h: float = key_h / 2 - 2

    # curvature of rounded key rectangles
    key_rx: float = 6
    key_ry: float = 6

    # turn on dark mode which applies svg_style_dark overrides
    # "auto" enables adapting to the web page or OS light/dark theme setting
    dark_mode: bool | Literal["auto"] = False

    # number of columns in the output drawing
    n_columns: int = 1

    # draw separate combo diagrams instead of drawing them on layers. `draw_separate` field in
    # the combo spec overrides this if it is explicitly set to true or false
    separate_combo_diagrams: bool = False

    # if drawing separate combo diagrams, shrink physical layout by this factor
    combo_diagrams_scale: int = 2

    # padding between keys
    inner_pad_w: float = 2
    inner_pad_h: float = 2

    # padding between layers
    outer_pad_w: float = key_w / 2
    outer_pad_h: float = key_h

    # spacing between multi-line text in key labels in units of em
    line_spacing: float = 1.2

    # curve radius for combo dendrons
    arc_radius: float = 6

    # whether to add a colon after layer name while printing the layer header
    append_colon_to_layer_header: bool = True

    # padding from edge of cap to top and bottom legends
    small_pad: float = 2.0

    # position of center ("tap") key legend relative to the center of the key
    legend_rel_x: float = 0
    legend_rel_y: float = 0

    # draw key sides
    draw_key_sides: bool = False

    # key side parameters
    key_side_pars: KeySidePars = KeySidePars()

    # style CSS to be output in the SVG
    # if you do not need to remove existing definitions, consider using svg_extra_style instead
    svg_style: str = Field(
        exclude=True,
        default=dedent(
            """\
            /* inherit to force styles through use tags */
            svg path {
                fill: inherit;
            }

            /* font and background color specifications */
            svg.keymap {
                font-family: SFMono-Regular,Consolas,Liberation Mono,Menlo,monospace;
                font-size: 14px;
                font-kerning: normal;
                text-rendering: optimizeLegibility;
                fill: #24292e;
            }

            /* default key styling */
            rect.key {
                fill: #f6f8fa;
            }

            rect.key, rect.combo {
                stroke: #c9cccf;
                stroke-width: 1;
            }

            /* default key side styling, only used is draw_key_sides is set */
            rect.side {
                filter: brightness(90%);
            }

            /* color accent for combo boxes */
            rect.combo, rect.combo-separate {
                fill: #cdf;
            }

            /* color accent for held keys */
            rect.held, rect.combo.held {
                fill: #fdd;
            }

            /* color accent for ghost (optional) keys */
            rect.ghost, rect.combo.ghost {
                stroke-dasharray: 4, 4;
                stroke-width: 2;
            }

            text {
                text-anchor: middle;
                dominant-baseline: middle;
            }

            /* styling for layer labels */
            text.label {
                font-weight: bold;
                text-anchor: start;
                stroke: white;
                stroke-width: 4;
                paint-order: stroke;
            }

            /* styling for optional footer */
            text.footer {
                text-anchor: end;
                dominant-baseline: auto;
                stroke: white;
                stroke-width: 4;
                paint-order: stroke;
            }

            /* styling for combo tap, and key non-tap label text */
            text.combo, text.hold, text.shifted, text.left, text.right {
                font-size: 11px;
            }

            text.hold {
                text-anchor: middle;
                dominant-baseline: auto;
            }

            text.shifted {
                text-anchor: middle;
                dominant-baseline: hanging;
            }

            text.left {
                text-anchor: start;
            }

            text.right {
                text-anchor: end;
            }

            text.layer-activator {
                text-decoration: underline;
            }

            /* styling for hold/shifted label text in combo box */
            text.combo.hold, text.combo.shifted, text.combo.left, text.combo.right {
                font-size: 8px;
            }

            /* lighter symbol for transparent keys */
            text.trans {
                fill: #7b7e81;
            }

            /* styling for combo dendrons */
            path.combo {
                stroke-width: 1;
                stroke: gray;
                fill: none;
            }

            /* Start Tabler Icons Cleanup */
            /* cannot use height/width with glyphs */
            .icon-tabler > path {
                fill: inherit;
                stroke: inherit;
                stroke-width: 2;
            }
            /* hide tabler's default box */
            .icon-tabler > path[stroke="none"][fill="none"] {
                visibility: hidden;
            }
            /* End Tabler Icons Cleanup */
            """
        ),
    )

    # style CSS to override colors for dark mode
    svg_style_dark: str = Field(
        exclude=True,
        default=dedent(
            """\
            svg.keymap { fill: #d1d6db; }
            rect.key { fill: #3f4750; }
            rect.key, rect.combo { stroke: #60666c; }
            rect.combo, rect.combo-separate { fill: #1f3d7a; }
            rect.held, rect.combo.held { fill: #854747; }
            text.label, text.footer { stroke: black; }
            text.trans { fill: #7e8184; }
            path.combo { stroke: #7f7f7f; }
            """
        ),
    )

    # extra CSS to be appended to svg_style
    # prefer to set this over modifying svg_style since the default value of svg_style can change
    svg_extra_style: str = ""

    # footer text to be added to the bottom of the drawing, aligned right
    footer_text: str = ""

    # shrink font size for legends wider than this many chars, set to 0 to disable
    # ideal value depends on the font size defined in svg_style and width of the boxes
    shrink_wide_legends: int = 7

    # add special styling and hyperlinks for layer activator keys
    # change styling via `layer-activators` CSS class
    style_layer_activators: bool = True

    # height in pixels for glyphs in different key fields
    glyph_tap_size: int = 14
    glyph_hold_size: int = 12
    glyph_shifted_size: int = 10

    # mapping of glyph names to be used in key fields to their SVG definitions
    glyphs: dict[str, str] = {}

    # mapping of sources to (possibly templated) URLs for fetching SVG glyphs
    # e.g. `$$material:settings$$` will use the value for `material` and replace `{}` with `settings`
    glyph_urls: dict[str, str] = Field(
        exclude=True,
        default={
            "tabler": "https://unpkg.com/@tabler/icons/icons/outline/{}.svg",
            "mdi": "https://raw.githubusercontent.com/Templarian/MaterialDesign-SVG/master/svg/{}.svg",
            "mdil": "https://raw.githubusercontent.com/Pictogrammers/MaterialDesignLight/master/svg/{}.svg",
            "material": "https://fonts.gstatic.com/s/i/short-term/release/materialsymbolsoutlined/{}/default/48px.svg",
            "phosphor": "https://unpkg.com/@phosphor-icons/core/assets/{}.svg",
            "fa": "https://unpkg.com/@fortawesome/fontawesome-free/svgs/{}.svg",
        },
    )

    # use a local filesystem cache on an OS-specific location for downloaded QMK keyboard jsons and SVG glyphs
    use_local_cache: bool = Field(exclude=True, default=True)


class ParseConfig(BaseSettings, env_prefix="KEYMAP_", extra="ignore"):
    """Configuration settings related to parsing QMK/ZMK keymaps."""

    class ModifierFnMap(BaseModel):
        """
        Mapping to replace modifiers in modifier functions with the given string. Includes `combiner`
        patterns to determine how to format the result. Mod combinations in `mod_combinations` take
        precedence over individual mod lookups.
        """

        left_ctrl: str = "Ctl"
        right_ctrl: str = "Ctl"
        left_shift: str = "Sft"
        right_shift: str = "Sft"
        left_alt: str = "Alt"  # Alt/Opt
        right_alt: str = "AltGr"  # Alt/Opt/AltGr
        left_gui: str = "Gui"  # Cmd/Win
        right_gui: str = "Gui"  # Cmd/Win
        keycode_combiner: str = "{mods}+{key}"  # pattern to join modifier functions with the modified keycode
        mod_combiner: str = "{mod_1}+{mod_2}"  # pattern to join multiple modifier function strings
        special_combinations: dict[str, str] = {  # special look-up for combinations of mods (mod order is ignored)
            "left_ctrl+left_alt+left_gui+left_shift": "Hyper",
            "left_ctrl+left_alt+left_shift": "Meh",
        }

    # run C preprocessor on ZMK keymaps
    preprocess: bool = True

    # do not do any keycode/binding parsing (except as specified by "raw_binding_map")
    skip_binding_parsing: bool = False

    # map raw keycode/binding strings as specified and shortcut any further key parsing
    # e.g. {"QK_BOOT": "BOOT", "&bootloader": "BOOT"}
    raw_binding_map: dict[str, str | dict] = {}

    # display text to place in hold field for sticky/one-shot keys
    sticky_label: str = "sticky"

    # display text to place in hold field for toggled keys
    toggle_label: str = "toggle"

    # display text to place in hold field for toggled keys
    tap_toggle_label: str = "tap-toggle"

    # legend to output for transparent keys
    trans_legend: str | dict = {"t": "▽", "type": "trans"}

    # override layer names displayed on keys to specified legends
    layer_legend_map: dict[str, str] = {}

    # rather than only marking the first sequence of key positions to reach a layer as "held",
    # mark all of the sequences to reach a given layer. this is disabled by default because it
    # creates ambiguity: you cannot tell if *all* the marked keys need to be held down while a
    # layer is active (which is the default behavior) or *any* of them (with this option)
    mark_alternate_layer_activators: bool = False

    # convert modifiers in modifier functions (used in keycodes with built-in modifiers like LC(V)
    # in ZMK or LCTL(KC_V) in QMK) to given symbols -- set to None/null to disable the mapping
    modifier_fn_map: ModifierFnMap | None = ModifierFnMap()

    # remove these prefixes from QMK keycodes before further processing
    # can be augmented with other locale prefixes, e.g. "DE_"
    qmk_remove_keycode_prefix: list[str] = ["KC_"]

    # convert QMK keycodes to their display forms, after removing prefixes in `qmk_remove_keycode_prefix`
    qmk_keycode_map: dict[str, str | dict] = {
        # QMK keycodes
        "XXXXXXX": "",
        "NO": "",
        "MINUS": "-",
        "MINS": "-",
        "EQUAL": "=",
        "EQL": "=",
        "LEFT_BRACKET": "[",
        "LBRC": "[",
        "RIGHT_BRACKET": "]",
        "RBRC": "]",
        "BACKSLASH": "\\",
        "BSLS": "\\",
        "NONUS_HASH": "#",
        "NUHS": "#",
        "SEMICOLON": ";",
        "SCLN": ";",
        "QUOTE": "'",
        "QUOT": "'",
        "GRAVE": "`",
        "GRV": "`",
        "COMMA": ",",
        "COMM": ",",
        "DOT": ".",
        "SLASH": "/",
        "SLSH": "/",
        "TILDE": "~",
        "TILD": "~",
        "EXCLAIM": "!",
        "EXLM": "!",
        "AT": "@",
        "HASH": "#",
        "DOLLAR": "$",
        "DLR": "$",
        "PERCENT": "%",
        "PERC": "%",
        "CIRCUMFLEX": "^",
        "CIRC": "^",
        "AMPERSAND": "&",
        "AMPR": "&",
        "ASTERISK": "*",
        "ASTR": "*",
        "LEFT_PAREN": "(",
        "LPRN": "(",
        "RIGHT_PAREN": ")",
        "RPRN": ")",
        "UNDERSCORE": "_",
        "UNDS": "_",
        "PLUS": "+",
        "LEFT_CURLY_BRACE": "{",
        "LCBR": "{",
        "RIGHT_CURLY_BRACE": "}",
        "RCBR": "}",
        "PIPE": "|",
        "COLON": ":",
        "COLN": ":",
        "DOUBLE_QUOTE": '"',
        "DQUO": '"',
        "DQT": '"',
        "LEFT_ANGLE_BRACKET": "<",
        "LABK": "<",
        "LT": "<",
        "RIGHT_ANGLE_BRACKET": ">",
        "RABK": ">",
        "GT": ">",
        "QUESTION": "?",
        "QUES": "?",
    }

    # remove these prefixes from ZMK keycodes before further processing
    # can be augmented with locale prefixes for zmk-locale-generator headers, e.g. "DE_"
    zmk_remove_keycode_prefix: list[str] = []

    # convert ZMK keycodes to their display forms, applied to parameters of behaviors like "&kp"
    zmk_keycode_map: dict[str, str | dict] = {
        "EXCLAMATION": "!",
        "EXCL": "!",
        "AT_SIGN": "@",
        "AT": "@",
        "HASH": "#",
        "POUND": "#",
        "DOLLAR": "$",
        "DLLR": "$",
        "PERCENT": "%",
        "PRCNT": "%",
        "CARET": "^",
        "AMPERSAND": "&",
        "AMPS": "&",
        "ASTERISK": "*",
        "ASTRK": "*",
        "STAR": "*",
        "LEFT_PARENTHESIS": "(",
        "LPAR": "(",
        "RIGHT_PARENTHESIS": ")",
        "RPAR": ")",
        "EQUAL": "=",
        "PLUS": "+",
        "MINUS": "-",
        "UNDERSCORE": "_",
        "UNDER": "_",
        "SLASH": "/",
        "FSLH": "/",
        "QUESTION": "?",
        "QMARK": "?",
        "BACKSLASH": "\\",
        "BSLH": "\\",
        "PIPE": "|",
        "NON_US_BACKSLASH": "\\",
        "PIPE2": "|",
        "NON_US_BSLH": "|",
        "SEMICOLON": ";",
        "SEMI": ";",
        "COLON": ":",
        "SINGLE_QUOTE": "'",
        "SQT": "'",
        "APOSTROPHE": "'",
        "APOS": "'",
        "DOUBLE_QUOTES": '"',
        "DQT": '"',
        "COMMA": ",",
        "LESS_THAN": "<",
        "LT": "<",
        "PERIOD": ".",
        "DOT": ".",
        "GREATER_THAN": ">",
        "GT": ">",
        "LEFT_BRACKET": "[",
        "LBKT": "[",
        "LEFT_BRACE": "{",
        "LBRC": "{",
        "RIGHT_BRACKET": "]",
        "RBKT": "]",
        "RIGHT_BRACE": "}",
        "RBRC": "}",
        "GRAVE": "`",
        "TILDE": "~",
        "NON_US_HASH": "#",
        "NUHS": "#",
        "TILDE2": "~",
    }

    # additional combo fields for a given combo node name in the keymap,
    # e.g. {"combo_esc": {"align": "top", "offset": 0.5}}
    zmk_combos: dict[str, dict] = {}

    # prepend this to ZMK keymaps before processing to customize parsing output
    zmk_preamble: str = "#define KEYMAP_DRAWER"

    # additional zmk include paths to be added to the preprocessor
    zmk_additional_includes: list[str] = []


class Config(BaseSettings, env_prefix="KEYMAP_"):
    """All configuration settings used for this module."""

    draw_config: DrawConfig = DrawConfig()
    parse_config: ParseConfig = ParseConfig()
