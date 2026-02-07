"""All drawing and annotation for the basketball analytics display."""

import cv2
import numpy as np

import config


class Visualizer:
    """Draws detection results, tracking info, trajectories, and stats onto frames."""

    def __init__(self):
        self.trail_color = config.TRAIL_COLOR
        self.trail_thickness = config.TRAIL_THICKNESS

    def draw_detections(self, frame, detections):
        """Draw green circles and center dots for each detection."""
        for det in detections:
            cx, cy = det.center
            r = int(det.radius)
            # Green circle outline
            cv2.circle(frame, (cx, cy), r, (0, 255, 0), 2)
            # Center dot
            cv2.circle(frame, (cx, cy), 3, (0, 255, 0), -1)
        return frame

    def draw_tracked_ids(self, frame, tracked_objects):
        """Draw ID labels near each tracked centroid."""
        for obj_id, (cx, cy) in tracked_objects.items():
            label = f"ID:{obj_id}"
            cv2.putText(frame, label, (cx - 10, cy - 15),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
        return frame

    def draw_trajectory_trail(self, frame, trajectory_analyzer, tracked_objects):
        """Draw fading polyline trail for each tracked object."""
        for obj_id in tracked_objects:
            trail = trajectory_analyzer.get_trail_points(obj_id)
            if len(trail) < 2:
                continue
            # Draw trail with fading opacity
            overlay = frame.copy()
            for i in range(1, len(trail)):
                # Fade: older points are more transparent
                alpha = i / len(trail)
                thickness = max(1, int(self.trail_thickness * alpha))
                pt1 = trail[i - 1]
                pt2 = trail[i]
                cv2.line(overlay, pt1, pt2, self.trail_color, thickness)
            cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)
        return frame

    def draw_hoop_roi(self, frame, hoop_roi):
        """Draw blue rectangle for the hoop region."""
        if hoop_roi is None:
            return frame
        x, y, w, h = hoop_roi
        cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 100, 0), 2)
        cv2.putText(frame, "HOOP", (x, y - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 100, 0), 2)
        return frame

    def draw_stats_overlay(self, frame, shot_detector, tracked_objects, frame_number):
        """Draw semi-transparent panel with shot stats and tracking info."""
        h, w = frame.shape[:2]
        panel_h = 120
        panel_w = 250
        # Semi-transparent dark panel in top-left
        overlay = frame.copy()
        cv2.rectangle(overlay, (5, 5), (5 + panel_w, 5 + panel_h), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)

        y_offset = 25
        cv2.putText(frame, f"Frame: {frame_number}", (15, y_offset),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        y_offset += 22
        cv2.putText(frame, f"Tracked: {len(tracked_objects)} objects", (15, y_offset),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        if shot_detector.enabled:
            y_offset += 22
            stats = shot_detector.get_stats()
            cv2.putText(frame, f"Shots: {stats['shots_made']}/{stats['shots_taken']}",
                        (15, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            y_offset += 22
            cv2.putText(frame, f"Pct: {stats['shooting_percentage']:.1f}%",
                        (15, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

        return frame

    def draw_shot_flash(self, frame, shot_detector, frame_number):
        """Flash green/red border on made/missed shots."""
        result = shot_detector.get_recent_shot_result(frame_number)
        if result is None:
            return frame
        shot_result, frames_ago = result
        # Fade out over time
        alpha = max(0.0, 1.0 - frames_ago / 30.0)
        if alpha <= 0:
            return frame

        color = (0, 255, 0) if shot_result == "scored" else (0, 0, 255)
        h, w = frame.shape[:2]
        overlay = frame.copy()
        border = 8
        cv2.rectangle(overlay, (0, 0), (w, border), color, -1)
        cv2.rectangle(overlay, (0, h - border), (w, h), color, -1)
        cv2.rectangle(overlay, (0, 0), (border, h), color, -1)
        cv2.rectangle(overlay, (w - border, 0), (w, h), color, -1)
        cv2.addWeighted(overlay, alpha * 0.7, frame, 1 - alpha * 0.7, 0, frame)

        # Show result text
        text = "SCORED!" if shot_result == "scored" else "MISSED"
        text_color = (0, 255, 0) if shot_result == "scored" else (0, 0, 255)
        text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 1.5, 3)[0]
        tx = (w - text_size[0]) // 2
        ty = h // 2
        cv2.putText(frame, text, (tx, ty),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.5, text_color, 3)
        return frame

    def draw_velocity_vector(self, frame, tracked_objects, trajectory_analyzer):
        """Draw arrowed line showing motion direction for each object."""
        for obj_id, (cx, cy) in tracked_objects.items():
            vx, vy = trajectory_analyzer.get_velocity(obj_id)
            speed = (vx ** 2 + vy ** 2) ** 0.5
            if speed < 2:
                continue
            # Scale the arrow for visibility
            scale = 3.0
            end_x = int(cx + vx * scale)
            end_y = int(cy + vy * scale)
            cv2.arrowedLine(frame, (cx, cy), (end_x, end_y),
                            (0, 200, 255), 2, tipLength=0.3)
        return frame
