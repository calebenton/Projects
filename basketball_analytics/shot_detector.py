"""Shot detection via hoop ROI and state machine."""

from collections import defaultdict
from enum import Enum, auto
import time

import config


class ShotState(Enum):
    IDLE = auto()
    ABOVE_HOOP = auto()
    IN_HOOP = auto()
    SCORED = auto()
    MISSED = auto()


class ShotDetector:
    """Detects basketball shots using a hoop ROI and per-object state machine.

    State transitions:
        IDLE -> ABOVE_HOOP: ball center is above the ROI
        ABOVE_HOOP -> IN_HOOP: ball enters ROI while moving downward
        IN_HOOP -> SCORED: ball exits through the bottom of ROI
        IN_HOOP -> MISSED: ball exits sideways or upward
    """

    def __init__(self, hoop_roi=None):
        """Initialize with optional hoop ROI (x, y, w, h)."""
        self.hoop_roi = hoop_roi or config.HOOP_ROI
        self.states = defaultdict(lambda: ShotState.IDLE)
        self.shots_taken = 0
        self.shots_made = 0
        self.shot_log = []
        self.last_shot_result = None  # ("scored" | "missed", frame_number)
        self._enabled = self.hoop_roi is not None

    def set_hoop_roi(self, roi):
        """Set the hoop ROI (x, y, w, h)."""
        self.hoop_roi = roi
        self._enabled = roi is not None

    @property
    def enabled(self):
        return self._enabled

    @property
    def shooting_percentage(self):
        if self.shots_taken == 0:
            return 0.0
        return (self.shots_made / self.shots_taken) * 100.0

    def _is_above_roi(self, center):
        """Check if the ball center is above the hoop ROI."""
        x, y, w, h = self.hoop_roi
        cx, cy = center
        return (x <= cx <= x + w) and (cy < y)

    def _is_in_roi(self, center):
        """Check if the ball center is inside the hoop ROI."""
        x, y, w, h = self.hoop_roi
        cx, cy = center
        return (x <= cx <= x + w) and (y <= cy <= y + h)

    def _is_below_roi(self, center):
        """Check if the ball center is below the hoop ROI."""
        x, y, w, h = self.hoop_roi
        cx, cy = center
        return cy > y + h

    def _is_moving_down(self, velocity):
        """Check if ball is moving downward (positive y in image coords)."""
        return velocity[1] > 0

    def update(self, tracked_objects, trajectory_analyzer, frame_number):
        """Update shot detection for all tracked objects.

        Args:
            tracked_objects: OrderedDict of {object_id: (cx, cy)}
            trajectory_analyzer: TrajectoryAnalyzer instance for velocity data
            frame_number: Current frame number
        """
        if not self._enabled:
            return

        for obj_id, center in tracked_objects.items():
            velocity = trajectory_analyzer.get_velocity(obj_id)
            state = self.states[obj_id]

            if state == ShotState.IDLE:
                if self._is_above_roi(center):
                    self.states[obj_id] = ShotState.ABOVE_HOOP

            elif state == ShotState.ABOVE_HOOP:
                if self._is_in_roi(center) and self._is_moving_down(velocity):
                    self.states[obj_id] = ShotState.IN_HOOP
                elif not self._is_above_roi(center) and not self._is_in_roi(center):
                    self.states[obj_id] = ShotState.IDLE

            elif state == ShotState.IN_HOOP:
                if self._is_below_roi(center):
                    # Ball exited through the bottom — scored
                    self.states[obj_id] = ShotState.SCORED
                    self.shots_taken += 1
                    self.shots_made += 1
                    self.last_shot_result = ("scored", frame_number)
                    self.shot_log.append({
                        "frame": frame_number,
                        "object_id": obj_id,
                        "result": "scored",
                        "position": center,
                    })
                    # Reset to IDLE for next shot
                    self.states[obj_id] = ShotState.IDLE

                elif not self._is_in_roi(center):
                    # Ball exited sideways or upward — missed
                    self.states[obj_id] = ShotState.MISSED
                    self.shots_taken += 1
                    self.last_shot_result = ("missed", frame_number)
                    self.shot_log.append({
                        "frame": frame_number,
                        "object_id": obj_id,
                        "result": "missed",
                        "position": center,
                    })
                    # Reset to IDLE for next shot
                    self.states[obj_id] = ShotState.IDLE

    def get_recent_shot_result(self, frame_number, flash_duration=30):
        """Get the most recent shot result if it happened within flash_duration frames.

        Returns ("scored"|"missed", frames_ago) or None.
        """
        if self.last_shot_result is None:
            return None
        result, shot_frame = self.last_shot_result
        frames_ago = frame_number - shot_frame
        if frames_ago <= flash_duration:
            return result, frames_ago
        return None

    def get_stats(self):
        """Get shot detection statistics."""
        return {
            "shots_taken": self.shots_taken,
            "shots_made": self.shots_made,
            "shooting_percentage": round(self.shooting_percentage, 1),
            "shot_log": self.shot_log,
        }

    def cleanup(self, active_ids):
        """Remove state for objects no longer tracked."""
        all_ids = set(self.states.keys())
        for obj_id in all_ids - set(active_ids):
            del self.states[obj_id]
