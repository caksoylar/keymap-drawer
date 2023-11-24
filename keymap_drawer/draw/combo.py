"""Module containing class and methods to draw combo representations."""
from io import StringIO
from math import copysign
from typing import Sequence

from keymap_drawer.config import DrawConfig
from keymap_drawer.draw.utils import UtilsMixin
from keymap_drawer.keymap import ComboSpec, LayoutKey
from keymap_drawer.physical_layout import PhysicalKey, PhysicalLayout, Point


class ComboDrawerMixin(UtilsMixin):
    """Mixin that adds combo drawing for KeymapDrawer."""

    # initialized in KeymapDrawer
    cfg: DrawConfig
    out: StringIO
    layout: PhysicalLayout

    def _draw_arc_dendron(  # pylint: disable=too-many-arguments
        self, p_1: Point, p_2: Point, x_first: bool, shorten: float, arc_scale: float
    ) -> None:
        diff = p_2 - p_1

        # check if the points are too close to draw an arc, if so draw a line instead
        if (x_first and abs(diff.x) < self.cfg.arc_radius) or (not x_first and abs(diff.y) < self.cfg.arc_radius):
            self._draw_line_dendron(p_1, p_2, shorten)
            return

        start = f"M{round(p_1.x)},{round(p_1.y)}"
        arc_x = copysign(self.cfg.arc_radius, diff.x)
        arc_y = copysign(self.cfg.arc_radius, diff.y)
        clockwise = (diff.x > 0) ^ (diff.y > 0)
        if x_first:
            line_1 = f"h{round(arc_scale * diff.x - arc_x)}"
            line_2 = f"v{round(diff.y - arc_y - copysign(shorten, diff.y))}"
            clockwise = not clockwise
        else:
            line_1 = f"v{round(arc_scale * diff.y - arc_y)}"
            line_2 = f"h{round(diff.x - arc_x - copysign(shorten, diff.x))}"
        arc = f"a{self.cfg.arc_radius},{self.cfg.arc_radius} 0 0 {int(clockwise)} {arc_x},{arc_y}"
        self.out.write(f'<path d="{start} {line_1} {arc} {line_2}" class="combo"/>\n')

    def _draw_line_dendron(self, p_1: Point, p_2: Point, shorten: float) -> None:
        start = f"M{round(p_1.x)},{round(p_1.y)}"
        diff = p_2 - p_1
        if shorten and shorten < (magn := abs(diff)):
            diff = (1 - shorten / magn) * diff
        line = f"l{round(diff.x)},{round(diff.y)}"
        self.out.write(f'<path d="{start} {line}" class="combo"/>\n')

    def print_combo(self, combo: ComboSpec, combo_ind: int) -> Point:
        """
        Print SVG code for a rectangle with text representing a combo specification, which contains the key positions
        that trigger it and what it does when triggered. The position of the rectangle depends on the alignment
        specified, along with whether dendrons are drawn going to each key position from the combo.

        Returns the midpoint of the combo box, for bounding box calculations.
        """
        p_keys = [self.layout.keys[p] for p in combo.key_positions]
        width, height = combo.width or self.cfg.combo_w, combo.height or self.cfg.combo_h

        # find center of combo box
        p_mid = (1 / len(p_keys)) * sum((k.pos for k in p_keys), start=Point(0, 0))
        if combo.slide is not None:  # find two keys furthest from the midpoint, interpolate between their positions
            sorted_keys = sorted(p_keys, key=lambda k: (-abs(k.pos - p_mid), k.pos.x, k.pos.y))
            start, end = sorted_keys[0:2]
            p_mid = (1 - combo.slide) / 2 * start.pos + (1 + combo.slide) / 2 * end.pos

        match combo.align:
            case "mid":
                p = p_mid
            case "top":
                p = Point(
                    p_mid.x,
                    min(k.pos.y - k.height / 2 for k in p_keys)
                    - self.cfg.inner_pad_h / 2
                    - combo.offset * self.layout.min_height,
                )
            case "bottom":
                p = Point(
                    p_mid.x,
                    max(k.pos.y + k.height / 2 for k in p_keys)
                    + self.cfg.inner_pad_h / 2
                    + combo.offset * self.layout.min_height,
                )
            case "left":
                p = Point(
                    min(k.pos.x - k.width / 2 for k in p_keys)
                    - self.cfg.inner_pad_w / 2
                    - combo.offset * self.layout.min_width,
                    p_mid.y,
                )
            case "right":
                p = Point(
                    max(k.pos.x + k.width / 2 for k in p_keys)
                    + self.cfg.inner_pad_w / 2
                    + combo.offset * self.layout.min_width,
                    p_mid.y,
                )

        class_str = self._to_class_str(["combo", combo.type, f"combopos-{combo_ind}"])
        self.out.write(f"<g{class_str}>\n")

        # draw dendrons going from box to combo keys
        if combo.dendron is not False:
            match combo.align:
                case "top" | "bottom":
                    for k in p_keys:
                        offset = (
                            k.height / 5
                            if abs((k.pos - p).x) < width / 2 and abs((k.pos - p).y) <= k.height / 3 + height / 2
                            else k.height / 3
                        )
                        self._draw_arc_dendron(p, k.pos, True, offset, combo.arc_scale)
                case "left" | "right":
                    for k in p_keys:
                        offset = (
                            k.width / 5
                            if abs((k.pos - p).y) < height / 2 and abs((k.pos - p).x) <= k.width / 3 + width / 2
                            else k.width / 3
                        )
                        self._draw_arc_dendron(p, k.pos, False, offset, combo.arc_scale)
                case "mid":
                    for k in p_keys:
                        if combo.dendron is True or abs(k.pos - p) >= k.width - 1:
                            self._draw_line_dendron(p, k.pos, k.width / 3)

        # draw combo box with text
        if combo.rotation != 0.0:
            self.out.write(f'<g transform="rotate({combo.rotation}, {p.x}, {p.y})">\n')
        self._draw_rect(
            p,
            Point(width, height),
            Point(self.cfg.key_rx, self.cfg.key_ry),
            classes=["combo", combo.type],
        )

        self._draw_legend(p, self._split_text(combo.key.tap), classes=["combo", combo.type], legend_type="tap")
        self._draw_legend(
            p + Point(0, self.cfg.combo_h / 2 - self.cfg.small_pad),
            [combo.key.hold],
            classes=["combo", combo.type],
            legend_type="hold",
        )
        self._draw_legend(
            p - Point(0, self.cfg.combo_h / 2 - self.cfg.small_pad),
            [combo.key.shifted],
            classes=["combo", combo.type],
            legend_type="shifted",
        )
        if combo.rotation != 0.0:
            self.out.write("</g>\n")

        self.out.write("</g>\n")
        return p

    def print_combos_for_layer(self, combos: Sequence[ComboSpec]) -> tuple[float | None, float | None]:
        """
        Print SVG for all given combos, relative to that point.
        Return min and max y-coordinates of combo boxes, for bounding box calculations.
        """
        combo_pts = []
        for combo_ind, combo_spec in enumerate(combos):
            combo_pts.append(self.print_combo(combo_spec, combo_ind))
        return min((p.y for p in combo_pts), default=0.0), max((p.y for p in combo_pts), default=0.0)

    def create_combo_diagrams(
        self, scale_factor: int, ghost_keys: Sequence[int] | None = None
    ) -> tuple[PhysicalLayout, dict[str, list[LayoutKey]]]:
        """
        Create and return both a shrunk down physical layout and layers representing combo
        locations with held key highlighting.
        """
        w, h = self.layout.min_width, self.layout.min_height
        header_p_key = PhysicalKey(Point(w / 2, h / 2), w, h)

        layout = 1 / scale_factor * self.layout + Point(0, h + self.cfg.inner_pad_h)
        layout.keys = [header_p_key, *layout.keys]

        layers = {}
        for ind, combo in enumerate(self.keymap.combos):
            empty_layer = [LayoutKey() for _ in range(len(self.layout))]
            if ghost_keys:
                for key_position in ghost_keys:
                    empty_layer[key_position].type = "ghost"
            for key_position in combo.key_positions:
                empty_layer[key_position].type = "held"

            header_l_key = combo.key
            header_l_key.type = " ".join([header_l_key.type, "combo-separate"])
            layers[f"combopos-{ind}"] = [combo.key] + empty_layer

        return layout, layers
