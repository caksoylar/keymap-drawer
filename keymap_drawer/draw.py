from html import escape

from .keymap import KeymapData, ComboSpec, Layer, LayoutKey
from .physical_layout import PhysicalKey


KEY_W = 55
KEY_H = 50
KEY_RX = 6
KEY_RY = 6
INNER_PAD_W = 2
INNER_PAD_H = 2
OUTER_PAD_W = KEY_W / 2
OUTER_PAD_H = KEY_H
KEYSPACE_W = KEY_W + 2 * INNER_PAD_W
KEYSPACE_H = KEY_H + 2 * INNER_PAD_H
LINE_SPACING = 18

STYLE = """
    svg {
        font-family: SFMono-Regular,Consolas,Liberation Mono,Menlo,monospace;
        font-size: 14px;
        font-kerning: normal;
        text-rendering: optimizeLegibility;
        fill: #24292e;
    }

    rect {
        fill: #f6f8fa;
        stroke: #d6d8da;
        stroke-width: 1;
    }

    .held {
        fill: #fdd;
    }

    .combo {
        fill: #cdf;
    }

    .ghost {
        fill: #ddd;
    }

    text {
        text-anchor: middle;
        dominant-baseline: middle;
    }

    .label {
        font-weight: bold;
        text-anchor: start;
        stroke: white;
        stroke-width: 2;
        paint-order: stroke;
    }

    .small {
        font-size: 80%;
    }
"""


class KeymapDrawer:
    def __init__(self, **kwargs) -> None:
        data = KeymapData(**kwargs)
        self.layout = data.layout
        self.layers = data.layers

    @staticmethod
    def _draw_rect(x: float, y: float, w: float, h: float, cls: str | None = None) -> None:
        class_str = f' class="{cls}"' if cls is not None else ""
        print(f'<rect rx="{KEY_RX}" ry="{KEY_RY}" x="{x - w / 2}" y="{y - h / 2}" width="{w}" height="{h}"{class_str}/>')

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
            print(f'<tspan x="{x}" dy="1.2em">{escape(word)}</tspan>')
        print("</text>")

    @classmethod
    def print_key(cls, x_0: float, y_0: float, p_key: PhysicalKey, l_key: LayoutKey) -> None:
        x, y, w, h = x_0 + p_key.x_pos, y_0 + p_key.y_pos, p_key.width, p_key.height
        cls._draw_rect(x + w/2, y + h/2, w, h, l_key.type)
        cls._draw_text(x + w / 2, y + h / 2, l_key.tap)
        cls._draw_text(x + w / 2, y + h - LINE_SPACING / 2, l_key.hold, cls="small")

    def print_combo(self, x_0: float, y_0: float, combo_spec: ComboSpec) -> None:
        pos_idx = combo_spec.positions

        p_keys = [self.layout.keys[p] for p in pos_idx]
        x_pos = [k.x_pos + k.width / 2 for k in p_keys]
        y_pos = [k.y_pos + k.height / 2 for k in p_keys]

        x_mid, y_mid = x_0 + sum(x_pos) / len(pos_idx), y_0 + sum(y_pos) / len(pos_idx)

        self._draw_rect(x_mid, y_mid, KEY_W / 2, KEY_H / 2, "combo")
        self._draw_text(x_mid + INNER_PAD_W / 2, y_mid, combo_spec.key.tap, cls="small")

    def print_layer(self, x_0: float, y_0: float, name: str, layer: Layer) -> None:
        self._draw_text(KEY_W / 2, y_0 - KEY_H / 2, f"{name}:", cls="label")
        for p_key, l_key in zip(self.layout.keys, layer.keys):
            self.print_key(x_0, y_0, p_key, l_key)
        if layer.combos:
            for combo_spec in layer.combos:
                self.print_combo(x_0, y_0, combo_spec)

    def print_board(self) -> None:
        board_w = self.layout.width + 2 * OUTER_PAD_W
        board_h = len(self.layers) * self.layout.height + (len(self.layers) + 1) * OUTER_PAD_H
        print(
            f'<svg width="{board_w}" height="{board_h}" viewBox="0 0 {board_w} {board_h}" '
            'xmlns="http://www.w3.org/2000/svg">'
        )
        print(f"<style>{STYLE}</style>")

        x, y = OUTER_PAD_W, 0.0
        for name, layer in self.layers.items():
            y += OUTER_PAD_H
            self.print_layer(x, y, name, layer)
            y += self.layout.height

        print("</svg>")
