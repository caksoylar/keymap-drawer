"""Redirect users to the canonical URL pointing to the new app."""

import streamlit as st

APP_URL = "https://caksoylar.github.io/keymap-drawer"


def main():
    """Lay out Streamlit elements and widgets, run parsing and drawing logic."""
    st.set_page_config(page_title="Keymap Drawer live demo", page_icon=":keyboard:", layout="wide")
    st.write('<style>textarea[class^="st-"] { font-family: monospace; }</style>', unsafe_allow_html=True)
    st.header("`keymap-drawer` interactive demo")
    st.subheader("A visualizer for keyboard keymaps")
    st.caption(
        "Check out the documentation and Python CLI tool in the "
        "[GitHub repo](https://github.com/caksoylar/keymap-drawer)!"
    )

    st.info(
        f"Keymap drawer web app has moved! Use and bookmark this link to reach the new app: {APP_URL}",
        icon="ℹ️",
    )


main()
