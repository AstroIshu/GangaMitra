import pybullet as p
import pybullet_data
import numpy as np
import zmq
import json
import time
import math

class HexapodRobot:
    def __init__(self, start_pos=[16, 16, 1.5]):
        self.start_pos = start_pos
        
        # Robot parameters
        self.body_mass = 2.0
        self.leg_mass = 0.3
        self.body_size = [0.2, 0.12, 0.08]
        self.leg_length = 0.18
        self.leg_radius = 0.02
        
        # Joint indices will be stored here
        self.leg_joints = []  # Each leg: [hip_joint, knee_joint]
        
        self.create_robot()
    
    def create_robot(self):
        """Create a simple hexapod robot with fixed legs"""
        
        # Create body (ellipsoid)
        body_collision = p.createCollisionShape(p.GEOM_BOX, halfExtents=self.body_size)
        body_visual = p.createVisualShape(p.GEOM_BOX, halfExtents=self.body_size, 
                                         rgbaColor=[0.2, 0.7, 0.9, 1])  # Bright blue
        
        # Leg positions relative to body center
        # [x, y] positions for each leg: front/middle/back, right/left
        leg_positions = [
            [0.18, -0.15],  # Leg 1: front right
            [0, -0.15],      # Leg 2: middle right
            [-0.18, -0.15],  # Leg 3: back right
            [0.18, 0.15],    # Leg 4: front left
            [0, 0.15],       # Leg 5: middle left
            [-0.18, 0.15]    # Leg 6: back left
        ]
        
        # Create base body
        self.robot_id = p.createMultiBody(
            baseMass=self.body_mass,
            baseCollisionShapeIndex=body_collision,
            baseVisualShapeIndex=body_visual,
            basePosition=self.start_pos
        )
        
        # Create simple visual legs (no joints for now - simplified version)
        for i, (leg_x, leg_y) in enumerate(leg_positions):
            # Create a simple leg as a separate visual-only body
            leg_pos = [
                self.start_pos[0] + leg_x, 
                self.start_pos[1] + leg_y, 
                self.start_pos[2] - 0.15
            ]
            
            leg_visual = p.createVisualShape(
                p.GEOM_CAPSULE, 
                radius=self.leg_radius, 
                length=self.leg_length,
                rgbaColor=[0.3, 0.3, 0.3, 1]  # Dark gray legs
            )
            
            # Create visual-only leg (no collision, no mass)
            leg_body = p.createMultiBody(
                baseMass=0,
                baseVisualShapeIndex=leg_visual,
                basePosition=leg_pos
            )
            
            # Store for later (though we won't animate them in this simplified version)
            self.leg_joints.append([leg_body])
    
    def set_leg_angles(self, leg_index, hip_angle, knee_angle):
        """Set angles for a specific leg - simplified version (no-op for now)"""
        # In this simplified version, legs are fixed
        pass
    
    def tripod_gait(self, time):
        """Simple tripod gait - simplified version (no animation for now)"""
        # In this simplified version, we don't animate the legs
        # The robot body can still move around the terrain
        pass

