"""Tests for keymap_drawer.physical_layout: Point, PhysicalKey/PhysicalLayout
and the Ortho / CPT / QMK layout generators."""

import dataclasses
import io
import json

import pytest
from pydantic import ValidationError

from keymap_drawer.config import Config
from keymap_drawer.physical_layout import (
    CPTLayout,
    OrthoLayout,
    PhysicalKey,
    PhysicalLayout,
    PhysicalLayoutGenerator,
    Point,
    QmkLayout,
)


class TestPoint:
    def test_add_and_sub(self):
        assert Point(1, 2) + Point(3, 4) == Point(4, 6)
        assert Point(1, 2) - Point(1, 1) == Point(0, 1)

    def test_abs_is_euclidean_length(self):
        assert abs(Point(3, 4)) == 5.0
        assert abs(Point(0, 0)) == 0.0

    def test_scalar_mul_both_directions(self):
        assert Point(1, 2) * 2 == Point(2, 4)
        assert 3 * Point(1, 2) == Point(3, 6)

    def test_copy_is_equal_but_distinct(self):
        point = Point(1, 2)
        assert point.copy() == point
        assert point.copy() is not point

    def test_point_is_immutable(self):
        with pytest.raises(dataclasses.FrozenInstanceError):
            Point(1, 2).x = 5


class TestPhysicalKey:
    def test_unrotated_bounding_box_equals_size(self):
        key = PhysicalKey(pos=Point(30, 28), width=60, height=56)
        assert (key.bounding_width, key.bounding_height) == (60, 56)
        assert key.rotation == 0
        assert key.is_iso_enter is False

    def test_rotated_bounding_box_swaps_dimensions_at_90_degrees(self):
        key = PhysicalKey(pos=Point(0, 0), width=10, height=20, rotation=90)
        assert key.bounding_width == pytest.approx(20.0)
        assert key.bounding_height == pytest.approx(10.0)

    def test_from_qmk_spec_centers_key(self):
        key = PhysicalKey.from_qmk_spec(
            scale=56, pos=Point(0, 0), width=1.0, height=1.0, rotation=0, rotation_pos=Point(0, 0)
        )
        assert key.pos == Point(28.0, 28.0)
        assert (key.width, key.height) == (56.0, 56.0)

    def test_from_qmk_spec_detects_iso_enter(self):
        key = PhysicalKey.from_qmk_spec(
            scale=56, pos=Point(0, 0), width=1.25, height=2.0, rotation=0, rotation_pos=Point(0, 0)
        )
        assert key.is_iso_enter is True
        assert (key.width, key.height) == (70.0, 112.0)

    def test_from_qmk_spec_rotates_center_around_rotation_pos(self):
        key = PhysicalKey.from_qmk_spec(
            scale=10, pos=Point(0, 0), width=1.0, height=1.0, rotation=90, rotation_pos=Point(0, 0)
        )
        assert key.pos.x == pytest.approx(-5.0)
        assert key.pos.y == pytest.approx(5.0)

    def test_add_sub_move_position_only(self):
        key = PhysicalKey(pos=Point(30, 28), width=60, height=56)
        assert (key + Point(1, 1)).pos == Point(31, 29)
        assert (key - Point(1, 1)).pos == Point(29, 27)
        assert (key + Point(1, 1)).width == 60

    def test_rmul_scales_position_and_size(self):
        key = PhysicalKey(pos=Point(30, 28), width=60, height=56)
        scaled = 2 * key
        assert scaled.pos == Point(60, 56)
        assert scaled.width == 120


def make_layout(*positions, w=60, h=56):
    return PhysicalLayout(keys=[PhysicalKey(pos=Point(x, y), width=w, height=h) for x, y in positions])


