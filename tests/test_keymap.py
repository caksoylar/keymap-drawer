"""Tests for keymap_drawer.keymap: LayoutKey, ComboSpec and KeymapData."""

import pytest
from pydantic import ValidationError

from keymap_drawer.config import Config
from keymap_drawer.keymap import ComboSpec, KeymapData, LayoutKey
from keymap_drawer.physical_layout import PhysicalKey, PhysicalLayout, Point


class TestLayoutKeyFromKeySpec:
    """LayoutKey.from_key_spec accepts dict / str / int / None specs only."""

    def test_string_spec_becomes_tap(self):
        key = LayoutKey.from_key_spec("A")
        assert key.tap == "A"
        assert key.hold == "" and key.shifted == "" and key.type == ""

    def test_int_spec_is_stringified(self):
        assert LayoutKey.from_key_spec(7).tap == "7"

    def test_none_spec_is_empty_key(self):
        assert LayoutKey.from_key_spec(None) == LayoutKey()

    def test_dict_spec_with_aliases(self):
        key = LayoutKey.from_key_spec({"t": "A", "h": "Ctrl", "s": "!"})
        assert (key.tap, key.hold, key.shifted) == ("A", "Ctrl", "!")

    def test_dict_spec_with_long_field_names(self):
        key = LayoutKey.from_key_spec({"tap": "A", "hold": "Ctrl"})
        assert (key.tap, key.hold) == ("A", "Ctrl")

    def test_dict_spec_with_center_bottom_aliases(self):
        key = LayoutKey.from_key_spec({"center": "A", "bottom": "Ctrl"})
        assert (key.tap, key.hold) == ("A", "Ctrl")

    def test_dict_spec_with_type(self):
        assert LayoutKey.from_key_spec({"t": "A", "type": "ghost"}).type == "ghost"

    @pytest.mark.parametrize("bad", [1.5, ["A"], ("A",), object()])
    def test_invalid_spec_types_raise_value_error(self, bad):
        with pytest.raises(ValueError, match="Invalid key specification"):
            LayoutKey.from_key_spec(bad)

    def test_bool_spec_is_treated_as_int(self):
        # bool is a subclass of int in Python, so it follows the int branch.
        assert LayoutKey.from_key_spec(True).tap == "True"

    def test_unknown_dict_field_is_forbidden(self):
        with pytest.raises(ValidationError):
            LayoutKey.from_key_spec({"bogus": 1})

    def test_numbers_are_coerced_to_str(self):
        assert LayoutKey(tap=5).tap == "5"


class TestLayoutKeySerialization:
    """The custom serializer collapses simple keys to a plain string."""

    def test_simple_key_serializes_to_string(self):
        assert LayoutKey(tap="A").model_dump() == "A"

    def test_empty_key_serializes_to_empty_string(self):
        assert LayoutKey().model_dump() == ""

    def test_multi_field_key_serializes_to_dict_with_short_aliases(self):
        key = LayoutKey(tap="A", hold="Ctrl", shifted="!", type="held")
        assert key.model_dump() == {"t": "A", "h": "Ctrl", "s": "!", "type": "held"}

    def test_empty_fields_are_omitted_from_dict_form(self):
        assert LayoutKey(tap="A", hold="Ctrl").model_dump() == {"t": "A", "h": "Ctrl"}

    def test_full_serializer_uses_long_names(self):
        key = LayoutKey(tap="A", hold="Ctrl")
        assert key.full_serializer() == {"tap": "A", "hold": "Ctrl"}

    def test_full_serializer_of_empty_key_is_empty_dict(self):
        assert LayoutKey().full_serializer() == {}

    def test_serialization_round_trip(self):
        key = LayoutKey(tap="A", hold="Ctrl", tl="x")
        assert LayoutKey.from_key_spec(key.model_dump()) == key

    def test_equality(self):
        assert LayoutKey(tap="A") == LayoutKey(tap="A")
        assert LayoutKey(tap="A") != LayoutKey(tap="B")
        assert LayoutKey(tap="A") != LayoutKey(tap="A", hold="Ctrl")


