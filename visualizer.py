import matplotlib.pyplot as plt
import matplotlib.animation as animation
import numpy as np
import zmq
import json

# ZeroMQ subscriber setup
context = zmq.Context()
socket = context.socket(zmq.SUB)
socket.connect("tcp://localhost:5555")
socket.setsockopt_string(zmq.SUBSCRIBE, "")

# Set up the figure with two subplots
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

# Initialize with empty data (will be filled on first frame)
extent = [0, 32, 0, 32]  # 64 cells * 0.5m = 32m
height_dummy = np.zeros((64, 64))
silt_dummy = np.zeros((64, 64))

# Create image objects and colorbars ONCE
im1 = ax1.imshow(height_dummy, origin='lower', extent=extent, cmap='terrain', vmin=0, vmax=2)
ax1.set_title('Heightmap')
ax1.set_xlabel('X (m)')
ax1.set_ylabel('Y (m)')
cbar1 = plt.colorbar(im1, ax=ax1, label='Height (m)')

im2 = ax2.imshow(silt_dummy, origin='lower', extent=extent, cmap='YlOrBr', vmin=0, vmax=0.5)
ax2.set_title('Silt Depth')
ax2.set_xlabel('X (m)')
ax2.set_ylabel('Y (m)')
cbar2 = plt.colorbar(im2, ax=ax2, label='Silt depth (m)')

# Create scatter plot objects for debris (initially empty)
scat1 = ax1.scatter([], [], c=[], s=50, edgecolors='black', zorder=5)
scat2 = ax2.scatter([], [], c=[], s=50, edgecolors='black', zorder=5)

fig.suptitle('GangaMitra Generator – Waiting for data...')

def update_plot(frame):
    try:
        # Receive latest message (non‑blocking)
        msg = socket.recv_json(flags=zmq.NOBLOCK)
    except zmq.Again:
        return im1, im2, scat1, scat2  # no new data

    seq = msg['sequence_id']
    terrain = msg['terrain']
    debris = msg['debris']
    metadata = msg.get('metadata', {})
    grid_size = metadata.get('grid_size', 64)
    cell_size = metadata.get('cell_size', 0.5)

    # Update extent in case grid_size changes (it shouldn't)
    extent = [0, grid_size * cell_size, 0, grid_size * cell_size]
    
    # Reshape data
    height = np.array(terrain['heightmap']).reshape(grid_size, grid_size)
    silt = np.array(terrain['silt_depth']).reshape(grid_size, grid_size)

    # Update image data (this is fast – only pixel values change)
    im1.set_data(height)
    im2.set_data(silt)
    
    # Update debris scatter data
    if debris:
        debris_x = [d['x'] for d in debris]
        debris_y = [d['y'] for d in debris]
        # Color by type
        colors = []
        for d in debris:
            if d['type'] == 'bottle':
                colors.append('green')
            elif d['type'] == 'idol':
                colors.append('gold')
            elif d['type'] == 'cloth':
                colors.append('red')
            else:
                colors.append('gray')
        
        # Update scatter positions and colors
        scat1.set_offsets(np.c_[debris_x, debris_y])
        scat1.set_color(colors)
        scat2.set_offsets(np.c_[debris_x, debris_y])
        scat2.set_color(colors)
    else:
        # No debris – clear the scatter plots
        scat1.set_offsets(np.empty((0, 2)))
        scat2.set_offsets(np.empty((0, 2)))

    # Update title
    fig.suptitle(f'GangaMitra Generator – Frame {seq} – Debris: {len(debris)}')
    
    return im1, im2, scat1, scat2

# Use matplotlib animation for smooth updates
ani = animation.FuncAnimation(fig, update_plot, interval=100, cache_frame_data=False)
plt.tight_layout()
plt.show(block=True)