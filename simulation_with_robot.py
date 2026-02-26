# # import pybullet as p
# # import pybullet_data
# # import numpy as np
# # import zmq
# # import json
# # import time
# # from pybullet_terrain import EnhancedTerrain
# # from simple_robot import SimpleBoxRobot

# # class RobotSimulation:
# #     def __init__(self, grid_size=64, cell_size=0.5, terrain_height_scale=2.0):
# #         self.grid_size = grid_size
# #         self.cell_size = cell_size
# #         self.terrain_height_scale = terrain_height_scale
# #         self.terrain_size = grid_size * cell_size
        
# #         # Connect to PyBullet with GUI (single connection for everything)
# #         self.physics_client = p.connect(p.GUI)
# #         p.setAdditionalSearchPath(pybullet_data.getDataPath())
        
# #         # Configure graphics
# #         p.configureDebugVisualizer(p.COV_ENABLE_SHADOWS, 1)
# #         p.configureDebugVisualizer(p.COV_ENABLE_TINY_RENDERER, 0)
# #         p.configureDebugVisualizer(p.COV_ENABLE_GUI, 1)
# #         p.configureDebugVisualizer(p.COV_ENABLE_RGB_BUFFER_PREVIEW, 0)
# #         p.configureDebugVisualizer(p.COV_ENABLE_DEPTH_BUFFER_PREVIEW, 0)
# #         p.configureDebugVisualizer(p.COV_ENABLE_SEGMENTATION_MARK_PREVIEW, 0)
# #         p.setGravity(0, 0, -9.81)
        
# #         # Set camera to overview
# #         p.resetDebugVisualizerCamera(
# #             cameraDistance=self.terrain_size * 0.8,
# #             cameraYaw=45,
# #             cameraPitch=-30,
# #             cameraTargetPosition=[self.terrain_size/2, self.terrain_size/2, 1]
# #         )
        
# #         # Create enhanced terrain (geometry only — no separate PyBullet connection)
# #         self.terrain = EnhancedTerrain(grid_size, cell_size, terrain_height_scale)
        
# #         # Terrain data arrays
# #         self.current_heightmap = np.zeros((grid_size, grid_size))
# #         self.current_silt = np.zeros((grid_size, grid_size))
# #         self.current_trav = np.ones((grid_size, grid_size))
# #         self.current_flow_u = np.zeros((grid_size, grid_size))
# #         self.current_flow_v = np.zeros((grid_size, grid_size))
        
# #         # Debris tracking (moved from viewer)
# #         self.debris_bodies = []
# #         self.debris_config = {
# #             "bottle": {
# #                 "shape": p.GEOM_CYLINDER,
# #                 "color": [0.2, 0.8, 0.3, 0.85],
# #                 "radius": 0.08, "length": 0.25,
# #             },
# #             "idol": {
# #                 "shape": p.GEOM_BOX,
# #                 "color": [0.85, 0.65, 0.12, 1.0],
# #                 "halfExtents": [0.12, 0.12, 0.2],
# #             },
# #             "cloth": {
# #                 "shape": p.GEOM_BOX,
# #                 "color": [0.9, 0.85, 0.95, 0.8],
# #                 "halfExtents": [0.3, 0.3, 0.02],
# #             },
# #             "metal": {
# #                 "shape": p.GEOM_CYLINDER,
# #                 "color": [0.35, 0.35, 0.4, 1.0],
# #                 "radius": 0.1, "length": 0.2,
# #             },
# #         }
        
# #         # Create robot (start near bottom center)
# #         start_x = self.terrain_size / 2  # Center X
# #         start_y = 5.0  # Near bottom edge
# #         start_z = 1.0  # Will be adjusted to terrain height
        
# #         self.robot = SimpleBoxRobot(start_pos=[start_x, start_y, start_z])
        
# #         # Movement control
# #         self.auto_mode = True
# #         self.target_x = start_x
# #         self.target_y = start_y
        
# #         # Setup networking
# #         self.setup_networking()
        
# #         # Simulation state
# #         self.sim_time = 0
# #         self.last_print_time = time.time()
# #         self.frame_count = 0
        
# #         print("\n" + "="*50)
# #         print("Robot Simulation Started")
# #         print("="*50)
# #         print("Controls:")
# #         print("  [A] Toggle auto/manual mode")
# #         print("  [Space] Pause simulation")
# #         print("  [R] Reset robot to start")
# #         print("  [Up/Down] Move forward/backward (manual mode)")
# #         print("  [Left/Right] Turn left/right (manual mode)")
# #         print("="*50)
    
