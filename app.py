import streamlit as st
import fitz  # PyMuPDF
import pytesseract
from PIL import Image, ImageEnhance
import io
import os

# Page setup must come before any Streamlit output
st.set_page_config(
    page_title="PDF Question Extractor",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Theme-aware CSS (works in dark and light mode)
st.markdown("""
<style>
    .main {
        padding: 2rem;
    }

    .stButton>button {
        background-color: var(--primary-color);
        color: white;
        border-radius: 8px;
        padding: 0.5rem 2rem;
        font-size: 16px;
        border: none;
        transition: all 0.3s ease;
        width: 100%;
    }
    .stButton>button:hover {
        background-color: rgba(0, 123, 255, 0.85);
        transform: translateY(-2px);
    }

    .info-box {
        background-color: var(--background-color-secondary);
        border-left: 4px solid var(--primary-color);
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 4px;
        color: var(--text-color);
    }

    .success-box {
        background-color: rgba(40, 167, 69, 0.15);
        border-left: 4px solid #28a745;
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 4px;
        color: var(--text-color);
    }

    .stDownloadButton>button {
        background-color: #28a745;
        color: white;
        width: 100%;
        padding: 0.75rem;
        font-size: 16px;
        border-radius: 8px;
    }
    .stDownloadButton>button:hover {
        background-color: #218838;
    }

    .upload-section {
        border: 2px dashed #666;
        border-radius: 10px;
        padding: 2rem;
        text-align: center;
        margin: 2rem 0;
        background-color: rgba(255,255,255,0.02);
        color: var(--text-color);
    }

    :root {
        --primary-color: #007bff;
        --background-color-secondary: #f8f9fa;
        --text-color: #111;
    }
    @media (prefers-color-scheme: dark) {
        :root {
            --primary-color: #339af0;
            --background-color-secondary: #1e1e1e;
            --text-color: #e0e0e0;
        }
    }
</style>
""", unsafe_allow_html=True)
