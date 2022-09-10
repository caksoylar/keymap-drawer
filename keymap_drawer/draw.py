from itertools import chain
from html import escape
from typing import Optional

from .keymap import KeymapData, KeyRow, KeyBlock, Key, ComboSpec, Layer


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
        kd = KeymapData(**kwargs)
        self.layout = kd.layout
        self.layers = kd.layers

        self.block_w = self.layout.columns * KEYSPACE_W
        self.block_h = (self.layout.rows + (1 if self.layout.thumbs else 0)) * KEYSPACE_H
        self.layer_w = (2 if self.layout.split else 1) * self.block_w + OUTER_PAD_W
        self.layer_h = self.block_h
        self.board_w = self.layer_w + 2 * OUTER_PAD_W
        self.board_h = len(self.layers) * self.layer_h + (len(self.layers) + 1) * OUTER_PAD_H

    @staticmethod
    def _draw_rect(x: float, y: float, w: float, h: float, cls: Optional[str] = None) -> None:
        class_str = f' class="{cls}"' if cls is not None else ""
        print(f'<rect rx="{KEY_RX}" ry="{KEY_RY}" x="{x}" y="{y}" width="{w}" height="{h}"{class_str}/>')

    @staticmethod
    def _draw_text(x: float, y: float, text: str, cls: Optional[str] = None) -> None:
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

    def print_key(self, x: float, y: float, key: Key, width: int = 1) -> None:
        key_width = (width * KEY_W) + 2 * (width - 1) * INNER_PAD_W
        self._draw_rect(x + INNER_PAD_W, y + INNER_PAD_H, key_width, KEY_H, key.type)
        self._draw_text(x + INNER_PAD_W + key_width / 2, y + KEYSPACE_H / 2, key.tap)
        self._draw_text(x + INNER_PAD_W + key_width / 2, y + KEYSPACE_H - LINE_SPACING / 2, key.hold, cls="small")

    def print_combo(self, x: float, y: float, combo_spec: ComboSpec) -> None:
        pos_idx = combo_spec.positions

        cols = [self.layout.pos_to_col(p) for p in pos_idx]
        rows = [self.layout.pos_to_row(p) for p in pos_idx]
        x_pos = [
            x + c * KEYSPACE_W + (OUTER_PAD_W if self.layout.split and c >= self.layout.columns else 0) for c in cols
        ]
        y_pos = [y + r * KEYSPACE_H for r in rows]

        x_mid, y_mid = sum(x_pos) / len(pos_idx), sum(y_pos) / len(pos_idx)

        self._draw_rect(x_mid + INNER_PAD_W + KEY_W / 4, y_mid + INNER_PAD_H + KEY_H / 4, KEY_W / 2, KEY_H / 2, "combo")
        self._draw_text(x_mid + KEYSPACE_W / 2, y_mid + INNER_PAD_H + KEY_H / 2, combo_spec.key.tap, cls="small")

    def print_row(self, x: float, y: float, row: KeyRow) -> None:
        prev_key, width = None, 0
        for i, key in enumerate(chain(row, [None])):
            if i > 0 and (prev_key is None or key != prev_key or i == len(row)):
                self.print_key(x, y, prev_key or Key(tap=""), width=width)

                x += width * KEYSPACE_W
                width = 0

            prev_key = key
            width += 1

    def print_block(self, x: float, y: float, block: KeyBlock) -> None:
        for row in block:
            self.print_row(x, y, row)
            y += KEYSPACE_H

    def print_layer(self, x: float, y: float, name: str, layer: Layer) -> None:
        self._draw_text(KEY_W / 2, y - KEY_H / 2, f"{name}:", cls="label")
        self.print_block(x, y, layer.left)
        if layer.right:
            self.print_block(
                x + self.block_w + OUTER_PAD_W,
                y,
                layer.right,
            )
        if self.layout.thumbs and layer.left_thumbs and layer.right_thumbs:
            self.print_row(
                x + (self.layout.columns - self.layout.thumbs) * KEYSPACE_W,
                y + self.layout.rows * KEYSPACE_H,
                layer.left_thumbs,
            )
            self.print_row(x + self.block_w + OUTER_PAD_W, y + self.layout.rows * KEYSPACE_H, layer.right_thumbs)
        if layer.combos:
            for combo_spec in layer.combos:
                self.print_combo(x, y, combo_spec)

    def print_board(self) -> None:
        print(
            f'<svg width="{self.board_w}" height="{self.board_h}" viewBox="0 0 {self.board_w} {self.board_h}" '
            'xmlns="http://www.w3.org/2000/svg">'
        )
        print(f"<style>{STYLE}</style>")

        x, y = OUTER_PAD_W, 0
        for name, layer in self.layers.items():
            y += OUTER_PAD_H
            self.print_layer(x, y, name, layer)
            y += self.layer_h

        print("</svg>")
