import json
import time
import zmq
import numpy as np
from noise import pnoise2

# Configuration
GRID_SIZE = 64
CELL_SIZE = 0.5
PUB_FREQ = 0.5
ZMQ_PORT = 5555

def carve_river_channel(heightmap):
    rows, cols = heightmap.shape
    x = np.linspace(0, 4*np.pi, cols)
    amplitude = 10 + 3 * np.random.randn()
    phase = np.random.uniform(0, 2*np.pi)
    centerline = rows//2 + amplitude * np.sin(x + phase)
    centerline = np.clip(centerline, 2, rows-3)

    river_width = 5
    river_depth = 0.8
    for j in range(cols):
        center = int(centerline[j])
        for i in range(max(0, center - river_width), min(rows, center + river_width + 1)):
            dist = abs(i - center)
            factor = np.exp(- (dist**2) / (2*(river_width/2)**2))
            heightmap[i, j] -= river_depth * factor

    heightmap = np.clip(heightmap, 0, None)
    return heightmap, centerline

def generate_silt_depth(centerline):
    rows, cols = GRID_SIZE, GRID_SIZE
    silt = np.zeros((rows, cols))
    river_width = 5
    for i in range(rows):
        for j in range(cols):
            dist_to_center = abs(i - centerline[j])
            bank_dist = abs(dist_to_center - river_width/2)
            silt_factor = np.exp(- (bank_dist**2) / (2*(river_width/4)**2))
            noise_val = pnoise2(i/5, j/5, octaves=2) * 0.5 + 0.5
            silt[i, j] = (silt_factor * 0.8 + noise_val * 0.2) * 0.5
    return silt

def place_debris(centerline):
    debris = []
    num_items = np.random.randint(5, 15)
    types = ["bottle", "idol", "cloth", "metal"]
    for _ in range(num_items):
        j = np.random.randint(0, GRID_SIZE)
        center = centerline[j]
        river_width = 5
        bank_offset = np.random.choice([-1, 1]) * (river_width/2 + np.random.uniform(-1, 2))
        i = int(center + bank_offset)
        i = np.clip(i, 0, GRID_SIZE-1)
        
        item_type = np.random.choice(types)
        if item_type == "bottle":
            size, buoyant, tangle = 0.2, True, False
        elif item_type == "idol":
            size, buoyant, tangle = 0.5, False, False
        elif item_type == "cloth":
            size, buoyant, tangle = 0.8, False, True
        else:  # metal
            size, buoyant, tangle = 0.3, False, False
        
        debris.append({
            "x": j * CELL_SIZE,
            "y": i * CELL_SIZE,
            "type": item_type,
            "size": size,
            "buoyant": buoyant,
            "tangle_risk": tangle
        })
    return debris

def generate_flow_field():
    u = np.ones((GRID_SIZE, GRID_SIZE)) * 0.5
    v = np.zeros((GRID_SIZE, GRID_SIZE))
    for i in range(GRID_SIZE):
        for j in range(GRID_SIZE):
            u[i, j] += pnoise2(i/3, j/3) * 0.2
            v[i, j] += pnoise2(i/3+100, j/3) * 0.2
    return u, v

def generate_terrain_frame():
    # Base heightmap
    heightmap = np.zeros((GRID_SIZE, GRID_SIZE))
    scale = 10.0
    for i in range(GRID_SIZE):
        for j in range(GRID_SIZE):
            heightmap[i, j] = pnoise2(i / scale, j / scale, octaves=6)
    heightmap = (heightmap - heightmap.min()) / (heightmap.max() - heightmap.min())
    heightmap = heightmap * 2.0

    # Carve river
    heightmap, centerline = carve_river_channel(heightmap)

    # Silt
    silt = generate_silt_depth(centerline)

    # Debris
    debris = place_debris(centerline)

    # Flow (optional)
    u, v = generate_flow_field()

    return heightmap, silt, debris, u, v

def main():
    context = zmq.Context()
    socket = context.socket(zmq.PUB)
    socket.bind(f"tcp://*:{ZMQ_PORT}")
    print(f"Generator started, publishing on port {ZMQ_PORT}")

    seq = 0
    while True:
        heightmap, silt, debris, flow_u, flow_v = generate_terrain_frame()
        
        msg = {
    "timestamp": time.time(),
    "sequence_id": seq,
    "terrain": {
        "heightmap": heightmap.flatten().tolist(),
        "silt_depth": silt.flatten().tolist(),
        "flow_u": flow_u.flatten().tolist(),
        "flow_v": flow_v.flatten().tolist()
    },
    "debris": debris,
    "metadata": {
        "grid_size": GRID_SIZE,
        "cell_size": CELL_SIZE,
        "season": np.random.choice(["dry", "monsoon"])
    }
}
        print("Message keys:", msg.keys())
        if 'terrain' in msg:
            print("Terrain keys:", msg['terrain'].keys())
        print("Debris count:", len(msg['debris']))

        socket.send_json(msg)
        print(f"Sent frame {seq} with {len(debris)} debris items")

        seq += 1
        time.sleep(1.0 / PUB_FREQ)

if __name__ == "__main__":
    main()