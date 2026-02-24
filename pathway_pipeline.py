import os
import pathway as pw
import numpy as np
import json
import zmq
import time
import threading
from datetime import datetime

# Get configuration from environment variables
GENERATOR_HOST = os.environ.get('GENERATOR_HOST', 'host.docker.internal')
GENERATOR_PORT = int(os.environ.get('GENERATOR_PORT', '5555'))
OUTPUT_PORT = int(os.environ.get('OUTPUT_PORT', '5556'))
DASHBOARD_PORT = int(os.environ.get('DASHBOARD_PORT', '5557'))

print(f"Pathway pipeline starting with config:")
print(f"  Generator: {GENERATOR_HOST}:{GENERATOR_PORT}")
print(f"  Output binding: 0.0.0.0:{OUTPUT_PORT}")
print(f"  Dashboard binding: 0.0.0.0:{DASHBOARD_PORT}")

# ZeroMQ setup
context = zmq.Context()

# Input socket (SUB) - connects to generator on Windows
input_socket = context.socket(zmq.SUB)
input_socket.connect(f"tcp://{GENERATOR_HOST}:{GENERATOR_PORT}")
input_socket.setsockopt_string(zmq.SUBSCRIBE, "")
input_socket.RCVTIMEO = 1000  # 1 second timeout
print(f"✓ Connected to generator at {GENERATOR_HOST}:{GENERATOR_PORT}")

# Output socket (PUB) - binds for simulator to connect
output_socket = context.socket(zmq.PUB)
output_socket.bind(f"tcp://0.0.0.0:{OUTPUT_PORT}")
print(f"✓ Output bound to 0.0.0.0:{OUTPUT_PORT}")

# Dashboard socket (PUB) - binds for dashboard to connect
dashboard_socket = context.socket(zmq.PUB)
dashboard_socket.bind(f"tcp://0.0.0.0:{DASHBOARD_PORT}")
print(f"✓ Dashboard bound to 0.0.0.0:{DASHBOARD_PORT}")

def compute_traversability(heightmap_list, silt_list, grid_size, cell_size):
    """Compute traversability from heightmap and silt depth."""
    try:
        heightmap = np.array(heightmap_list).reshape(grid_size, grid_size)
        silt = np.array(silt_list).reshape(grid_size, grid_size)
        
        # Calculate slope
        gy, gx = np.gradient(heightmap, cell_size)
        slope_magnitude = np.sqrt(gx**2 + gy**2)
        
        # Penalties
        slope_penalty = np.tanh(slope_magnitude * 2)
        silt_penalty = np.clip(silt / 0.5, 0, 1)
        
        # Combined traversability
        traversability = 1.0 - (0.4 * slope_penalty + 0.6 * silt_penalty)
        traversability = np.clip(traversability, 0, 1)
        
        return traversability.flatten().tolist()
    except Exception as e:
        print(f"Error in traversability computation: {e}")
        return [0.0] * (grid_size * grid_size)

def main():
    print("\n🚀 Pathway pipeline is running!")
    print("Waiting for data from generator...\n")
    
    frame_count = 0
    
    while True:
        try:
            # Receive message from generator (with timeout)
            msg = input_socket.recv_json()
            frame_count += 1
            
            # Extract data
            terrain = msg.get('terrain', {})
            metadata = msg.get('metadata', {})
            grid_size = metadata.get('grid_size', 64)
            cell_size = metadata.get('cell_size', 0.5)
            
            print(f"\n📦 Frame {msg['sequence_id']} received")
            
            # Compute traversability
            if 'heightmap' in terrain and 'silt_depth' in terrain:
                start_time = time.time()
                traversability = compute_traversability(
                    terrain['heightmap'],
                    terrain['silt_depth'],
                    grid_size,
                    cell_size
                )
                compute_time = (time.time() - start_time) * 1000
                
                # Add traversability to message
                terrain['traversability'] = traversability
                
                print(f"  ⚙️  Traversability computed in {compute_time:.1f}ms")
            
            # Add processing metadata
            current_time = datetime.now().timestamp()
            msg['pathways'] = {
                'ingest_time': msg['timestamp'],
                'process_time': current_time,
                'processing_latency_ms': (current_time - msg['timestamp']) * 1000,
                'processor': 'pathway-docker',
                'frame_count': frame_count
            }
            
            # Forward to simulator
            output_socket.send_json(msg)
            print(f"  📤 Forwarded to simulator")
            
            # Send metrics to dashboard
            metrics = {
                'timestamp': current_time,
                'sequence_id': msg['sequence_id'],
                'debris_count': len(msg.get('debris', [])),
                'latency_ms': msg['pathways']['processing_latency_ms'],
                'grid_size': grid_size,
                'compute_time_ms': compute_time if 'compute_time' in locals() else 0
            }
            dashboard_socket.send_json(metrics)
            print(f"  📊 Metrics sent to dashboard")
            
        except zmq.Again:
            # No message received within timeout - this is normal
            pass
        except Exception as e:
            print(f"❌ Error: {e}")
            time.sleep(0.1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nShutting down Pathway pipeline...")