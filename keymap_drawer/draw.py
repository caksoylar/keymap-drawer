"""
Module that contains the KeymapDrawer class which takes a physical layout,
keymap with layers and optionally combo definitions, then can draw an SVG
representation of the keymap using these two.
"""
from math import copysign
from html import escape

from .keymap import KeymapData, ComboSpec, Layer, LayoutKey
from .physical_layout import Point, PhysicalKey
from .config import DrawConfig


class KeymapDrawer:
    """Class that draws a keyboard representation in SVG."""

    def __init__(self, config: DrawConfig, **kwargs) -> None:
        self.cfg = config
        data = KeymapData(config=config, **kwargs)
        self.layout = data.layout
        self.layers = data.layers

    def _draw_rect(self, p: Point, w: float, h: float, cls: str | None = None) -> None:
        class_str = f' class="{cls}"' if cls is not None else ""
        print(
            f'<rect rx="{self.cfg.key_rx}" ry="{self.cfg.key_ry}" x="{p.x - w / 2}" y="{p.y - h / 2}" '
            f'width="{w}" height="{h}"{class_str}/>'
        )

    @staticmethod
    def _draw_text(p: Point, text: str, cls: str | None = None) -> None:
        if not (words := text.split()):
            return
        class_str = f' class="{cls}"' if cls is not None else ""
        if len(words) == 1:
            print(f'<text x="{p.x}" y="{p.y}"{class_str}>{escape(words[0])}</text>')
            return
        print(f'<text x="{p.x}" y="{p.y}"{class_str}>')
        print(f'<tspan x="{p.x}" dy="-{(len(words) - 1) * 0.6}em">{escape(words[0])}</tspan>', end="")
        for word in words[1:]:
            print(f'<tspan x="{p.x}" dy="1.2em">{escape(word)}</tspan>', end="")
        print("</text>")

    def _draw_arc_dendron(self, p_1: Point, p_2: Point, x_first: bool, shorten: float) -> None:
        start = f"M{p_1.x},{p_1.y}"
        arc_x = copysign(self.cfg.arc_radius, p_2.x - p_1.x)
        arc_y = copysign(self.cfg.arc_radius, p_2.y - p_1.y)
        clockwise = (p_2.x > p_1.x) ^ (p_2.y > p_1.y)
        if x_first:
            line_1 = f"h{self.cfg.arc_scale * (p_2.x - p_1.x) - arc_x}"
            line_2 = f"v{p_2.y - p_1.y - arc_y - copysign(shorten, p_2.y - p_1.y)}"
            clockwise = not clockwise
        else:
            line_1 = f"v{self.cfg.arc_scale * (p_2.y - p_1.y) - arc_y}"
            line_2 = f"h{p_2.x - p_1.x - arc_x - copysign(shorten, p_2.x - p_1.x)}"
        arc = f"a{self.cfg.arc_radius},{self.cfg.arc_radius} 0 0 {int(clockwise)} {arc_x},{arc_y}"
        print(f'<path d="{start} {line_1} {arc} {line_2}"/>')

    @staticmethod
    def _draw_line_dendron(p_1: Point, p_2: Point, shorten: float) -> None:
        start = f"M{p_1.x},{p_1.y}"
        diff = p_2 - p_1
        if shorten and shorten < (magn := abs(diff)):
            diff = Point((1 - shorten / magn) * diff.x, (1 - shorten / magn) * diff.y)
        line = f"l{diff.x},{diff.y}"
        print(f'<path d="{start} {line}"/>')

    def print_key(self, p_0: Point, p_key: PhysicalKey, l_key: LayoutKey) -> None:
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
        self._draw_rect(p, w - 2 * self.cfg.inner_pad_w, h - 2 * self.cfg.inner_pad_h, l_key.type)
        self._draw_text(p, l_key.tap)
        self._draw_text(p + Point(0, h / 2 - self.cfg.line_spacing / 2), l_key.hold, cls="small")
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
        match combo_spec.align:
            case "mid":
                p_mid.x += sum(k.pos.x for k in p_keys) / n_keys
                p_mid.y += sum(k.pos.y for k in p_keys) / n_keys
            case "upper":
                p_mid.x += sum(k.pos.x for k in p_keys) / n_keys
                p_mid.y += min(k.pos.y - k.height / 2 for k in p_keys) - self.cfg.inner_pad_h / 2
                p_mid.y -= combo_spec.offset * self.layout.min_height
            case "lower":
                p_mid.x += sum(k.pos.x for k in p_keys) / n_keys
                p_mid.y += max(k.pos.y + k.height / 2 for k in p_keys) + self.cfg.inner_pad_h / 2
                p_mid.y += combo_spec.offset * self.layout.min_height
            case "left":
                p_mid.x += min(k.pos.x - k.width / 2 for k in p_keys) - self.cfg.inner_pad_w / 2
                p_mid.y += sum(k.pos.y for k in p_keys) / n_keys
                p_mid.x -= combo_spec.offset * self.layout.min_width
            case "right":
                p_mid.x += max(k.pos.x + k.width / 2 for k in p_keys) + self.cfg.inner_pad_w / 2
                p_mid.y += sum(k.pos.y for k in p_keys) / n_keys
                p_mid.x += combo_spec.offset * self.layout.min_width

        # draw dendrons going from box to combo keys
        if combo_spec.dendron is not False:
            match combo_spec.align:
                case "upper" | "lower":
                    for k in p_keys:
                        offset = k.height / 5 if abs(p_0.x + k.pos.x - p_mid.x) < self.cfg.combo_w / 2 else k.height / 3
                        self._draw_arc_dendron(p_mid, p_0 + k.pos, True, offset)
                case "left" | "right":
                    for k in p_keys:
                        offset = k.width / 5 if abs(p_0.y + k.pos.y - p_mid.y) < self.cfg.combo_h / 2 else k.width / 3
                        self._draw_arc_dendron(p_mid, p_0 + k.pos, False, offset)
                case "mid":
                    for k in p_keys:
                        if combo_spec.dendron is True or abs(p_0 + k.pos - p_mid) >= k.width - 1:
                            self._draw_line_dendron(p_mid, p_0 + k.pos, k.width / 3)

        # draw combo box with text
        self._draw_rect(p_mid, self.cfg.combo_w, self.cfg.combo_h, "combo")
        self._draw_text(p_mid, combo_spec.key.tap, cls="small")
        self._draw_text(
            p_mid + Point(0, self.cfg.combo_h / 2 - self.cfg.line_spacing / 5), combo_spec.key.hold, cls="smaller"
        )

    def print_layer(self, p_0: Point, name: str, layer: Layer) -> None:
        """
        Given anchor coordinates p_0, print SVG code for keys and combos for a given layer,
        and a layer label (name) at the top.
        """
        self._draw_text(p_0 - Point(0, self.cfg.outer_pad_h / 2), f"{name}:", cls="label")
        for p_key, l_key in zip(self.layout.keys, layer.keys):
            self.print_key(p_0, p_key, l_key)
        if layer.combos:
            for combo_spec in layer.combos:
                self.print_combo(p_0, combo_spec)

    def print_board(self) -> None:
        """Print SVG code representing the keymap."""
        board_w = self.layout.width + 2 * self.cfg.outer_pad_w
        board_h = len(self.layers) * self.layout.height + (len(self.layers) + 1) * self.cfg.outer_pad_h
        print(
            f'<svg width="{board_w}" height="{board_h}" viewBox="0 0 {board_w} {board_h}" '
            'xmlns="http://www.w3.org/2000/svg">'
        )
        print(f"<style>{self.cfg.svg_style}</style>")

        p = Point(self.cfg.outer_pad_w, 0.0)
        for name, layer in self.layers.items():
            p.y += self.cfg.outer_pad_h
            self.print_layer(p, name, layer)
            p.y += self.layout.height

        print("</svg>")
