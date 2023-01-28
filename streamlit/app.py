"""Simple streamlit app for interactive drawing."""
import os
import base64
import io
import json
from urllib.request import urlopen

import yaml
import streamlit as st

from keymap_drawer.draw import KeymapDrawer
from keymap_drawer.config import Config, DrawConfig


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

    out = io.StringIO()
    drawer = KeymapDrawer(
        config=config, out=out, layers=yaml_data["layers"], layout=layout, combos=yaml_data.get("combos", [])
    )
    drawer.print_board()
    return out.getvalue()


@st.cache
def get_example_yamls() -> str:
    out = {}
    examples_path = f"{os.path.dirname(__file__)}/../examples"
    for filename in sorted(os.listdir(examples_path)):
        full_path = f"{examples_path}/{filename}"
        if os.path.isfile(full_path):
            with open(full_path) as f:
                out[filename] = f.read()
    return out


@st.cache
def get_default_config() -> str:
    def cfg_str_representer(dumper, in_str):
        if "\n" in in_str:  # use '|' style for multiline strings
            return dumper.represent_scalar("tag:yaml.org,2002:str", in_str, style="|")
        return dumper.represent_scalar("tag:yaml.org,2002:str", in_str)

    yaml.representer.SafeRepresenter.add_representer(str, cfg_str_representer)
    out = io.StringIO()
    yaml.safe_dump(Config().dict(), out, indent=4, default_flow_style=False)
    return out.getvalue()


@st.cache
def parse_config(config: str) -> Config:
    return Config.parse_obj(yaml.safe_load(config))


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
if "config" not in st.session_state:
    st.session_state.config = get_default_config()


examples = get_example_yamls()

left_column, right_column = st.columns(2)
left_column.subheader("Keymap YAML")
left_column.selectbox(label="Load example", options=list(examples.keys()), index=0, key="example_yaml")
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
        label="[Drawing config parameters](https://github.com/caksoylar/keymap-drawer#customization)",
        key="config",
        height=400,
        value=get_default_config(),
    )
    st.download_button(label="Download config", data=st.session_state.config, file_name="my_config.yaml")