class PyBulletSimulator:
    def __init__(self, grid_size=64, cell_size=0.5, terrain_height_scale=2.0):
        self.grid_size = grid_size
        self.cell_size = cell_size
        self.terrain_height_scale = terrain_height_scale
        
        # Connect to PyBullet GUI
        self.physics_client = p.connect(p.GUI)
        p.setAdditionalSearchPath(pybullet_data.getDataPath())
        p.setGravity(0, 0, -9.81)
        
        # Set background color to light blue sky
        p.configureDebugVisualizer(p.COV_ENABLE_RGB_BUFFER_PREVIEW, 1)
        p.configureDebugVisualizer(p.COV_ENABLE_SHADOWS, 1)
        
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.SUB)
        self.socket.connect("tcp://localhost:5556")
        self.socket.setsockopt_string(zmq.SUBSCRIBE, "")
        self.socket.RCVTIMEO = 100
        
        # Terrain
        self.terrain_id = None
        self.create_terrain()
        
        # Robot
        self.robot = HexapodRobot()
        
        # Add some visual aids
        self.add_visual_aids()
        
        # Timing
        self.sim_time = 0
        self.last_step_time = time.time()
        
        print("PyBullet Simulator initialized. Waiting for terrain data...")
    
    def create_terrain(self):
        """Create initial terrain"""
        heightfield_data = np.zeros(self.grid_size * self.grid_size, dtype=np.float32)
        
        terrain_shape = p.createCollisionShape(
            shapeType=p.GEOM_HEIGHTFIELD,
            meshScale=[self.cell_size, self.cell_size, self.terrain_height_scale],
            heightfieldData=heightfield_data,
            numHeightfieldRows=self.grid_size,
            numHeightfieldColumns=self.grid_size
        )
        
        self.terrain_id = p.createMultiBody(
            baseMass=0,
            baseCollisionShapeIndex=terrain_shape,
            baseVisualShapeIndex=-1,
            basePosition=[self.grid_size * self.cell_size / 2, 
                         self.grid_size * self.cell_size / 2, 0]
        )
        
        # Set terrain to sandy brown color
        p.changeVisualShape(self.terrain_id, -1, rgbaColor=[0.76, 0.6, 0.42, 1])
    
    def update_terrain(self, heightmap):
        """Update terrain with new heightmap"""
        if self.terrain_id is None:
            return
        
        # Remove old terrain
        p.removeBody(self.terrain_id)
        
        heightmap_flat = heightmap.flatten().astype(np.float32)
        
        # Create new terrain with updated heightmap
        terrain_shape = p.createCollisionShape(
            shapeType=p.GEOM_HEIGHTFIELD,
            meshScale=[self.cell_size, self.cell_size, self.terrain_height_scale],
            heightfieldData=heightmap_flat,
            numHeightfieldRows=self.grid_size,
            numHeightfieldColumns=self.grid_size
        )
        
        self.terrain_id = p.createMultiBody(
            baseMass=0,
            baseCollisionShapeIndex=terrain_shape,
            baseVisualShapeIndex=-1,
            basePosition=[self.grid_size * self.cell_size / 2, 
                         self.grid_size * self.cell_size / 2, 0]
        )
        
        # Set terrain to sandy brown color
        p.changeVisualShape(self.terrain_id, -1, rgbaColor=[0.76, 0.6, 0.42, 1])
    
    def add_visual_aids(self):
        """Add helpful visual elements"""
        # Add coordinate axes
        p.addUserDebugLine([0, 0, 0], [10, 0, 0], [1, 0, 0], lineWidth=3)
        p.addUserDebugLine([0, 0, 0], [0, 10, 0], [0, 1, 0], lineWidth=3)
        p.addUserDebugLine([0, 0, 0], [0, 0, 10], [0, 0, 1], lineWidth=3)
        
        # Add text for current frame
        p.addUserDebugText("Frame: 0", [5, 5, 5], textSize=1.5)
    
    def run(self):
        """Main simulation loop"""
        frame_count = 0
        
        while True:
            current_time = time.time()
            dt = current_time - self.last_step_time
            self.last_step_time = current_time
            self.sim_time += dt
            
            try:
                # Check for new terrain data
                msg = self.socket.recv_json()
                
                terrain = msg.get('terrain', {})
                seq = msg.get('sequence_id', 0)
                
                if 'heightmap' in terrain:
                    heightmap = np.array(terrain['heightmap']).reshape(self.grid_size, self.grid_size)
                    self.update_terrain(heightmap)
                    frame_count += 1
                    
                    # Update frame counter text
                    p.removeAllUserDebugItems()
                    self.add_visual_aids()
                    p.addUserDebugText(f"Frame: {seq}", [5, 5, 5], textSize=1.5)
                    
                    print(f"Frame {seq} - Robot position: {p.getBasePositionAndOrientation(self.robot.robot_id)[0]}")
                
            except zmq.Again:
                pass
            
            # Control robot with tripod gait
            self.robot.tripod_gait(self.sim_time)
            
            # Step simulation
            p.stepSimulation()
            time.sleep(max(0, 0.01 - dt))  # Maintain ~100Hz simulation

if __name__ == "__main__":
    sim = PyBulletSimulator()
    try:
        sim.run()
    except KeyboardInterrupt:
        print("Shutting down...")
        p.disconnect()