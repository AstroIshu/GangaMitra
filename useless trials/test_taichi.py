# test_taichi.py
import taichi as ti
import numpy as np
import matplotlib.pyplot as plt

ti.init(arch=ti.gpu)  # Try ti.cpu if GPU doesn't work

# Create a simple wave simulation
grid_size = 128
height = ti.field(dtype=ti.f32, shape=(grid_size, grid_size))

@ti.kernel
def update_wave(t: ti.f32):
    for i, j in height:
        x = i / grid_size * 4.0 - 2.0
        y = j / grid_size * 4.0 - 2.0
        dist = ti.sqrt(x*x + y*y)
        height[i, j] = 1.0 + 0.5 * ti.sin(dist * 3.0 - t * 2.0)

print("Taichi Wave Test - Close window to exit")

fig, ax = plt.subplots()
im = ax.imshow(height.to_numpy(), cmap='terrain', vmin=0, vmax=2)
plt.colorbar(im)

for t in range(200):
    update_wave(t * 0.1)
    im.set_data(height.to_numpy())
    plt.pause(0.05)
    