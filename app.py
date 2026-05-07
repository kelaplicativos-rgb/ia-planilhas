from __future__ import annotations

import streamlit as st

from bling_app_zero.ui.home import render_home


APP_VERSION = '3.0.0-BLINGCREATOR'


def main() -> None:
    st.set_page_config(
        page_title='IA Planilhas → Bling',
        page_icon='🚀',
        layout='wide',
        initial_sidebar_state='collapsed',
    )

    render_home()


if __name__ == '__main__':
    main()
