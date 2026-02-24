import mujoco
import mujoco.viewer
import numpy as np
import time

# A simple XML with a ball that you can interact with
XML = """
<mujoco>
  <option timestep="0.005" gravity="0 0 -9.81"/>
  
  <asset>
    <texture name="grid" type="2d" builtin="checker" rgb1=".1 .2 .3" rgb2=".2 .3 .4" width="300" height="300"/>
    <material name="ground" texture="grid" texrepeat="5 5" reflectance=".2"/>
  </asset>
  
  <worldbody>
    <!-- Ground plane -->
    <geom name="floor" type="plane" size="5 5 0.1" material="ground"/>
    
    <!-- Light -->
    <light pos="0 2 5" dir="0 0 -1" directional="true"/>
    
    <!-- A red ball you can push around -->
    <body name="ball" pos="0 0 1">
      <joint name="ball_slide" type="slide" axis="1 0 0" limited="false"/>
      <joint name="ball_slide2" type="slide" axis="0 1 0" limited="false"/>
      <joint name="ball_spin" type="ball" limited="false"/>
      <geom name="ball_geom" type="sphere" size="0.5" rgba="1 0 0 1" mass="1"/>
    </body>
    
    <!-- A green block -->
    <body name="block" pos="1 1 0.25">
      <joint name="block_slide" type="slide" axis="1 0 0" limited="false"/>
      <joint name="block_slide2" type="slide" axis="0 1 0" limited="false"/>
      <geom name="block_geom" type="box" size="0.3 0.3 0.25" rgba="0 1 0 1" mass="2"/>
    </body>
    
    <!-- A blue ramp to slide things down -->
    <body name="ramp" pos="-1 -1 0">
      <geom name="ramp_geom" type="box" size="1 0.5 0.1" rgba="0 0 1 1" euler="0.3 0 0"/>
    </body>
  </worldbody>
  
  <actuator>
    <!-- Motors to control the ball (optional) -->
    <motor name="push_x" joint="ball_slide" gear="10" ctrlrange="-1 1"/>
    <motor name="push_y" joint="ball_slide2" gear="10" ctrlrange="-1 1"/>
  </actuator>
  
  <contact>
    <pair geom1="ball_geom" geom2="floor" solref="0.02 1"/>
  </contact>
</mujoco>
"""

# Save the XML
xml_path = 'playground.xml'
with open(xml_path, 'w') as f:
    f.write(XML)

print("Loading MuJoCo playground...")
print(f"MuJoCo version: {mujoco.__version__}")

# Load model
model = mujoco.MjModel.from_xml_path(xml_path)
data = mujoco.MjData(model)

print("Model loaded successfully!")
print("\nControls:")
print("- Click and drag objects with mouse (right button to rotate view)")
print("- Scroll to zoom")
print("- Press SPACE to pause")
print("- Press Ctrl+C in terminal to exit")
print("\nTry pushing the red ball into the green block!")

# Launch viewer
with mujoco.viewer.launch_passive(model, data) as viewer:
    # Enable contact points visualization
    viewer.opt.flags[mujoco.mjtVisFlag.mjVIS_CONTACTPOINT] = True
    
    # Simulation loop
    step = 0
    while viewer.is_running():
        # Step simulation
        mujoco.mj_step(model, data)
        
        # Sync viewer
        viewer.sync()
        
        # Add some simple periodic motion to demonstrate animation
        if step % 100 == 0:
            # Print ball position occasionally
            ball_pos = data.body("ball").xpos
            print(f"\rBall position: ({ball_pos[0]:.2f}, {ball_pos[1]:.2f}, {ball_pos[2]:.2f})", end="")
        
        step += 1
        time.sleep(0.001)  # Small sleep to prevent CPU hogging
        