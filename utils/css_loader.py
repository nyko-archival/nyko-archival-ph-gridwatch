# utils/css_loader.py
import streamlit as st
from pathlib import Path

def load_css(css_file_path: str) -> None:
    """
    Load a CSS file and inject it into the Streamlit app.
    """
    try:
        css_path = Path(css_file_path)
        if not css_path.exists():
            st.warning(f"CSS file not found at {css_path.resolve()}")
            return
        with open(css_path, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Error loading CSS: {str(e)}")