# #     def setup_networking(self):
# #         """Setup ZeroMQ subscriber for terrain data"""
# #         self.context = zmq.Context()
# #         self.socket = self.context.socket(zmq.SUB)
# #         self.socket.connect("tcp://localhost:5555")
# #         self.socket.setsockopt_string(zmq.SUBSCRIBE, "")
# #         self.socket.RCVTIMEO = 100
    
# #     def handle_keyboard(self):
# #         """Handle keyboard input for robot control"""
# #         keys = p.getKeyboardEvents()
        
# #         for k, state in keys.items():
# #             if state & p.KEY_WAS_TRIGGERED:
# #                 if k == ord('a'):  # Toggle auto mode
# #                     self.auto_mode = not self.auto_mode
# #                     print(f"Auto mode: {'ON' if self.auto_mode else 'OFF'}")
                
# #                 elif k == ord(' '):  # Space - pause
# #                     self.paused = not getattr(self, 'paused', False)
# #                     print(f"{'Paused' if self.paused else 'Resumed'}")
                
# #                 elif k == ord('r'):  # Reset robot
# #                     self.reset_robot()
                
# #                 elif k == p.B3G_UP_ARROW:  # Up arrow
# #                     if not self.auto_mode:
# #                         self.robot.set_movement(1.0, 0)
                
# #                 elif k == p.B3G_DOWN_ARROW:  # Down arrow
# #                     if not self.auto_mode:
# #                         self.robot.set_movement(-0.5, 0)
                
# #                 elif k == p.B3G_LEFT_ARROW:  # Left arrow
# #                     if not self.auto_mode:
# #                         self.robot.set_movement(0.5, -0.3)
                
# #                 elif k == p.B3G_RIGHT_ARROW:  # Right arrow
# #                     if not self.auto_mode:
# #                         self.robot.set_movement(0.5, 0.3)
    
# #     def auto_navigation(self):
# #         """Simple auto navigation - move towards bottom while avoiding obstacles"""
# #         if not self.auto_mode:
# #             return
        
# #         # Get current position
# #         pos, orn = self.robot.get_position()
# #         current_x, current_y, current_z = pos
        
# #         # Target: move towards bottom (decreasing y) while staying near center x
# #         target_x = self.terrain_size / 2
# #         target_y = 3.0  # Near bottom
        
# #         # Calculate direction to target
# #         dx = target_x - current_x
# #         dy = target_y - current_y
        
# #         # Get robot forward direction
# #         forward_dir = [1, 0, 0]
# #         rot_matrix = p.getMatrixFromQuaternion(orn)
# #         forward_world = [
# #             rot_matrix[0] * forward_dir[0] + rot_matrix[3] * forward_dir[1] + rot_matrix[6] * forward_dir[2],
# #             rot_matrix[1] * forward_dir[0] + rot_matrix[4] * forward_dir[1] + rot_matrix[7] * forward_dir[2],
# #             rot_matrix[2] * forward_dir[0] + rot_matrix[5] * forward_dir[1] + rot_matrix[8] * forward_dir[2]
# #         ]
        
# #         # Calculate angle to target
# #         target_angle = np.arctan2(dy, dx)
# #         robot_angle = np.arctan2(forward_world[1], forward_world[0])
        
# #         # Calculate angle difference
# #         angle_diff = target_angle - robot_angle
# #         angle_diff = np.arctan2(np.sin(angle_diff), np.cos(angle_diff))  # Normalize
        
# #         # Check for obstacles (debris collisions)
# #         has_collision = len(self.robot.collision_debris) > 0
        
# #         if has_collision:
# #             # Back up and turn to avoid obstacle
# #             self.robot.set_movement(-0.3, angle_diff * 2)
# #         else:
# #             # Normal movement
# #             distance = np.sqrt(dx**2 + dy**2)
# #             if distance > 1.0:
# #                 speed = min(1.0, distance / 5.0)
# #                 steering = np.clip(angle_diff * 2, -0.5, 0.5)
# #                 self.robot.set_movement(speed, steering)
# #             else:
# #                 self.robot.set_movement(0, 0)
    
# #     def reset_robot(self):
# #         """Reset robot to starting position"""
# #         start_x = self.terrain_size / 2
# #         start_y = 5.0
        
