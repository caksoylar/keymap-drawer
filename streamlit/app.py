"""Simple streamlit app for interactive drawing."""
import os
import base64
import io
import json
import zipfile
from tempfile import TemporaryDirectory
from pathlib import PurePosixPath
from urllib.parse import urlsplit
from urllib.request import urlopen

import yaml
import streamlit as st

from keymap_drawer.draw import KeymapDrawer
from keymap_drawer.config import Config, DrawConfig, ParseConfig
from keymap_drawer.parse import QmkJsonParser, ZmkKeymapParser


@st.cache
def svg_to_html(svg_string: str) -> str:
    """Convert SVG string in SVG/XML format to one embedded in a img tag."""
    b64 = base64.b64encode(svg_string.encode("utf-8")).decode("utf-8")
    return f'<img src="data:image/svg+xml;base64,{b64}"/>'


@st.cache
def _get_qmk_keyboard(qmk_keyboard: str) -> dict:
    with urlopen(f"https://keyboards.qmk.fm/v1/keyboards/{qmk_keyboard}/info.json") as f:
        return json.load(f)["keyboards"][qmk_keyboard]


@st.cache
def draw(yaml_str: str, config: DrawConfig) -> str:
    """Given a YAML keymap string, draw the keymap in SVG format to a string."""
    yaml_data = yaml.safe_load(yaml_str)
    assert "layers" in yaml_data, 'Keymap needs to be specified via the "layers" field in keymap_yaml'

    qmk_keyboard = yaml_data.get("layout", {}).get("qmk_keyboard")
    qmk_layout = yaml_data.get("layout", {}).get("qmk_layout")
    ortho_layout = yaml_data.get("layout", {}).get("ortho_layout")

    if qmk_keyboard:
        qmk_info = _get_qmk_keyboard(qmk_keyboard)
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

    with io.StringIO() as out:
        drawer = KeymapDrawer(
            config=config, out=out, layers=yaml_data["layers"], layout=layout, combos=yaml_data.get("combos", [])
        )
        drawer.print_board()
        return out.getvalue()


@st.cache
def get_example_yamls() -> dict[str, str]:
    out = {}
    examples_path = f"{os.path.dirname(__file__)}/../examples"
    for filename in sorted(os.listdir(examples_path)):
        full_path = f"{examples_path}/{filename}"
        if os.path.isfile(full_path):
            with open(full_path, encoding="utf-8") as f:
                out[filename] = f.read()
    return out


@st.cache
def get_default_config() -> str:
    def cfg_str_representer(dumper, in_str):
        if "\n" in in_str:  # use '|' style for multiline strings
            return dumper.represent_scalar("tag:yaml.org,2002:str", in_str, style="|")
        return dumper.represent_scalar("tag:yaml.org,2002:str", in_str)

    yaml.representer.SafeRepresenter.add_representer(str, cfg_str_representer)
    with io.StringIO() as out:
        yaml.safe_dump(Config().dict(), out, indent=4, default_flow_style=False)
        return out.getvalue()


@st.cache
def parse_config(config: str) -> Config:
    return Config.parse_obj(yaml.safe_load(config))


@st.cache
def parse_qmk_to_yaml(qmk_keymap_buf: io.BytesIO, config: ParseConfig, num_cols: int) -> str:
    parsed = QmkJsonParser(config, num_cols).parse(qmk_keymap_buf)
    with io.StringIO() as out:
        yaml.safe_dump(parsed, out, indent=4, width=160, sort_keys=False, default_flow_style=None)
        return out.getvalue()


@st.cache
def parse_zmk_to_yaml(zmk_keymap: str | io.BytesIO, config: ParseConfig, num_cols: int) -> str:
    parsed = ZmkKeymapParser(config, num_cols).parse(zmk_keymap)
    with io.StringIO() as out:
        yaml.safe_dump(parsed, out, indent=4, width=160, sort_keys=False, default_flow_style=None)
        return out.getvalue()


@st.cache
def _get_zmk_zip(zmk_url: str) -> bytes:
    if not zmk_url.startswith("https") and not zmk_url.startswith("//"):
        zmk_url = "//" + zmk_url
    split_url = urlsplit(zmk_url, scheme="https")
    path = PurePosixPath(split_url.path)
    assert split_url.netloc == "github.com", "Please provide a Github URL"
    assert path.parts[3] == "blob", "Please provide URL for a file"
    assert path.parts[-1].endswith(".keymap"), "Please provide URL to a .keymap file"
    zip_url = f"https://github.com/{path.parts[1]}/{path.parts[2]}/archive/refs/heads/{path.parts[4]}.zip"
    with urlopen(zip_url) as f:
        return f.read(), path


