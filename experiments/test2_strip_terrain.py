"""
Test 2: Strip-based Progressive Terrain
Terrain updates in strips as robot moves forward
Only the terrain ahead is generated and rendered
"""

import pybullet as p
import pybullet_data
import numpy as np
import zmq
import json
import time
import cv2
from PIL import Image
import os
import tempfile
from simple_robot import SimpleRobot
from pybullet_terrain import EnhancedTerrain

class StripTerrainTest:
    def __init__(self, grid_size=64, cell_size=0.5, terrain_height_scale=2.0):
        self.grid_size = grid_size
        self.cell_size = cell_size
        self.terrain_height_scale = terrain_height_scale
        self.terrain_size = grid_size * cell_size
        
        # Strip parameters
        self.strip_width = 8  # Number of cells per strip
        self.visible_strips = 4  # Number of strips visible at once
        self.current_strip = 0  # Current strip index
        self.robot_start_strip = 2  # Robot starts in middle strip
        
        # Connect to PyBullet
        self.setup_pybullet()
        
        # Create terrain (will update strips)
        self.terrain = EnhancedTerrain(grid_size, cell_size, terrain_height_scale)
        
        # Initialize terrain data - only first few strips are visible
        self.heightmap = np.zeros((grid_size, grid_size))
        self.generate_initial_strips()
        
        # Create robot at starting position
        start_x = self.terrain_size / 2
        start_y = self.robot_start_strip * self.strip_width * cell_size + self.strip_width * cell_size / 2
        self.robot = SimpleRobot(start_pos=[start_x, start_y, 1.0])
        
        # Add strip markers
        self.add_strip_markers()
        
        # Setup networking (optional - can use generator or generate internally)
        self.setup_networking()
        
        # Track robot's progress
        self.last_strip = self.robot_start_strip
        
        # Control variables
        self.forward = 0
        self.turn = 0
        
        # For smooth camera
        self._debug_text_ids = []
        self._last_display_time = 0
        
        print("\n" + "="*60)
        print("TEST 2: STRIP-BASED PROGRESSIVE TERRAIN")
        print("="*60)
        print(f"Strip width: {self.strip_width} cells ({self.strip_width * cell_size}m)")
        print(f"Visible strips: {self.visible_strips}")
        print(f"Total strips: {grid_size // self.strip_width}")
        print("\nTerrain updates in strips as robot moves forward")
        print("Only the terrain ahead is generated and rendered")
        print("\nControls: Arrow keys to move, Space to stop")
        print("="*60)
    
    def setup_pybullet(self):
        """Setup PyBullet"""
        self.physics_client = p.connect(p.GUI)
        p.setAdditionalSearchPath(pybullet_data.getDataPath())
        
        p.configureDebugVisualizer(p.COV_ENABLE_SHADOWS, 1)
        p.configureDebugVisualizer(p.COV_ENABLE_GUI, 0)
        p.configureDebugVisualizer(p.COV_ENABLE_KEYBOARD_SHORTCUTS, 0)
        p.setGravity(0, 0, -9.81)
        
        center = self.terrain_size / 2
        p.resetDebugVisualizerCamera(
            cameraDistance=25,
            cameraYaw=45,
            cameraPitch=-35,
            cameraTargetPosition=[center, center, 0],
        )
    
    def add_strip_markers(self):
        """Add visual markers for strips"""
        num_strips = self.grid_size // self.strip_width
        strip_height = self.strip_width * self.cell_size
        
        for i in range(num_strips):
            y_pos = (i + 0.5) * strip_height
            # Draw strip boundary lines
            p.addUserDebugLine(
                [0, y_pos - strip_height/2, 0.1],
                [self.terrain_size, y_pos - strip_height/2, 0.1],
                [1, 1, 1, 0.5],
                lineWidth=1
            )
            
            # Add strip number
            p.addUserDebugText(
                f"Strip {i}",
                [2, y_pos, 2],
                textColorRGB=[1, 1, 0],
                textSize=0.8
            )
    
    def generate_strip_terrain(self, strip_index):
        """Generate terrain for a specific strip"""
        start_row = strip_index * self.strip_width
        end_row = start_row + self.strip_width
        
        # Different terrain types per strip
        if strip_index % 4 == 0:
            # Flat
            for i in range(start_row, min(end_row, self.grid_size)):
                for j in range(self.grid_size):
                    self.heightmap[i, j] = 0.5 + 0.1 * np.sin(j/10)
        elif strip_index % 4 == 1:
            # Hills
            for i in range(start_row, min(end_row, self.grid_size)):
                for j in range(self.grid_size):
                    self.heightmap[i, j] = 0.8 + 0.4 * np.sin(i/5) * np.cos(j/5)
        elif strip_index % 4 == 2:
            # Rough
            for i in range(start_row, min(end_row, self.grid_size)):
                for j in range(self.grid_size):
                    self.heightmap[i, j] = 1.0 + 0.6 * np.random.random()
        else:
            # Valley
            for i in range(start_row, min(end_row, self.grid_size)):
                for j in range(self.grid_size):
                    dist = abs(j - self.grid_size/2) / (self.grid_size/2)
                    self.heightmap[i, j] = 0.5 + 0.8 * (1 - dist)
    
    def generate_initial_strips(self):
        """Generate initial visible strips"""
        num_strips = self.grid_size // self.strip_width
        
        # Generate all strips (but only first few will be visible initially)
        for i in range(num_strips):
            self.generate_strip_terrain(i)
        
        # Initially hide strips beyond visible range
        visible_start = max(0, self.robot_start_strip - 1)
        visible_end = min(num_strips, self.robot_start_strip + self.visible_strips)
        
        # Zero out strips outside visible range
        for i in range(num_strips):
            if i < visible_start or i >= visible_end:
                start_row = i * self.strip_width
                end_row = min(start_row + self.strip_width, self.grid_size)
                self.heightmap[start_row:end_row, :] = 0
        
        self.terrain.current_heightmap = self.heightmap
        self.terrain.update_terrain(self.heightmap, None, None)
    
    def setup_networking(self):
        """Setup ZeroMQ subscriber (optional)"""
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.SUB)
        self.socket.connect("tcp://localhost:5555")
        self.socket.setsockopt_string(zmq.SUBSCRIBE, "")
        self.socket.RCVTIMEO = 100
    
    def handle_keyboard(self):
        """Handle keyboard input"""
        keys = p.getKeyboardEvents()
        
        self.forward = 0
        self.turn = 0
        
        if p.B3G_UP_ARROW in keys and keys[p.B3G_UP_ARROW] & p.KEY_IS_DOWN:
            self.forward = 1
        if p.B3G_DOWN_ARROW in keys and keys[p.B3G_DOWN_ARROW] & p.KEY_IS_DOWN:
            self.forward = -1
        if p.B3G_LEFT_ARROW in keys and keys[p.B3G_LEFT_ARROW] & p.KEY_IS_DOWN:
            self.turn = 1
        if p.B3G_RIGHT_ARROW in keys and keys[p.B3G_RIGHT_ARROW] & p.KEY_IS_DOWN:
            self.turn = -1
        if ord(' ') in keys and keys[ord(' ')] & p.KEY_WAS_TRIGGERED:
            self.forward = 0
            self.turn = 0
            p.resetBaseVelocity(self.robot.robot_id)
    
    def check_strip_transition(self):
        """Check if robot has moved to a new strip and update terrain"""
        robot_pos = self.robot.get_position()
        current_strip = int(robot_pos[1] // (self.strip_width * self.cell_size))
        
        # Clamp to valid range
        current_strip = max(0, min(current_strip, self.grid_size // self.strip_width - 1))
        
        if current_strip != self.last_strip:
            print(f"\n📍 Robot entered strip {current_strip}")
            
            # Generate new strips ahead
            num_strips = self.grid_size // self.strip_width
            visible_start = max(0, current_strip - 1)
            visible_end = min(num_strips, current_strip + self.visible_strips)
            
            # Generate terrain for upcoming strips if not already generated
            for i in range(visible_start, visible_end):
                if i > self.last_strip + 2:  # Only generate new strips ahead
                    print(f"   Generating strip {i}")
                    self.generate_strip_terrain(i)
            
            # Update terrain visualization
            self.terrain.current_heightmap = self.heightmap
            self.terrain.update_terrain(self.heightmap, None, None)
            
            self.last_strip = current_strip
    
    def update_display_info(self):
        """Update on-screen information"""
        now = time.time()
        if now - self._last_display_time < 0.2:
            return
        self._last_display_time = now
        
        for tid in self._debug_text_ids:
            p.removeUserDebugItem(tid)
        self._debug_text_ids.clear()
        
        robot_pos = self.robot.get_position()
        current_strip = int(robot_pos[1] // (self.strip_width * self.cell_size))
        num_strips = self.grid_size // self.strip_width
        
        info = [
            "TEST 2: STRIP-BASED TERRAIN",
            f"Current Strip: {current_strip}/{num_strips-1}",
            f"Robot Y: {robot_pos[1]:.1f}m",
            f"Visible: Strips {max(0,current_strip-1)}-{min(num_strips-1, current_strip+self.visible_strips-1)}",
            "",
            "Arrow keys = move, Space = stop"
        ]
        
        for i, text in enumerate(info):
            tid = p.addUserDebugText(
                text,
                [2, self.terrain_size - 2 - i*1.2, 5],
                textColorRGB=[1, 1, 1],
                textSize=1.0,
                lifeTime=0.3
            )
            self._debug_text_ids.append(tid)
    
    def run(self):
        """Main simulation loop"""
        p.setRealTimeSimulation(1)
        
        print("\nStarting strip-based terrain test...")
        print(f"Robot starts in strip {self.robot_start_strip}")
        print("Drive forward to see new strips generate!")
        
        while True:
            # Handle keyboard
            self.handle_keyboard()
            
            # Apply robot control
            if self.forward != 0 or self.turn != 0:
                props = self.robot.apply_terrain_aware_control(
                    self.forward, self.turn, self.terrain
                )
            else:
                self.robot.apply_control(0, 0)
            
            self.robot.update()
            
            # Check for strip transitions
            self.check_strip_transition()
            
            # Update display
            self.update_display_info()
            
            time.sleep(0.01)

if __name__ == "__main__":
    test = StripTerrainTest()
    try:
        test.run()
    except KeyboardInterrupt:
        print("\nShutting down...")
        p.disconnect()