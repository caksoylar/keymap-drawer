"""
Given keymap description with layers and combos (in a yaml), and physical
keyboard layout definition (either via QMK info files or with parameters
specified in the aforementioned yaml), print an SVG representing the keymap
to standard output.
"""
import json
import argparse
from urllib.request import urlopen

from ruamel import yaml

from .draw import KeymapDrawer


def main() -> None:
    """Parse the configuration and print SVG using KeymapDrawer."""
    parser = argparse.ArgumentParser(description=__doc__)
    info_srcs = parser.add_mutually_exclusive_group()
    info_srcs.add_argument(
        "-j", "--qmk-info-json", help="Path to QMK info.json for a keyboard, containing the physical layout description"
    )
    info_srcs.add_argument(
        "-k",
        "--qmk-keyboard",
        help="Name of the keyboard in QMK to fetch info.json containing the physical layout info, "
        "including revision if any",
    )
    parser.add_argument(
        "-l",
        "--qmk-layout",
        help='Name of the layout (starting with "LAYOUT_") to use in the QMK keyboard info file, '
        "use the first defined one by default",
    )
    parser.add_argument(
        "layout_yaml",
        help="YAML file containing keymap definition with layers and (optionally) combos, see examples for schema",
    )

    args = parser.parse_args()

    with open(args.layout_yaml, "rb") as f:
        yaml_data = yaml.safe_load(f)

    if args.qmk_keyboard or args.qmk_info_json:
        if args.qmk_keyboard:
            with urlopen(f"https://keyboards.qmk.fm/v1/keyboards/{args.qmk_keyboard}/info.json") as f:
                qmk_info = json.load(f)["keyboards"][args.qmk_keyboard]
        else:
            with open(args.qmk_info_json, "rb") as f:
                qmk_info = json.load(f)

        if args.qmk_layout is None:
            layout = next(iter(qmk_info["layouts"].values()))["layout"]  # take the first layout in map
        else:
            layout = qmk_info["layouts"][args.qmk_layout]["layout"]
        layout = {"ltype": "qmk", "layout": layout}
    else:
        layout = {"ltype": "ortho", **yaml_data["layout"]}

    drawer = KeymapDrawer(layers=yaml_data["layers"], layout=layout, combos=yaml_data.get("combos", []))
    drawer.print_board()


if __name__ == "__main__":
    main()