class TestLayoutKeyFormatter:
    def test_formatter_applies_to_all_non_empty_label_fields(self):
        key = LayoutKey(tap="a", hold="b", tl="c")
        key.apply_formatter(str.upper)
        assert (key.tap, key.hold, key.tl) == ("A", "B", "C")

    def test_formatter_skips_empty_fields_and_type(self):
        key = LayoutKey(tap="a", type="held")
        key.apply_formatter(str.upper)
        assert key.tap == "A"
        assert key.shifted == ""
        assert key.type == "held"  # type is not a label, it is left alone


class TestComboSpec:
    def test_defaults(self):
        combo = ComboSpec(p=[0, 1], k="Esc")
        assert combo.key_positions == [0, 1]
        assert combo.key == LayoutKey(tap="Esc")
        assert combo.layers == []
        assert combo.align == "mid"
        assert combo.offset == 0.0
        assert combo.rotation == 0.0
        assert combo.hidden is False
        assert combo.draw_separate is None

    def test_dump_by_alias(self):
        combo = ComboSpec(p=[0, 1], k="Esc")
        assert combo.model_dump(by_alias=True) == {
            "p": [0, 1],
            "tk": [],
            "k": "Esc",
            "l": [],
            "a": "mid",
            "o": 0.0,
            "d": None,
            "s": None,
            "arc_scale": 1.0,
            "type": "",
            "w": None,
            "h": None,
            "r": 0.0,
            "draw_separate": None,
            "hidden": False,
        }

    def test_key_spec_is_parsed_to_layout_key(self):
        combo = ComboSpec(p=[0, 1], k={"t": "Esc", "h": "Ctrl"})
        assert combo.key.tap == "Esc" and combo.key.hold == "Ctrl"

    def test_trigger_keys_are_parsed_to_layout_keys(self):
        combo = ComboSpec(tk=["A", {"t": "B", "h": "Ctrl"}], k="Esc")
        assert combo.trigger_keys[0] == LayoutKey(tap="A")
        assert combo.trigger_keys[1].hold == "Ctrl"

    def test_normalize_fields_renames_long_names_to_aliases(self):
        spec = ComboSpec.normalize_fields({"key_positions": [0, 1], "key": "Esc", "layers": ["L0"]})
        assert spec["p"] == [0, 1]
        assert spec["l"] == ["L0"]
        assert spec["k"] == LayoutKey(tap="Esc")
        combo = ComboSpec(**spec)
        assert combo.key_positions == [0, 1] and combo.layers == ["L0"]

    def test_normalize_fields_keeps_already_aliased_spec(self):
        spec = ComboSpec.normalize_fields({"p": [0, 1], "k": "Esc"})
        assert ComboSpec(**spec).key.tap == "Esc"

    @pytest.mark.parametrize(
        "spec",
        [
            {"p": [0], "k": "X"},  # fewer than two positions
            {"p": [0, 1], "tk": ["A", "B"], "k": "X"},  # both positions and trigger keys
            {"k": "X"},  # neither positions nor trigger keys
            {"p": [0, 1], "k": "X", "s": 1.5},  # slide out of [-1, 1]
            {"p": [0, 1], "k": "X", "a": "diagonal"},  # unknown alignment
        ],
    )
    def test_invalid_specs_raise_validation_error(self, spec):
        with pytest.raises(ValidationError):
            ComboSpec(**spec)

    def test_single_trigger_key_is_accepted_upstream_quirk(self):
        # Current behavior (suspected upstream bug): the "at least two trigger
        # keys" validator is mistakenly registered on key_positions a second
        # time, so a lone trigger key passes validation.
        combo = ComboSpec(tk=["A"], k="X")
        assert [k.tap for k in combo.trigger_keys] == ["A"]

    def test_slide_bounds_are_inclusive(self):
        assert ComboSpec(p=[0, 1], k="X", s=-1.0).slide == -1.0
        assert ComboSpec(p=[0, 1], k="X", s=1.0).slide == 1.0


def make_keymap(layers, combos=None, config=None):
    """Build a no-layout KeymapData (the mode used while parsing)."""
    return KeymapData(layers=layers, combos=combos or [], layout=None, config=config)