@st.cache
def parse_zmk_url_to_yaml(zmk_url: str, config: ParseConfig, num_cols: int) -> str:
    zip_bytes, path = _get_zmk_zip(zmk_url)
    with TemporaryDirectory() as tmpdir:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zipped:
            zipped.extractall(tmpdir)
        keymap_file = f"{tmpdir}/{path.parts[2]}-{path.parts[4]}/{'/'.join(path.parts[5:])}"
        return parse_zmk_to_yaml(keymap_file, config, num_cols)


def main():
    st.set_page_config(page_title="Keymap Drawer live demo", page_icon=":keyboard:", layout="wide")
    st.write(
        """
        <style>
        textarea[class^="st-"] { font-family: monospace; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.header("`keymap-drawer` interactive demo")
    st.subheader("[GitHub repo](https://github.com/caksoylar/keymap-drawer)")
    if "config" not in st.session_state:
        st.session_state.config = get_default_config()

    examples = get_example_yamls()

    tab_ex, tab_qmk, tab_zmk = st.tabs(["Example keymaps", "Parse QMK", "Parse ZMK"])
    with tab_ex:
        st.selectbox(label="Load example", options=list(examples.keys()), index=0, key="example_yaml")
    with tab_qmk:
        num_cols = st.number_input("Number of columns in keymap", min_value=0, max_value=20, key="qmk_cols")
        qmk_file = st.file_uploader(label="Import QMK `keymap.json`", type=["json"])
        if qmk_file is not None:
            parsed = parse_qmk_to_yaml(
                qmk_file, parse_config(st.session_state.config).parse_config, None if not num_cols else num_cols
            )
            if parsed != st.session_state.get("prev_qmk_parsed"):
                st.session_state.prev_qmk_parsed = parsed
                st.session_state.keymap_yaml = parsed
    with tab_zmk:
        num_cols = st.number_input("Number of columns in keymap", min_value=0, max_value=20, key="zmk_cols")
        zmk_file = st.file_uploader(label="Import a ZMK `<keyboard>.keymap` file", type=["keymap"])
        if zmk_file is not None:
            parsed = parse_zmk_to_yaml(
                zmk_file, parse_config(st.session_state.config).parse_config, None if not num_cols else num_cols
            )
            if parsed != st.session_state.get("prev_zmk_parsed_file"):
                st.session_state.prev_zmk_parsed_file = parsed
                st.session_state.keymap_yaml = parsed
        zmk_url = st.text_input(
            label="or, input GitHub URL to keymap",
            placeholder="https://github.com/caksoylar/zmk-config/blob/main/config/hypergolic.keymap",
        )
        if zmk_url and (zmk_url != st.session_state.get("prev_zmk_url") or num_cols != st.session_state.get("prev_zmk_cols")):
            parsed = parse_zmk_url_to_yaml(
                zmk_url, parse_config(st.session_state.config).parse_config, None if not num_cols else num_cols
            )
            st.session_state.prev_zmk_url = zmk_url
            st.session_state.prev_zmk_cols = num_cols
            st.session_state.keymap_yaml = parsed
        st.caption("Please add a `layout` field with physical layout specification below after parsing")

    left_column, right_column = st.columns(2)
    left_column.subheader("Keymap YAML")
    left_column.text_area(
        value=examples[st.session_state.example_yaml],
        height=800,
        key="keymap_yaml",
        label="[Keymap Spec](https://github.com/caksoylar/keymap-drawer/blob/main/KEYMAP_SPEC.md)",
    )

    svg = draw(st.session_state.keymap_yaml, parse_config(st.session_state.config).draw_config)
    right_column.subheader("Keymap SVG")
    right_column.write(svg_to_html(svg), unsafe_allow_html=True)

    st.download_button(label="Download keymap", data=st.session_state.keymap_yaml, file_name="my_keymap.yaml")
    st.download_button(
        label="Download SVG",
        data=svg,
        file_name="my_keymap.svg",
    )
    with st.expander("Configuration"):
        st.text_area(
            label="[Config parameters](https://github.com/caksoylar/keymap-drawer/blob/main/keymap_drawer/config.py)",
            key="config",
            height=400,
            value=get_default_config(),
        )
        st.download_button(label="Download config", data=st.session_state.config, file_name="my_config.yaml")


main()
