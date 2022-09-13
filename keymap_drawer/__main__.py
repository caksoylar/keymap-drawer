"""
Script that takes a yaml containing physical keyboard layout and
keymap descriptions, then prints an SVG representing the keymap.
"""
import sys
import json
from ruamel import yaml

from .draw import KeymapDrawer


def main() -> None:
    """Parse the configuration and print SVG using KeymapDrawer."""
    with open(sys.argv[1], "rb") as f:
        data = yaml.safe_load(f)
    layers = data["layers"]
    if len(sys.argv) > 2:
        with open(sys.argv[2], 'rb') as f:
            qmk_json = json.load(f)
        layout = next(iter(qmk_json["layouts"].values()))["layout"]  # take the first layout in map
        drawer = KeymapDrawer(layers=data["layers"], layout={"ltype": "qmk", "layout": layout})
    else:
        drawer = KeymapDrawer(layers=layers, layout=data["layout"])
    drawer.print_board()


if __name__ == "__main__":
    main()