# #         ix = int(start_x / self.cell_size)
# #         iy = int(start_y / self.cell_size)
# #         if 0 <= ix < self.grid_size and 0 <= iy < self.grid_size:
# #             h_min = self.current_heightmap.min()
# #             h_max = self.current_heightmap.max()
# #             mid_h = (h_min + h_max) / 2.0
# #             terrain_z = self.current_heightmap[iy, ix] - mid_h
# #             start_z = terrain_z + 0.5
# #         else:
# #             start_z = 1.0
        
# #         self.robot.reset_position([start_x, start_y, start_z])
# #         print("Robot reset to start position")
    
# #     def update_debris(self, debris_list):
# #         """Remove old debris bodies and spawn new ones from the latest data."""
# #         for body_id in self.debris_bodies:
# #             p.removeBody(body_id)
# #         self.debris_bodies = []
        
# #         default_cfg = {
# #             "shape": p.GEOM_SPHERE,
# #             "color": [1.0, 0.0, 1.0, 1.0],
# #         }
        
# #         for item in debris_list:
# #             x = item.get("x", 0)
# #             y = item.get("y", 0)
# #             item_type = item.get("type", "unknown")
# #             item_size = item.get("size", 0.2)
            
# #             cfg = self.debris_config.get(item_type, default_cfg)
# #             shape_type = cfg["shape"]
# #             color = cfg["color"]
            
# #             # Sample terrain height at debris position
# #             ix = int(x / self.cell_size)
# #             iy = int(y / self.cell_size)
# #             h_min = self.current_heightmap.min()
# #             h_max = self.current_heightmap.max()
# #             mid_h = (h_min + h_max) / 2.0
# #             if 0 <= ix < self.grid_size and 0 <= iy < self.grid_size:
# #                 z = (self.current_heightmap[iy, ix] - mid_h) + item_size * 0.5
# #             else:
# #                 z = item_size * 0.5
            
# #             if shape_type == p.GEOM_CYLINDER:
# #                 radius = cfg.get("radius", 0.1) * (item_size / 0.3)
# #                 length = cfg.get("length", 0.2) * (item_size / 0.3)
# #                 vis = p.createVisualShape(shape_type, radius=radius, length=length, rgbaColor=color)
# #                 col = p.createCollisionShape(shape_type, radius=radius, height=length)
# #             elif shape_type == p.GEOM_BOX:
# #                 he = cfg.get("halfExtents", [0.1, 0.1, 0.1])
# #                 scale = item_size / 0.3
# #                 he_scaled = [h * scale for h in he]
# #                 vis = p.createVisualShape(shape_type, halfExtents=he_scaled, rgbaColor=color)
# #                 col = p.createCollisionShape(shape_type, halfExtents=he_scaled)
# #             else:
# #                 vis = p.createVisualShape(p.GEOM_SPHERE, radius=item_size * 0.3, rgbaColor=color)
# #                 col = p.createCollisionShape(p.GEOM_SPHERE, radius=item_size * 0.3)
            
# #             body = p.createMultiBody(
# #                 baseMass=0,
# #                 baseCollisionShapeIndex=col,
# #                 baseVisualShapeIndex=vis,
# #                 basePosition=[x, y, z]
# #             )
# #             self.debris_bodies.append(body)
    
# #     def update_display_info(self):
# #         """Update on-screen information"""
# #         p.removeAllUserDebugItems()
        
# #         pos, orn = self.robot.get_position()
# #         linear_vel, angular_vel = self.robot.get_velocity()
# #         speed = np.sqrt(linear_vel[0]**2 + linear_vel[1]**2)
        
# #         info_text = [
# #             f"Frame: {self.frame_count}",
# #             f"Robot Position: ({pos[0]:.1f}, {pos[1]:.1f}, {pos[2]:.2f})",
# #             f"Speed: {speed:.2f} m/s",
# #             f"Mode: {'AUTO' if self.auto_mode else 'MANUAL'}",
# #             f"Collisions: {len(self.robot.collision_debris)}",
# #             f"Time: {self.sim_time:.1f}s"
# #         ]
        
# #         for i, text in enumerate(info_text):
# #             p.addUserDebugText(
# #                 text,
# #                 [2, self.terrain_size - 2 - i*1.5, 5],
# #                 textColorRGB=[1, 1, 1],
# #                 textSize=1.2
# #             )
        
# #         # Draw robot's forward direction
# #         self.robot.draw_debug_info()
    
# #     def run(self):
# #         """Main simulation loop"""
# #         p.setRealTimeSimulation(1)
        
# #         while True:
# #             self.handle_keyboard()
            
# #             # Skip if paused
# #             if hasattr(self, 'paused') and self.paused:
# #                 time.sleep(0.1)
# #                 continue
            
