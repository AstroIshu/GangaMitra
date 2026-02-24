# test_pinocchio.py
import pinocchio as pin
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import time

print("Pinocchio version:", pin.__version__)

# Create a simple terrain visualization with matplotlib
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4))

grid_size = 32
x = np.linspace(0, 16, grid_size)
y = np.linspace(0, 16, grid_size)
X, Y = np.meshgrid(x, y)

# Initial heightmap
Z = np.zeros((grid_size, grid_size))

# Plot
ax1.set_title('Heightmap 3D')
ax2.set_title('Heightmap 2D')
im = ax2.imshow(Z, cmap='terrain', vmin=0, vmax=2)

def update(frame):
    global Z
    # Create wave
    t = frame * 0.1
    for i in range(grid_size):
        for j in range(grid_size):
            dist = np.sqrt((i - grid_size/2)**2 + (j - grid_size/2)**2)
            Z[i, j] = 1.0 + 0.8 * np.sin(dist * 0.5 - t * 2)
    
    # Update 2D plot
    im.set_data(Z)
    
    # Update 3D plot
    ax1.clear()
    ax1.plot_surface(X, Y, Z, cmap='terrain', vmin=0, vmax=2)
    ax1.set_zlim(0, 2)
    ax1.set_title(f'Frame {frame}')
    
    return [im]

ani = FuncAnimation(fig, update, frames=100, interval=50, blit=False)
plt.show()