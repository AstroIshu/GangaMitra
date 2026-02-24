# test_pychrono_simple.py
import pychrono as chrono
try:
    import pychrono.irrlicht as chronoirr
    HAS_IRRLICHT = True
except ImportError:
    print("Warning: pychrono.irrlicht not available. Running in headless mode.")
    HAS_IRRLICHT = False
import numpy as np
import math

# Create system
system = chrono.ChSystemNSC()
system.Set_G_acc(chrono.ChVectorD(0, 0, -9.81))

# Create a moving platform
platform = chrono.ChBodyEasyBox(10, 10, 0.2, 1000, True, True)
platform.SetPos(chrono.ChVectorD(0, 0, 0))
platform.SetBodyFixed(False)  # Let it move
system.Add(platform)

# Add a sphere on top
sphere = chrono.ChBodyEasySphere(0.5, 100, True, True)
sphere.SetPos(chrono.ChVectorD(0, 0, 0.5))
system.Add(sphere)

# Add a constraint to make the platform move up and down
# We'll use a motor to control position
motor = chrono.ChLinkMotorLinearPosition()
motor.Initialize(platform, chrono.ChBody(system.Get_bodylist()[0]), 
                 chrono.ChFrameD(chrono.ChVectorD(0, 0, 0)))
motor.SetMotionFunction(chrono.ChFunction_Sine(0, 0.5, 2.0))  # amplitude 0.5, frequency 2Hz
system.Add(motor)

# Visualization
if HAS_IRRLICHT:
    vis = chronoirr.ChVisualSystemIrrlicht()
    vis.AttachSystem(system)
    vis.SetWindowSize(1024, 768)
    vis.SetWindowTitle('PyChrono Simple Test')
    vis.Initialize()
    vis.AddCamera(chrono.ChVectorD(5, -10, 5), chrono.ChVectorD(0, 0, 1))
    vis.AddTypicalLights()

    print("PyChrono Simple Test - Platform should oscillate up and down")
    print("Close window to exit")

    while vis.Run():
        vis.Render()
        system.DoStepDynamics(0.01)
else:
    print("PyChrono Simple Test - Running headless simulation")
    print("Platform should oscillate up and down (no visualization available)")
    print("Running for 5 seconds...")
    
    for i in range(500):  # 5 seconds at 0.01 timestep
        system.DoStepDynamics(0.01)
        if i % 50 == 0:  # Print every 0.5 seconds
            print(f"Time: {i*0.01:.2f}s - Platform Z: {platform.GetPos().z:.3f} - Sphere Z: {sphere.GetPos().z:.3f}")
    
    print("Simulation completed!")
    
    # Print platform height occasionally
    if system.GetChTime() % 1 < 0.01:
        pos = platform.GetPos()
        print(f"Time: {system.GetChTime():.1f}, Platform height: {pos.z:.2f}")