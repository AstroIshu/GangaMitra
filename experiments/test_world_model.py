import mujoco
import mujoco.viewer
import numpy as np
import zmq
import json
import time
import threading
from collections import deque

class FixedWorldModel:
    def __init__(self, model_path='minimal_terrain.xml', pathway_port=5556):
        # Load model
        self.model = mujoco.MjModel.from_xml_path(model_path)
        self.data = mujoco.MjData(self.model)
        
        # Heightfield parameters
        self.grid_size = 64
        self.cell_size = 0.5
        self.hfield_id = 0
        self.max_height = self.model.hfield_size[self.hfield_id, 2]
        self.hfield_adr = self.model.hfield_adr[self.hfield_id]
        self.hfield_nrow = self.model.hfield_nrow[self.hfield_id]
        self.hfield_ncol = self.model.hfield_ncol[self.hfield_id]
        
        # For tracking terrain changes
        self.current_heightmap = np.zeros((self.grid_size, self.grid_size))
        self.last_heightmap = np.zeros((self.grid_size, self.grid_size))
        self.terrain_updated = False
        
        # For visualization enhancement - add a floating grid to show deformation
        self.add_visual_markers()
        
        # ZeroMQ setup
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.SUB)
        self.socket.connect(f"tcp://localhost:{pathway_port}")
        self.socket.setsockopt_string(zmq.SUBSCRIBE, "")
        self.socket.RCVTIMEO = 100
        
        # Statistics
        self.frame_count = 0
        self.last_print_time = time.time()
        
        print(f"✅ Fixed World Model Initialized")
        print(f"   Grid: {self.grid_size}x{self.grid_size}")
        print(f"   Height range: 0 to {self.max_height}m")
        print(f"   Listening on port: {pathway_port}")
        print(f"\n📌 Tip: Look for the RED floating grid - it will move with terrain!")
        
    def add_visual_markers(self):
        """Add visual markers that will move with terrain to show changes."""
        # We'll add a grid of small spheres at each cell corner
        # This is a hack to visualize terrain deformation
        spacing = 4  # Place a marker every 4 cells
        marker_size = 0.1
        
        # We'll store marker positions for later updating
        self.marker_bodies = []
        
        # In MuJoCo, we'd need to add geoms to the model, but that's complex
        # Instead, we'll create a simple overlay grid in the viewer using custom geoms
        pass
    
    def update_heightfield(self, heightmap):
        """Update the heightfield and force visual refresh."""
        # Ensure heightmap is within bounds
        heightmap = np.clip(heightmap, 0, self.max_height)
        
        # Update MuJoCo heightfield data (use 1D indexing with address)
        ndata = self.hfield_nrow * self.hfield_ncol
        self.model.hfield_data[self.hfield_adr:self.hfield_adr + ndata] = heightmap.flatten()
        
        # CRITICAL: Force MuJoCo to recompute everything related to the heightfield
        # This includes visual, collision, etc.
        
        # Method 1: Touch the geom to force update (works in some versions)
        geom_id = 0  # Assuming ground geom is first
        self.model.geom_pos[geom_id, 2] += 0.0001  # Tiny nudge
        self.model.geom_pos[geom_id, 2] -= 0.0001
        
        # Method 2: Update the data structure that holds rendering info
        if hasattr(self.model, 'geom_rgba'):
            # Force visual refresh by toggling transparency (very subtle)
            orig = self.model.geom_rgba[geom_id, 3]
            self.model.geom_rgba[geom_id, 3] = min(1.0, orig + 0.01)
            self.model.geom_rgba[geom_id, 3] = orig
        
        # Mark that terrain has been updated
        self.terrain_updated = True
        self.current_heightmap = heightmap.copy()
        
    def update_from_pathway(self):
        """Receive and process latest terrain data."""
        try:
            msg = self.socket.recv_json()
            terrain = msg['terrain']
            
            if 'heightmap' in terrain:
                # Get heightmap
                heightmap = np.array(terrain['heightmap']).reshape(self.grid_size, self.grid_size)
                
                # Update heightfield
                self.update_heightfield(heightmap)
                
                # Update stats
                self.frame_count += 1
                
                # Print occasional updates
                if self.frame_count % 10 == 0:
                    print(f"\n📦 Frame {msg['sequence_id']} received")
                    print(f"   Height range: {heightmap.min():.2f} - {heightmap.max():.2f}m")
                    print(f"   Debris: {len(msg.get('debris', []))} items")
                
                return True
                
        except zmq.Again:
            pass
        except Exception as e:
            print(f"Error: {e}")
        
        return False
    
    def add_visual_overlay(self, viewer):
        """Add visual overlay to show terrain changes."""
        # Clear previous custom geoms
        viewer.user_scn.ngeom = 0
        
        # Add a wireframe grid floating above terrain to show deformation
        if self.terrain_updated:
            n_lines = 8
            spacing = self.world_size / n_lines
            
            for i in range(n_lines + 1):
                for j in range(n_lines + 1):
                    x = i * spacing
                    y = j * spacing
                    
                    # Get height at this point
                    ix = int(i * self.grid_size / n_lines)
                    iy = int(j * self.grid_size / n_lines)
                    if 0 <= ix < self.grid_size and 0 <= iy < self.grid_size:
                        z = self.current_heightmap[iy, ix] + 0.2  # Float above
                    else:
                        z = 1.0
                    
                    # Add a small sphere at this point
                    if i < n_lines and j < n_lines:
                        viewer.user_scn.ngeom += 1
                        geom = viewer.user_scn.geoms[viewer.user_scn.ngeom - 1]
                        geom.type = mujoco.mjtGeom.mjGEOM_SPHERE
                        geom.size[:] = [0.1, 0, 0]
                        geom.pos[:] = [x, y, z]
                        geom.rgba[:] = [1, 0, 0, 0.7]  # Red semi-transparent
    
    def run(self):
        """Main simulation loop."""
        print("\n🚀 Starting simulation with FIXED terrain updates...")
        print("Press Ctrl+C to stop\n")
        
        with mujoco.viewer.launch_passive(self.model, self.data) as viewer:
            # Configure viewer
            viewer.opt.flags[mujoco.mjtVisFlag.mjVIS_CONTACTPOINT] = True
            viewer.opt.flags[mujoco.mjtVisFlag.mjVIS_TRANSPARENT] = True
            
            last_print = time.time()
            
            try:
                while viewer.is_running():
                    # Check for new terrain data
                    self.update_from_pathway()
                    
                    # Step simulation
                    mujoco.mj_step(self.model, self.data)
                    
                    # Add visual overlay to show terrain changes
                    self.add_visual_overlay(viewer)
                    
                    # Sync viewer
                    viewer.sync()
                    
                    # Print status every second
                    if time.time() - last_print > 1.0:
                        if self.terrain_updated:
                            print(f"\r🔄 Terrain active | Frames: {self.frame_count}", end="")
                        else:
                            print(f"\r⏳ Waiting for terrain data...", end="")
                        last_print = time.time()
                    
                    # Small sleep to prevent CPU hogging
                    time.sleep(0.01)
                    
            except KeyboardInterrupt:
                print("\n\n👋 Simulation stopped")
    
    @property
    def world_size(self):
        return self.grid_size * self.cell_size

if __name__ == "__main__":
    # Create and run fixed world model
    world = FixedWorldModel(
        model_path='minimal_terrain.xml',
        pathway_port=5556
    )
    world.run()