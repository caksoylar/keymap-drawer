import base64

import streamlit as st


def svg_to_html(svg_string: str) -> str:
    b64 = base64.b64encode(svg.encode('utf-8')).decode('utf-8')
    return f'<img src="data:image/svg+xml;base64,{b64}"/>'

svg = open('combo_test.svg').read()
_ = st.write(html, unsafe_allow_html=True)
