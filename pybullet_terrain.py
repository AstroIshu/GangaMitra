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

class EnhancedTerrain:
    def __init__(self, grid_size=64, cell_size=0.5, terrain_height_scale=2.0):
        self.grid_size = grid_size
        self.cell_size = cell_size
        self.terrain_height_scale = terrain_height_scale
        self.terrain_size = grid_size * cell_size
        self._tex_counter = 0  # Unique counter for texture filenames
        
        # Terrain textures
        self.terrain_texture_id = None
        self.create_terrain_texture()
        
        # Create terrain with smooth shading
        self.create_enhanced_terrain()
        
        # Add solid ground plane below terrain as a safety floor
        self.create_ground_plane()
        
        # Add water effects
        self.create_water_effect()
        
        # Add vegetation/rocks for visual interest
        self.add_environment_details()
    
    def create_terrain_texture(self):
        """Create a realistic terrain texture using vectorized numpy"""
        texture_size = 256  # Smaller for speed
        
        # Vectorized coordinate grids
        ii, jj = np.meshgrid(
            np.linspace(0, 10, texture_size),
            np.linspace(0, 10, texture_size),
            indexing='ij'
        )
        
        # Vectorized noise layers
        n1 = np.abs(np.sin(ii * 10) * np.cos(jj * 10)) * 0.5
        n2 = np.abs(np.sin(ii * 20 + 1) * np.cos(jj * 20 + 1)) * 0.3
        n3 = np.abs(np.sin(ii * 40 + 2) * np.cos(jj * 40 + 2)) * 0.2
        noise_val = n1 + n2 + n3
        
        # Color mapping (vectorized)
        texture = np.zeros((texture_size, texture_size, 3), dtype=np.float64)
        
        # Wet sand (noise < 0.3)
        mask1 = noise_val < 0.3
        texture[mask1] = [139, 119, 101]
        
        # Dry sand (0.3 <= noise < 0.6)
        mask2 = (noise_val >= 0.3) & (noise_val < 0.6)
        texture[mask2] = [194, 178, 128]
        
        # Gravel (noise >= 0.6)
        mask3 = noise_val >= 0.6
        texture[mask3] = [128, 128, 128]
        
        # Add random variation
        variation = 0.8 + 0.4 * np.random.random((texture_size, texture_size, 1))
        texture = np.clip(texture * variation, 0, 255).astype(np.uint8)
        
        img = Image.fromarray(texture)
        self.texture_path = os.path.join(tempfile.gettempdir(), "gangamitra_terrain_texture.png")
        img.save(self.texture_path)
        
        self.terrain_texture_id = None
    
    def create_enhanced_terrain(self):
        """Create terrain with proper coloring"""
        
        # Create heightfield data (initially flat)
        heightfield_data = np.zeros(self.grid_size * self.grid_size, dtype=np.float32)
        
        # Create collision shape — PyBullet auto-generates the visual from this
        terrain_collision = p.createCollisionShape(
            shapeType=p.GEOM_HEIGHTFIELD,
            meshScale=[self.cell_size, self.cell_size, self.terrain_height_scale],
            heightfieldData=heightfield_data,
            numHeightfieldRows=self.grid_size,
            numHeightfieldColumns=self.grid_size
        )
        
        # Create the terrain body (visual is auto-generated from collision shape)
        self.terrain_id = p.createMultiBody(
            baseMass=0,
            baseCollisionShapeIndex=terrain_collision,
            basePosition=[self.terrain_size/2, self.terrain_size/2, 0]
        )
        
        # Set a base color so terrain isn't black (sandy color)
        p.changeVisualShape(self.terrain_id, -1, rgbaColor=[0.76, 0.70, 0.50, 1])
        
        # Load and apply the procedural texture
        if hasattr(self, 'texture_path') and os.path.exists(self.texture_path):
            self.terrain_texture_id = p.loadTexture(self.texture_path)
            p.changeVisualShape(self.terrain_id, -1, textureUniqueId=self.terrain_texture_id)
    
    def create_ground_plane(self):
        """Create a solid ground plane below the terrain as a safety floor for robots."""
        # Place it well below the terrain's lowest possible point.
        # The heightfield is centered at z=0; with scale=2 and data range ~[-1,1],
        # the lowest terrain point is about -1. Put the floor at -2.
        self.ground_z = -2.0
        
        ground_col = p.createCollisionShape(
            p.GEOM_BOX,
            halfExtents=[self.terrain_size, self.terrain_size, 0.5]
        )
        ground_vis = p.createVisualShape(
            p.GEOM_BOX,
            halfExtents=[self.terrain_size, self.terrain_size, 0.5],
            rgbaColor=[0.3, 0.25, 0.2, 1.0]  # Dark brown
        )
        self.ground_plane_id = p.createMultiBody(
            baseMass=0,
            baseCollisionShapeIndex=ground_col,
            baseVisualShapeIndex=ground_vis,
            basePosition=[self.terrain_size / 2, self.terrain_size / 2, self.ground_z - 0.5]
        )
    
    def create_water_effect(self):
        """Create a water surface layer — a grid of tiles that follow terrain height."""
        # Water surface resolution — match terrain grid for tight fit
        self.water_res = 32  # 32x32 = 1024 smaller tiles
        self.water_tile_size = self.terrain_size / self.water_res
        self.water_bodies = []
        self.water_level = 0.8

        # Flow field (will be updated from generator data)
        self.flow_u = np.zeros((self.grid_size, self.grid_size))
        self.flow_v = np.zeros((self.grid_size, self.grid_size))

        for i in range(self.water_res):
            row = []
            for j in range(self.water_res):
                x = (j + 0.5) * self.water_tile_size
                y = (i + 0.5) * self.water_tile_size

                vis = p.createVisualShape(
                    p.GEOM_BOX,
                    halfExtents=[self.water_tile_size / 2, self.water_tile_size / 2, 0.02],
                    rgbaColor=[0.1, 0.4, 0.8, 0.45]
                )
                body = p.createMultiBody(
                    baseMass=0,
                    baseVisualShapeIndex=vis,
                    basePosition=[x, y, self.water_level]
                )
                row.append(body)
            self.water_bodies.append(row)
    
    def update_water_surface(self, heightmap):
        """Update water tile heights and visibility to match the terrain."""
        # PyBullet heightfields are centered vertically around basePosition.z (0).
        # World-space z for a heightmap value h is: h - (h_min + h_max) / 2
        h_min = heightmap.min()
        h_max = heightmap.max()
        mid_h = (h_min + h_max) / 2.0
        
        # Compute world-space heights (matching PyBullet's vertical centering)
        world_heights = heightmap - mid_h
        
        # Water level: 30th percentile of world heights + small offset above surface
        water_z = np.percentile(world_heights, 30) + 0.15
        world_min = world_heights.min()
        
        for i in range(self.water_res):
            for j in range(self.water_res):
                cx = (j + 0.5) * self.water_tile_size
                cy = (i + 0.5) * self.water_tile_size
                
                ix = int(cx / self.cell_size)
                iy = int(cy / self.cell_size)
                ix = np.clip(ix, 0, self.grid_size - 1)
                iy = np.clip(iy, 0, self.grid_size - 1)
                
                terrain_z = world_heights[iy, ix]
                body = self.water_bodies[i][j]
                
                if terrain_z < water_z:
                    # Tile is in a low area — show water
                    depth = water_z - terrain_z
                    max_depth = water_z - world_min + 0.01
                    depth_ratio = np.clip(depth / max_depth, 0.15, 1.0)
                    
                    r = max(0.02, 0.15 - depth_ratio * 0.1)
                    g = max(0.15, 0.50 - depth_ratio * 0.15)
                    b = min(0.95, 0.70 + depth_ratio * 0.2)
                    a = min(0.7, 0.25 + depth_ratio * 0.4)
                    
                    # fu = self.flow_u[iy, ix]
                    # fv = self.flow_v[iy, ix]
                    # flow_mag = np.sqrt(fu**2 + fv**2)
                    # wave = np.sin(time.time() * 3 + cx + cy) * 0.02 * (1 + flow_mag)
                    
                    # # Ensure tile always sits above the terrain surface
                    # tile_z = max(water_z + wave, terrain_z + 0.05)
                    # In the tile loop, use the flow properly:
                    fu = self.flow_u[iy, ix] if hasattr(self, 'flow_u') else 0
                    fv = self.flow_v[iy, ix] if hasattr(self, 'flow_v') else 0
                    flow_mag = min(1.0, np.sqrt(fu**2 + fv**2) / 0.5)  # Normalize
    
                    # Animated wave with flow influence
                    wave = (
                        np.sin(time.time() * 3 + cx * 0.5 + cy * 0.3) * 0.02 +
                        np.sin(time.time() * 5 + cy * 0.7) * 0.01 * (1 + flow_mag * 2)
                    )
    
                    # Flow-based surface distortion
                    flow_offset_x = fu * 0.5 * np.sin(time.time() * 2)
                    flow_offset_y = fv * 0.5 * np.cos(time.time() * 2)
    
                    tile_z = max(water_z + wave + flow_offset_x + flow_offset_y, terrain_z + 0.05)
                    
                    p.resetBasePositionAndOrientation(
                        body, [cx, cy, tile_z], [0, 0, 0, 1]
                    )
                    p.changeVisualShape(body, -1, rgbaColor=[r, g, b, a])
                else:
                    # Tile is above water level — hide it
                    p.resetBasePositionAndOrientation(
                        body, [cx, cy, -10], [0, 0, 0, 1]
                    )
    
    def add_environment_details(self):
        """Add rocks, plants, etc. for visual interest"""
        # Add some random rocks (will be positioned based on terrain height later)
        self.rocks = []
        for i in range(20):
            x = np.random.uniform(2, self.terrain_size - 2)
            y = np.random.uniform(2, self.terrain_size - 2)
            
            # Rock visual
            rock_visual = p.createVisualShape(
                shapeType=p.GEOM_SPHERE,
                radius=0.2 + np.random.random() * 0.3,
                rgbaColor=[0.5, 0.5, 0.5, 1]
            )
            
            rock_collision = p.createCollisionShape(
                shapeType=p.GEOM_SPHERE,
                radius=0.2 + np.random.random() * 0.3
            )
            
            rock = p.createMultiBody(
                baseMass=0,  # Static
                baseCollisionShapeIndex=rock_collision,
                baseVisualShapeIndex=rock_visual,
                basePosition=[x, y, 0]  # Height will be updated
            )
            self.rocks.append(rock)
    
    def update_terrain(self, heightmap, silt_depth=None, traversability=None):
        """Update terrain with new data and adjust colors based on silt/traversability"""
        
        # Normalize heights for PyBullet
        heightmap_flat = heightmap.flatten().astype(np.float32)
        normalized_heights = heightmap_flat / self.terrain_height_scale
        
        # Rebuild the collision/visual shape with new height data
        # Remove old terrain body
        p.removeBody(self.terrain_id)
        
        terrain_collision = p.createCollisionShape(
            shapeType=p.GEOM_HEIGHTFIELD,
            meshScale=[self.cell_size, self.cell_size, self.terrain_height_scale],
            heightfieldData=normalized_heights,
            numHeightfieldRows=self.grid_size,
            numHeightfieldColumns=self.grid_size
        )
        
        self.terrain_id = p.createMultiBody(
            baseMass=0,
            baseCollisionShapeIndex=terrain_collision,
            basePosition=[self.terrain_size/2, self.terrain_size/2, 0]
        )
        
        # Always generate a dynamic color texture from the current data
        self._update_terrain_color_texture(heightmap, silt_depth, traversability)
        
        # Update rock positions to sit on terrain (world-space z)
        h_min = heightmap.min()
        h_max = heightmap.max()
        mid_h = (h_min + h_max) / 2.0
        for rock in self.rocks:
            pos, _ = p.getBasePositionAndOrientation(rock)
            x, y, _ = pos
            ix = int(x / self.cell_size)
            iy = int(y / self.cell_size)
            if 0 <= ix < self.grid_size and 0 <= iy < self.grid_size:
                h = heightmap[iy, ix] - mid_h
                p.resetBasePositionAndOrientation(rock, [x, y, h + 0.3], [0, 0, 0, 1])
    
    def _update_terrain_color_texture(self, heightmap, silt_depth, traversability):
        """Generate a color texture that smoothly reflects current terrain data."""
        gs = self.grid_size  # 64
        
        h = heightmap
        s = silt_depth if silt_depth is not None else np.zeros((gs, gs))
        t = traversability if traversability is not None else np.ones((gs, gs))
        
        # Normalize height to 0-1 range for smooth color blending
        h_min, h_max = h.min(), h.max()
        h_norm = (h - h_min) / (h_max - h_min + 1e-8)
        
        # Normalize silt to 0-1
        s_max = s.max()
        s_norm = s / (s_max + 1e-8) if s_max > 0 else s
        
        # --- Smooth continuous color blending ---
        # Layer 1: height-based gradient  (deep blue -> sand -> brown -> gray rock)
        # Deep water color
        deep_r, deep_g, deep_b = 30.0, 90.0, 160.0
        # Shallow water
        shal_r, shal_g, shal_b = 70.0, 140.0, 200.0
        # Sand
        sand_r, sand_g, sand_b = 210.0, 190.0, 140.0
        # Green bank
        green_r, green_g, green_b = 90.0, 160.0, 80.0
        # Rocky high ground
        rock_r, rock_g, rock_b = 140.0, 130.0, 120.0
        
        r = np.zeros((gs, gs), dtype=np.float64)
        g = np.zeros((gs, gs), dtype=np.float64)
        b = np.zeros((gs, gs), dtype=np.float64)
        
        # Height bands with smooth interpolation
        # Band 0: deep water (h_norm 0 - 0.2)
        m0 = h_norm < 0.2
        a0 = np.clip(h_norm / 0.2, 0, 1)
        r[m0] = deep_r * (1 - a0[m0]) + shal_r * a0[m0]
        g[m0] = deep_g * (1 - a0[m0]) + shal_g * a0[m0]
        b[m0] = deep_b * (1 - a0[m0]) + shal_b * a0[m0]
        
        # Band 1: shallow water to sand (h_norm 0.2 - 0.4)
        m1 = (h_norm >= 0.2) & (h_norm < 0.4)
        a1 = np.clip((h_norm - 0.2) / 0.2, 0, 1)
        r[m1] = shal_r * (1 - a1[m1]) + sand_r * a1[m1]
        g[m1] = shal_g * (1 - a1[m1]) + sand_g * a1[m1]
        b[m1] = shal_b * (1 - a1[m1]) + sand_b * a1[m1]
        
        # Band 2: sand to green (h_norm 0.4 - 0.65)
        m2 = (h_norm >= 0.4) & (h_norm < 0.65)
        a2 = np.clip((h_norm - 0.4) / 0.25, 0, 1)
        r[m2] = sand_r * (1 - a2[m2]) + green_r * a2[m2]
        g[m2] = sand_g * (1 - a2[m2]) + green_g * a2[m2]
        b[m2] = sand_b * (1 - a2[m2]) + green_b * a2[m2]
        
        # Band 3: green to rock (h_norm 0.65 - 1.0)
        m3 = h_norm >= 0.65
        a3 = np.clip((h_norm - 0.65) / 0.35, 0, 1)
        r[m3] = green_r * (1 - a3[m3]) + rock_r * a3[m3]
        g[m3] = green_g * (1 - a3[m3]) + rock_g * a3[m3]
        b[m3] = green_b * (1 - a3[m3]) + rock_b * a3[m3]
        
        # Layer 2: silt overlay — darken and brown-shift where silt is present
        silt_influence = np.clip(s_norm * 1.5, 0, 1)
        mud_r, mud_g, mud_b = 90.0, 65.0, 40.0
        r = r * (1 - silt_influence) + mud_r * silt_influence
        g = g * (1 - silt_influence) + mud_g * silt_influence
        b = b * (1 - silt_influence) + mud_b * silt_influence
        
        # Layer 3: traversability tint — good traversability gets slight green boost
        trav_boost = np.clip((t - 0.5) * 2, 0, 1) * 0.15
        g = np.clip(g + trav_boost * 60, 0, 255)
        
        # Subtle noise for natural look
        noise = 0.92 + 0.16 * np.random.random((gs, gs))
        r = np.clip(r * noise, 0, 255)
        g = np.clip(g * noise, 0, 255)
        b = np.clip(b * noise, 0, 255)
        
        # Assemble texture
        texture = np.stack([r, g, b], axis=-1).astype(np.uint8)
        
        # Upscale to 128x128
        texture_up = np.repeat(np.repeat(texture, 2, axis=0), 2, axis=1)
        
        img = Image.fromarray(texture_up)
        # Use unique filename each frame to defeat PyBullet's texture cache
        # Only create new texture if data changed significantly
        if hasattr(self, '_last_tex_data'):
            diff = np.abs(texture - self._last_tex_data).mean()
            if diff < 5:  # Small change, skip update
                return
    
        self._last_tex_data = texture.copy()
        self._tex_counter += 1
        path = os.path.join(tempfile.gettempdir(), f"gangamitra_tex_{self._tex_counter % 4}.png")
        img.save(path)
        
        tex_id = p.loadTexture(path)
        p.changeVisualShape(self.terrain_id, -1, rgbaColor=[1, 1, 1, 1])
        p.changeVisualShape(self.terrain_id, -1, textureUniqueId=tex_id)

