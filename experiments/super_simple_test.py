import mujoco
import mujoco.viewer
import numpy as np
import time
import os

print(f"MuJoCo version: {mujoco.__version__}")

# Create XML with heightfield
XML = """
<mujoco>
  <asset>
    <hfield name="wave_hfield" nrow="32" ncol="32" size="16 16 2 0.1"/>
  </asset>
  <worldbody>
    <light pos="0 0 10" directional="true"/>
    <geom name="terrain" type="hfield" hfield="wave_hfield" rgba="0.3 0.6 0.3 1"/>
    <!-- Add a grid of spheres to visually track movement -->
    <body name="marker_grid">
"""
# Add marker spheres at grid points
for i in range(0, 32, 4):
    for j in range(0, 32, 4):
        x = i * 0.5
        y = j * 0.5
        XML += f'      <geom name="marker_{i}_{j}" type="sphere" size="0.1" pos="{x} {y} 2" rgba="1 0 0 1"/>\n'
XML += """
    </body>
  </worldbody>
</mujoco>
"""

# Save XML
xml_path = 'debug_wave.xml'
with open(xml_path, 'w') as f:
    f.write(XML)

print("XML created successfully")

# Load model
try:
    model = mujoco.MjModel.from_xml_path(xml_path)
    data = mujoco.MjData(model)
    print("Model loaded successfully")
except Exception as e:
    print(f"Error loading model: {e}")
    exit(1)

# Heightfield reference
hfield_id = 0
grid_size = 32
hfield_adr = model.hfield_adr[hfield_id]
hfield_nrow = model.hfield_nrow[hfield_id]
hfield_ncol = model.hfield_ncol[hfield_id]

print("\n" + "="*50)
print("DEBUGGING WAVE TEST")
print("="*50)
print(f"Number of heightfields: {model.nhfield}")
print(f"Hfield size: {model.hfield_size[hfield_id]}")
print(f"Hfield data shape: {model.hfield_data.shape}")
print(f"Hfield data type: {model.hfield_data.dtype}")
print("="*50 + "\n")

# Create initial heightmap
heightmap = np.zeros((grid_size, grid_size))

# Store previous heightmap to detect changes
prev_heightmap = heightmap.copy()
update_count = 0

with mujoco.viewer.launch_passive(model, data) as viewer:
    print("Viewer launched. Starting simulation...")
    print("Look for the RED spheres - they should move up/down with terrain")
    print("Press Ctrl+C to stop\n")
    
    t = 0
    step_count = 0
    
    try:
        while viewer.is_running():
            # Create a moving wave pattern
            for i in range(grid_size):
                for j in range(grid_size):
                    # Distance from center
                    dx = i - grid_size/2
                    dy = j - grid_size/2
                    dist = np.sqrt(dx*dx + dy*dy)
                    
                    # Moving wave - amplitude varies with time
                    heightmap[i, j] = 1.0 + 0.8 * np.sin(dist * 0.5 - t * 2)
            
            # Check if heightmap actually changed
            if not np.array_equal(heightmap, prev_heightmap):
                update_count += 1
                prev_heightmap = heightmap.copy()
                
                # METHOD 1: Direct update (use 1D indexing with address)
                ndata = hfield_nrow * hfield_ncol
                model.hfield_data[hfield_adr:hfield_adr + ndata] = heightmap.flatten().astype(np.float32)
                
                # METHOD 2: Force recompute of visual by nudging terrain position
                geom_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "terrain")
                if geom_id >= 0:
                    # Save original position
                    orig_pos = model.geom_pos[geom_id].copy()
                    # Nudge it slightly and back
                    model.geom_pos[geom_id, 2] += 0.001
                    model.geom_pos[geom_id, 2] = orig_pos[2]
            
            # Step simulation - this is crucial for visual updates
            mujoco.mj_step(model, data)
            
            # Sync viewer
            viewer.sync()
            
            # Print status every 10 steps
            if step_count % 10 == 0:
                # Get height at center
                center_height = heightmap[grid_size//2, grid_size//2]
                print(f"\rTime: {t:.2f} | Center height: {center_height:.3f}m | Updates: {update_count}", end="")
            
            t += 0.05
            step_count += 1
            time.sleep(0.01)  # Small delay for smooth animation
            
    except KeyboardInterrupt:
        print("\n\nTest stopped by user")
    
    print(f"\nTotal updates performed: {update_count}")