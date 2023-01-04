"""
Module that contains the KeymapDrawer class which takes a physical layout,
keymap with layers and optionally combo definitions, then can draw an SVG
representation of the keymap using these two.
"""
from math import copysign
from html import escape

from .keymap import KeymapData, ComboSpec, Layer, LayoutKey
from .physical_layout import Point, PhysicalKey
from .style import (
    SVG_STYLE,
    COMBO_W,
    COMBO_H,
    KEY_RX,
    KEY_RY,
    INNER_PAD_W,
    INNER_PAD_H,
    OUTER_PAD_W,
    OUTER_PAD_H,
    LINE_SPACING,
    ARC_RADIUS,
)


class KeymapDrawer:
    """Class that draws a keyboard representation in SVG."""

    def __init__(self, **kwargs) -> None:
        data = KeymapData.parse_obj(kwargs)
        self.layout = data.layout
        self.layers = data.layers

    @staticmethod
    def _draw_rect(p: Point, w: float, h: float, cls: str | None = None) -> None:
        class_str = f' class="{cls}"' if cls is not None else ""
        print(
            f'<rect rx="{KEY_RX}" ry="{KEY_RY}" x="{p.x - w / 2}" y="{p.y - h / 2}" '
            f'width="{w}" height="{h}"{class_str}/>'
        )

    @staticmethod
    def _draw_text(p: Point, text: str, cls: str | None = None) -> None:
        class_str = f' class="{cls}"' if cls is not None else ""
        words = text.split()
        if not words:
            return
        if len(words) == 1:
            print(f'<text x="{p.x}" y="{p.y}"{class_str}>{escape(words[0])}</text>')
            return
        print(f'<text x="{p.x}" y="{p.y}"{class_str}>')
        print(f'<tspan x="{p.x}" dy="-{(len(words) - 1) * 0.6}em">{escape(words[0])}</tspan>', end="")
        for word in words[1:]:
            print(f'<tspan x="{p.x}" dy="1.2em">{escape(word)}</tspan>', end="")
        print("</text>")

    @staticmethod
    def _draw_dendron(p_1: Point, p_2: Point, x_first: bool, shorten: float) -> None:
        start = f"M{p_1.x},{p_1.y}"
        arc_x = copysign(ARC_RADIUS, p_2.x - p_1.x)
        arc_y = copysign(ARC_RADIUS, p_2.y - p_1.y)
        clockwise = (p_2.x > p_1.x) ^ (p_2.y > p_1.y)
        if x_first:
            line_1 = f"h{p_2.x - p_1.x - arc_x}"
            line_2 = f"v{p_2.y - p_1.y - arc_y - copysign(shorten, p_2.y - p_1.y)}"
            clockwise = not clockwise
        else:
            line_1 = f"v{p_2.y - p_1.y - arc_y}"
            line_2 = f"h{p_2.x - p_1.x - arc_x - copysign(shorten, p_2.x - p_1.x)}"
        arc = f"a{ARC_RADIUS},{ARC_RADIUS} 0 0 {int(clockwise)} {arc_x},{arc_y}"
        print(f'<path d="{start} {line_1} {arc} {line_2}"/>')

    @classmethod
    def print_key(cls, p_0: Point, p_key: PhysicalKey, l_key: LayoutKey) -> None:
        """
        Given anchor coordinates p_0, print SVG code for a rectangle with text representing
        the key, which is described by its physical representation (p_key) and what it does in
        the given layer (l_key).
        """
        p, w, h, r = (
            p_0 + p_key.pos,
            p_key.width,
            p_key.height,
            p_key.rotation,
        )
        if r != 0:
            print(f'<g transform="rotate({r}, {p.x}, {p.y})">')
        cls._draw_rect(p, w - 2 * INNER_PAD_W, h - 2 * INNER_PAD_H, l_key.type)
        cls._draw_text(p, l_key.tap)
        cls._draw_text(p + Point(0, h / 2 - LINE_SPACING / 2), l_key.hold, cls="small")
        if r != 0:
            print("</g>")

    def print_combo(self, p_0: Point, combo_spec: ComboSpec) -> None:
        """
        Given anchor coordinates p_0, print SVG code for a rectangle with text representing
        a combo specification, which contains the key positions that trigger it and what it does
        when triggered. The position of the rectangle depends on the alignment specified,
        along with whether dendrons are drawn going to each key position from the combo.
        """
        p_keys = [self.layout.keys[p] for p in combo_spec.key_positions]
        n_keys = len(p_keys)

        # find center of combo box
        p_mid = Point(p_0.x, p_0.y)
        if combo_spec.align == "mid":
            p_mid.x += sum(k.pos.x for k in p_keys) / n_keys
            p_mid.y += sum(k.pos.y for k in p_keys) / n_keys
        if combo_spec.align == "upper":
            p_mid.x += sum(k.pos.x for k in p_keys) / n_keys
            p_mid.y += min(k.pos.y - k.height / 2 for k in p_keys) - INNER_PAD_H / 2
        if combo_spec.align == "lower":
            p_mid.x += sum(k.pos.x for k in p_keys) / n_keys
            p_mid.y += max(k.pos.y + k.height / 2 for k in p_keys) + INNER_PAD_H / 2
        if combo_spec.align == "left":
            p_mid.x += min(k.pos.x - k.width / 2 for k in p_keys) - INNER_PAD_W / 2
            p_mid.y += sum(k.pos.y for k in p_keys) / n_keys
        if combo_spec.align == "right":
            p_mid.x += max(k.pos.x + k.width / 2 for k in p_keys) + INNER_PAD_W / 2
            p_mid.y += sum(k.pos.y for k in p_keys) / n_keys

        # draw dendrons going from box to combo keys
        if combo_spec.align in ("upper", "lower"):
            for k in p_keys:
                offset = k.height / 5 if abs(p_0.x + k.pos.x - p_mid.x) < COMBO_W / 2 else k.height / 3
                self._draw_dendron(p_mid, p_0 + k.pos, True, offset)
        if combo_spec.align in ("left", "right"):
            for k in p_keys:
                offset = k.width / 5 if abs(p_0.y + k.pos.y - p_mid.y) < COMBO_H / 2 else k.width / 3
                self._draw_dendron(p_mid, p_0 + k.pos, False, offset)

        # draw combo box with text
        self._draw_rect(p_mid, COMBO_W, COMBO_H, "combo")
        self._draw_text(p_mid, combo_spec.key.tap, cls="small")

    def print_layer(self, p_0: Point, name: str, layer: Layer) -> None:
        """
        Given anchor coordinates p_0, print SVG code for keys and combos for a given layer,
        and a layer label (name) at the top.
        """
        self._draw_text(p_0 - Point(0, OUTER_PAD_H / 2), f"{name}:", cls="label")
        for p_key, l_key in zip(self.layout.keys, layer.keys):
            self.print_key(p_0, p_key, l_key)
        if layer.combos:
            for combo_spec in layer.combos:
                self.print_combo(p_0, combo_spec)

    def print_board(self) -> None:
        """Print SVG code representing the keymap."""
        board_w = self.layout.width + 2 * OUTER_PAD_W
        board_h = len(self.layers) * self.layout.height + (len(self.layers) + 1) * OUTER_PAD_H
        print(
            f'<svg width="{board_w}" height="{board_h}" viewBox="0 0 {board_w} {board_h}" '
            'xmlns="http://www.w3.org/2000/svg">'
        )
        print(f"<style>{SVG_STYLE}</style>")

        p = Point(OUTER_PAD_W, 0.0)
        for name, layer in self.layers.items():
            p.y += OUTER_PAD_H
            self.print_layer(p, name, layer)
            p.y += self.layout.height

        print("</svg>")
