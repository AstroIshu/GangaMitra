"""
Test 1: Smooth Morphing Terrain
The entire terrain gradually and smoothly transitions between states
No abrupt changes - everything morphs over time
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

class SmoothMorphingTest:
    def __init__(self, grid_size=64, cell_size=0.5, terrain_height_scale=2.0):
        self.grid_size = grid_size
        self.cell_size = cell_size
        self.terrain_height_scale = terrain_height_scale
        self.terrain_size = grid_size * cell_size
        
        # Connect to PyBullet
        self.setup_pybullet()
        
        # Create terrain
        self.terrain = EnhancedTerrain(grid_size, cell_size, terrain_height_scale)
        
        # Initialize terrain data
        self.current_heightmap = np.zeros((grid_size, grid_size))
        self.target_heightmap = np.zeros((grid_size, grid_size))
        self.morph_speed = 0.02  # How fast terrain morphs (per frame)
        
        # Create robot at center
        center_x = self.terrain_size / 2
        center_y = self.terrain_size / 2
        self.robot = SimpleRobot(start_pos=[center_x, center_y, 1.0])
        
        # Add goal markers for different terrain zones
        self.add_zone_markers()
        
        # Setup networking
        self.setup_networking()
        
        # Morphing state
        self.morph_phase = 0
        self.last_terrain_update = time.time()
        
        # Control variables
        self.forward = 0
        self.turn = 0
        
        # For smooth camera
        self._debug_text_ids = []
        self._last_display_time = 0
        
        print("\n" + "="*60)
        print("TEST 1: SMOOTH MORPHING TERRAIN")
        print("="*60)
        print("The entire terrain smoothly morphs between states")
        print("No abrupt changes - everything transitions gradually")
        print("\nTerrain Zones:")
        print("  Zone 1 (Red): Flat → Hills")
        print("  Zone 2 (Green): Hills → Mountains") 
        print("  Zone 3 (Blue): Mountains → Valley")
        print("  Zone 4 (Yellow): Valley → Flat")
        print("\nControls: Arrow keys to move, Space to stop")
        print("="*60)
    
    def setup_pybullet(self):
        """Setup PyBullet with good viewing angle"""
        self.physics_client = p.connect(p.GUI)
        p.setAdditionalSearchPath(pybullet_data.getDataPath())
        
        p.configureDebugVisualizer(p.COV_ENABLE_SHADOWS, 1)
        p.configureDebugVisualizer(p.COV_ENABLE_GUI, 0)
        p.configureDebugVisualizer(p.COV_ENABLE_KEYBOARD_SHORTCUTS, 0)
        p.setGravity(0, 0, -9.81)
        
        # Set camera to overview
        center = self.terrain_size / 2
        p.resetDebugVisualizerCamera(
            cameraDistance=25,
            cameraYaw=45,
            cameraPitch=-35,
            cameraTargetPosition=[center, center, 0],
        )
    
    def add_zone_markers(self):
        """Add visual markers for different terrain zones"""
        zone_size = self.terrain_size / 4
        colors = [[1,0,0,0.3], [0,1,0,0.3], [0,0,1,0.3], [1,1,0,0.3]]
        
        for i in range(4):
            center_x = (i + 0.5) * zone_size
            center_y = self.terrain_size / 2
            
            # Semi-transparent zone marker
            vis = p.createVisualShape(
                p.GEOM_BOX,
                halfExtents=[zone_size/2, self.terrain_size/2, 0.1],
                rgbaColor=colors[i]
            )
            marker = p.createMultiBody(
                baseMass=0,
                baseVisualShapeIndex=vis,
                basePosition=[center_x, self.terrain_size/2, 0.2]
            )
    
    def setup_networking(self):
        """Setup ZeroMQ subscriber"""
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
    
    def generate_terrain_states(self):
        """Generate 4 different terrain states for morphing"""
        states = []
        gs = self.grid_size
        
        # State 0: Flat terrain
        flat = np.zeros((gs, gs))
        states.append(flat)
        
        # State 1: Rolling hills
        hills = np.zeros((gs, gs))
        for i in range(gs):
            for j in range(gs):
                hills[i,j] = 0.5 + 0.3 * np.sin(i/10) * np.cos(j/8)
        states.append(hills)
        
        # State 2: Mountains
        mountains = np.zeros((gs, gs))
        for i in range(gs):
            for j in range(gs):
                dist = np.sqrt((i-gs/2)**2 + (j-gs/2)**2) / (gs/2)
                mountains[i,j] = 1.5 * np.exp(-dist*2) + 0.5 * np.sin(i/5) * np.cos(j/5)
        states.append(mountains)
        
        # State 3: Valley
        valley = np.zeros((gs, gs))
        for i in range(gs):
            for j in range(gs):
                dist = np.sqrt((i-gs/2)**2 + (j-gs/2)**2) / (gs/2)
                valley[i,j] = 0.5 + 0.8 * (1 - np.exp(-dist*3))
        states.append(valley)
        
        return states
    
    def smooth_morph(self, current, target, speed):
        """Morph current terrain towards target smoothly"""
        diff = target - current
        # Only move a small step towards target
        step = diff * speed
        # Ensure we don't overshoot
        new_current = current + step
        
        # If we're very close to target, just set to target
        if np.max(np.abs(diff)) < 0.01:
            new_current = target
            
        return new_current
    
    def update_display_info(self, morph_progress, current_state):
        """Update on-screen information"""
        now = time.time()
        if now - self._last_display_time < 0.2:
            return
        self._last_display_time = now
        
        for tid in self._debug_text_ids:
            p.removeUserDebugItem(tid)
        self._debug_text_ids.clear()
        
        robot_pos, _ = self.robot.get_position()
        
        info = [
            "TEST 1: SMOOTH MORPHING TERRAIN",
            f"Morph Progress: {morph_progress*100:.1f}%",
            f"Current State: {current_state}",
            f"Robot: ({robot_pos[0]:.1f}, {robot_pos[1]:.1f})",
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
        
        # Generate terrain states
        terrain_states = self.generate_terrain_states()
        num_states = len(terrain_states)
        
        # Start with first state
        self.target_heightmap = terrain_states[0]
        self.current_heightmap = self.target_heightmap.copy()
        self.terrain.current_heightmap = self.current_heightmap
        self.terrain.update_terrain(self.current_heightmap, None, None)
        
        current_state = 0
        morph_progress = 1.0  # Start fully at state 0
        
        print("\nStarting smooth morphing...")
        print("Terrain will cycle through: Flat → Hills → Mountains → Valley → Flat")
        
        frame_count = 0
        
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
            
            # Update terrain morphing
            if morph_progress >= 1.0:
                # Move to next state
                current_state = (current_state + 1) % num_states
                next_state = (current_state + 1) % num_states
                self.target_heightmap = terrain_states[next_state]
                morph_progress = 0.0
                print(f"\n🔄 Transitioning to state {next_state}")
            else:
                # Morph smoothly
                target = terrain_states[(current_state + 1) % num_states]
                self.current_heightmap = self.smooth_morph(
                    self.current_heightmap, target, self.morph_speed
                )
                morph_progress += self.morph_speed
                
                # Update terrain visualization
                if frame_count % 5 == 0:  # Update every 5 frames for performance
                    self.terrain.update_terrain(self.current_heightmap, None, None)
            
            # Update display
            self.update_display_info(morph_progress, current_state)
            
            frame_count += 1
            time.sleep(0.01)

if __name__ == "__main__":
    test = SmoothMorphingTest()
    try:
        test.run()
    except KeyboardInterrupt:
        print("\nShutting down...")
        p.disconnect()