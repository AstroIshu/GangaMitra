import pybullet as p
import pybullet_data
import numpy as np
import zmq
import json
import time

class PyBulletTerrainViewer:
    def __init__(self, grid_size=64, cell_size=0.5, terrain_height_scale=2.0):
        self.grid_size = grid_size
        self.cell_size = cell_size
        self.terrain_height_scale = terrain_height_scale
        
        # Connect to PyBullet GUI
        self.physics_client = p.connect(p.GUI)
        p.setAdditionalSearchPath(pybullet_data.getDataPath())
        p.setGravity(0, 0, -9.81)
        
        # Configure visualizer for better appearance
        p.configureDebugVisualizer(p.COV_ENABLE_RGB_BUFFER_PREVIEW, 1)
        p.configureDebugVisualizer(p.COV_ENABLE_SHADOWS, 1)
        
        p.resetDebugVisualizerCamera(cameraDistance=25, cameraYaw=45, cameraPitch=-30, cameraTargetPosition=[16, 16, 1])
        
        # Set up ZeroMQ subscriber
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.SUB)
        self.socket.connect("tcp://localhost:5556")  # Connect to Pathway output
        self.socket.setsockopt_string(zmq.SUBSCRIBE, "")
        self.socket.RCVTIMEO = 100  # milliseconds
        
        # Terrain mesh will be stored here
        self.terrain_id = None
        self.create_initial_terrain()
        
        # Add some reference objects
        self.add_reference_objects()
        
        print("PyBullet Terrain Viewer initialized. Waiting for terrain data...")
    
    def create_initial_terrain(self):
        """Create a flat terrain initially"""
        # Create a flat heightfield (all zeros)
        heightfield_data = np.zeros(self.grid_size * self.grid_size, dtype=np.float32)
        
        # Create terrain collision shape
        terrain_shape = p.createCollisionShape(
            shapeType=p.GEOM_HEIGHTFIELD,
            meshScale=[self.cell_size, self.cell_size, self.terrain_height_scale],
            heightfieldData=heightfield_data,
            numHeightfieldRows=self.grid_size,
            numHeightfieldColumns=self.grid_size
        )
        
        # Create the terrain body (visual shape auto-generated from collision shape)
        self.terrain_id = p.createMultiBody(
            baseMass=0,
            baseCollisionShapeIndex=terrain_shape,
            baseVisualShapeIndex=-1,
            basePosition=[self.grid_size * self.cell_size / 2, 
                         self.grid_size * self.cell_size / 2, 0]
        )
        
        # Set the terrain color to sandy brown
        p.changeVisualShape(self.terrain_id, -1, rgbaColor=[0.76, 0.6, 0.42, 1])
    
    def update_terrain(self, heightmap):
        """Update the terrain with new heightmap data"""
        if self.terrain_id is None:
            return
        
        # Remove the old terrain body
        p.removeBody(self.terrain_id)
        
        # Ensure heightmap is the right size and type
        heightmap_flat = heightmap.flatten().astype(np.float32)
        
        # Create new terrain collision shape with updated data
        terrain_shape = p.createCollisionShape(
            shapeType=p.GEOM_HEIGHTFIELD,
            meshScale=[self.cell_size, self.cell_size, self.terrain_height_scale],
            heightfieldData=heightmap_flat,
            numHeightfieldRows=self.grid_size,
            numHeightfieldColumns=self.grid_size
        )
        
        # Create the new terrain body
        self.terrain_id = p.createMultiBody(
            baseMass=0,
            baseCollisionShapeIndex=terrain_shape,
            baseVisualShapeIndex=-1,
            basePosition=[self.grid_size * self.cell_size / 2, 
                         self.grid_size * self.cell_size / 2, 0]
        )
        
        # Set the terrain color to sandy brown
        p.changeVisualShape(self.terrain_id, -1, rgbaColor=[0.76, 0.6, 0.42, 1])
    
    def add_reference_objects(self):
        """Add some reference objects to help visualize scale and movement"""
        # Add a grid for reference
        p.loadURDF("plane.urdf", [0, 0, -0.1], useFixedBase=True)
        
        # Add some floating spheres to see if terrain is moving
        for i in range(5):
            for j in range(5):
                x = i * 6 + 3
                y = j * 6 + 3
                visual = p.createVisualShape(p.GEOM_SPHERE, radius=0.2, rgbaColor=[1, 0, 0, 0.5])
                p.createMultiBody(baseMass=0, baseVisualShapeIndex=visual, 
                                 basePosition=[x, y, 5])
        
        # Add axes
        p.addUserDebugLine([0, 0, 0], [10, 0, 0], [1, 0, 0], lineWidth=3)  # X axis
        p.addUserDebugLine([0, 0, 0], [0, 10, 0], [0, 1, 0], lineWidth=3)  # Y axis
        p.addUserDebugLine([0, 0, 0], [0, 0, 10], [0, 0, 1], lineWidth=3)  # Z axis
    
    def run(self):
        """Main loop"""
        frame_count = 0
        last_print_time = time.time()
        
        while True:
            try:
                # Check for new terrain data
                msg = self.socket.recv_json()
                
                terrain = msg.get('terrain', {})
                seq = msg.get('sequence_id', 0)
                
                if 'heightmap' in terrain:
                    heightmap = np.array(terrain['heightmap']).reshape(self.grid_size, self.grid_size)
                    self.update_terrain(heightmap)
                    
                    frame_count += 1
                    if time.time() - last_print_time > 2:  # Print every 2 seconds
                        print(f"Received frame {seq}, updated terrain. Total frames: {frame_count}")
                        last_print_time = time.time()
                
            except zmq.Again:
                pass
            
            # Step simulation (required for PyBullet to update)
            p.stepSimulation()
            time.sleep(0.01)  # Small sleep to prevent CPU overload

if __name__ == "__main__":
    viewer = PyBulletTerrainViewer()
    try:
        viewer.run()
    except KeyboardInterrupt:
        print("Shutting down...")
        p.disconnect()