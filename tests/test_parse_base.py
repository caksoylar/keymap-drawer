"""Tests for the shared parser machinery in keymap_drawer.parse.parse.

The concrete QmkJsonParser is used to instantiate the abstract KeymapParser
base class, since the modifier tables live on the subclasses.
"""

import pytest

from keymap_drawer.config import ParseConfig
from keymap_drawer.keymap import LayoutKey
from keymap_drawer.parse.qmk import QmkJsonParser


def make_parser(config=None, **kwargs):
    return QmkJsonParser(config or ParseConfig(), None, **kwargs)


class TestParseModifierFns:
    def test_plain_keycode_has_no_modifiers(self):
        assert make_parser().parse_modifier_fns("KC_A") == ("KC_A", [])

    def test_single_modifier_function(self):
        assert make_parser().parse_modifier_fns("LCTL(KC_C)") == ("KC_C", ["left_ctrl"])

    def test_nested_modifier_functions_accumulate_in_order(self):
        parser = make_parser()
        assert parser.parse_modifier_fns("LCTL(LSFT(KC_A))") == ("KC_A", ["left_ctrl", "left_shift"])

    def test_unknown_function_is_left_alone(self):
        assert make_parser().parse_modifier_fns("FOO(KC_A)") == ("FOO(KC_A)", [])

    def test_combined_modifier_shortcut_expands(self):
        # LSG is the QMK shortcut for left shift + left gui.
        assert make_parser().parse_modifier_fns("LSG(KC_A)") == ("KC_A", ["left_shift", "left_gui"])

    def test_disabled_modifier_map_returns_keycode_unchanged(self):
        parser = make_parser(ParseConfig(modifier_fn_map=None))
        assert parser.parse_modifier_fns("LCTL(KC_C)") == ("LCTL(KC_C)", [])


class TestFormatModifiedKeys:
    def test_no_modifiers_returns_key_unchanged(self):
        assert make_parser().format_modified_keys("A", []) == "A"

    def test_single_modifier(self):
        assert make_parser().format_modified_keys("A", ["left_ctrl"]) == "Ctl+A"

    def test_multiple_modifiers_are_joined_with_mod_combiner(self):
        parser = make_parser()
        assert parser.format_modified_keys("A", ["left_ctrl", "left_shift"]) == "Ctl+Sft+A"

    def test_special_combination_hyper(self):
        parser = make_parser()
        mods = ["left_ctrl", "left_alt", "left_gui", "left_shift"]
        assert parser.format_modified_keys("A", mods) == "Hyper+A"

    def test_special_combination_is_order_insensitive(self):
        parser = make_parser()
        mods = ["left_shift", "left_alt", "left_ctrl"]
        assert parser.format_modified_keys("A", mods) == "Meh+A"

    def test_right_alt_maps_to_altgr(self):
        assert make_parser().format_modified_keys("A", ["right_alt"]) == "AltGr+A"

    def test_disabled_modifier_map_returns_key_unchanged(self):
        parser = make_parser(ParseConfig(modifier_fn_map=None))
        assert parser.format_modified_keys("A", ["left_ctrl"]) == "A"

    def test_custom_combiner_patterns(self):
        config = ParseConfig()
        config.modifier_fn_map.keycode_combiner = "{mods}({key})"
        config.modifier_fn_map.mod_combiner = "{mod_1}-{mod_2}"
        parser = make_parser(config)
        assert parser.format_modified_keys("A", ["left_ctrl", "left_shift"]) == "Ctl-Sft(A)"


