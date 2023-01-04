"""Module containing constants related to styling of produced SVG."""

# key dimensions, non-ortho layouts use KEY_H for width as well
KEY_W = 60
KEY_H = 56

# gap between two halves for ortho layout generator
SPLIT_GAP = KEY_W / 2

# combo box dimensions
COMBO_W = KEY_W / 2 - 2
COMBO_H = KEY_H / 2 - 2

# curvature of rounded key rectangles
KEY_RX = 6
KEY_RY = 6

# padding between keys
INNER_PAD_W = 2
INNER_PAD_H = 2

# padding between layers
OUTER_PAD_W = KEY_W / 2
OUTER_PAD_H = KEY_H

# spacing between multi-line text in key labels
LINE_SPACING = 18

# curve radius for combo dendrons
ARC_RADIUS = 6

SVG_STYLE = """
    /* font and background color specifications */
    svg {
        font-family: SFMono-Regular,Consolas,Liberation Mono,Menlo,monospace;
        font-size: 14px;
        font-kerning: normal;
        text-rendering: optimizeLegibility;
        fill: #24292e;
    }

    /* default key styling */
    rect {
        fill: #f6f8fa;
        stroke: #d6d8da;
        stroke-width: 1;
    }

    /* color accent for held keys */
    .held {
        fill: #fdd;
    }

    /* color accent for combo boxes */
    .combo {
        fill: #cdf;
    }

    /* color accent for ghost (optional) keys */
    .ghost {
        fill: #ddd;
    }

    text {
        text-anchor: middle;
        dominant-baseline: middle;
    }

    /* styling for layer labels */
    .label {
        font-weight: bold;
        text-anchor: start;
        stroke: white;
        stroke-width: 2;
        paint-order: stroke;
    }

    /* styling for combo box label text */
    .small {
        font-size: 80%;
    }

    /* styling for combo dendrons */
    path {
        stroke-width: 1;
        stroke: gray;
        fill: none;
    }
"""
