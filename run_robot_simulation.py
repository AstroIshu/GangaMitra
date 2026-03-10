#!/usr/bin/env python
"""Helper script to run the Robot Simulation from the root directory."""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Import and run
from simulators.simulation_with_robot import RobotSimulation
import pybullet as p

if __name__ == "__main__":
    sim = RobotSimulation()
    try:
        sim.run()
    except KeyboardInterrupt:
        print("\nShutting down...")
        p.disconnect()
