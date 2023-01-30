"""
Given keymap description with layers and combos (in a yaml), and physical
keyboard layout definition (either via QMK info files or using a parametrized
ortho layout), print an SVG representing the keymap to standard output.
"""
import sys
import json
import argparse
from importlib.metadata import version
from urllib.request import urlopen

import yaml

from .config import Config, DrawConfig, ParseConfig
from .draw import KeymapDrawer
from .parse import QmkJsonParser, ZmkKeymapParser


def draw(args, config: DrawConfig) -> None:
    """Draw the keymap in SVG format to stdout."""
    with sys.stdin.buffer if args.keymap_yaml == "-" else open(args.keymap_yaml, "rb") as f:
        yaml_data = yaml.safe_load(f)
        assert "layers" in yaml_data, 'Keymap needs to be specified via the "layers" field in keymap_yaml'

    qmk_keyboard = args.qmk_keyboard or yaml_data.get("layout", {}).get("qmk_keyboard")
    qmk_layout = args.qmk_layout or yaml_data.get("layout", {}).get("qmk_layout")
    ortho_layout = args.ortho_layout or yaml_data.get("layout", {}).get("ortho_layout")

    if qmk_keyboard or args.qmk_info_json:
        if qmk_keyboard:
            with urlopen(f"https://keyboards.qmk.fm/v1/keyboards/{qmk_keyboard}/info.json") as f:
                qmk_info = json.load(f)["keyboards"][qmk_keyboard]
        else:
            with open(args.qmk_info_json, "rb") as f:
                qmk_info = json.load(f)

        if qmk_layout is None:
            layout = next(iter(qmk_info["layouts"].values()))["layout"]  # take the first layout in map
        else:
            layout = qmk_info["layouts"][qmk_layout]["layout"]
        layout = {"ltype": "qmk", "layout": layout}
    elif ortho_layout:
        layout = {"ltype": "ortho", **ortho_layout}
    else:
        raise ValueError(
            "A physical layout needs to be specified either via --qmk-keyboard/--qmk-layout/--ortho-layout, "
            'or in a "layout" field in the keymap_yaml'
        )

    if custom_config := yaml_data.get("draw_config"):
        config = config.copy(update=custom_config)

    drawer = KeymapDrawer(
        config=config, out=sys.stdout, layers=yaml_data["layers"], layout=layout, combos=yaml_data.get("combos", [])
    )
    drawer.print_board()


def parse(args, config: ParseConfig) -> None:
    """Call the appropriate parser for given args and dump YAML keymap representation to stdout."""
    if args.qmk_keymap_json:
        parsed = QmkJsonParser(config, args.columns).parse(args.qmk_keymap_json)
    else:
        parsed = ZmkKeymapParser(config, args.columns).parse(args.zmk_keymap)

    yaml.safe_dump(parsed, sys.stdout, indent=4, width=160, sort_keys=False, default_flow_style=None)


def dump_config(config: Config) -> None:
    """Dump the currently active config, either default or parsed from args."""

    def cfg_str_representer(dumper, in_str):
        if "\n" in in_str:  # use '|' style for multiline strings
            return dumper.represent_scalar("tag:yaml.org,2002:str", in_str, style="|")
        return dumper.represent_scalar("tag:yaml.org,2002:str", in_str)

    yaml.representer.SafeRepresenter.add_representer(str, cfg_str_representer)
    yaml.safe_dump(config.dict(), sys.stdout, indent=4, default_flow_style=False)


def main() -> None:
    """Parse the configuration and print SVG using KeymapDrawer."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-v", "--version", action="version", version=version("keymap-drawer"))
    parser.add_argument(
        "-c",
        "--config",
        help="A YAML file containing settings for parsing and drawing, "
        "default can be dumped using `dump-config` command and to be modified",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    draw_p = subparsers.add_parser("draw", help="draw an SVG representation of the keymap")
    info_srcs = draw_p.add_mutually_exclusive_group()
    info_srcs.add_argument(
        "-j", "--qmk-info-json", help="Path to QMK info.json for a keyboard, containing the physical layout description"
    )
    info_srcs.add_argument(
        "-k",
        "--qmk-keyboard",
        help="Name of the keyboard in QMK to fetch info.json containing the physical layout info, "
        "including revision if any",
    )
    draw_p.add_argument(
        "-l",
        "--qmk-layout",
        help='Name of the layout (starting with "LAYOUT_") to use in the QMK keyboard info file, '
        "use the first defined one by default",
    )
    draw_p.add_argument(
        "-o",
        "--ortho-layout",
        help="Parametrized ortholinear layout definition in a YAML format, "
        "for example '{split: false, rows: 4, columns: 12}'",
        type=yaml.safe_load,
    )
    draw_p.add_argument(
        "keymap_yaml",
        help='YAML file (or stdin for "-") containing keymap definition with layers and (optionally) combos, '
        "see README for schema",
    )

    parse_p = subparsers.add_parser(
        "parse", help="parse a QMK/ZMK keymap to YAML representation to stdout, to be used with the `draw` command"
    )
    keymap_srcs = parse_p.add_mutually_exclusive_group(required=True)
    keymap_srcs.add_argument("-q", "--qmk-keymap-json", help="Path to QMK keymap.json to parse")
    keymap_srcs.add_argument("-z", "--zmk-keymap", help="Path to ZMK *.keymap to parse")
    parse_p.add_argument(
        "-c",
        "--columns",
        help="Number of columns in the layout to enable better key grouping in the output, optional",
        type=int,
    )

    _ = subparsers.add_parser(
        "dump-config", help="dump default draw and parse config to stdout that can be passed to -c/--config option"
    )

    args = parser.parse_args()

    if args.config:
        with sys.stdin.buffer if args.config == "-" else open(args.config, "rb") as f:
            config = Config.parse_obj(yaml.safe_load(f))
    else:
        config = Config()

    match args.command:
        case "draw":
            draw(args, config.draw_config)
        case "parse":
            parse(args, config.parse_config)
        case "dump-config":
            dump_config(config)


if __name__ == "__main__":
    main()
