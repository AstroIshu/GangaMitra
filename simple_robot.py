
import pybullet as p
import numpy as np
import math

class SimpleRobot:
    def __init__(self, start_pos=[16, 16, 1.0]):
        self.start_pos = list(start_pos)
        self.robot_id = None
        self.speed = 8.0
        self.turn_speed = 4.0

        # For keyboard control
        self.forward = 0
        self.turn = 0

        # For debris interaction tracking
        self.collision_debris = set()
        self.collected_debris = []

        # Robot dimensions
        self.length = 1.0
        self.width = 0.8
        self.height = 0.4
        self.wheel_radius = 0.25
        self.wheel_width = 0.15
        self.num_wheels = 4

        self.create_robot()

    def create_robot(self):
        """Create a box robot with 4 wheels attached as child links."""

        # --- shapes -------------------------------------------------
        body_col = p.createCollisionShape(
            p.GEOM_BOX,
            halfExtents=[self.length / 2, self.width / 2, self.height / 2],
        )
        body_vis = p.createVisualShape(
            p.GEOM_BOX,
            halfExtents=[self.length / 2, self.width / 2, self.height / 2],
            rgbaColor=[0.2, 0.5, 0.8, 1.0],
        )

        wheel_col = p.createCollisionShape(
            p.GEOM_CYLINDER, radius=self.wheel_radius, height=self.wheel_width
        )
        wheel_vis = p.createVisualShape(
            p.GEOM_CYLINDER,
            radius=self.wheel_radius,
            length=self.wheel_width,
            rgbaColor=[0.3, 0.3, 0.3, 1.0],
        )

        # --- wheel link parameters ----------------------------------
        wx = self.length * 0.35
        wy = self.width / 2 + self.wheel_width / 2
        wz = -self.height / 2          # bottom edge of body

        wheel_positions = [
            [ wx, -wy, wz],             # front-left
            [ wx,  wy, wz],             # front-right
            [-wx, -wy, wz],             # rear-left
            [-wx,  wy, wz],             # rear-right
        ]

        # Rotate cylinder so its axis (Z) points along parent Y (sideways)
        wheel_orn = p.getQuaternionFromEuler([math.pi / 2, 0, 0])

        self.robot_id = p.createMultiBody(
            baseMass=5.0,
            baseCollisionShapeIndex=body_col,
            baseVisualShapeIndex=body_vis,
            basePosition=self.start_pos,
            linkMasses=[0.5] * self.num_wheels,
            linkCollisionShapeIndices=[wheel_col] * self.num_wheels,
            linkVisualShapeIndices=[wheel_vis] * self.num_wheels,
            linkPositions=wheel_positions,
            linkOrientations=[wheel_orn] * self.num_wheels,
            linkInertialFramePositions=[[0, 0, 0]] * self.num_wheels,
            linkInertialFrameOrientations=[[0, 0, 0, 1]] * self.num_wheels,
            linkParentIndices=[0] * self.num_wheels,
            linkJointTypes=[p.JOINT_REVOLUTE] * self.num_wheels,
            linkJointAxis=[[0, 0, 1]] * self.num_wheels,
        )

        # --- dynamics ------------------------------------------------
        p.changeDynamics(
            self.robot_id, -1,
            lateralFriction=0.5,
            angularDamping=0.9,
            linearDamping=0.1,
        )
        for i in range(self.num_wheels):
            p.changeDynamics(
                self.robot_id, i,
                lateralFriction=1.5,
                spinningFriction=0.3,
                rollingFriction=0.01,
            )
            # Let wheels spin freely
            p.setJointMotorControl2(
                self.robot_id, i, p.VELOCITY_CONTROL,
                targetVelocity=0, force=0,
            )

        print(f"Robot created at position {self.start_pos}")

    # -----------------------------------------------------------------
    # Control
    # -----------------------------------------------------------------
    def apply_control(self, forward_cmd, turn_cmd):
        """Apply force-based control for smooth, non-jittery movement."""
        pos, orn = p.getBasePositionAndOrientation(self.robot_id)
        yaw = p.getEulerFromQuaternion(orn)[2]
        current_lin, current_ang = p.getBaseVelocity(self.robot_id)

        # --- linear velocity (smooth blend) --------------------------
        target_vx = math.cos(yaw) * forward_cmd * self.speed
        target_vy = math.sin(yaw) * forward_cmd * self.speed

        # Lerp towards target (higher = more responsive)
        blend = 0.4
        new_vx = current_lin[0] + (target_vx - current_lin[0]) * blend
        new_vy = current_lin[1] + (target_vy - current_lin[1]) * blend

        # --- angular velocity (smooth blend) -------------------------
        target_wz = turn_cmd * self.turn_speed
        new_wz = current_ang[2] + (target_wz - current_ang[2]) * blend

        p.resetBaseVelocity(
            self.robot_id,
            linearVelocity=[new_vx, new_vy, current_lin[2]],
            angularVelocity=[0, 0, new_wz],
        )

        # Spin wheel visuals
        wheel_spin = forward_cmd * self.speed / self.wheel_radius
        for i in range(self.num_wheels):
            p.setJointMotorControl2(
                self.robot_id, i, p.VELOCITY_CONTROL,
                targetVelocity=wheel_spin, force=2,
            )

    def set_movement(self, speed, steering):
        """Alias for apply_control."""
        self.apply_control(speed, steering)

    # -----------------------------------------------------------------
    # State queries
    # -----------------------------------------------------------------
    def get_position(self):
        """Return (x, y, z) position tuple."""
        pos, _ = p.getBasePositionAndOrientation(self.robot_id)
        return pos

    def get_orientation(self):
        """Return orientation quaternion (x, y, z, w)."""
        _, orn = p.getBasePositionAndOrientation(self.robot_id)
        return orn

    def get_velocity(self):
        """Return (linear_vel, angular_vel)."""
        return p.getBaseVelocity(self.robot_id)

    # -----------------------------------------------------------------
    # Per-frame update
    # -----------------------------------------------------------------
    def update(self):
        """Call once per frame – gently keeps robot upright & clears collision set."""
        pos, orn = p.getBasePositionAndOrientation(self.robot_id)
        roll, pitch, yaw = p.getEulerFromQuaternion(orn)

        # Only correct if tilt is significant (> ~17 degrees)
        # Use a torque-based correction instead of hard reset to avoid jitter
        if abs(roll) > 0.3 or abs(pitch) > 0.3:
            corrected = p.getQuaternionFromEuler([0, 0, yaw])
            lin_vel, ang_vel = p.getBaseVelocity(self.robot_id)
            p.resetBasePositionAndOrientation(self.robot_id, pos, corrected)
            p.resetBaseVelocity(self.robot_id, lin_vel, [0, 0, ang_vel[2]])

        self.collision_debris.clear()

    # -----------------------------------------------------------------
    # Reset
    # -----------------------------------------------------------------
    def reset_position(self, pos):
        """Teleport robot to *pos* with zero velocity."""
        orn = p.getQuaternionFromEuler([0, 0, 0])
        p.resetBasePositionAndOrientation(self.robot_id, pos, orn)
        p.resetBaseVelocity(self.robot_id, [0, 0, 0], [0, 0, 0])

    # -----------------------------------------------------------------
    # Debug drawing
    # -----------------------------------------------------------------
    def draw_debug_info(self):
        """Draw a forward-direction line above the robot."""
        pos, orn = p.getBasePositionAndOrientation(self.robot_id)
        yaw = p.getEulerFromQuaternion(orn)[2]
        end = [pos[0] + math.cos(yaw) * 1.5,
               pos[1] + math.sin(yaw) * 1.5,
               pos[2]]
        p.addUserDebugLine(pos, end, [1, 0, 0], 2, lifeTime=0.1)

    # -----------------------------------------------------------------
    # Debris interaction
    # -----------------------------------------------------------------
    def check_collision_with_debris(self, debris_bodies):
        """Return list of debris body-ids currently in contact."""
        collisions = []
        for debris_id in debris_bodies:
            if p.getContactPoints(self.robot_id, debris_id):
                collisions.append(debris_id)
        return collisions

    def push_debris(self, debris_id, force=10.0):
        """Push a debris body away from the robot."""
        robot_pos = self.get_position()
        debris_pos, _ = p.getBasePositionAndOrientation(debris_id)

        direction = np.array([
            debris_pos[0] - robot_pos[0],
            debris_pos[1] - robot_pos[1],
            0,
        ])
        dist = np.linalg.norm(direction)
        if dist > 0:
            direction /= dist
            p.applyExternalForce(
                debris_id, -1,
                forceObj=[direction[0] * force, direction[1] * force, 0],
                posObj=debris_pos,
                flags=p.WORLD_FRAME,
            )

    # -----------------------------------------------------------------
    # Terrain helpers
    # -----------------------------------------------------------------
    def get_terrain_properties(self, terrain):
        """Sample terrain height / silt / slope at robot position."""
        pos = self.get_position()

        cell_size = getattr(terrain, 'cell_size', 0.5)
        grid_size = getattr(terrain, 'grid_size', 64)

        ix = int(np.clip(pos[0] / cell_size, 0, grid_size - 1))
        iy = int(np.clip(pos[1] / cell_size, 0, grid_size - 1))

        height = 0.0
        silt   = 0.0
        slope  = 0.0

        if hasattr(terrain, 'current_heightmap'):
            h = terrain.current_heightmap
            height = float(h[iy, ix])
            if 0 < ix < grid_size - 1 and 0 < iy < grid_size - 1:
                dx = (h[iy, ix + 1] - h[iy, ix - 1]) / (2 * cell_size)
                dy = (h[iy + 1, ix] - h[iy - 1, ix]) / (2 * cell_size)
                slope = float(math.sqrt(dx ** 2 + dy ** 2))

        if hasattr(terrain, 'current_silt'):
            silt = float(terrain.current_silt[iy, ix])

        return {
            'height': height,
            'silt': silt,
            'slope': slope,
            'traversability': max(0, 1 - silt * 2 - slope * 5),
        }

    def apply_terrain_aware_control(self, forward_cmd, turn_cmd, terrain):
        """Like apply_control but slows down on silt / steep slopes."""
        props = self.get_terrain_properties(terrain)
        speed_factor = props['traversability']

        adjusted_turn = turn_cmd
        if props['silt'] > 0.3:
            adjusted_turn += np.random.normal(0, props['silt'] * 0.5)

        self.apply_control(forward_cmd * speed_factor, adjusted_turn)
        return props