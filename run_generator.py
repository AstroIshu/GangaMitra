#!/usr/bin/env python
"""Helper script to run the terrain generator from the root directory."""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Import and run
from core.generator import main

if __name__ == "__main__":
    main()
