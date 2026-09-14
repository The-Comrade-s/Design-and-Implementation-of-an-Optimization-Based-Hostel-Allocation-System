import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st

for k, v in st.secrets.items():
    os.environ[k] = str(v)

from app.main import main

if __name__ == "__main__":
    main()