class TestUpdateLayerActivatedFrom:
    def test_first_activation_is_recorded(self):
        parser = make_parser()
        parser.update_layer_activated_from([0], 1, [3])
        assert parser.layer_activated_from == {1: {(3, False)}}

    def test_second_activation_is_ignored_by_default(self):
        parser = make_parser()
        parser.update_layer_activated_from([0], 1, [3])
        parser.update_layer_activated_from([0], 1, [4])
        assert parser.layer_activated_from == {1: {(3, False)}}

    def test_reverse_activation_is_ignored(self):
        parser = make_parser()
        parser.update_layer_activated_from([1], 0, [0])
        assert parser.layer_activated_from == {}

    def test_activation_chains_through_intermediate_layers(self):
        parser = make_parser()
        parser.update_layer_activated_from([0], 1, [3])
        parser.update_layer_activated_from([1], 2, [5])
        # Position 3 (which activates layer 1) also counts as activating layer 2.
        assert parser.layer_activated_from[2] == {(5, False), (3, False)}

    def test_alternate_activators_are_marked_when_configured(self):
        parser = make_parser(ParseConfig(mark_alternate_layer_activators=True))
        parser.update_layer_activated_from([0], 1, [3])
        parser.update_layer_activated_from([0], 1, [4])
        assert parser.layer_activated_from == {1: {(3, False), (4, True)}}


class TestAddHeldKeys:
    def test_activating_keys_are_marked_held_on_target_layer(self):
        parser = make_parser()
        parser.update_layer_names(["L0", "L1"])
        parser.update_layer_activated_from([0], 1, [0])
        layers = {"L0": [LayoutKey(tap="MO")], "L1": [LayoutKey(tap="B")]}
        out = parser.add_held_keys(layers)
        assert out["L1"][0].type == "held"
        assert out["L0"][0].type == ""  # the activator itself is untouched

    def test_transparent_key_legend_is_cleared_when_held(self):
        parser = make_parser()
        parser.update_layer_names(["L0", "L1"])
        parser.update_layer_activated_from([0], 1, [0])
        layers = {"L0": [LayoutKey(tap="MO")], "L1": [parser.trans_key.model_copy()]}
        out = parser.add_held_keys(layers)
        assert out["L1"][0] == LayoutKey(type="held")

    def test_out_of_range_position_is_skipped(self):
        parser = make_parser()
        parser.update_layer_names(["L0", "L1"])
        parser.layer_activated_from = {1: {(99, False)}}
        layers = {"L0": [LayoutKey(tap="MO")], "L1": [LayoutKey(tap="B")]}
        out = parser.add_held_keys(layers)
        assert out["L1"][0].type == ""

    def test_trans_key_comes_from_config(self):
        parser = make_parser()
        assert parser.trans_key == LayoutKey(tap="▽", type="trans")


class TestAppendVirtualLayers:
    def test_virtual_layers_match_existing_layer_length(self):
        parser = make_parser(virtual_layers=["V1", "V2"])
        out = parser.append_virtual_layers({"L0": [LayoutKey(tap="A"), LayoutKey(tap="B")]})
        assert list(out) == ["L0", "V1", "V2"]
        assert out["V1"] == [LayoutKey(), LayoutKey()]
        assert out["V2"] == [LayoutKey(), LayoutKey()]

    def test_no_virtual_layers_returns_input_unchanged(self):
        layers = {"L0": [LayoutKey(tap="A")]}
        assert make_parser().append_virtual_layers(layers) == layers

    def test_virtual_layers_on_empty_keymap_are_empty(self):
        parser = make_parser(virtual_layers=["V1"])
        assert parser.append_virtual_layers({}) == {"V1": []}


class TestLayerNamesAndLegends:
    def test_update_layer_names_sets_legends(self):
        parser = make_parser()
        parser.update_layer_names(["Base", "Nav"])
        assert parser.layer_names == ["Base", "Nav"]
        assert parser.layer_legends == ["Base", "Nav"]

    def test_update_layer_names_twice_raises(self):
        parser = make_parser()
        parser.update_layer_names(["Base"])
        with pytest.raises(AssertionError):
            parser.update_layer_names(["Other"])

    def test_legends_use_legend_map(self):
        parser = make_parser(ParseConfig(layer_legend_map={"Base": "B!"}), layer_names=["Base", "Nav"])
        assert parser.layer_legends == ["B!", "Nav"]
