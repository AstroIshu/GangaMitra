import mujoco
import mujoco.viewer
import numpy as np
import zmq
import json
import time

# Configuration
MODEL_PATH = 'minimal_terrain.xml'
GENERATOR_PORT = 5555   # Direct from generator, or use 5556 if going through Pathway

# ZeroMQ setup
context = zmq.Context()
socket = context.socket(zmq.SUB)
socket.connect(f"tcp://localhost:{GENERATOR_PORT}")
socket.setsockopt_string(zmq.SUBSCRIBE, "")
socket.RCVTIMEO = 100  # milliseconds

# Load model
model = mujoco.MjModel.from_xml_path(MODEL_PATH)
data = mujoco.MjData(model)

# Heightfield parameters
grid_size = 64
hfield_id = 0  # first (and only) heightfield
# MuJoCo expects heights in range [0, size[2]] where size[2] is max height (2.0)
max_height = model.hfield_size[hfield_id, 2]
hfield_adr = model.hfield_adr[hfield_id]
hfield_nrow = model.hfield_nrow[hfield_id]
hfield_ncol = model.hfield_ncol[hfield_id]

print("Minimal simulator started. Waiting for terrain data...")

# Launch viewer
with mujoco.viewer.launch_passive(model, data) as viewer:
    # Simulation loop
    while viewer.is_running():
        # Check for new terrain data
        try:
            msg = socket.recv_json()
            seq = msg['sequence_id']
            terrain = msg['terrain']
            
            # Extract heightmap
            heightmap = np.array(terrain['heightmap']).reshape(grid_size, grid_size)
            
            # Clip to max height (just in case generator produces higher values)
            heightmap = np.clip(heightmap, 0, max_height)
            
            # Update MuJoCo heightfield data (use 1D indexing with address)
            ndata = hfield_nrow * hfield_ncol
            model.hfield_data[hfield_adr:hfield_adr + ndata] = heightmap.flatten()
            
            print(f"Received frame {seq}, updated terrain")
            
        except zmq.Again:
            pass  # No new data
        
        # Step simulation (small step to keep viewer responsive)
        mujoco.mj_step(model, data)
        
        # Sync viewer
        viewer.sync()
        
        # Sleep a tiny bit to not hog CPU
        time.sleep(0.01)