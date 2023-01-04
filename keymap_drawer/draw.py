"""
Module that contains the KeymapDrawer class which takes a physical layout,
keymap with layers and optionally combo definitions, then can draw an SVG
representation of the keymap using these two.
"""
from math import copysign
from html import escape

from .keymap import KeymapData, ComboSpec, Layer, LayoutKey
from .physical_layout import PhysicalKey
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
    def _draw_rect(x: float, y: float, w: float, h: float, cls: str | None = None) -> None:
        class_str = f' class="{cls}"' if cls is not None else ""
        print(
            f'<rect rx="{KEY_RX}" ry="{KEY_RY}" x="{x - w / 2}" y="{y - h / 2}" '
            f'width="{w}" height="{h}"{class_str}/>'
        )

    @staticmethod
    def _draw_text(x: float, y: float, text: str, cls: str | None = None) -> None:
        class_str = f' class="{cls}"' if cls is not None else ""
        words = text.split()
        if not words:
            return
        if len(words) == 1:
            print(f'<text x="{x}" y="{y}"{class_str}>{escape(words[0])}</text>')
            return
        print(f'<text x="{x}" y="{y}"{class_str}>')
        print(f'<tspan x="{x}" dy="-{(len(words) - 1) * 0.6}em">{escape(words[0])}</tspan>', end="")
        for word in words[1:]:
            print(f'<tspan x="{x}" dy="1.2em">{escape(word)}</tspan>', end="")
        print("</text>")

    @staticmethod
    def _draw_dendron(x_1: float, y_1: float, x_2: float, y_2: float, x_first: bool, shorten: float) -> None:
        start = f"M{x_1},{y_1}"
        arc_x = copysign(ARC_RADIUS, x_2 - x_1)
        arc_y = copysign(ARC_RADIUS, y_2 - y_1)
        clockwise = (x_2 > x_1) ^ (y_2 > y_1)
        if x_first:
            line_1 = f"h{x_2 - x_1 - arc_x}"
            line_2 = f"v{y_2 - y_1 - arc_y - copysign(shorten, y_2 - y_1)}"
            clockwise = not clockwise
        else:
            line_1 = f"v{y_2 - y_1 - arc_y}"
            line_2 = f"h{x_2 - x_1 - arc_x - copysign(shorten, x_2 - x_1)}"
        arc = f"a{ARC_RADIUS},{ARC_RADIUS} 0 0 {int(clockwise)} {arc_x},{arc_y}"
        print(f'<path d="{start} {line_1} {arc} {line_2}"/>')

    @classmethod
    def print_key(cls, x_0: float, y_0: float, p_key: PhysicalKey, l_key: LayoutKey) -> None:
        """
        Given anchor coordinates x_0/y_0, print SVG code for a rectangle with text representing
        the key, which is described by its physical representation (p_key) and what it does in
        the given layer (l_key).
        """
        x, y, w, h, r = (
            x_0 + p_key.x_pos,
            y_0 + p_key.y_pos,
            p_key.width,
            p_key.height,
            p_key.rotation,
        )
        if r != 0:
            print(f'<g transform="rotate({r}, {x}, {y})">')
        cls._draw_rect(x, y, w - 2 * INNER_PAD_W, h - 2 * INNER_PAD_H, l_key.type)
        cls._draw_text(x, y, l_key.tap)
        cls._draw_text(x, y + h / 2 - LINE_SPACING / 2, l_key.hold, cls="small")
        if r != 0:
            print("</g>")

    def print_combo(self, x_0: float, y_0: float, combo_spec: ComboSpec) -> None:
        """
        Given anchor coordinates x_0/y_0, print SVG code for a rectangle with text representing
        a combo specification, which contains the key positions that trigger it and what it does
        when triggered. The rectangle is drawn at the midpoint of the physical representations
        of the key positions.
        """
        pos_idx = combo_spec.key_positions
        n_keys = len(pos_idx)

        p_keys = [self.layout.keys[p] for p in pos_idx]

        x_mid, y_mid = x_0, y_0
        x_mid += sum(k.x_pos for k in p_keys) / n_keys
        if combo_spec.align == "mid":
            y_mid += sum(k.y_pos for k in p_keys) / n_keys
        if combo_spec.align == "upper":
            y_mid += min(k.y_pos - k.height / 2 for k in p_keys) - INNER_PAD_H / 2
        if combo_spec.align == "lower":
            y_mid += max(k.y_pos + k.height / 2 for k in p_keys) + INNER_PAD_H / 2
        if combo_spec.align != "mid":
            for k in p_keys:
                offset = k.height / 5 if x_0 + k.x_pos == x_mid else k.height / 3
                self._draw_dendron(x_mid, y_mid, x_0 + k.x_pos, y_0 + k.y_pos, True, offset)

        self._draw_rect(x_mid, y_mid, COMBO_W, COMBO_H, "combo")
        self._draw_text(x_mid, y_mid, combo_spec.key.tap, cls="small")

    def print_layer(self, x_0: float, y_0: float, name: str, layer: Layer) -> None:
        """
        Given anchor coordinates x_0/y_0, print SVG code for keys and combos for a given layer,
        and a layer label (name) at the top.
        """
        self._draw_text(OUTER_PAD_W, y_0 - OUTER_PAD_H / 2, f"{name}:", cls="label")
        for p_key, l_key in zip(self.layout.keys, layer.keys):
            self.print_key(x_0, y_0, p_key, l_key)
        if layer.combos:
            for combo_spec in layer.combos:
                self.print_combo(x_0, y_0, combo_spec)

    def print_board(self) -> None:
        """Print SVG code representing the keymap."""
        board_w = self.layout.width + 2 * OUTER_PAD_W
        board_h = len(self.layers) * self.layout.height + (len(self.layers) + 1) * OUTER_PAD_H
        print(
            f'<svg width="{board_w}" height="{board_h}" viewBox="0 0 {board_w} {board_h}" '
            'xmlns="http://www.w3.org/2000/svg">'
        )
        print(f"<style>{SVG_STYLE}</style>")

        x, y = OUTER_PAD_W, 0.0
        for name, layer in self.layers.items():
            y += OUTER_PAD_H
            self.print_layer(x, y, name, layer)
            y += self.layout.height

        print("</svg>")
