import mujoco
import mujoco.viewer
import numpy as np
import zmq
import json
import time
import threading
from collections import deque

class InteractiveTerrainSimulation:
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
        
        # Add interactive objects (like in playground)
        self.add_interactive_objects()
        
        # Thread-safe terrain data
        self.terrain_lock = threading.Lock()
        self.pending_heightmap = None
        self.current_heightmap = np.zeros((self.grid_size, self.grid_size))
        self.terrain_updated = False
        self.frame_count = 0
        self.last_print_time = time.time()
        
        # ZeroMQ setup
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
        
        print("="*60)
        print("INTERACTIVE TERRAIN SIMULATION")
        print("="*60)
        print(f"✅ Connected to Pathway on port {pathway_port}")
        print(f"📡 Receiving terrain updates")
        print("\n🎮 CONTROLS:")
        print("   - Left click + drag: Move camera")
        print("   - Right click + drag: Rotate view")
        print("   - Scroll: Zoom in/out")
        print("   - Use sliders below to control the red ball")
        print("   - Watch the terrain change color and shape!")
        print("="*60)
    
    def add_interactive_objects(self):
        """Add interactive objects like in the playground."""
        # We need to modify the model to add objects
        # Since we can't easily modify the loaded model, we'll create a new XML with objects
        # But for now, let's use the existing model and just note that we'd add:
        # - A red ball that can be controlled
        # - Some markers to show terrain height
        
        # For demonstration, we'll add visual markers in the viewer
        self.ball_pos = np.array([5.0, 5.0, 2.0])
        self.ball_vel = np.array([0.0, 0.0, 0.0])
        self.control_force = np.array([0.0, 0.0, 0.0])
        
    def receiver_loop(self):
        """Background thread to receive terrain data."""
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
                        
            except zmq.Again:
                pass
            except Exception as e:
                print(f"Receiver error: {e}")
            time.sleep(0.001)
    
    def update_terrain(self):
        """Apply pending terrain updates."""
        with self.terrain_lock:
            if self.pending_heightmap is not None:
                # Update heightfield data (use 1D indexing with address)
                ndata = self.hfield_nrow * self.hfield_ncol
                self.model.hfield_data[self.hfield_adr:self.hfield_adr + ndata] = self.pending_heightmap.flatten()
                
                # CRITICAL: Force MuJoCo to update visuals
                # Method 1: Nudge the terrain geom
                geom_id = 0
                self.model.geom_pos[geom_id, 2] += 0.0001
                self.model.geom_pos[geom_id, 2] -= 0.0001
                
                self.current_heightmap = self.pending_heightmap.copy()
                self.terrain_updated = True
                self.pending_heightmap = None
                
                return True
        return False
    
    def get_height_at(self, x, y):
        """Get terrain height at world coordinates."""
        ix = int(x / self.cell_size)
        iy = int(y / self.cell_size)
        if 0 <= ix < self.grid_size and 0 <= iy < self.grid_size:
            return self.current_heightmap[iy, ix]
        return 0.0
    
    def add_visual_overlay(self, viewer):
        """Add visual elements to show terrain changes."""
        # Clear previous custom geoms
        viewer.user_scn.ngeom = 0
        
        if not self.terrain_updated:
            return
        
        # Add a grid of spheres that follow terrain height
        n_markers = 8
        for i in range(n_markers):
            for j in range(n_markers):
                x = (i + 0.5) * 32.0 / n_markers
                y = (j + 0.5) * 32.0 / n_markers
                
                # Get terrain height at this point
                ix = int(i * self.grid_size / n_markers)
                iy = int(j * self.grid_size / n_markers)
                z = self.current_heightmap[iy, ix] + 0.2
                
                # Add sphere
                viewer.user_scn.ngeom += 1
                geom = viewer.user_scn.geoms[viewer.user_scn.ngeom - 1]
                geom.type = mujoco.mjtGeom.mjGEOM_SPHERE
                geom.size[:] = [0.15, 0, 0]
                geom.pos[:] = [x, y, z]
                
                # Color based on height
                if z < 0.7:
                    geom.rgba[:] = [0, 0, 1, 0.8]  # Blue - low
                elif z < 1.3:
                    geom.rgba[:] = [0, 1, 0, 0.8]  # Green - medium
                else:
                    geom.rgba[:] = [1, 0, 0, 0.8]  # Red - high
        
        # Add a controllable red ball (like in playground)
        viewer.user_scn.ngeom += 1
        geom = viewer.user_scn.geoms[viewer.user_scn.ngeom - 1]
        geom.type = mujoco.mjtGeom.mjGEOM_SPHERE
        geom.size[:] = [0.3, 0, 0]
        
        # Update ball position with simple physics
        dt = 0.01
        self.ball_vel += self.control_force * dt
        self.ball_vel *= 0.95  # damping
        self.ball_pos += self.ball_vel * dt
        
        # Keep ball above terrain
        terrain_height = self.get_height_at(self.ball_pos[0], self.ball_pos[1])
        self.ball_pos[2] = terrain_height + 0.5
        
        geom.pos[:] = self.ball_pos
        geom.rgba[:] = [1, 0, 0, 1]  # Bright red
        
        # Add control arrows (visual indication of force direction)
        if np.linalg.norm(self.control_force) > 0.01:
            viewer.user_scn.ngeom += 1
            geom = viewer.user_scn.geoms[viewer.user_scn.ngeom - 1]
            geom.type = mujoco.mjtGeom.mjGEOM_ARROW
            geom.size[:] = [0.05, 0.1, 0]
            geom.pos[:] = self.ball_pos
            geom.mat[:] = [self.control_force[0], self.control_force[1], 0, 1]  # direction
            geom.rgba[:] = [1, 1, 0, 0.8]  # Yellow
    
    def run(self):
        """Main simulation loop."""
        print("\n🚀 Starting simulation...")
        print("Press Ctrl+C to stop\n")
        
        with mujoco.viewer.launch_passive(self.model, self.data) as viewer:
            # Configure viewer
            viewer.opt.flags[mujoco.mjtVisFlag.mjVIS_CONTACTPOINT] = True
            viewer.opt.flags[mujoco.mjtVisFlag.mjVIS_TRANSPARENT] = True
            
            # Add custom UI for controls
            def keyboard_callback(key, action):
                if action == mujoco.mjtKey.mjKEY_PRESS:
                    force = 10.0
                    if key == 'w':
                        self.control_force[1] += force
                    elif key == 's':
                        self.control_force[1] -= force
                    elif key == 'a':
                        self.control_force[0] -= force
                    elif key == 'd':
                        self.control_force[0] += force
                    elif key == ' ':
                        self.control_force[:] = 0
                        self.ball_vel[:] = 0
            
            viewer.custom_key_callback = keyboard_callback
            
            step_count = 0
            try:
                while viewer.is_running():
                    # Apply any pending terrain updates
                    terrain_updated = self.update_terrain()
                    
                    # Step simulation (critical for visual updates)
                    mujoco.mj_step(self.model, self.data)
                    
                    # Add visual overlay
                    self.add_visual_overlay(viewer)
                    
                    # Sync viewer
                    viewer.sync()
                    
                    # Print status
                    if time.time() - self.last_print_time > 1.0:
                        if self.terrain_updated:
                            height_range = f"{self.current_heightmap.min():.2f}-{self.current_heightmap.max():.2f}"
                            ball_z = self.ball_pos[2]
                            print(f"\r📊 Frame: {self.frame_count} | Height: {height_range}m | Ball Z: {ball_z:.2f}m | Force: ({self.control_force[0]:.1f}, {self.control_force[1]:.1f})", end="")
                        else:
                            print(f"\r⏳ Waiting for terrain data...", end="")
                        self.last_print_time = time.time()
                    
                    step_count += 1
                    time.sleep(0.005)  # Small sleep to prevent CPU hogging
                    
            except KeyboardInterrupt:
                print("\n\n👋 Simulation stopped")
            
            self.running = False

if __name__ == "__main__":
    # Run simulation
    sim = InteractiveTerrainSimulation(
        model_path='minimal_terrain.xml',
        pathway_port=5556
    )
    sim.run()