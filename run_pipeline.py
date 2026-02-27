#!/usr/bin/env python
"""Helper script to run the Pathway pipeline from the root directory."""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Import and run
from pipeline.pathway_pipeline import *

if __name__ == "__main__":
    # The pathway_pipeline.py has its main code at module level, so importing runs it
    pass
