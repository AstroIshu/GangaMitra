import zmq
import json

context = zmq.Context()
socket = context.socket(zmq.SUB)
socket.connect("tcp://localhost:5556")
socket.setsockopt_string(zmq.SUBSCRIBE, "")

print("Mock Simulator listening...")

while True:
    msg = socket.recv_json()
    terrain = msg['terrain']
    print(f"Seq {msg['sequence_id']} – Traversability present: {'traversability' in terrain}")
    if 'traversability' in terrain:
        trav = terrain['traversability'][:5]  # first few values
        print(f"  Traversability sample: {trav}")