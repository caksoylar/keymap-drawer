"""Module containing constants related to styling of produced SVG."""

KEY_W = 59
KEY_H = 54

SPLIT_GAP = KEY_W / 2

COMBO_W = KEY_W / 2 - 2
COMBO_H = KEY_H / 2 - 2
KEY_RX = 6
KEY_RY = 6
INNER_PAD_W = 2
INNER_PAD_H = 2
OUTER_PAD_W = KEY_W / 2
OUTER_PAD_H = KEY_H
LINE_SPACING = 18

ARC_RADIUS = 3

SVG_STYLE = """
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

    path {
        stroke-width: 1;
        stroke: gray;
        fill: none;
    }
"""
