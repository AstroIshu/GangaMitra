import matplotlib.pyplot as plt
import matplotlib.animation as animation
import matplotlib.gridspec as gridspec
import numpy as np
import zmq
import json
from collections import deque
import time

# Set up ZeroMQ subscribers
context = zmq.Context()

# Metrics subscriber (from Pathway)
metrics_socket = context.socket(zmq.SUB)
metrics_socket.connect("tcp://localhost:5557")
metrics_socket.setsockopt_string(zmq.SUBSCRIBE, "")

# Data subscriber (full terrain data for visualization)
data_socket = context.socket(zmq.SUB)
data_socket.connect("tcp://localhost:5556")
data_socket.setsockopt_string(zmq.SUBSCRIBE, "")

# Create figure with GridSpec for symmetrical layout
fig = plt.figure(figsize=(16, 12))
fig.suptitle('🌊 GangaMitra Pathway Pipeline - Performance Dashboard', fontsize=16, fontweight='bold')

# Main grid: 4 rows, 2 columns (plus internal subdivisions)
gs_main = gridspec.GridSpec(4, 2, figure=fig, hspace=0.3, wspace=0.3)

# Row 0: Terrain Visualization (Heightmap and Silt Depth)
ax_height = fig.add_subplot(gs_main[0, 0])
ax_height.set_title('Heightmap', fontsize=12)
ax_height.set_xlabel('X (m)')
ax_height.set_ylabel('Y (m)')
height_plot = ax_height.imshow(np.zeros((64, 64)), origin='lower', 
                               cmap='terrain', vmin=0, vmax=2, extent=[0, 32, 0, 32])
plt.colorbar(height_plot, ax=ax_height, label='Height (m)', fraction=0.046, pad=0.04)

ax_silt = fig.add_subplot(gs_main[0, 1])
ax_silt.set_title('Silt Depth', fontsize=12)
ax_silt.set_xlabel('X (m)')
ax_silt.set_ylabel('Y (m)')
silt_plot = ax_silt.imshow(np.zeros((64, 64)), origin='lower', 
                           cmap='YlOrBr', vmin=0, vmax=0.5, extent=[0, 32, 0, 32])
plt.colorbar(silt_plot, ax=ax_silt, label='Silt Depth (m)', fraction=0.046, pad=0.04)

# Row 1: Traversability Map and Debris Distribution
ax_trav = fig.add_subplot(gs_main[1, 0])
ax_trav.set_title('Traversability Map', fontsize=12)
ax_trav.set_xlabel('X (m)')
ax_trav.set_ylabel('Y (m)')
trav_plot = ax_trav.imshow(np.zeros((64, 64)), origin='lower', 
                           cmap='RdYlGn', vmin=0, vmax=1, extent=[0, 32, 0, 32])
plt.colorbar(trav_plot, ax=ax_trav, label='Traversability', fraction=0.046, pad=0.04)

ax_debris = fig.add_subplot(gs_main[1, 1])
ax_debris.set_title('Debris Distribution', fontsize=12)
ax_debris.set_xlabel('X (m)')
ax_debris.set_ylabel('Y (m)')
ax_debris.set_xlim(0, 32)
ax_debris.set_ylim(0, 32)
debris_scatter = ax_debris.scatter([], [], c=[], s=80, alpha=0.7, edgecolors='black')
# Add legend for debris types manually? We'll add a text annotation instead.

# Row 2: Performance Metrics (2x2 grid inside the third row)
# We'll create a nested GridSpec within gs_main[2, :] to have 2 rows and 2 columns
gs_perf = gridspec.GridSpecFromSubplotSpec(2, 2, subplot_spec=gs_main[2, :], hspace=0.4, wspace=0.3)

ax_latency = fig.add_subplot(gs_perf[0, 0])
ax_latency.set_title('Processing Latency', fontsize=11)
ax_latency.set_xlabel('Frame')
ax_latency.set_ylabel('ms')
ax_latency.set_ylim(0, 100)
line_latency, = ax_latency.plot([], [], 'b-', linewidth=2)

ax_throughput = fig.add_subplot(gs_perf[0, 1])
ax_throughput.set_title('Throughput', fontsize=11)
ax_throughput.set_xlabel('Time (s)')
ax_throughput.set_ylabel('FPS')
ax_throughput.set_ylim(0, 10)
line_throughput, = ax_throughput.plot([], [], 'g-', linewidth=2)

ax_debris_history = fig.add_subplot(gs_perf[1, 0])
ax_debris_history.set_title('Debris Count Over Time', fontsize=11)
ax_debris_history.set_xlabel('Frame')
ax_debris_history.set_ylabel('Items')
ax_debris_history.set_ylim(0, 30)
line_debris_history, = ax_debris_history.plot([], [], 'r-', linewidth=2)

ax_trav_avg = fig.add_subplot(gs_perf[1, 1])
ax_trav_avg.set_title('Avg Traversability', fontsize=11)
ax_trav_avg.set_xlabel('Frame')
ax_trav_avg.set_ylabel('Score')
ax_trav_avg.set_ylim(0, 1)
line_trav_avg, = ax_trav_avg.plot([], [], 'm-', linewidth=2)