# #             # Process terrain updates from ZMQ
# #             try:
# #                 msg = self.socket.recv_json()
                
# #                 terrain = msg.get('terrain', {})
# #                 seq = msg.get('sequence_id', 0)
# #                 debris = msg.get('debris', [])
                
# #                 # Update local terrain data
# #                 if 'heightmap' in terrain:
# #                     self.current_heightmap = np.array(terrain['heightmap']).reshape(self.grid_size, self.grid_size)
# #                 if 'silt_depth' in terrain:
# #                     self.current_silt = np.array(terrain['silt_depth']).reshape(self.grid_size, self.grid_size)
# #                 if 'flow_u' in terrain:
# #                     self.current_flow_u = np.array(terrain['flow_u']).reshape(self.grid_size, self.grid_size)
# #                 if 'flow_v' in terrain:
# #                     self.current_flow_v = np.array(terrain['flow_v']).reshape(self.grid_size, self.grid_size)
                
# #                 # Compute traversability if not provided
# #                 if 'traversability' in terrain:
# #                     self.current_trav = np.array(terrain['traversability']).reshape(self.grid_size, self.grid_size)
# #                 else:
# #                     grad_x = np.gradient(self.current_heightmap, axis=1)
# #                     grad_y = np.gradient(self.current_heightmap, axis=0)
# #                     slope = np.sqrt(grad_x**2 + grad_y**2)
# #                     slope_max = slope.max()
# #                     slope_norm = np.clip(slope / slope_max if slope_max > 0 else slope, 0, 1)
# #                     silt_max = self.current_silt.max()
# #                     silt_norm = np.clip(self.current_silt / silt_max if silt_max > 0 else self.current_silt, 0, 1)
# #                     self.current_trav = np.clip(1.0 - 0.5 * slope_norm - 0.5 * silt_norm, 0, 1)
                
# #                 # Push flow field into terrain's water system
# #                 self.terrain.flow_u = self.current_flow_u
# #                 self.terrain.flow_v = self.current_flow_v
                
# #                 # Update terrain visualization
# #                 p.configureDebugVisualizer(p.COV_ENABLE_RENDERING, 0)
# #                 self.terrain.update_terrain(
# #                     self.current_heightmap,
# #                     self.current_silt,
# #                     self.current_trav
# #                 )
# #                 self.update_debris(debris)
# #                 self.terrain.update_water_surface(self.current_heightmap)
# #                 p.configureDebugVisualizer(p.COV_ENABLE_RENDERING, 1)
                
# #                 self.frame_count = seq
                
# #             except zmq.Again:
# #                 # No new data — still update water surface animation
# #                 self.terrain.update_water_surface(self.current_heightmap)
            
# #             # Auto navigation
# #             self.auto_navigation()
            
# #             # Update robot
# #             self.robot.update()
            
# #             # Adjust robot height to terrain
# #             self.adjust_robot_height()
            
# #             # Update display
# #             self.update_display_info()
            
# #             # Step simulation
# #             p.stepSimulation()
            
# #             # Update time
# #             self.sim_time += 0.01
            
# #             # Print status occasionally
# #             if time.time() - self.last_print_time > 2.0:
# #                 pos, _ = self.robot.get_position()
# #                 print(f"Robot position: ({pos[0]:.1f}, {pos[1]:.1f}, {pos[2]:.2f})")
# #                 self.last_print_time = time.time()
            
# #             time.sleep(0.01)
    
# #     def adjust_robot_height(self):
# #         """Adjust robot's height to match terrain"""
# #         pos, orn = self.robot.get_position()
        
# #         # Get terrain height at robot position
# #         ix = int(pos[0] / self.cell_size)
# #         iy = int(pos[1] / self.cell_size)
        
# #         if 0 <= ix < self.grid_size and 0 <= iy < self.grid_size:
# #             h_min = self.current_heightmap.min()
# #             h_max = self.current_heightmap.max()
# #             mid_h = (h_min + h_max) / 2.0
# #             terrain_z = self.current_heightmap[iy, ix] - mid_h
            
# #             # Adjust robot height to stay on terrain
# #             target_z = terrain_z + 0.3  # Keep robot slightly above terrain
            
# #             # Apply small correction (not a hard reset to maintain physics)
# #             current_vel = p.getBaseVelocity(self.robot.robot_id)[0]
# #             if abs(pos[2] - target_z) > 0.1:
# #                 # Apply force to correct height
# #                 correction_force = (target_z - pos[2]) * 100
# #                 p.applyExternalForce(
# #                     self.robot.robot_id,
# #                     -1,
# #                     [0, 0, correction_force],
# #                     pos,
# #                     p.WORLD_FRAME
# #                 )