class TestPhysicalLayout:
    def test_len(self):
        assert len(make_layout((30, 28), (90, 28))) == 2

    def test_width_and_height_extend_to_key_edges(self):
        layout = make_layout((30, 28), (90, 28))
        assert layout.width == 120.0
        assert layout.height == 56.0

    def test_min_dimensions(self):
        layout = make_layout((30, 28), (90, 28))
        assert layout.min_width == 60
        assert layout.min_height == 56

    def test_normalize_shifts_min_corner_to_origin(self):
        layout = make_layout((90, 84))
        normalized = layout.normalize()
        assert normalized.keys[0].pos == Point(30.0, 28.0)

    def test_add_shifts_all_keys(self):
        layout = make_layout((30, 28))
        assert (layout + Point(10, 0)).keys[0].pos == Point(40, 28)

    def test_rmul_scales_all_keys(self):
        layout = make_layout((30, 28))
        assert (2 * layout).keys[0].width == 120


class TestOrthoLayout:
    def test_plain_grid(self):
        layout = OrthoLayout(rows=2, columns=3).generate(60, 56, 30)
        assert len(layout) == 6
        assert layout.keys[0].pos == Point(30.0, 28.0)
        assert layout.keys[-1].pos == Point(150.0, 84.0)

    def test_split_doubles_columns_with_gap(self):
        layout = OrthoLayout(split=True, rows=1, columns=2).generate(60, 56, 30)
        assert [k.pos for k in layout.keys] == [
            Point(30.0, 28.0),
            Point(90.0, 28.0),
            Point(180.0, 28.0),
            Point(240.0, 28.0),
        ]

    def test_split_thumbs_are_added_below(self):
        layout = OrthoLayout(split=True, rows=1, columns=3, thumbs=2).generate(60, 56, 30)
        assert len(layout) == 6 + 4

    def test_mit_bottom_row_has_one_wide_key(self):
        layout = OrthoLayout(rows=2, columns=4, thumbs="MIT").generate(60, 56, 30)
        assert len(layout) == 7
        bottom = layout.keys[-3:]
        assert [k.width for k in bottom] == [60, 120, 60]
        assert bottom[1].pos == Point(120.0, 84.0)

    def test_2x2u_bottom_row_has_two_wide_keys(self):
        layout = OrthoLayout(rows=2, columns=6, thumbs="2x2u").generate(60, 56, 30)
        assert len(layout) == 10
        assert sum(1 for k in layout.keys if k.width == 120) == 2

    def test_drop_pinky_removes_bottom_row_corner_keys(self):
        layout = OrthoLayout(split=True, rows=2, columns=2, drop_pinky=True).generate(60, 56, 30)
        assert len(layout) == 6

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"rows": 1, "columns": 2, "thumbs": 1},  # thumbs require split
            {"rows": 1, "columns": 2, "thumbs": 3, "split": True},  # more thumbs than columns
            {"rows": 2, "columns": 4, "thumbs": "MIT", "split": True},  # MIT is non-split only
            {"rows": 2, "columns": 3, "thumbs": "MIT"},  # MIT needs even columns
            {"rows": 1, "columns": 2, "drop_pinky": True},  # drops require split
        ],
    )
    def test_invalid_specs_raise_validation_error(self, kwargs):
        with pytest.raises(ValidationError):
            OrthoLayout(**kwargs)


