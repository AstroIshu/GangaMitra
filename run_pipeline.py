#!/usr/bin/env python
"""Helper script to run the Pathway pipeline from the root directory."""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Import and run
from pipeline.pathway_pipeline import main

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nShutting down Pathway pipeline...")