# # if __name__ == "__main__":
# #     sim = RobotSimulation()
# #     try:
# #         sim.run()
# #     except KeyboardInterrupt:
# #         print("\nShutting down simulation...")
# #         p.disconnect()
# import pybullet as p
# import pybullet_data
# import numpy as np
# import zmq
# import json
# import time
# import cv2
# from PIL import Image
# import io
# import os
# import tempfile
# from simple_robot import SimpleRobot

# class RobotSimulation:
#     def __init__(self, grid_size=64, cell_size=0.5, terrain_height_scale=2.0):
#         self.grid_size = grid_size
#         self.cell_size = cell_size
#         self.terrain_height_scale = terrain_height_scale
#         self.terrain_size = grid_size * cell_size
        
#         # Connect to PyBullet
#         self.setup_pybullet()
        
#         # Create enhanced terrain (using your existing class)
#         from enhanced_terrain import EnhancedTerrain
#         self.terrain = EnhancedTerrain(grid_size, cell_size, terrain_height_scale)
        
#         # Create robot at center
#         center_x = self.terrain_size / 2
#         center_y = self.terrain_size / 2
#         self.robot = SimpleRobot(start_pos=[center_x, center_y, 1.0])
        
#         # Add goal marker (where robot should go)
#         self.add_goal_marker()
        
#         # Setup networking
#         self.setup_networking()
        
#         # Control variables
#         self.forward = 0
#         self.turn = 0
        
#         # Debris tracking
#         self.debris_bodies = []
        
#         # Statistics
#         self.collision_count = 0
#         self.debris_collected = 0
#         self.path_travelled = []
        
#         print("Robot Simulation initialized")
#         print("Controls: W/S = forward/back, A/D = turn, Space = stop")
#         print("Objective: Move robot to the red goal marker")
    
#     def setup_pybullet(self):
#         """Setup PyBullet with good viewing angle"""
#         self.physics_client = p.connect(p.GUI)
#         p.setAdditionalSearchPath(pybullet_data.getDataPath())
        
#         # Graphics settings
#         p.configureDebugVisualizer(p.COV_ENABLE_SHADOWS, 1)
#         p.configureDebugVisualizer(p.COV_ENABLE_GUI, 0)
#         p.setGravity(0, 0, -9.81)
        
#         # Set camera to follow robot (ish)
#         self.camera_distance = 15
#         self.camera_yaw = 45
#         self.camera_pitch = -30
    
#     def add_goal_marker(self):
#         """Add a visual marker for the goal (bottom of terrain)"""
#         goal_x = self.terrain_size / 2
#         goal_y = 2.0  # Near bottom edge
        
#         # Get terrain height at goal
#         h_min = self.terrain.current_heightmap.min()
#         h_max = self.terrain.current_heightmap.max()
#         mid_h = (h_min + h_max) / 2.0
        
#         ix = int(goal_x / self.cell_size)
#         iy = int(goal_y / self.cell_size)
#         if 0 <= ix < self.grid_size and 0 <= iy < self.grid_size:
#             goal_z = (self.terrain.current_heightmap[iy, ix] - mid_h) + 0.5
#         else:
#             goal_z = 0.5
        
#         # Goal marker (red cylinder)
#         goal_vis = p.createVisualShape(
#             p.GEOM_CYLINDER,
#             radius=0.5,
#             length=0.2,
#             rgbaColor=[1, 0, 0, 0.7]
#         )
#         self.goal_id = p.createMultiBody(
#             baseMass=0,
#             baseVisualShapeIndex=goal_vis,
#             basePosition=[goal_x, goal_y, goal_z]
#         )
        
#         # Add floating text
#         p.addUserDebugText(
#             "GOAL",
#             [goal_x, goal_y, goal_z + 1],
#             textColorRGB=[1, 0, 0],
#             textSize=1.5
#         )
        
#         self.goal_position = [goal_x, goal_y, goal_z]
    
#     def setup_networking(self):
#         """Setup ZeroMQ subscriber"""
#         self.context = zmq.Context()
#         self.socket = self.context.socket(zmq.SUB)
#         self.socket.connect("tcp://localhost:5555")
#         self.socket.setsockopt_string(zmq.SUBSCRIBE, "")
#         self.socket.RCVTIMEO = 100
    
