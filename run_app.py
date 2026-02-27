#!/usr/bin/env python
"""Helper script to run the Streamlit app from the root directory."""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Note: Streamlit apps need to be run with: streamlit run src/ui/app.py
# This script provides a Python interface
if __name__ == "__main__":
    import subprocess
    app_path = os.path.join(os.path.dirname(__file__), 'src', 'ui', 'app.py')
    subprocess.run(['streamlit', 'run', app_path])
