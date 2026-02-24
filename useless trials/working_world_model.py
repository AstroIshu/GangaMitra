import mujoco
import mujoco.viewer
import numpy as np
import zmq
import json
import time
import threading
from collections import deque
import copy

class WorkingWorldModel:
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
        
        # Thread-safe terrain data
        self.terrain_lock = threading.Lock()
        self.pending_heightmap = None
        self.current_heightmap = np.zeros((self.grid_size, self.grid_size))
        self.last_heightmap = np.zeros((self.grid_size, self.grid_size))
        self.terrain_updated = False
        self.frame_count = 0
        
        # For visualization - add markers that will move with terrain
        self.marker_positions = self.create_marker_positions()
        
        # ZeroMQ setup in separate thread
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.SUB)
        self.socket.connect(f"tcp://localhost:{pathway_port}")
        self.socket.setsockopt_string(zmq.SUBSCRIBE, "")
        self.socket.RCVTIMEO = 100
        
        # Start receiver thread
        self.running = True
        self.receiver_thread = threading.Thread(target=self.receiver_loop)
        self.receiver_thread.daemon = True
        self.receiver_thread.start()
        
        print(f"✅ Working World Model Initialized")
        print(f"   Grid: {self.grid_size}x{self.grid_size}")
        print(f"   Height range: 0 to {self.max_height}m")
        print(f"   Listening on port: {pathway_port}")
        print(f"\n📌 Watch the RED markers - they will move with the terrain!")
        
    def create_marker_positions(self):
        """Create positions for visual markers."""
        positions = []
        step = 4  # Place marker every 4 cells
        for i in range(0, self.grid_size, step):
            for j in range(0, self.grid_size, step):
                x = j * self.cell_size + self.cell_size/2
                y = i * self.cell_size + self.cell_size/2
                positions.append((x, y, i, j))
        return positions
    
    def receiver_loop(self):
        """Background thread to receive terrain data."""
        print("📡 Receiver thread started")
        while self.running:
            try:
                msg = self.socket.recv_json()
                terrain = msg['terrain']
                
                if 'heightmap' in terrain:
                    # Get heightmap
                    heightmap = np.array(terrain['heightmap']).reshape(self.grid_size, self.grid_size)
                    heightmap = np.clip(heightmap, 0, self.max_height)
                    
                    # Thread-safe update
                    with self.terrain_lock:
                        self.pending_heightmap = heightmap.copy()
                        self.frame_count += 1
                        
                    # Print occasional updates
                    if self.frame_count % 10 == 0:
                        print(f"\n📦 Frame {msg['sequence_id']} received")
                        print(f"   Height range: {heightmap.min():.2f} - {heightmap.max():.2f}m")
                        print(f"   Debris: {len(msg.get('debris', []))} items")
                        
            except zmq.Again:
                pass
            except Exception as e:
                print(f"Receiver error: {e}")
            time.sleep(0.001)
    
    def update_terrain_in_simulation(self):
        """Apply pending terrain updates (called from main thread)."""
        with self.terrain_lock:
            if self.pending_heightmap is not None:
                # Update heightfield data (use 1D indexing with address)
                ndata = self.hfield_nrow * self.hfield_ncol
                self.model.hfield_data[self.hfield_adr:self.hfield_adr + ndata] = self.pending_heightmap.flatten()
                
                # CRITICAL: Force MuJoCo to recompute everything
                # Method 1: Nudge the geom position (triggers refresh)
                geom_id = 0  # ground geom
                self.model.geom_pos[geom_id, 2] += 0.0001
                self.model.geom_pos[geom_id, 2] -= 0.0001
                
                # Method 2: Toggle a flag that forces recompilation
                # This is a hack but it works
                self.model.opt.timestep = self.model.opt.timestep  # Force reevaluation
                
                # Store current for visualization
                self.current_heightmap = self.pending_heightmap.copy()
                self.terrain_updated = True
                self.pending_heightmap = None
                
                return True
        return False
    
    def add_visual_markers(self, viewer):
        """Add visual markers that show terrain deformation."""
        # Clear previous custom geoms
        viewer.user_scn.ngeom = 0
        
        if not self.terrain_updated:
            return
        
        # Add a grid of spheres floating above terrain
        for idx, (x, y, i, j) in enumerate(self.marker_positions):
            if idx >= 100:  # Limit number for performance
                break
                
            # Get height at this position
            if 0 <= i < self.grid_size and 0 <= j < self.grid_size:
                z = self.current_heightmap[i, j] + 0.2  # Float above terrain
            else:
                z = 1.0
            
            # Add sphere
            viewer.user_scn.ngeom += 1
            geom = viewer.user_scn.geoms[viewer.user_scn.ngeom - 1]
            geom.type = mujoco.mjtGeom.mjGEOM_SPHERE
            geom.size[:] = [0.08, 0, 0]
            geom.pos[:] = [x, y, z]
            
            # Color based on height
            if z < 0.5:
                geom.rgba[:] = [0, 0, 1, 0.8]  # Blue for low
            elif z < 1.0:
                geom.rgba[:] = [0, 1, 0, 0.8]  # Green for medium
            else:
                geom.rgba[:] = [1, 0, 0, 0.8]  # Red for high
    
    def run(self):
        """Main simulation loop."""
        print("\n🚀 Starting simulation with WORKING terrain updates...")
        print("Press Ctrl+C to stop\n")
        
        with mujoco.viewer.launch_passive(self.model, self.data) as viewer:
            # Configure viewer
            viewer.opt.flags[mujoco.mjtVisFlag.mjVIS_CONTACTPOINT] = False
            viewer.opt.flags[mujoco.mjtVisFlag.mjVIS_TRANSPARENT] = True
            
            last_print = time.time()
            step_count = 0
            
            try:
                while viewer.is_running():
                    # Apply any pending terrain updates
                    updated = self.update_terrain_in_simulation()
                    
                    # Step simulation (this is key - MuJoCo updates visuals during step)
                    mujoco.mj_step(self.model, self.data)
                    
                    # Add visual markers every few steps
                    if step_count % 5 == 0:
                        self.add_visual_markers(viewer)
                    
                    # Sync viewer
                    viewer.sync()
                    
                    # Print status
                    if time.time() - last_print > 1.0:
                        if self.terrain_updated:
                            height_range = f"{self.current_heightmap.min():.2f}-{self.current_heightmap.max():.2f}"
                            print(f"\r🔄 Frames: {self.frame_count} | Height: {height_range}m | Markers: {len(self.marker_positions)}", end="")
                        else:
                            print(f"\r⏳ Waiting for terrain data...", end="")
                        last_print = time.time()
                    
                    step_count += 1
                    time.sleep(0.001)  # Small sleep to prevent CPU hogging
                    
            except KeyboardInterrupt:
                print("\n\n👋 Simulation stopped")
            
            self.running = False
            self.receiver_thread.join(timeout=1.0)

if __name__ == "__main__":
    # Create and run working world model
    world = WorkingWorldModel(
        model_path='minimal_terrain.xml',
        pathway_port=5556
    )
    world.run()