class EnhancedTerrainViewer:
    def __init__(self, grid_size=64, cell_size=0.5, terrain_height_scale=2.0):
        self.grid_size = grid_size
        self.cell_size = cell_size
        self.terrain_height_scale = terrain_height_scale
        self.terrain_size = grid_size * cell_size
        
        # Connect to PyBullet with enhanced settings
        self.physics_client = p.connect(p.GUI)
        p.setAdditionalSearchPath(pybullet_data.getDataPath())
        
        # Enhanced graphics settings
        p.configureDebugVisualizer(p.COV_ENABLE_SHADOWS, 1)
        p.configureDebugVisualizer(p.COV_ENABLE_TINY_RENDERER, 0)
        p.configureDebugVisualizer(p.COV_ENABLE_GUI, 0)  # Hide GUI for cleaner look
        p.configureDebugVisualizer(p.COV_ENABLE_KEYBOARD_SHORTCUTS, 0)
        
        # Set gravity
        p.setGravity(0, 0, -9.81)
        
        # Set better camera angle
        p.resetDebugVisualizerCamera(
            cameraDistance=self.terrain_size * 0.8,
            cameraYaw=45,
            cameraPitch=-30,
            cameraTargetPosition=[self.terrain_size/2, self.terrain_size/2, 1]
        )
        
        # Add better lighting
        p.configureDebugVisualizer(p.COV_ENABLE_RGB_BUFFER_PREVIEW, 0)
        p.configureDebugVisualizer(p.COV_ENABLE_DEPTH_BUFFER_PREVIEW, 0)
        p.configureDebugVisualizer(p.COV_ENABLE_SEGMENTATION_MARK_PREVIEW, 0)
        
        # Create enhanced terrain
        self.terrain = EnhancedTerrain(grid_size, cell_size, terrain_height_scale)
        
        # Add sky and ambient lighting
        self.add_sky_and_fog()
        
        # ZeroMQ setup
        self.setup_networking()
        
        # For smooth animation
        self.last_update_time = time.time()
        self.current_heightmap = np.zeros((grid_size, grid_size))
        self.current_silt = np.zeros((grid_size, grid_size))
        self.current_trav = np.ones((grid_size, grid_size))
        self.current_flow_u = np.zeros((grid_size, grid_size))
        self.current_flow_v = np.zeros((grid_size, grid_size))
        
        # Debris tracking
        self.debris_bodies = []  # list of PyBullet body IDs
        
        # Visual config per debris type: (shape, color, scale_factor)
        # bottle  -> cylinder, green/transparent
        # idol    -> box, golden/orange
        # cloth   -> flat box, white/purple
        # metal   -> cylinder, dark gray/metallic
        self.debris_config = {
            "bottle": {
                "shape": p.GEOM_CYLINDER,
                "color": [0.2, 0.8, 0.3, 0.85],   # Green-ish translucent
                "radius": 0.08,
                "length": 0.25,
            },
            "idol": {
                "shape": p.GEOM_BOX,
                "color": [0.85, 0.65, 0.12, 1.0],  # Golden
                "halfExtents": [0.12, 0.12, 0.2],
            },
            "cloth": {
                "shape": p.GEOM_BOX,
                "color": [0.9, 0.85, 0.95, 0.8],   # White-purple, slightly transparent
                "halfExtents": [0.3, 0.3, 0.02],   # Flat
            },
            "metal": {
                "shape": p.GEOM_CYLINDER,
                "color": [0.35, 0.35, 0.4, 1.0],   # Dark metallic gray
                "radius": 0.1,
                "length": 0.2,
            },
        }
        
        print("Enhanced Terrain Viewer initialized. Waiting for data...")
    
    def setup_debug_controls(self):
        # FPS counter
        self.fps_counter = 0
        self.fps_last_time = time.time()
        self.fps_display = 0
    
        # Bind keys
        p.addUserDebugParameter("Camera Zoom", 10, 50, 30)
        p.addUserDebugParameter("Camera Yaw", -180, 180, 45)
        p.addUserDebugParameter("Camera Pitch", -90, 0, -30)
    
        # Print controls
        print("\nCamera Controls:")
        print("  Mouse drag: rotate view")
        print("  Mouse wheel: zoom")
        print("  [R] Reset camera")
        print("  [Space] Pause simulation")
        print("  [F] Toggle flow visualization")
    
    def setup_networking(self):
        """Setup ZeroMQ subscriber"""
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.SUB)
        self.socket.connect("tcp://localhost:5555")
        self.socket.setsockopt_string(zmq.SUBSCRIBE, "")
        self.socket.RCVTIMEO = 100
    
    def add_sky_and_fog(self):
        """Add atmospheric effects"""
        p.configureDebugVisualizer(p.COV_ENABLE_RENDERING, 0)
        # Enable fog if supported by this PyBullet version
        if hasattr(p, 'COV_ENABLE_FOG'):
            p.configureDebugVisualizer(p.COV_ENABLE_FOG, 1)
        p.configureDebugVisualizer(p.COV_ENABLE_RENDERING, 1)
    
    def get_terrain_color_at(self, height, silt, traversability):
        """Get color for a terrain point based on height, silt, and traversability"""
        # Base colors
        water_color = [0.2, 0.5, 0.8, 0.8]    # Blue for water
        sand_color = [0.76, 0.7, 0.5, 1]      # Light sand
        mud_color = [0.4, 0.3, 0.2, 1]        # Dark mud
        rock_color = [0.5, 0.5, 0.5, 1]       # Gray rock
        vegetation_color = [0.3, 0.6, 0.3, 1] # Green for traversable areas
        
        # Blend colors based on parameters
        if height < 0.5:  # Underwater
            return water_color
        elif silt > 0.3:  # Muddy areas
            # Blend mud and sand
            alpha = min(1, silt * 2)
            return [mud_color[i] * alpha + sand_color[i] * (1-alpha) for i in range(3)] + [1]
        elif traversability > 0.8:  # Good traversable areas (maybe vegetation)
            # Blend vegetation and sand
            alpha = traversability
            return [vegetation_color[i] * alpha + sand_color[i] * (1-alpha) for i in range(3)] + [1]
        else:
            return sand_color
    
    def update_debris(self, debris_list):
        """Remove old debris bodies and spawn new ones from the latest data."""
        # Remove previous debris
        for body_id in self.debris_bodies:
            p.removeBody(body_id)
        self.debris_bodies = []
        
        default_cfg = {
            "shape": p.GEOM_SPHERE,
            "color": [1.0, 0.0, 1.0, 1.0],  # Magenta fallback
        }
        
        for item in debris_list:
            x = item.get("x", 0)
            y = item.get("y", 0)
            item_type = item.get("type", "unknown")
            item_size = item.get("size", 0.2)
            
            cfg = self.debris_config.get(item_type, default_cfg)
            shape_type = cfg["shape"]
            color = cfg["color"]
            
            # Sample terrain height at debris position (world-space, matching PyBullet centering)
            ix = int(x / self.cell_size)
            iy = int(y / self.cell_size)
            h_min = self.current_heightmap.min()
            h_max = self.current_heightmap.max()
            mid_h = (h_min + h_max) / 2.0
            if 0 <= ix < self.grid_size and 0 <= iy < self.grid_size:
                z = (self.current_heightmap[iy, ix] - mid_h) + item_size * 0.5
            else:
                z = item_size * 0.5
            
            # Create visual + collision per type
            if shape_type == p.GEOM_CYLINDER:
                radius = cfg.get("radius", 0.1) * (item_size / 0.3)
                length = cfg.get("length", 0.2) * (item_size / 0.3)
                vis = p.createVisualShape(shape_type, radius=radius, length=length, rgbaColor=color)
                col = p.createCollisionShape(shape_type, radius=radius, height=length)
            elif shape_type == p.GEOM_BOX:
                he = cfg.get("halfExtents", [0.1, 0.1, 0.1])
                scale = item_size / 0.3
                he_scaled = [h * scale for h in he]
                vis = p.createVisualShape(shape_type, halfExtents=he_scaled, rgbaColor=color)
                col = p.createCollisionShape(shape_type, halfExtents=he_scaled)
            else:  # GEOM_SPHERE fallback
                vis = p.createVisualShape(p.GEOM_SPHERE, radius=item_size * 0.3, rgbaColor=color)
                col = p.createCollisionShape(p.GEOM_SPHERE, radius=item_size * 0.3)
            
            body = p.createMultiBody(
                baseMass=0,
                baseCollisionShapeIndex=col,
                baseVisualShapeIndex=vis,
                basePosition=[x, y, z]
            )
            self.debris_bodies.append(body)
    
    def update_display_info(self, seq, debris_count, avg_trav):
        """Update on-screen information"""
        # Clear previous text
        p.removeAllUserDebugItems()
        
        # Add info panel
        info_text = [
            f"Frame: {seq}",
            f"Debris: {debris_count}",
            f"Avg Traversability: {avg_trav:.2f}",
            f"Time: {time.strftime('%H:%M:%S')}"
        ]
        
        for i, text in enumerate(info_text):
            p.addUserDebugText(
                text,
                [2, self.terrain_size - 2 - i*1.5, 5],
                textColorRGB=[1, 1, 1],
                textSize=1.2
            )
    
    def run(self):
        """Main loop with smooth updates"""
        p.setRealTimeSimulation(1)  # Enable real-time
        
        frame_count = 0
        last_frame_time = time.time()
        
        while True:
            current_time = time.time()
            
            try:
                # Check for new terrain data
                msg = self.socket.recv_json()
                
                terrain = msg.get('terrain', {})
                seq = msg.get('sequence_id', 0)
                debris = msg.get('debris', [])
                
                print(f"Received frame {seq}, heightmap range: ", end="")
                
                # Update terrain data
                if 'heightmap' in terrain:
                    self.current_heightmap = np.array(terrain['heightmap']).reshape(self.grid_size, self.grid_size)
                    print(f"[{self.current_heightmap.min():.2f}, {self.current_heightmap.max():.2f}]")
                else:
                    print("no heightmap")
                
                if 'silt_depth' in terrain:
                    self.current_silt = np.array(terrain['silt_depth']).reshape(self.grid_size, self.grid_size)
                
                if 'flow_u' in terrain:
                    self.current_flow_u = np.array(terrain['flow_u']).reshape(self.grid_size, self.grid_size)
                if 'flow_v' in terrain:
                    self.current_flow_v = np.array(terrain['flow_v']).reshape(self.grid_size, self.grid_size)
                
                # Push flow field into the terrain's water system
                self.terrain.flow_u = self.current_flow_u
                self.terrain.flow_v = self.current_flow_v
                
                if 'traversability' in terrain:
                    self.current_trav = np.array(terrain['traversability']).reshape(self.grid_size, self.grid_size)
                else:
                    # Compute traversability from heightmap and silt
                    grad_x = np.gradient(self.current_heightmap, axis=1)
                    grad_y = np.gradient(self.current_heightmap, axis=0)
                    slope = np.sqrt(grad_x**2 + grad_y**2)
                    slope_max = slope.max()
                    slope_norm = np.clip(slope / slope_max if slope_max > 0 else slope, 0, 1)
                    silt_max = self.current_silt.max()
                    silt_norm = np.clip(self.current_silt / silt_max if silt_max > 0 else self.current_silt, 0, 1)
                    self.current_trav = np.clip(1.0 - 0.5 * slope_norm - 0.5 * silt_norm, 0, 1)
                
                # Disable rendering during update for speed, re-enable after
                p.configureDebugVisualizer(p.COV_ENABLE_RENDERING, 0)
                
                # Update terrain with new data
                self.terrain.update_terrain(
                    self.current_heightmap,
                    self.current_silt,
                    self.current_trav
                )
                
                # Update debris objects
                self.update_debris(debris)
                
                # Update water surface layer
                self.terrain.update_water_surface(self.current_heightmap)
                
                p.configureDebugVisualizer(p.COV_ENABLE_RENDERING, 1)
                
                # Update display info
                avg_trav = np.mean(self.current_trav)
                self.update_display_info(seq, len(debris), avg_trav)
                
                frame_count += 1
                if current_time - last_frame_time > 1:
                    print(f"Rendering frame {seq} - FPS: {frame_count}")
                    frame_count = 0
                    last_frame_time = current_time
                
            except zmq.Again:
                # No new message — still update water surface animation
                self.terrain.update_water_surface(self.current_heightmap)
            
            # Small sleep to prevent CPU overload
            time.sleep(0.01)

if __name__ == "__main__":
    viewer = EnhancedTerrainViewer()
    try:
        viewer.run()
    except KeyboardInterrupt:
        print("Shutting down...")
        p.disconnect()