"""Tests for keymap_drawer.parse.qmk.QmkJsonParser (QMK JSON keymaps)."""

import json

import pytest

from keymap_drawer.config import ParseConfig
from keymap_drawer.keymap import LayoutKey
from keymap_drawer.parse.parse import ParseError
from keymap_drawer.parse.qmk import QmkJsonParser


def parse_qmk(obj, config=None, **parser_kwargs):
    """Run QmkJsonParser._parse on a JSON-serializable keymap dict."""
    parser = QmkJsonParser(config or ParseConfig(), None, **parser_kwargs)
    return parser._parse(json.dumps(obj))


def taps(keymap_data, layer="L0"):
    """Return (tap, hold, shifted, type) tuples for a layer."""
    return [(k.tap, k.hold, k.shifted, k.type) for k in keymap_data.layers[layer]]


class TestLayoutExtraction:
    def test_keyboard_and_layout_name_are_extracted(self):
        layout, _ = parse_qmk(
            {"keyboard": "planck/rev6", "layout": "LAYOUT_ortho_4x12", "layers": [["KC_A"]]}
        )
        assert layout == {"qmk_keyboard": "planck/rev6", "layout_name": "LAYOUT_ortho_4x12"}

    def test_missing_keyboard_gives_empty_layout(self):
        layout, _ = parse_qmk({"layers": [["KC_A"]]})
        assert layout == {}

    def test_default_layer_names_are_generated(self):
        _, kd = parse_qmk({"layers": [["KC_A"], ["KC_B"]]})
        assert list(kd.layers) == ["L0", "L1"]

    def test_custom_layer_names_are_used(self):
        _, kd = parse_qmk({"layers": [["KC_A"], ["KC_B"]]}, layer_names=["Base", "Nav"])
        assert list(kd.layers) == ["Base", "Nav"]

    def test_layer_name_count_mismatch_raises(self):
        with pytest.raises(AssertionError, match="does not match the number of parsed layers"):
            parse_qmk({"layers": [["KC_A"]]}, layer_names=["Base", "Nav"])

    def test_invalid_json_raises_decode_error(self):
        parser = QmkJsonParser(ParseConfig(), None)
        with pytest.raises(json.JSONDecodeError):
            parser._parse("this is not json")


class TestPlainKeycodes:
    def test_prefix_is_removed_and_keycode_kept(self):
        _, kd = parse_qmk({"layers": [["KC_A", "KC_B"]]})
        assert taps(kd) == [("A", "", "", ""), ("B", "", "", "")]

    @pytest.mark.parametrize(
        "keycode,expected",
        [
            ("KC_MINUS", "-"),
            ("KC_EQUAL", "="),
            ("KC_LEFT_BRACKET", "["),
            ("KC_RIGHT_BRACKET", "]"),
            ("KC_BACKSLASH", "\\"),
            ("KC_SEMICOLON", ";"),
            ("KC_QUOTE", "'"),
            ("KC_GRAVE", "`"),
            ("KC_COMMA", ","),
            ("KC_DOT", "."),
            ("KC_SLASH", "/"),
            ("KC_NO", ""),
            ("KC_XXXXXXX", ""),
        ],
    )
    def test_keycode_map_symbols(self, keycode, expected):
        _, kd = parse_qmk({"layers": [[keycode]]})
        assert taps(kd) == [(expected, "", "", "")]

    def test_unknown_keycode_passes_through_without_prefix(self):
        _, kd = parse_qmk({"layers": [["KC_FOO_BAR", "SOME_KEY"]]})
        assert [t[0] for t in taps(kd)] == ["FOO BAR", "SOME KEY"]

    def test_custom_keycode_map_entry_can_be_a_full_key_spec(self):
        config = ParseConfig(qmk_keycode_map={"A": {"t": "alpha", "h": "mod"}})
        _, kd = parse_qmk({"layers": [["KC_A"]]}, config=config)
        assert taps(kd) == [("alpha", "mod", "", "")]