#     def handle_keyboard(self):
#         """Handle keyboard input for robot control"""
#         keys = p.getKeyboardEvents()
        
#         # Reset controls
#         self.forward = 0
#         self.turn = 0
        
#         # W/S for forward/backward
#         if ord('w') in keys and keys[ord('w')] & p.KEY_IS_DOWN:
#             self.forward = 1
#         if ord('s') in keys and keys[ord('s')] & p.KEY_IS_DOWN:
#             self.forward = -1
            
#         # A/D for turning
#         if ord('a') in keys and keys[ord('a')] & p.KEY_IS_DOWN:
#             self.turn = 1
#         if ord('d') in keys and keys[ord('d')] & p.KEY_IS_DOWN:
#             self.turn = -1
        
#         # Space to stop
#         if ord(' ') in keys and keys[ord(' ')] & p.KEY_WAS_TRIGGERED:
#             self.forward = 0
#             self.turn = 0
#             p.resetBaseVelocity(self.robot.robot_id)
    
#     def update_terrain_data(self):
#         """Receive and update terrain data from generator"""
#         try:
#             msg = self.socket.recv_json()
            
#             terrain = msg.get('terrain', {})
#             seq = msg.get('sequence_id', 0)
#             debris_data = msg.get('debris', [])
            
#             # Update terrain data in EnhancedTerrain
#             if 'heightmap' in terrain:
#                 heightmap = np.array(terrain['heightmap']).reshape(self.grid_size, self.grid_size)
#                 self.terrain.current_heightmap = heightmap
            
#             if 'silt_depth' in terrain:
#                 silt = np.array(terrain['silt_depth']).reshape(self.grid_size, self.grid_size)
#                 self.terrain.current_silt = silt
            
#             if 'flow_u' in terrain:
#                 self.terrain.flow_u = np.array(terrain['flow_u']).reshape(self.grid_size, self.grid_size)
#             if 'flow_v' in terrain:
#                 self.terrain.flow_v = np.array(terrain['flow_v']).reshape(self.grid_size, self.grid_size)
            
#             # Update terrain visualization
#             p.configureDebugVisualizer(p.COV_ENABLE_RENDERING, 0)
#             self.terrain.update_terrain(
#                 self.terrain.current_heightmap,
#                 self.terrain.current_silt,
#                 None  # traversability computed inside
#             )
            
#             # Update debris
#             self.update_debris(debris_data)
            
#             # Update water
#             self.terrain.update_water_surface(self.terrain.current_heightmap)
            
#             p.configureDebugVisualizer(p.COV_ENABLE_RENDERING, 1)
            
#             return seq, debris_data
            
#         except zmq.Again:
#             return None, None
    
#     def update_debris(self, debris_data):
#         """Update debris from generator data"""
#         # Remove old debris
#         for body_id in self.debris_bodies:
#             p.removeBody(body_id)
#         self.debris_bodies = []
        
#         for item in debris_data:
#             x = item.get('x', 0)
#             y = item.get('y', 0)
#             item_type = item.get('type', 'unknown')
#             size = item.get('size', 0.2)
            
#             # Get terrain height at this position
#             ix = int(x / self.cell_size)
#             iy = int(y / self.cell_size)
#             if 0 <= ix < self.grid_size and 0 <= iy < self.grid_size:
#                 h_min = self.terrain.current_heightmap.min()
#                 h_max = self.terrain.current_heightmap.max()
#                 mid_h = (h_min + h_max) / 2.0
#                 z = (self.terrain.current_heightmap[iy, ix] - mid_h) + size/2
#             else:
#                 z = size/2
            
#             # Color by type
#             colors = {
#                 'bottle': [0.2, 0.8, 0.2, 1],  # Green
#                 'idol': [0.9, 0.7, 0.1, 1],    # Gold
#                 'cloth': [0.9, 0.2, 0.2, 1],   # Red
#                 'metal': [0.5, 0.5, 0.5, 1]    # Gray
#             }
#             color = colors.get(item_type, [1, 0, 1, 1])
            
#             # Create debris as simple sphere (for now)
#             vis = p.createVisualShape(
#                 p.GEOM_SPHERE,
#                 radius=size,
#                 rgbaColor=color
#             )
#             col = p.createCollisionShape(
#                 p.GEOM_SPHERE,
#                 radius=size
#             )
            
#             body = p.createMultiBody(
#                 baseMass=0.5,  # Light mass so robot can push
#                 baseCollisionShapeIndex=col,
#                 baseVisualShapeIndex=vis,
#                 basePosition=[x, y, z]
#             )
            