# Row 3: Statistics Text Box (spans both columns)
ax_stats = fig.add_subplot(gs_main[3, :])
ax_stats.axis('off')
stats_text = ax_stats.text(0.02, 0.5, '', fontsize=10, family='monospace',
                           transform=ax_stats.transAxes,
                           bbox=dict(boxstyle="round,pad=0.5", facecolor="lightyellow", alpha=0.8),
                           verticalalignment='center')

# Data storage for time series
max_len = 100
frame_numbers = deque(maxlen=max_len)
latencies = deque(maxlen=max_len)
throughput_vals = deque(maxlen=max_len)
debris_counts_ts = deque(maxlen=max_len)
trav_avgs = deque(maxlen=max_len)

# For throughput calculation
last_time = time.time()
frames_since_last = 0

def update_plot(frame):
    global last_time, frames_since_last
    
    # Check for metrics data
    try:
        metrics_msg = metrics_socket.recv_json(flags=zmq.NOBLOCK)
        
        current_time = time.time()
        seq = metrics_msg.get('sequence_id', 0)
        latency = metrics_msg.get('latency_ms', 0)
        debris_cnt = metrics_msg.get('debris_count', 0)
        
        frame_numbers.append(seq)
        latencies.append(latency)
        debris_counts_ts.append(debris_cnt)
        
        # Throughput calculation
        frames_since_last += 1
        if current_time - last_time >= 1.0:
            fps = frames_since_last / (current_time - last_time)
            throughput_vals.append(fps)
            frames_since_last = 0
            last_time = current_time
        else:
            if throughput_vals:
                throughput_vals.append(throughput_vals[-1])
            else:
                throughput_vals.append(0)
        
        # Update line plots if we have data
        if len(frame_numbers) > 0:
            x = range(len(frame_numbers))
            line_latency.set_data(x, latencies)
            ax_latency.relim()
            ax_latency.autoscale_view()
            
            line_throughput.set_data(x, throughput_vals)
            ax_throughput.relim()
            ax_throughput.autoscale_view()
            
            line_debris_history.set_data(x, debris_counts_ts)
            ax_debris_history.relim()
            ax_debris_history.autoscale_view()
            
    except zmq.Again:
        pass
    
    # Check for full terrain data
    try:
        data_msg = data_socket.recv_json(flags=zmq.NOBLOCK)
        
        terrain = data_msg.get('terrain', {})
        debris = data_msg.get('debris', [])
        metadata = data_msg.get('metadata', {})
        grid_size = metadata.get('grid_size', 64)
        cell_size = metadata.get('cell_size', 0.5)
        seq = data_msg.get('sequence_id', 0)
        
        # Update heightmap
        if 'heightmap' in terrain:
            heightmap = np.array(terrain['heightmap']).reshape(grid_size, grid_size)
            height_plot.set_data(heightmap)
            ax_height.set_title(f'Heightmap (Frame {seq})', fontsize=12)
        
        # Update silt depth
        if 'silt_depth' in terrain:
            silt = np.array(terrain['silt_depth']).reshape(grid_size, grid_size)
            silt_plot.set_data(silt)
        
        # Update traversability
        if 'traversability' in terrain:
            trav = np.array(terrain['traversability']).reshape(grid_size, grid_size)
            trav_plot.set_data(trav)
            
            avg_trav = np.mean(trav)
            trav_avgs.append(avg_trav)
            if len(trav_avgs) > 0:
                x_trav = range(len(trav_avgs))
                line_trav_avg.set_data(x_trav, trav_avgs)
                ax_trav_avg.relim()
                ax_trav_avg.autoscale_view()
        
        # Update debris scatter
        if debris:
            debris_x = [d['x'] for d in debris]
            debris_y = [d['y'] for d in debris]
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
            debris_scatter.set_offsets(np.c_[debris_x, debris_y])
            debris_scatter.set_color(colors)
            ax_debris.set_title(f'Debris Distribution ({len(debris)} items)', fontsize=12)
        else:
            debris_scatter.set_offsets(np.empty((0, 2)))
        
        # Update stats text
        if latencies:
            current_latency = latencies[-1]
            avg_latency = np.mean(latencies)
            max_latency = max(latencies)
        else:
            current_latency = avg_latency = max_latency = 0
        
        # Calculate some derived metrics
        fps_now = throughput_vals[-1] if throughput_vals else 0
        avg_trav_now = np.mean(trav_avgs) if trav_avgs else 0
        
        stats_str = f"""
╔══════════════════════════════════════════════════════════════╗
║                    PERFORMANCE SUMMARY                        ║
╠══════════════════════════════════════════════════════════════╣
║  Current Frame    : {seq:<8d}       Debris Count    : {len(debris):<8d}      ║
║  Avg Traversability: {avg_trav_now:.3f}         Latency (ms)    : {current_latency:<8.2f}      ║
║  Throughput (fps)  : {fps_now:<8.2f}       Avg Latency     : {avg_latency:<8.2f}      ║
║  Max Latency (ms)  : {max_latency:<8.2f}       Grid Size       : {grid_size}x{grid_size:<8d}      ║
╚══════════════════════════════════════════════════════════════╝
        """
        stats_text.set_text(stats_str)
        
    except zmq.Again:
        pass
    
    return (height_plot, silt_plot, trav_plot, debris_scatter,
            line_latency, line_throughput, line_debris_history, line_trav_avg)

# Create animation
ani = animation.FuncAnimation(fig, update_plot, interval=100, cache_frame_data=False)

plt.tight_layout()
plt.show()