class TestTransparentKeys:
    @pytest.mark.parametrize("keycode", ["KC_TRANSPARENT", "KC_TRNS", "_______"])
    def test_transparent_variants_use_trans_legend(self, keycode):
        _, kd = parse_qmk({"layers": [[keycode]]})
        assert taps(kd) == [("▽", "", "", "trans")]

    def test_custom_trans_legend(self):
        # A plain string legend replaces the tap only; the "trans" type comes
        # from the default dict-valued trans_legend and is lost here.
        _, kd = parse_qmk({"layers": [["KC_TRNS"]]}, config=ParseConfig(trans_legend="trans!"))
        assert taps(kd) == [("trans!", "", "", "")]


class TestLayerKeys:
    def test_momentary_layer_uses_layer_legend(self):
        _, kd = parse_qmk({"layers": [["MO(1)", "KC_A"], ["KC_B", "KC_C"]]})
        assert taps(kd) == [("L1", "", "", ""), ("A", "", "", "")]

    def test_momentary_layer_marks_held_key_on_target_layer(self):
        _, kd = parse_qmk({"layers": [["MO(1)", "KC_A"], ["KC_B", "KC_C"]]})
        assert taps(kd, "L1") == [("B", "", "", "held"), ("C", "", "", "")]

    @pytest.mark.parametrize("fn", ["TG", "TO", "DF"])
    def test_toggled_layer_keys_get_toggle_hold_label(self, fn):
        _, kd = parse_qmk({"layers": [[f"{fn}(1)", "KC_A", "KC_B"], ["KC_C", "KC_D", "KC_E"]]})
        assert taps(kd)[0] == ("L1", "toggle", "", "")

    def test_layer_tap(self):
        _, kd = parse_qmk({"layers": [["LT(1,KC_A)", "KC_B"], ["KC_C", "KC_D"]]})
        assert taps(kd)[0] == ("A", "L1", "", "")
        # LT also registers as a momentary activator, marking the target key held.
        assert taps(kd, "L1")[0] == ("C", "", "", "held")

    def test_layer_tap_with_spaces(self):
        _, kd = parse_qmk({"layers": [["LT(1, KC_A)", "KC_B"], ["KC_C", "KC_D"]]})
        assert taps(kd)[0] == ("A", "L1", "", "")

    def test_one_shot_layer(self):
        _, kd = parse_qmk({"layers": [["OSL(1)", "KC_A"], ["KC_B", "KC_C"]]})
        assert taps(kd)[0] == ("L1", "sticky", "", "")

    def test_tap_toggle_layer(self):
        _, kd = parse_qmk({"layers": [["TT(1)", "KC_A"], ["KC_B", "KC_C"]]})
        assert taps(kd)[0] == ("L1", "tap-toggle", "", "")

    def test_layer_legends_come_from_legend_map(self):
        config = ParseConfig(layer_legend_map={"L1": "NAV"})
        _, kd = parse_qmk({"layers": [["MO(1)", "KC_A"], ["KC_B", "KC_C"]]}, config=config)
        assert taps(kd)[0] == ("NAV", "", "", "")

    def test_out_of_range_layer_raises_parse_error(self):
        with pytest.raises(ParseError, match='Could not parse keycode "MO\\(5\\)"'):
            parse_qmk({"layers": [["MO(5)", "KC_A"]]})


class TestModTapAndOneShotMod:
    def test_short_mod_tap_syntax(self):
        _, kd = parse_qmk({"layers": [["LSFT_T(KC_A)", "LCTL_T(KC_C)"]]})
        assert taps(kd) == [("A", "LSFT", "", ""), ("C", "LCTL", "", "")]

    def test_long_mod_tap_syntax(self):
        _, kd = parse_qmk({"layers": [["MT(MOD_LCTL,KC_B)"]]})
        # Current behavior: the raw MOD_ argument is used as the hold legend.
        assert taps(kd) == [("B", "MOD_LCTL", "", "")]

    def test_one_shot_mod(self):
        _, kd = parse_qmk({"layers": [["OSM(MOD_LSFT)"]]})
        assert taps(kd) == [("LSFT", "sticky", "", "")]


