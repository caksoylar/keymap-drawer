"""
Module containing configuration related to styling of produced SVG and other drawing options,
keycode converters for parsing.
"""

from textwrap import dedent
from pydantic import BaseSettings


class DrawConfig(BaseSettings, env_prefix="KEYMAP_", extra="ignore"):
    """Configuration related to SVG drawing, including key sizes, padding amounts, combo drawing settings etc."""

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

    # length multiplier for dendrons
    arc_scale: float = 1.0

    # whether to add a colon after layer name while printing the layer header
    append_colon_to_layer_header: bool = True

    # padding from edge of cap to top and bottom legends
    small_pad: float = 2.0

    svg_style: str = dedent(
        """\
        /* inherit to force styles through use tags*/
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
            stroke: #c9cccf;
            stroke-width: 1;
        }

        /* color accent for combo boxes */
        rect.combo {
            fill: #cdf;
        }

        /* color accent for held keys */
        rect.held, rect.combo.held {
            fill: #fdd;
        }

        /* color accent for ghost (optional) keys */
        rect.ghost, rect.combo.ghost {
            fill: #ddd;
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
            stroke-width: 2;
            paint-order: stroke;
        }

        /* styling for combo tap, and key hold/shifted label text */
        text.combo, text.hold, text.shifted {
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

        /* styling for hold/shifted label text in combo box */
        text.combo.hold, text.combo.shifted {
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
        }
        /* hide tabler's default box */
        .icon-tabler > path[stroke="none"][fill="none"] {
            visibility: collapse;
        }
        /* End Tabler Icons Cleanup */
        """
    )

    # shrink font size for legends wider than this many chars, set to 0 to disable
    # ideal value depends on the font size defined in svg_style and width of the boxes
    shrink_wide_legends: int = 7

    # height in pixels for glyphs in different key fields
    glyph_tap_size: int = 14
    glyph_hold_size: int = 12
    glyph_shifted_size: int = 10

    # mapping of glyph names to be used in key fields to their SVG definitions
    glyphs: dict[str, str] = {}

    # mapping of sources to (possibly templated) URLs for fetching SVG glyphs
    # e.g. `$$material:settings$$` will use the value for `material` and replace `{}` with `settings`
    glyph_urls: dict[str, str] = {
        "tabler": "https://tabler-icons.io/static/tabler-icons/icons/{}.svg",
        "mdi": "https://raw.githubusercontent.com/Templarian/MaterialDesign-SVG/master/svg/{}.svg",
        "mdil": "https://raw.githubusercontent.com/Pictogrammers/MaterialDesignLight/master/svg/{}.svg",
        "material": "https://fonts.gstatic.com/s/i/short-term/release/materialsymbolsoutlined/{}/default/48px.svg",
    }

    # use a local filesystem cache on an OS-specific location for downloaded QMK keyboard jsons and SVG glyphs
    use_local_cache: bool = True


class ParseConfig(BaseSettings, env_prefix="KEYMAP_", extra="ignore"):
    """Configuration settings related to parsing QMK/ZMK keymaps."""

    # run C preprocessor on ZMK keymaps
    preprocess: bool = True

    # do not do any keycode/binding parsing (except as specified by "raw_binding_map")
    skip_binding_parsing: bool = False

    # map raw keycode/binding strings as specified and shortcut any further key parsing
    # e.g. {"QK_BOOT": "BOOT", "&bootloader": "BOOT"}
    raw_binding_map: dict[str, str | dict] = {}

    # display text to place in hold field for sticky/one-shot keys
    sticky_label: str = "sticky"

    trans_legend: str | dict = {"t": "▽", "type": "trans"}

    # convert QMK keycodes to their display forms, omitting "KC_" prefix on the keys
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
        "APOSTROPHE": "<",
        "APOS": ".",
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


class Config(BaseSettings, env_prefix="KEYMAP_"):
    """All configuration settings used for this module."""

    draw_config: DrawConfig = DrawConfig()
    parse_config: ParseConfig = ParseConfig()
