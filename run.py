"""Convenience launcher: `python run.py` runs the Streamlit app."""
import subprocess
import sys

if __name__ == "__main__":
    subprocess.run([sys.executable, "-m", "streamlit", "run", "app/main.py"] + sys.argv[1:])