class TestKeymapDataConstruction:
    def test_layer_keys_are_parsed_from_mixed_specs(self):
        kd = make_keymap({"L0": ["A", {"t": "C", "h": "Ctrl"}, None, 7]})
        keys = kd.layers["L0"]
        assert keys[0] == LayoutKey(tap="A")
        assert keys[1] == LayoutKey(tap="C", hold="Ctrl")
        assert keys[2] == LayoutKey()
        assert keys[3] == LayoutKey(tap="7")

    def test_nested_sublists_are_flattened(self):
        kd = make_keymap({"L0": [["A", "B"], ["C"]]})
        assert [k.tap for k in kd.layers["L0"]] == ["A", "B", "C"]

    def test_empty_keymap_is_rejected(self):
        with pytest.raises(ValidationError, match="No layers or combos found"):
            make_keymap({})

    def test_uneven_layer_lengths_rejected_without_layout(self):
        with pytest.raises(ValidationError, match="Number of keys differ between layers"):
            make_keymap({"L0": ["A"], "L1": ["A", "B"]})

    def test_layer_length_must_match_physical_layout(self, config):
        with pytest.raises(ValidationError, match="does not match physical layout"):
            KeymapData(
                layers={"L0": ["A", "B", "C"]},
                layout={"ortho_layout": {"rows": 1, "columns": 2}},
                config=config,
            )

    def test_layout_dict_is_generated(self, config):
        kd = KeymapData(
            layers={"L0": ["A", "B"]},
            layout={"ortho_layout": {"rows": 1, "columns": 2}},
            config=config,
        )
        assert len(kd.layout) == 2
        assert kd.layout.width == 120.0
        assert kd.layout.height == 56.0

    def test_physical_layout_object_is_passed_through(self, config):
        layout = PhysicalLayout(keys=[PhysicalKey(pos=Point(30, 28), width=60, height=56)])
        kd = KeymapData(layers={"L": ["A"]}, layout=layout, config=config)
        assert kd.layout is layout


class TestKeymapDataCombos:
    def test_combo_with_unknown_layer_is_rejected(self, config):
        with pytest.raises(ValidationError, match="not found in the layer definitions"):
            make_keymap({"L0": ["A", "B"]}, combos=[{"p": [0, 1], "k": "X", "l": ["NOPE"]}], config=config)

    def test_combo_position_beyond_layout_is_rejected(self, config):
        with pytest.raises(ValidationError, match="exceed number of keys"):
            KeymapData(
                layers={"L0": ["A", "B"]},
                combos=[{"p": [0, 5], "k": "X"}],
                layout={"ortho_layout": {"rows": 1, "columns": 2}},
                config=config,
            )

    def test_trigger_keys_resolve_to_positions(self):
        kd = make_keymap({"L0": ["A", "B", "C"]}, combos=[{"tk": ["A", "C"], "k": "Esc"}])
        assert kd.combos[0].key_positions == [0, 2]

    def test_trigger_keys_fall_back_to_tap_only_match(self):
        kd = make_keymap(
            {"L0": [{"t": "A", "h": "Ctrl"}, "B"]},
            combos=[{"tk": ["A", "B"], "k": "Esc"}],
        )
        assert kd.combos[0].key_positions == [0, 1]

    def test_unresolvable_trigger_keys_raise(self):
        with pytest.raises(ValidationError, match="Cannot find matching key positions"):
            make_keymap({"L0": ["A", "B"]}, combos=[{"tk": ["A", "Z"], "k": "Esc"}])

    def test_get_combos_per_layer(self, config):
        kd = make_keymap(
            {"L0": ["A", "B", "C"], "L1": ["D", "E", "F"]},
            combos=[
                {"p": [0, 1], "k": "Esc"},  # on all layers
                {"p": [0, 2], "k": "Tab", "l": ["L1"]},  # only on L1
                {"p": [1, 2], "k": "X", "draw_separate": True},  # separate diagram
            ],
            config=config,
        )
        per_layer = kd.get_combos_per_layer()
        assert [c.key.tap for c in per_layer["L0"]] == ["Esc"]
        assert [c.key.tap for c in per_layer["L1"]] == ["Esc", "Tab"]
        assert [c.key.tap for c in kd.get_separate_combos()] == ["X"]

    def test_get_combos_per_layer_subset(self, config):
        kd = make_keymap(
            {"L0": ["A", "B"], "L1": ["C", "D"]},
            combos=[{"p": [0, 1], "k": "Esc"}],
            config=config,
        )
        per_layer = kd.get_combos_per_layer(["L1"])
        assert list(per_layer) == ["L1"]
        assert [c.key.tap for c in per_layer["L1"]] == ["Esc"]

    def test_separate_combo_diagrams_config_moves_unmarked_combos(self):
        config = Config()
        config.draw_config.separate_combo_diagrams = True
        kd = make_keymap(
            {"L0": ["A", "B", "C"]},
            combos=[
                {"p": [0, 1], "k": "Esc"},  # unmarked: follows the config
                {"p": [0, 2], "k": "Tab", "draw_separate": False},  # explicitly on-layer
            ],
            config=config,
        )
        assert [c.key.tap for c in kd.get_combos_per_layer()["L0"]] == ["Tab"]
        assert [c.key.tap for c in kd.get_separate_combos()] == ["Esc"]