class TestCPTLayout:
    def test_simple_split_spec(self):
        layout = CPTLayout(spec="33 33").generate(60, 56, 30)
        assert len(layout) == 12
        assert layout.keys[0].pos == Point(30.0, 28.0)
        # Right half is offset by the left half's width plus the split gap.
        assert layout.keys[2].pos == Point(180.0, 28.0)

    def test_underscore_also_separates_halves(self):
        assert len(CPTLayout(spec="33_33").generate(60, 56, 30)) == 12

    def test_full_corne_style_spec(self):
        assert len(CPTLayout(spec="333+2 2+333").generate(60, 56, 30)) == 22

    def test_thumbs_row_is_below_alphas(self):
        layout = CPTLayout(spec="33+2").generate(60, 56, 30)
        assert len(layout) == 8
        thumb_ys = max(k.pos.y for k in layout.keys)
        assert thumb_ys == 196.0
        assert sum(1 for k in layout.keys if k.pos.y == thumb_ys) == 2

    @pytest.mark.parametrize("spec", ["abc", "3"])
    def test_invalid_specs_raise_validation_error(self, spec):
        with pytest.raises(ValidationError, match="does not match the expected syntax"):
            CPTLayout(spec=spec)

    def test_empty_spec_passes_validation_but_cannot_generate(self):
        # Current behavior: the validator's all() over zero parts is vacuously
        # true, so "" is accepted; generate() then fails on max() of no parts.
        layout = CPTLayout(spec="")
        with pytest.raises(ValueError, match="max\\(\\) iterable argument is empty"):
            layout.generate(60, 56, 30)


class TestQmkLayout:
    def test_generate_scales_and_normalizes(self):
        qmk = QmkLayout(layouts={"LAYOUT": [{"x": 0, "y": 0}, {"x": 1, "y": 0, "w": 2}]})
        layout = qmk.generate(layout_name="LAYOUT", key_size=56)
        assert len(layout) == 2
        assert layout.keys[0].pos == Point(28.0, 28.0)
        assert layout.keys[1].pos == Point(112.0, 28.0)
        assert layout.keys[1].width == 112.0

    def test_none_layout_name_picks_first_layout(self):
        qmk = QmkLayout(layouts={"ONLY": [{"x": 0, "y": 0}]})
        assert len(qmk.generate(layout_name=None, key_size=56)) == 1

    def test_width_can_be_given_with_u_alias(self):
        qmk = QmkLayout(layouts={None: [{"x": 0, "y": 0, "u": 1.5}]})
        assert qmk.generate(None, 56).keys[0].width == 84.0

    def test_unknown_layout_name_raises(self):
        qmk = QmkLayout(layouts={"LAYOUT": [{"x": 0, "y": 0}]})
        with pytest.raises(AssertionError, match="Could not find layout"):
            qmk.generate(layout_name="NOPE", key_size=56)

    def test_empty_layouts_raise(self):
        with pytest.raises(AssertionError, match="cannot be empty"):
            QmkLayout(layouts={}).generate(layout_name=None, key_size=56)


class TestPhysicalLayoutGenerator:
    def test_ortho_layout_via_generator(self):
        gen = PhysicalLayoutGenerator(config=Config(), ortho_layout={"rows": 1, "columns": 2})
        assert len(gen.generate()) == 2

    def test_cols_thumbs_notation_via_generator(self):
        gen = PhysicalLayoutGenerator(config=Config(), cols_thumbs_notation="33 33")
        assert len(gen.generate()) == 12

    def test_qmk_info_json_from_bytes(self):
        info = {"layouts": {"LAYOUT": {"layout": [{"x": 0, "y": 0}, {"x": 1, "y": 0}]}}}
        gen = PhysicalLayoutGenerator(
            config=Config(), qmk_info_json=io.BytesIO(json.dumps(info).encode()), layout_name="LAYOUT"
        )
        layout = gen.generate()
        assert len(layout) == 2
        assert layout.keys[1].pos == Point(84.0, 28.0)

    def test_qmk_info_json_list_format(self):
        gen = PhysicalLayoutGenerator(
            config=Config(), qmk_info_json=io.BytesIO(json.dumps([{"x": 0, "y": 0}]).encode())
        )
        assert len(gen.generate()) == 1

    def test_no_layout_spec_is_rejected(self):
        with pytest.raises(ValidationError, match="exactly one of"):
            PhysicalLayoutGenerator(config=Config())

    def test_two_layout_specs_are_rejected(self):
        with pytest.raises(ValidationError, match="exactly one of"):
            PhysicalLayoutGenerator(
                config=Config(), ortho_layout={"rows": 1, "columns": 2}, cols_thumbs_notation="33"
            )
