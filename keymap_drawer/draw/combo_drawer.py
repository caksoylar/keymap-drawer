"""Module containing class and methods to draw combo representations."""
from math import copysign
from typing import Sequence, TextIO, Literal

from keymap_drawer.keymap import ComboSpec
from keymap_drawer.physical_layout import Point, PhysicalLayout
from keymap_drawer.config import DrawConfig


LegendType = Literal["tap", "hold", "shifted"]


class ComboDrawerMixin:
    """Mixin that adds combo drawing for KeymapDrawer."""

    # initialized in KeymapDrawer
    cfg: DrawConfig
    out: TextIO
    layout: PhysicalLayout

    # methods defined in KeymapDrawer to make mypy happy
    def _draw_rect(self, p: Point, dims: Point, radii: Point, classes: Sequence[str]) -> None:
        raise NotImplementedError

    def _draw_legend(  # pylint: disable=too-many-arguments
        self, p: Point, words: Sequence[str], key_type: str, legend_type: LegendType, shift: float = 0
    ):
        raise NotImplementedError

    @staticmethod
    def _split_text(text: str) -> list[str]:
        raise NotImplementedError

    # actual methods
    def get_offsets_per_layer(self, combos_per_layer):
        """For each layer, return the minimum and maximum y-coordinates that can be caused by the combos."""
        return {
            name: (
                max((c.offset * self.layout.min_height for c in combos if c.align == "top"), default=0.0),
                max((c.offset * self.layout.min_height for c in combos if c.align == "bottom"), default=0.0),
            )
            for name, combos in combos_per_layer.items()
        }

    def _draw_arc_dendron(  # pylint: disable=too-many-arguments
        self, p_1: Point, p_2: Point, x_first: bool, shorten: float, arc_scale: float
    ) -> None:
        diff = p_2 - p_1

        # check if the points are too close to draw an arc, if so draw a line instead
        if (x_first and abs(diff.x) < self.cfg.arc_radius) or (not x_first and abs(diff.y) < self.cfg.arc_radius):
            self._draw_line_dendron(p_1, p_2, shorten)
            return

        start = f"M{p_1.x},{p_1.y}"
        arc_x = copysign(self.cfg.arc_radius, diff.x)
        arc_y = copysign(self.cfg.arc_radius, diff.y)
        clockwise = (diff.x > 0) ^ (diff.y > 0)
        if x_first:
            line_1 = f"h{arc_scale * diff.x - arc_x}"
            line_2 = f"v{diff.y - arc_y - copysign(shorten, diff.y)}"
            clockwise = not clockwise
        else:
            line_1 = f"v{arc_scale * diff.y - arc_y}"
            line_2 = f"h{diff.x - arc_x - copysign(shorten, diff.x)}"
        arc = f"a{self.cfg.arc_radius},{self.cfg.arc_radius} 0 0 {int(clockwise)} {arc_x},{arc_y}"
        self.out.write(f'<path d="{start} {line_1} {arc} {line_2}" class="combo"/>\n')

    def _draw_line_dendron(self, p_1: Point, p_2: Point, shorten: float) -> None:
        start = f"M{p_1.x},{p_1.y}"
        diff = p_2 - p_1
        if shorten and shorten < (magn := abs(diff)):
            diff = (1 - shorten / magn) * diff
        line = f"l{diff.x},{diff.y}"
        self.out.write(f'<path d="{start} {line}" class="combo"/>\n')

    def print_combo(self, p_0: Point, combo: ComboSpec) -> None:
        """
        Given anchor coordinates p_0, print SVG code for a rectangle with text representing
        a combo specification, which contains the key positions that trigger it and what it does
        when triggered. The position of the rectangle depends on the alignment specified,
        along with whether dendrons are drawn going to each key position from the combo.
        """
        p_keys = [self.layout.keys[p] for p in combo.key_positions]

        # find center of combo box
        p = p_0.copy()
        p_mid = (1 / len(p_keys)) * sum((k.pos for k in p_keys), start=Point(0, 0))
        if combo.slide is not None:  # find two keys furthest from the midpoint, interpolate between their positions
            sorted_keys = sorted(p_keys, key=lambda k: (-abs(k.pos - p_mid), k.pos.x, k.pos.y))
            start, end = sorted_keys[0:2]
            p_mid = (1 - combo.slide) / 2 * start.pos + (1 + combo.slide) / 2 * end.pos

        match combo.align:
            case "mid":
                p += p_mid
            case "top":
                p += Point(
                    p_mid.x,
                    min(k.pos.y - k.height / 2 for k in p_keys)
                    - self.cfg.inner_pad_h / 2
                    - combo.offset * self.layout.min_height,
                )
            case "bottom":
                p += Point(
                    p_mid.x,
                    max(k.pos.y + k.height / 2 for k in p_keys)
                    + self.cfg.inner_pad_h / 2
                    + combo.offset * self.layout.min_height,
                )
            case "left":
                p += Point(
                    min(k.pos.x - k.width / 2 for k in p_keys)
                    - self.cfg.inner_pad_w / 2
                    - combo.offset * self.layout.min_width,
                    p_mid.y,
                )
            case "right":
                p += Point(
                    max(k.pos.x + k.width / 2 for k in p_keys)
                    + self.cfg.inner_pad_w / 2
                    + combo.offset * self.layout.min_width,
                    p_mid.y,
                )

        # draw dendrons going from box to combo keys
        if combo.dendron is not False:
            match combo.align:
                case "top" | "bottom":
                    for k in p_keys:
                        key_pos = p_0 + k.pos
                        offset = (
                            k.height / 5
                            if abs((key_pos - p).x) < self.cfg.combo_w / 2
                            and abs((key_pos - p).y) <= k.height / 3 + self.cfg.combo_h / 2
                            else k.height / 3
                        )
                        self._draw_arc_dendron(p, key_pos, True, offset, combo.arc_scale)
                case "left" | "right":
                    for k in p_keys:
                        key_pos = p_0 + k.pos
                        offset = (
                            k.width / 5
                            if abs((key_pos - p).y) < self.cfg.combo_h / 2
                            and abs((key_pos - p).x) <= k.width / 3 + self.cfg.combo_w / 2
                            else k.width / 3
                        )
                        self._draw_arc_dendron(p, key_pos, False, offset, combo.arc_scale)
                case "mid":
                    for k in p_keys:
                        key_pos = p_0 + k.pos
                        if combo.dendron is True or abs(key_pos - p) >= k.width - 1:
                            self._draw_line_dendron(p, key_pos, k.width / 3)

        # draw combo box with text
        self._draw_rect(
            p, Point(self.cfg.combo_w, self.cfg.combo_h), Point(self.cfg.key_rx, self.cfg.key_ry), classes=[combo.type]
        )

        self._draw_legend(p, self._split_text(combo.key.tap), key_type=combo.type, legend_type="tap")
        self._draw_legend(
            p + Point(0, self.cfg.combo_h / 2 - self.cfg.small_pad),
            [combo.key.hold],
            key_type=combo.type,
            legend_type="hold",
        )
        self._draw_legend(
            p - Point(0, self.cfg.combo_h / 2 - self.cfg.small_pad),
            [combo.key.shifted],
            key_type=combo.type,
            legend_type="shifted",
        )

    def print_combos_for_layer(self, p_0: Point, combos: Sequence[ComboSpec]):
        """For a given anchor point p_0, print SVG for all given combos, relative to that point."""
        for combo_spec in combos:
            self.print_combo(p_0, combo_spec)
