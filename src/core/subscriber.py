import json
import zmq
import numpy as np

context = zmq.Context()
socket = context.socket(zmq.SUB)
socket.connect("tcp://localhost:5555")
socket.setsockopt_string(zmq.SUBSCRIBE, "")

while True:
    msg = socket.recv_json()
    print(f"Seq {msg['sequence_id']}, time {msg['timestamp']:.3f}")
    
    # Check terrain fields
    terrain = msg['terrain']
    print(f"  heightmap shape: {len(terrain['heightmap'])} values")
    print(f"  silt_depth shape: {len(terrain['silt_depth'])} values")
    print(f"  flow fields present: {'flow_u' in terrain}")
    
    # Print first few debris items
    debris = msg['debris']
    print(f"  debris count: {len(debris)}")
    for d in debris[:3]:   # first 3 items
        print(f"    {d}")
    print("-" * 40)