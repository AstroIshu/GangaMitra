#!/usr/bin/env python
"""Helper script to run the PyBullet simulator from the root directory."""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Import and run
from simulators.pybullet_terrain import *

if __name__ == "__main__":
    # The pybullet_terrain.py has its main code at module level, so importing runs it
    pass
