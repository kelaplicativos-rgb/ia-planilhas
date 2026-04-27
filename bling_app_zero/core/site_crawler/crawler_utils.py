import streamlit as st


def log(msg):
    print(msg)

    if "logs" not in st.session_state:
        st.session_state["logs"] = []

    st.session_state["logs"].append(msg)
