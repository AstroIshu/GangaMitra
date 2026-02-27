# test_gym.py
import gymnasium as gym
import numpy as np
import time

# Create a simple environment
env = gym.make('HalfCheetah-v4', render_mode='human')
env.reset()

print("Gym test - HalfCheetah should run")
print("Close window to exit")

for _ in range(1000):
    action = env.action_space.sample()
    obs, reward, terminated, truncated, info = env.step(action)
    env.render()
    if terminated or truncated:
        env.reset()
    time.sleep(0.01)

env.close()