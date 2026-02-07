"""Position history, velocity, acceleration, and trajectory fitting."""

from collections import defaultdict, deque
import numpy as np

import config
from basketball_analytics.utils import compute_velocity, compute_speed


class TrajectoryAnalyzer:
    """Tracks position history per object and computes motion analytics."""

    def __init__(self):
        self.history_length = config.TRAJECTORY_HISTORY_LENGTH
        self.positions = defaultdict(lambda: deque(maxlen=self.history_length))
        self.total_distance = defaultdict(float)
        self.max_speed = defaultdict(float)
        self.frame_count = defaultdict(int)

    def update(self, tracked_objects):
        """Record new positions for all tracked objects.

        Args:
            tracked_objects: OrderedDict of {object_id: (cx, cy)}
        """
        for obj_id, centroid in tracked_objects.items():
            positions = self.positions[obj_id]
            if len(positions) > 0:
                speed = compute_speed(positions[-1], centroid)
                self.total_distance[obj_id] += speed
                if speed > self.max_speed[obj_id]:
                    self.max_speed[obj_id] = speed
            positions.append(centroid)
            self.frame_count[obj_id] += 1

    def get_velocity(self, obj_id):
        """Get current velocity vector (dx, dy) for an object."""
        positions = self.positions.get(obj_id)
        if positions is None or len(positions) < 2:
            return (0, 0)
        return compute_velocity(positions[-2], positions[-1])

    def get_speed(self, obj_id):
        """Get current scalar speed for an object."""
        positions = self.positions.get(obj_id)
        if positions is None or len(positions) < 2:
            return 0.0
        return compute_speed(positions[-2], positions[-1])

    def get_acceleration(self, obj_id):
        """Get acceleration via central difference of last 3 positions."""
        positions = self.positions.get(obj_id)
        if positions is None or len(positions) < 3:
            return (0, 0)
        p0, p1, p2 = positions[-3], positions[-2], positions[-1]
        ax = (p2[0] - 2 * p1[0] + p0[0])
        ay = (p2[1] - 2 * p1[1] + p0[1])
        return (ax, ay)

    def get_trail_points(self, obj_id):
        """Get the position history as a list of (x, y) tuples."""
        return list(self.positions.get(obj_id, []))

    def fit_trajectory(self, obj_id):
        """Fit a degree-2 polynomial to the trajectory (parabolic arc).

        Returns polynomial coefficients or None if insufficient data.
        """
        positions = self.positions.get(obj_id)
        if positions is None or len(positions) < 3:
            return None
        pts = np.array(list(positions))
        x, y = pts[:, 0], pts[:, 1]
        # Avoid fitting if all x values are the same (vertical motion)
        if np.ptp(x) < 1:
            return None
        try:
            coeffs = np.polyfit(x, y, config.POLYFIT_DEGREE)
            return coeffs
        except (np.linalg.LinAlgError, ValueError):
            return None

    def get_summary(self, obj_id):
        """Get analytics summary for a tracked object."""
        positions = self.positions.get(obj_id, deque())
        frames = self.frame_count.get(obj_id, 0)
        total_dist = self.total_distance.get(obj_id, 0.0)
        avg_speed = total_dist / frames if frames > 1 else 0.0
        return {
            "object_id": obj_id,
            "frames_tracked": frames,
            "total_distance_px": round(total_dist, 1),
            "avg_speed_px_per_frame": round(avg_speed, 1),
            "max_speed_px_per_frame": round(self.max_speed.get(obj_id, 0.0), 1),
            "positions_in_buffer": len(positions),
        }

    def cleanup(self, active_ids):
        """Remove data for objects no longer tracked."""
        all_ids = set(self.positions.keys())
        for obj_id in all_ids - set(active_ids):
            del self.positions[obj_id]
            self.total_distance.pop(obj_id, None)
            self.max_speed.pop(obj_id, None)
            self.frame_count.pop(obj_id, None)
