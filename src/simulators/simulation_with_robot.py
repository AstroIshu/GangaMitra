import pybullet as p
import pybullet_data
import numpy as np
import zmq
import json
import time
import cv2
from PIL import Image
import io
import os
import sys
import tempfile

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'robots'))

from src.robots.simple_robot import SimpleRobot

class RobotSimulation:
    def __init__(self, grid_size=64, cell_size=0.5, terrain_height_scale=2.0):
        self.grid_size = grid_size
        self.cell_size = cell_size
        self.terrain_height_scale = terrain_height_scale
        self.terrain_size = grid_size * cell_size
        
        # Connect to PyBullet
        self.setup_pybullet()
        
        # Create enhanced terrain (using your existing class)
        from src.simulators.pybullet_terrain import EnhancedTerrain
        self.terrain = EnhancedTerrain(grid_size, cell_size, terrain_height_scale)
        
        # Initialize terrain data arrays (will be updated via ZMQ later)
        self.terrain.current_heightmap = np.zeros((grid_size, grid_size))
        self.terrain.current_silt = np.zeros((grid_size, grid_size))
        self.terrain.current_trav = np.ones((grid_size, grid_size))
        self.terrain.flow_u = np.zeros((grid_size, grid_size))
        self.terrain.flow_v = np.zeros((grid_size, grid_size))
        
        # Create robot at center
        center_x = self.terrain_size / 2
        center_y = self.terrain_size / 2
        self.robot = SimpleRobot(start_pos=[center_x, center_y, 1.0])
        
        # Setup networking
        self.setup_networking()
        
        # Control variables
        self.forward = 0
        self.turn = 0
        
        # Debris tracking
        self.debris_bodies = []
        
        # Statistics
        self.collision_count = 0
        self.debris_collected = 0
        self.path_travelled = []
        
        # For smooth camera
        self._cam_target = [center_x, center_y, 1.0]

        # Throttle debug-text updates (reduces flicker)
        self._last_display_time = 0
        self._debug_text_ids = []

        print("Robot Simulation initialized")
        print("Robot moves forward automatically.")
    
    def setup_pybullet(self):
        """Setup PyBullet with good viewing angle"""
        self.physics_client = p.connect(p.GUI)
        p.setAdditionalSearchPath(pybullet_data.getDataPath())
        
        # Graphics settings
        p.configureDebugVisualizer(p.COV_ENABLE_SHADOWS, 1)
        p.configureDebugVisualizer(p.COV_ENABLE_GUI, 0)
        # Disable built-in keyboard shortcuts so arrow keys go to
        # getKeyboardEvents() for robot control.  Mouse drag/scroll
        # still works for camera orbit/zoom/pan.
        p.configureDebugVisualizer(p.COV_ENABLE_KEYBOARD_SHORTCUTS, 0)
        p.configureDebugVisualizer(p.COV_ENABLE_MOUSE_PICKING, 1)
        p.setGravity(0, 0, -9.81)
        
        # Set initial camera view
        center = self.terrain_size / 2
        p.resetDebugVisualizerCamera(
            cameraDistance=20,
            cameraYaw=45,
            cameraPitch=-35,
            cameraTargetPosition=[center, center, 0],
        )
    
    def setup_networking(self):
        """Setup ZeroMQ subscriber"""
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.SUB)
        self.socket.connect("tcp://localhost:5555")
        self.socket.setsockopt_string(zmq.SUBSCRIBE, "")
        self.socket.RCVTIMEO = 100
    
    def handle_keyboard(self):
        """Handle keyboard input for robot control (arrow keys)"""
        keys = p.getKeyboardEvents()

        # Reset controls each frame
        self.forward = 0
        self.turn = 0

        # Up / Down arrow for forward / backward
        if p.B3G_UP_ARROW in keys and keys[p.B3G_UP_ARROW] & p.KEY_IS_DOWN:
            self.forward = 1
        if p.B3G_DOWN_ARROW in keys and keys[p.B3G_DOWN_ARROW] & p.KEY_IS_DOWN:
            self.forward = -1

        # Left / Right arrow for turning
        if p.B3G_LEFT_ARROW in keys and keys[p.B3G_LEFT_ARROW] & p.KEY_IS_DOWN:
            self.turn = 1
        if p.B3G_RIGHT_ARROW in keys and keys[p.B3G_RIGHT_ARROW] & p.KEY_IS_DOWN:
            self.turn = -1

        # Space to hard-stop
        if ord(' ') in keys and keys[ord(' ')] & p.KEY_WAS_TRIGGERED:
            self.forward = 0
            self.turn = 0
            lin, _ = p.getBaseVelocity(self.robot.robot_id)
            p.resetBaseVelocity(self.robot.robot_id,
                                linearVelocity=[0, 0, lin[2]],
                                angularVelocity=[0, 0, 0])
    
    def get_terrain_z(self, x, y):
        """Return world-space terrain Z at position (x, y)."""
        hm = self.terrain.current_heightmap
        ix = int(np.clip(x / self.cell_size, 0, self.grid_size - 1))
        iy = int(np.clip(y / self.cell_size, 0, self.grid_size - 1))
        mid_h = (hm.min() + hm.max()) / 2.0
        return float(hm[iy, ix] - mid_h)

    def update_terrain_data(self):
        """Receive and update terrain data from generator.

        Key stability measures:
        1. Disable rendering + real-time sim during the swap so
           the robot never 'sees' the gap between old/new terrain.
        2. After the new terrain is in place, teleport the robot
           (and goal marker) to sit on the new surface.
        3. Debris is spawned as static (mass=0) so it can't fly.
        """
        try:
            msg = self.socket.recv_json()

            terrain = msg.get('terrain', {})
            seq = msg.get('sequence_id', 0)
            debris_data = msg.get('debris', [])

            # ---------- save robot state before swap ----------
            robot_pos, robot_orn = p.getBasePositionAndOrientation(self.robot.robot_id)
            robot_lin_vel, robot_ang_vel = p.getBaseVelocity(self.robot.robot_id)

            # ---------- pause physics & rendering during swap ----------
            p.setRealTimeSimulation(0)
            p.configureDebugVisualizer(p.COV_ENABLE_RENDERING, 0)

            # ---------- update terrain arrays ----------
            if 'heightmap' in terrain:
                heightmap = np.array(terrain['heightmap']).reshape(self.grid_size, self.grid_size)
                self.terrain.current_heightmap = heightmap

            if 'silt_depth' in terrain:
                silt = np.array(terrain['silt_depth']).reshape(self.grid_size, self.grid_size)
                self.terrain.current_silt = silt

            if 'flow_u' in terrain:
                self.terrain.flow_u = np.array(terrain['flow_u']).reshape(self.grid_size, self.grid_size)
            if 'flow_v' in terrain:
                self.terrain.flow_v = np.array(terrain['flow_v']).reshape(self.grid_size, self.grid_size)

            # ---------- rebuild terrain collision ----------
            self.terrain.update_terrain(
                self.terrain.current_heightmap,
                self.terrain.current_silt,
                None,
            )

            # ---------- reposition robot on new surface ----------
            new_z = self.get_terrain_z(robot_pos[0], robot_pos[1]) + 0.45
            # Keep horizontal position & yaw, but correct Z
            p.resetBasePositionAndOrientation(
                self.robot.robot_id,
                [robot_pos[0], robot_pos[1], new_z],
                robot_orn,
            )
            # Preserve horizontal velocity, zero out vertical to avoid bounces
            p.resetBaseVelocity(
                self.robot.robot_id,
                linearVelocity=[robot_lin_vel[0], robot_lin_vel[1], 0],
                angularVelocity=[0, 0, robot_ang_vel[2]],
            )

            # ---------- update debris (static) ----------
            self.update_debris(debris_data)

            # ---------- update water ----------
            self.terrain.update_water_surface(self.terrain.current_heightmap)

            # ---------- resume ----------
            p.configureDebugVisualizer(p.COV_ENABLE_RENDERING, 1)
            p.setRealTimeSimulation(1)

            return seq, debris_data

        except zmq.Again:
            return None, None
    
    def update_debris(self, debris_data):
        """Update debris from generator data"""
        # Remove old debris
        for body_id in self.debris_bodies:
            p.removeBody(body_id)
        self.debris_bodies = []
        
        for item in debris_data:
            x = item.get('x', 0)
            y = item.get('y', 0)
            item_type = item.get('type', 'unknown')
            size = item.get('size', 0.2)
            
            # Get terrain height at this position
            ix = int(x / self.cell_size)
            iy = int(y / self.cell_size)
            if 0 <= ix < self.grid_size and 0 <= iy < self.grid_size:
                h_min = self.terrain.current_heightmap.min()
                h_max = self.terrain.current_heightmap.max()
                mid_h = (h_min + h_max) / 2.0
                z = (self.terrain.current_heightmap[iy, ix] - mid_h) + size/2
            else:
                z = size/2
            
            # Color by type
            colors = {
                'bottle': [0.2, 0.8, 0.2, 1],  # Green
                'idol': [0.9, 0.7, 0.1, 1],    # Gold
                'cloth': [0.9, 0.2, 0.2, 1],   # Red
                'metal': [0.5, 0.5, 0.5, 1]    # Gray
            }
            color = colors.get(item_type, [1, 0, 1, 1])
            
            # Create debris as simple sphere (for now)
            vis = p.createVisualShape(
                p.GEOM_SPHERE,
                radius=size,
                rgbaColor=color
            )
            col = p.createCollisionShape(
                p.GEOM_SPHERE,
                radius=size
            )
            
            body = p.createMultiBody(
                baseMass=0,  # Static – prevents flying on terrain update
                baseCollisionShapeIndex=col,
                baseVisualShapeIndex=vis,
                basePosition=[x, y, z]
            )
            
            self.debris_bodies.append(body)
    
    def record_path(self):  
        pos = self.robot.get_position()
        self.path_travelled.append(pos)
    
        # Keep only last 1000 points
        if len(self.path_travelled) > 1000:
            self.path_travelled.pop(0)
    
    # Draw path
        if len(self.path_travelled) > 1:
            for i in range(len(self.path_travelled)-1):
                p.addUserDebugLine(
                    self.path_travelled[i],
                    self.path_travelled[i+1],
                    [0, 1, 0],  # Green line
                    lineWidth=2,
                    lifeTime=0.1  # Short lifetime so it updates
            )
    
    def update_display_info(self, frame_num):
        """Update on-screen HUD (throttled to ~5 Hz to avoid flicker)"""
        now = time.time()
        if now - self._last_display_time < 0.2:
            return
        self._last_display_time = now

        # Remove previous text items
        for tid in self._debug_text_ids:
            p.removeUserDebugItem(tid)
        self._debug_text_ids.clear()

        robot_pos = self.robot.get_position()

        info = [
            f"Frame: {frame_num}",
            f"Robot: ({robot_pos[0]:.1f}, {robot_pos[1]:.1f}, {robot_pos[2]:.2f})",
            f"Debris: {len(self.debris_bodies)}",
            f"Collisions: {self.collision_count}",
        ]

        for i, text in enumerate(info):
            tid = p.addUserDebugText(
                text,
                [2, self.terrain_size - 2 - i * 1.2, 5],
                textColorRGB=[1, 1, 1],
                textSize=1.0,
                lifeTime=0.3,
            )
            self._debug_text_ids.append(tid)

    def run(self):
        """Main simulation loop – robot moves forward automatically"""
        p.setRealTimeSimulation(1)
        
        frame_num = 0
        
        print("\nStarting simulation...")
        print("Robot will move forward automatically.")
        
        while True:
            # Always drive forward (constant linear motion)
            self.robot.apply_control(1.0, 0)

            # Keep robot upright each frame
            self.robot.update()

            # Check for collisions with debris
            collisions = self.robot.check_collision_with_debris(self.debris_bodies)
            if collisions:
                self.collision_count += len(collisions)

            # Receive terrain updates
            seq, debris = self.update_terrain_data()
            if seq is not None:
                frame_num = seq

            # Update display
            self.update_display_info(frame_num)

            time.sleep(0.01)

if __name__ == "__main__":
    sim = RobotSimulation()
    try:
        sim.run()
    except KeyboardInterrupt:
        print("\nShutting down...")
        p.disconnect()