#             self.debris_bodies.append(body)
    
#     def check_goal_reached(self):
#         """Check if robot reached the goal"""
#         robot_pos = self.robot.get_position()
#         goal_pos = self.goal_position
        
#         distance = np.sqrt((robot_pos[0] - goal_pos[0])**2 + 
#                           (robot_pos[1] - goal_pos[1])**2)
        
#         if distance < 1.0:  # Within 1 meter of goal
#             return True
#         return False
    
#     def update_display_info(self, frame_num):
#         """Update on-screen information"""
#         p.removeAllUserDebugItems()
        
#         robot_pos = self.robot.get_position()
        
#         info = [
#             f"Frame: {frame_num}",
#             f"Robot Position: ({robot_pos[0]:.1f}, {robot_pos[1]:.1f}, {robot_pos[2]:.2f})",
#             f"Debris Count: {len(self.debris_bodies)}",
#             f"Collisions: {self.collision_count}",
#             f"Goal Distance: {np.sqrt((robot_pos[0]-self.goal_position[0])**2 + (robot_pos[1]-self.goal_position[1])**2):.1f}m",
#             "",
#             "Controls: W/S = forward/back, A/D = turn",
#             "Space = stop"
#         ]
        
#         for i, text in enumerate(info):
#             p.addUserDebugText(
#                 text,
#                 [2, self.terrain_size - 2 - i*1.2, 5],
#                 textColorRGB=[1, 1, 1],
#                 textSize=1.0
#             )
        
#         # Show goal reached message
#         if self.check_goal_reached():
#             p.addUserDebugText(
#                 "🎉 GOAL REACHED! 🎉",
#                 [self.terrain_size/2, self.terrain_size/2, 5],
#                 textColorRGB=[1, 0.5, 0],
#                 textSize=2.0
#             )
    
#     def run(self):
#         """Main simulation loop"""
#         p.setRealTimeSimulation(1)
        
#         frame_num = 0
#         last_camera_update = time.time()
        
#         print("\nStarting simulation...")
#         print(f"Goal at: ({self.goal_position[0]:.1f}, {self.goal_position[1]:.1f})")
        
#         while True:
#             # Handle keyboard input
#             self.handle_keyboard()
            
#             # Apply robot control
#             self.robot.apply_control(self.forward, self.turn)
            
#             # Check for collisions with debris
#             collisions = self.robot.check_collision_with_debris(self.debris_bodies)
#             if collisions:
#                 self.collision_count += len(collisions)
#                 # Push debris away
#                 for debris_id in collisions:
#                     self.robot.push_debris(debris_id)
            
#             # Receive terrain updates
#             seq, debris = self.update_terrain_data()
#             if seq is not None:
#                 frame_num = seq
            
#             # Update display
#             self.update_display_info(frame_num)
            
#             # Make camera follow robot (optional)
#             robot_pos = self.robot.get_position()
#             p.resetDebugVisualizerCamera(
#                 cameraDistance=self.camera_distance,
#                 cameraYaw=self.camera_yaw,
#                 cameraPitch=self.camera_pitch,
#                 cameraTargetPosition=[robot_pos[0], robot_pos[1], robot_pos[2]]
#             )
            
#             # Small sleep
#             time.sleep(0.01)

# if __name__ == "__main__":
#     sim = RobotSimulation()
#     try:
#         sim.run()
#     except KeyboardInterrupt:
#         print("\nShutting down...")
#         p.disconnect()

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
import tempfile
from simple_robot import SimpleRobot

