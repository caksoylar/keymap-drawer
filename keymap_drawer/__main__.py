"""
Command line interface for parse and draw functionalities of the keymap-drawer module.
"""
import sys
from pathlib import Path
from importlib.metadata import version

import yaml
from typer import Typer, Option, FileText, Exit

from .config import Config
from .keymap import KeymapData
from .draw import KeymapDrawer
from .parse import QmkJsonParser, ZmkKeymapParser


cli = Typer(no_args_is_help=True)
config_obj = Config()


def version_callback(show: bool) -> None:
    """Print the version and exit."""
    if show:
        print(f"keymap-drawer version: {version('keymap-drawer')}")
        raise Exit()


@cli.callback()
def main(
    show_version: bool = Option(  # pylint: disable=unused-argument
        False, "-v", "--version", callback=version_callback, is_eager=True
    ),
    config: FileText = Option(
        None,
        "-c",
        help="A YAML file containing settings for parsing and drawing, "
        "default can be dumped using `dump-config` command and modified",
    ),
) -> None:
    """
    A command-line utility to parse keyboard keymap files into an intermediate
    keymap representation in YAML format, or draw a layout diagram in SVG format given
    such a representation.
    """
    if config:
        global config_obj  # pylint: disable=global-statement
        config_obj = Config.parse_obj(yaml.safe_load(config))


@cli.command(short_help="draw an SVG representation of the keymap")
def draw(  # pylint: disable=too-many-arguments
    keymap_yaml: FileText,
    qmk_keyboard: str = Option(
        None,
        "-k",
        "--qmk-keyboard",
        help="Name of the keyboard in QMK to fetch info.json containing the physical layout info, "
        "including revision if any",
    ),
    qmk_info_json: Path = Option(
        None,
        "-j",
        "--qmk-info-json",
        help="Path to QMK info.json for a keyboard, containing the physical layout description",
    ),
    qmk_layout: str = Option(
        None,
        "-l",
        "--qmk-layout",
        help='Name of the layout (starting with "LAYOUT_") to use in the QMK keyboard info file, '
        "use the first defined one by default",
    ),
    ortho_layout: str = Option(
        None,
        "-o",
        "--ortho-layout",
        help="Parametrized ortholinear layout definition in a YAML format, "
        "for example '{split: false, rows: 4, columns: 12}'",
    ),
    select_layers: list[str] = Option(
        None, "-s", "--select-layers", help="A list of layer names to draw, draw all by default"
    ),
    keys_only: bool = Option(False, help="Only draw keys, not combos on layers"),
    combos_only: bool = Option(False, help="Only draw combos, not keys on layers"),
) -> None:
    """Draw the keymap provided by the KEYMAP_YAML argument in SVG format to stdout."""
    if ortho_layout:
        ortho_layout = yaml.safe_load(ortho_layout)

    yaml_data = yaml.safe_load(keymap_yaml)
    assert "layers" in yaml_data, 'Keymap needs to be specified via the "layers" field in keymap_yaml'

    if qmk_keyboard or qmk_info_json or ortho_layout:
        layout = {
            "qmk_keyboard": qmk_keyboard,
            "qmk_info_json": qmk_info_json,
            "qmk_layout": qmk_layout,
            "ortho_layout": ortho_layout,
        }
    else:
        assert "layout" in yaml_data, (
            "A physical layout needs to be specified either via --qmk-keyboard/--qmk-info-json/--ortho-layout, "
            'or in a "layout" field in the keymap_yaml'
        )
        layout = yaml_data["layout"]

    config = config_obj.draw_config
    if custom_config := yaml_data.get("draw_config"):
        config = config.copy(update=custom_config)

    drawer = KeymapDrawer(
        config=config, out=sys.stdout, layers=yaml_data["layers"], layout=layout, combos=yaml_data.get("combos", [])
    )
    drawer.print_board(draw_layers=select_layers or None, keys_only=keys_only, combos_only=combos_only)


@cli.command(short_help="parse a QMK/ZMK keymap to YAML representation")
def parse(
    qmk_keymap_json: FileText = Option(None, "-q", "--qmk-keymap-json", help="Path to QMK keymap.json to parse"),
    zmk_keymap: FileText = Option(None, "-z", "--zmk-keymap", help="Path to ZMK *.keymap to parse"),
    base_keymap: FileText = Option(
        None, "-b", "--base-keymap", help="A base keymap YAML to inherit certain properties from"
    ),
    layer_names: list[str] = Option(
        None,
        "-l",
        "--layer-names",
        help="List of layer names to override parsed names; its length should match the number of layers",
    ),
    columns: int = Option(
        0, "-c", "--columns", help="Number of columns in the layout to enable better key grouping in the output"
    ),
) -> None:
    """
    Parse a QMK/ZMK keymap to YAML representation to be used with the `draw` command to stdout.
    Either qmk_keymap_json or zmk_keymap is required.
    """
    if base_keymap:
        yaml_data = yaml.safe_load(base_keymap)
        base = KeymapData(layers=yaml_data["layers"], combos=yaml_data.get("combos", []), layout=None, config=None)
    else:
        base = None

    if qmk_keymap_json:
        parsed = QmkJsonParser(
            config_obj.parse_config, columns, base_keymap=base, layer_names=layer_names or None
        ).parse(qmk_keymap_json)
    else:
        assert zmk_keymap is not None, "Please provide either a QMK or ZMK keymap to parse"
        parsed = ZmkKeymapParser(config_obj.parse_config, columns, base_keymap=base, layer_names=layer_names).parse(
            zmk_keymap
        )

    yaml.safe_dump(parsed, sys.stdout, indent=2, width=160, sort_keys=False, default_flow_style=None)


@cli.command(short_help="dump default draw and parse config")
def dump_config() -> None:
    """Dump default draw and parse config to stdout that can be passed to -c/--config option."""

    def cfg_str_representer(dumper, in_str):
        if "\n" in in_str:  # use '|' style for multiline strings
            return dumper.represent_scalar("tag:yaml.org,2002:str", in_str, style="|")
        return dumper.represent_scalar("tag:yaml.org,2002:str", in_str)

    yaml.representer.SafeRepresenter.add_representer(str, cfg_str_representer)
    yaml.safe_dump(config_obj.dict(), sys.stdout, indent=2, default_flow_style=False)


if __name__ == "__main__":
    cli()