class TestKeymapDataDump:
    def test_dump_serializes_simple_keys_to_strings(self):
        kd = make_keymap({"L0": ["A", "B"]})
        assert kd.dump() == {"layers": {"L0": ["A", "B"]}}

    def test_dump_chunks_layers_by_num_cols(self):
        kd = make_keymap({"L0": ["A", "B", "C", "D", "E"]})
        assert kd.dump(num_cols=2) == {"layers": {"L0": [["A", "B"], ["C", "D"], ["E"]]}}

    def test_dump_with_zero_cols_does_not_chunk(self):
        kd = make_keymap({"L0": ["A", "B"]})
        assert kd.dump(num_cols=0) == {"layers": {"L0": ["A", "B"]}}


class TestKeymapDataRebase:
    def test_rebase_preserves_base_fields_not_in_new_keys(self):
        base = make_keymap({"L0": [{"t": "A", "type": "held"}, "B"]})
        new = make_keymap({"L0": ["X", "Y"]})
        new.rebase(base)
        assert new.layers["L0"][0] == LayoutKey(tap="X", type="held")
        assert new.layers["L0"][1] == LayoutKey(tap="Y")

    def test_rebase_inherits_combo_fields_by_positions(self):
        base = make_keymap({"L0": ["A", "B"]}, combos=[{"p": [0, 1], "k": "Esc", "a": "top"}])
        new = make_keymap({"L0": ["A", "B"]}, combos=[{"p": [1, 0], "k": "Tab"}])
        new.rebase(base)
        assert new.combos[0].key.tap == "Tab"  # new key wins
        assert new.combos[0].align == "top"  # positioning inherited from base

    def test_rebase_with_mismatched_layer_length_raises(self):
        base = make_keymap({"L0": ["A", "B"]})
        new = make_keymap({"L0": ["X"]})
        with pytest.raises(AssertionError, match="layer lengths"):
            new.rebase(base)

    def test_rebase_leaves_unmatched_layers_and_combos_alone(self):
        base = make_keymap({"L0": ["A", "B"]}, combos=[{"p": [0, 1], "k": "Esc", "a": "top"}])
        # Layer "L1" does not exist in base, and the combo's positions do not
        # match any base combo, so both pass through rebase unchanged.
        # (Positions are not bounds-checked in no-layout mode.)
        new = make_keymap({"L1": ["X", "Y"]}, combos=[{"p": [2, 3], "k": "Tab"}])
        new.rebase(base)
        assert [k.tap for k in new.layers["L1"]] == ["X", "Y"]
        assert new.combos[0].align == "mid"

    def test_rebase_matches_combos_by_positions_regardless_of_layer_names(self):
        base = make_keymap({"L0": ["A", "B"]}, combos=[{"p": [0, 1], "k": "Esc", "a": "top"}])
        new = make_keymap({"L1": ["X", "Y"]}, combos=[{"p": [0, 1], "k": "Tab"}])
        new.rebase(base)
        assert new.combos[0].align == "top"