class RobotSimulation:
    def __init__(self, grid_size=64, cell_size=0.5, terrain_height_scale=2.0):
        self.grid_size = grid_size
        self.cell_size = cell_size
        self.terrain_height_scale = terrain_height_scale
        self.terrain_size = grid_size * cell_size
        
        # Connect to PyBullet
        self.setup_pybullet()
        
        # Create enhanced terrain (using your existing class)
        from pybullet_terrain import EnhancedTerrain
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
        
        # Add goal marker (where robot should go)
        self.add_goal_marker()
        
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
        print("Controls: Arrow keys = move/turn, Space = stop")
        print("Objective: Move robot to the red goal marker")
    
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
    
    def add_goal_marker(self):
        """Add a visual marker for the goal (bottom of terrain)"""
        goal_x = self.terrain_size / 2
        goal_y = 2.0  # Near bottom edge
        
        # Get terrain height at goal
        h_min = self.terrain.current_heightmap.min()
        h_max = self.terrain.current_heightmap.max()
        mid_h = (h_min + h_max) / 2.0
        
        ix = int(goal_x / self.cell_size)
        iy = int(goal_y / self.cell_size)
        if 0 <= ix < self.grid_size and 0 <= iy < self.grid_size:
            goal_z = (self.terrain.current_heightmap[iy, ix] - mid_h) + 0.5
        else:
            goal_z = 0.5
        
        # Goal marker (red cylinder)
        goal_vis = p.createVisualShape(
            p.GEOM_CYLINDER,
            radius=0.5,
            length=0.2,
            rgbaColor=[1, 0, 0, 0.7]
        )
        self.goal_id = p.createMultiBody(
            baseMass=0,
            baseVisualShapeIndex=goal_vis,
            basePosition=[goal_x, goal_y, goal_z]
        )
        
        # Add floating text
        p.addUserDebugText(
            "GOAL",
            [goal_x, goal_y, goal_z + 1],
            textColorRGB=[1, 0, 0],
            textSize=1.5
        )
        
        self.goal_position = [goal_x, goal_y, goal_z]
    
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
    
    def update_terrain_data(self):
        """Receive and update terrain data from generator"""
        try:
            msg = self.socket.recv_json()
            
            terrain = msg.get('terrain', {})
            seq = msg.get('sequence_id', 0)
            debris_data = msg.get('debris', [])
            
            # Update terrain data in EnhancedTerrain
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
            
            # Update terrain visualization (no render toggle – avoids flicker)
            self.terrain.update_terrain(
                self.terrain.current_heightmap,
                self.terrain.current_silt,
                None  # traversability computed inside
            )
            
            # Update debris
            self.update_debris(debris_data)
            
            # Update water
            self.terrain.update_water_surface(self.terrain.current_heightmap)
            
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
                baseMass=0.5,  # Light mass so robot can push
                baseCollisionShapeIndex=col,
                baseVisualShapeIndex=vis,
                basePosition=[x, y, z]
            )
            
            self.debris_bodies.append(body)
    
    def check_goal_reached(self):
        """Check if robot reached the goal"""
        robot_pos = self.robot.get_position()
        goal_pos = self.goal_position
        
        distance = np.sqrt((robot_pos[0] - goal_pos[0])**2 + 
                          (robot_pos[1] - goal_pos[1])**2)
        
        if distance < 1.0:  # Within 1 meter of goal
            return True
        return False
    
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
        goal_dist = np.sqrt((robot_pos[0] - self.goal_position[0])**2 +
                            (robot_pos[1] - self.goal_position[1])**2)

        info = [
            f"Frame: {frame_num}",
            f"Robot: ({robot_pos[0]:.1f}, {robot_pos[1]:.1f}, {robot_pos[2]:.2f})",
            f"Debris: {len(self.debris_bodies)}",
            f"Collisions: {self.collision_count}",
            f"Goal Distance: {goal_dist:.1f}m",
            "",
            "Arrow keys = move/turn, Space = stop",
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

        if self.check_goal_reached():
            tid = p.addUserDebugText(
                "GOAL REACHED!",
                [self.terrain_size / 2, self.terrain_size / 2, 5],
                textColorRGB=[1, 0.5, 0],
                textSize=2.0,
                lifeTime=0.3,
            )
            self._debug_text_ids.append(tid)
    
    def run(self):
        """Main simulation loop"""
        p.setRealTimeSimulation(1)
        
        frame_num = 0
        last_camera_update = time.time()
        
        print("\nStarting simulation...")
        print(f"Goal at: ({self.goal_position[0]:.1f}, {self.goal_position[1]:.1f})")
        
        while True:
            # Handle keyboard input
            self.handle_keyboard()

            if self.forward != 0 or self.turn != 0:
                # Terrain-aware control (already calls apply_control inside)
                props = self.robot.apply_terrain_aware_control(
                    self.forward, self.turn, self.terrain
                )
                # Log challenging terrain
                if props['silt'] > 0.4:
                    print(f"High silt ({props['silt']:.2f}) - moving slower")
                if props['slope'] > 0.1:
                    print(f"Steep slope ({props['slope']:.2f})")
            else:
                # No input – brake
                self.robot.apply_control(0, 0)

            # Keep robot upright each frame
            self.robot.update()

            # Check for collisions with debris
            collisions = self.robot.check_collision_with_debris(self.debris_bodies)
            if collisions:
                self.collision_count += len(collisions)
                for debris_id in collisions:
                    self.robot.push_debris(debris_id)

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