class TestModifierFunctions:
    @pytest.mark.parametrize(
        "keycode,expected",
        [
            ("LCTL(KC_C)", "Ctl+C"),
            ("LSFT(KC_A)", "Sft+A"),
            ("LALT(KC_A)", "Alt+A"),
            ("LGUI(KC_A)", "Gui+A"),
            ("RALT(KC_A)", "AltGr+A"),
            ("LCTL(LSFT(KC_A))", "Ctl+Sft+A"),
            ("HYPR(KC_A)", "Hyper+A"),
            ("MEH(KC_A)", "Meh+A"),
        ],
    )
    def test_modifier_functions_are_formatted(self, keycode, expected):
        _, kd = parse_qmk({"layers": [[keycode]]})
        assert taps(kd) == [(expected, "", "", "")]

    def test_modifier_functions_disabled_by_config(self):
        config = ParseConfig(modifier_fn_map=None)
        _, kd = parse_qmk({"layers": [["LCTL(KC_C)"]]}, config=config)
        assert taps(kd) == [("LCTL(C)", "", "", "")]


class TestParserOptions:
    def test_raw_binding_map_shortcuts_parsing(self):
        config = ParseConfig(raw_binding_map={"QK_BOOT": "BOOT"})
        _, kd = parse_qmk({"layers": [["QK_BOOT", "KC_A"]]}, config=config)
        assert [t[0] for t in taps(kd)] == ["BOOT", "A"]

    def test_raw_binding_map_can_produce_full_key_spec(self):
        config = ParseConfig(raw_binding_map={"QK_BOOT": {"t": "BOOT", "type": "ghost"}})
        _, kd = parse_qmk({"layers": [["QK_BOOT"]]}, config=config)
        assert kd.layers["L0"][0] == LayoutKey(tap="BOOT", type="ghost")

    def test_skip_binding_parsing_keeps_keycodes_verbatim(self):
        config = ParseConfig(skip_binding_parsing=True)
        _, kd = parse_qmk({"layers": [["KC_A", "MO(1)"]]}, config=config)
        assert taps(kd) == [("KC_A", "", "", ""), ("MO(1)", "", "", "")]

    def test_virtual_layers_are_appended_blank(self):
        _, kd = parse_qmk({"layers": [["KC_A", "KC_B"]]}, virtual_layers=["Virt"])
        assert list(kd.layers) == ["L0", "Virt"]
        assert kd.layers["Virt"] == [LayoutKey(), LayoutKey()]


class TestParseWrapper:
    """The parse() wrapper (file-handle based) merges layout and dump output."""

    def test_parse_merges_layout_and_layers(self, named_buffer):
        buf = named_buffer(json.dumps({"keyboard": "kb", "layers": [["KC_A", "KC_B"]]}))
        result = QmkJsonParser(ParseConfig(), 0).parse(buf)
        assert result == {"layout": {"qmk_keyboard": "kb"}, "layers": {"L0": ["A", "B"]}}

    def test_parse_without_keyboard_has_no_layout_key(self, named_buffer):
        buf = named_buffer(json.dumps({"layers": [["KC_A"]]}))
        result = QmkJsonParser(ParseConfig(), 0).parse(buf)
        assert result == {"layers": {"L0": ["A"]}}

    def test_parse_chunks_layers_by_columns(self, named_buffer):
        buf = named_buffer(json.dumps({"layers": [["KC_A", "KC_B", "KC_C"]]}))
        result = QmkJsonParser(ParseConfig(), 2).parse(buf)
        assert result == {"layers": {"L0": [["A", "B"], ["C"]]}}
