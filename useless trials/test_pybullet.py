# test_pybullet.py
import pybullet as p
import pybullet_data
import numpy as np
import time

# Connect to physics server
p.connect(p.GUI)
p.setAdditionalSearchPath(pybullet_data.getDataPath())
p.setGravity(0, 0, -9.81)

# Load ground plane
plane_id = p.loadURDF("plane.urdf")

# Create terrain from heightmap
def create_terrain(heightmap, grid_size=32, cell_size=0.5):
    """Create a mesh terrain from heightmap."""
    vertices = []
    indices = []
    
    # Create vertices
    for i in range(grid_size):
        for j in range(grid_size):
            x = j * cell_size
            y = i * cell_size
            z = heightmap[i, j]
            vertices.append([x, y, z])
    
    # Create triangles (2 per cell)
    for i in range(grid_size - 1):
        for j in range(grid_size - 1):
            v0 = i * grid_size + j
            v1 = i * grid_size + j + 1
            v2 = (i + 1) * grid_size + j
            v3 = (i + 1) * grid_size + j + 1
            
            # Two triangles per cell
            indices.extend([v0, v1, v2])
            indices.extend([v1, v3, v2])
    
    # Create collision and visual shapes
    collision_id = p.createCollisionShape(p.GEOM_MESH, vertices=vertices, indices=indices)
    visual_id = p.createVisualShape(p.GEOM_MESH, vertices=vertices, indices=indices)
    
    # Create body
    terrain_id = p.createMultiBody(0, collision_id, visual_id)
    return terrain_id

# Create wave pattern
grid_size = 32
heightmap = np.zeros((grid_size, grid_size))

# Create initial terrain
terrain_id = create_terrain(heightmap)

# Add a sphere to see movement
sphere_id = p.createVisualShape(p.GEOM_SPHERE, radius=0.2, rgbaColor=[1, 0, 0, 1])
sphere_body = p.createMultiBody(1, sphere_id, basePosition=[8, 8, 2])

print("PyBullet Wave Test - Terrain should pulse")
print("Close window to exit")

# Animation loop
t = 0
while True:
    # Create wave pattern
    for i in range(grid_size):
        for j in range(grid_size):
            dist = np.sqrt((i - grid_size/2)**2 + (j - grid_size/2)**2)
            heightmap[i, j] = 1.0 + 0.8 * np.sin(dist * 0.5 - t * 2)
    
    # Update terrain (delete and recreate)
    p.removeBody(terrain_id)
    terrain_id = create_terrain(heightmap)
    
    # Update sphere height (should follow terrain)
    center_height = heightmap[grid_size//2, grid_size//2]
    p.resetBasePositionAndOrientation(sphere_body, [8, 8, center_height + 1.0], [0, 0, 0, 1])
    
    # Step simulation
    p.stepSimulation()
    time.sleep(0.05)
    t += 0.1