"""
Module containing configuration related to styling of produced SVG and other drawing options,
keycode converters for parsing.
"""

from textwrap import dedent
from pydantic import BaseSettings


class DrawConfig(BaseSettings):
    """Configuration related to SVG drawing, including key sizes, padding amounts, combo drawing settings etc."""

    class Config:  # pylint: disable=missing-class-docstring
        env_prefix = "KEYMAP_"

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

    # spacing between multi-line text in key labels
    line_spacing: float = 18

    # curve radius for combo dendrons
    arc_radius: float = 6

    # length multiplier for dendrons
    arc_scale: float = 1.0

    svg_style: str = dedent(
        """\
        /* font and background color specifications */
        svg {
            font-family: SFMono-Regular,Consolas,Liberation Mono,Menlo,monospace;
            font-size: 14px;
            font-kerning: normal;
            text-rendering: optimizeLegibility;
            fill: #24292e;
        }

        /* default key styling */
        rect {
            fill: #f6f8fa;
            stroke: #d6d8da;
            stroke-width: 1;
        }

        /* color accent for held keys */
        .held {
            fill: #fdd;
        }

        /* color accent for combo boxes */
        .combo {
            fill: #cdf;
        }

        /* color accent for ghost (optional) keys */
        .ghost {
            fill: #ddd;
        }

        text {
            text-anchor: middle;
            dominant-baseline: middle;
        }

        /* styling for layer labels */
        .label {
            font-weight: bold;
            text-anchor: start;
            stroke: white;
            stroke-width: 2;
            paint-order: stroke;
        }

        /* styling for combo box and hold-tap hold label text */
        .small {
            font-size: 11px;
        }

        /* styling for hold-tap hold label text in combo box */
        .smaller {
            font-size: 8px;
        }

        /* styling for combo dendrons */
        path {
            stroke-width: 1;
            stroke: gray;
            fill: none;
        }
    """
    )


class ParseConfig(BaseSettings):
    """Configuration settings related to parsing QMK/ZMK keymaps."""

    class Config:  # pylint: disable=missing-class-docstring
        env_prefix = "KEYMAP_"

    # run C preprocessor on ZMK keymaps
    preprocess: bool = True

    # instead of a root "combos" node in output with "layers" property on each combo,
    # assign combos to a "combos" node under each layer and remove the "layers" property
    # useful if you e.g. have single layer combos on different layers
    assign_combos_to_layers: bool = False

    # do not do any keycode/binding parsing (except as specified by "raw_binding_map")
    skip_binding_parsing: bool = False

    # map raw keycode/binding strings as specified and shortcut any further key parsing
    # e.g. {"QK_BOOT": "BOOT", "&bootloader": "BOOT"}
    raw_binding_map: dict[str, str | dict] = {}

    # convert QMK keycodes to their display forms, omitting "KC_" prefix on the keys
    qmk_keycode_map: dict[str, str] = {
        # QMK keycodes
        "XXXXXXX": "",
        "TRANSPARENT": "",
        "TRNS": "",
        "_______": "",
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
    zmk_keycode_map: dict[str, str] = {
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


class Config(BaseSettings):
    """All configuration settings used for this module."""

    class Config:  # pylint: disable=missing-class-docstring
        env_prefix = "KEYMAP_"

    draw_config: DrawConfig = DrawConfig()
    parse_config: ParseConfig = ParseConfig()
