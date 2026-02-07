"""Pipeline orchestrator: capture -> detect -> track -> analyze -> render."""

import json
import os
import cv2

import config
from basketball_analytics.detector import BallDetector
from basketball_analytics.tracker import CentroidTracker
from basketball_analytics.trajectory import TrajectoryAnalyzer
from basketball_analytics.shot_detector import ShotDetector
from basketball_analytics.visualizer import Visualizer
from basketball_analytics.utils import resize_frame


class VideoProcessor:
    """Orchestrates the full basketball analytics pipeline."""

    def __init__(self, input_path, output_path=None, display=True,
                 no_shot_detection=False, hoop_roi=None):
        self.input_path = input_path
        self.output_path = output_path
        self.display = display
        self.no_shot_detection = no_shot_detection

        self.detector = BallDetector()
        self.tracker = CentroidTracker()
        self.trajectory = TrajectoryAnalyzer()
        self.shot_detector = ShotDetector(hoop_roi=hoop_roi)
        self.visualizer = Visualizer()

        self.cap = None
        self.writer = None
        self.frame_number = 0
        self.total_frames = 0

    def _setup_capture(self):
        """Open video capture and get properties."""
        self.cap = cv2.VideoCapture(self.input_path)
        if not self.cap.isOpened():
            raise IOError(f"Cannot open video: {self.input_path}")
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or config.OUTPUT_FPS
        self.frame_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.frame_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    def _setup_writer(self, frame_shape):
        """Set up video writer for output."""
        if self.output_path is None:
            return
        os.makedirs(os.path.dirname(self.output_path) or ".", exist_ok=True)
        h, w = frame_shape[:2]
        fourcc = cv2.VideoWriter_fourcc(*config.OUTPUT_CODEC)
        self.writer = cv2.VideoWriter(self.output_path, fourcc, self.fps, (w, h))

    def _setup_hoop_roi(self, first_frame):
        """Interactive hoop ROI selection on the first frame."""
        if self.no_shot_detection:
            return
        if self.shot_detector.hoop_roi is not None:
            return

        if not self.display:
            print("No hoop ROI specified and --no-display is set. Skipping shot detection.")
            self.no_shot_detection = True
            return

        print("Select the hoop region (ROI) and press ENTER or SPACE to confirm.")
        print("Press 'c' to cancel and skip shot detection.")
        roi = cv2.selectROI(config.WINDOW_NAME, first_frame, fromCenter=False, showCrosshair=True)
        cv2.destroyWindow(config.WINDOW_NAME)

        if roi[2] > 0 and roi[3] > 0:
            self.shot_detector.set_hoop_roi(roi)
            print(f"Hoop ROI set: {roi}")
        else:
            print("No ROI selected. Shot detection disabled.")
            self.no_shot_detection = True

    def _process_frame(self, frame):
        """Run the full per-frame pipeline."""
        # Resize for processing
        processed, scale = resize_frame(frame, config.PROCESS_WIDTH)

        # Detect
        detections = self.detector.detect(processed)

        # Track
        tracked = self.tracker.update(detections)

        # Update trajectory
        self.trajectory.update(tracked)

        # Shot detection
        if not self.no_shot_detection:
            self.shot_detector.update(tracked, self.trajectory, self.frame_number)

        # Cleanup stale trajectory/shot data
        active_ids = set(tracked.keys())
        self.trajectory.cleanup(active_ids)
        if not self.no_shot_detection:
            self.shot_detector.cleanup(active_ids)

        # Visualize
        self.visualizer.draw_detections(processed, detections)
        self.visualizer.draw_tracked_ids(processed, tracked)
        self.visualizer.draw_trajectory_trail(processed, self.trajectory, tracked)
        self.visualizer.draw_velocity_vector(processed, tracked, self.trajectory)

        if not self.no_shot_detection:
            self.visualizer.draw_hoop_roi(processed, self.shot_detector.hoop_roi)
            self.visualizer.draw_shot_flash(processed, self.shot_detector, self.frame_number)

        self.visualizer.draw_stats_overlay(processed, self.shot_detector, tracked, self.frame_number)

        return processed

    def _save_analytics(self):
        """Save analytics summary as JSON."""
        if self.output_path is None:
            return

        analytics = {
            "input_video": self.input_path,
            "total_frames": self.total_frames,
            "frames_processed": self.frame_number,
            "fps": self.fps,
        }

        # Trajectory summaries
        trajectories = []
        for obj_id in self.trajectory.positions:
            trajectories.append(self.trajectory.get_summary(obj_id))
        analytics["trajectories"] = trajectories

        # Shot stats
        if not self.no_shot_detection:
            analytics["shot_detection"] = self.shot_detector.get_stats()

        json_path = os.path.splitext(self.output_path)[0] + "_analytics.json"
        with open(json_path, "w") as f:
            json.dump(analytics, f, indent=2, default=str)
        print(f"Analytics saved to: {json_path}")

    def run(self):
        """Run the full video processing pipeline."""
        self._setup_capture()

        # Read first frame for ROI setup
        ret, first_frame = self.cap.read()
        if not ret:
            raise IOError("Cannot read first frame from video.")

        first_processed, _ = resize_frame(first_frame, config.PROCESS_WIDTH)
        self._setup_hoop_roi(first_processed)
        self._setup_writer(first_processed.shape)

        # Reset to beginning
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

        print(f"Processing video: {self.input_path}")
        print(f"Total frames: {self.total_frames}")
        print("Press 'q' to quit, 'p' to pause/resume.")

        paused = False

        while True:
            if not paused:
                ret, frame = self.cap.read()
                if not ret:
                    break
                self.frame_number += 1
                result = self._process_frame(frame)

                if self.writer is not None:
                    self.writer.write(result)

            if self.display:
                if not paused:
                    cv2.imshow(config.WINDOW_NAME, result)
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    print("Quit requested.")
                    break
                elif key == ord("p"):
                    paused = not paused
                    print("Paused." if paused else "Resumed.")

            # Progress reporting
            if self.frame_number % 100 == 0:
                pct = (self.frame_number / self.total_frames * 100) if self.total_frames > 0 else 0
                print(f"  Frame {self.frame_number}/{self.total_frames} ({pct:.1f}%)")

        # Cleanup
        self.cap.release()
        if self.writer is not None:
            self.writer.release()
        if self.display:
            cv2.destroyAllWindows()

        self._save_analytics()
        self._print_summary()

    def _print_summary(self):
        """Print final analytics summary to console."""
        print("\n" + "=" * 50)
        print("BASKETBALL ANALYTICS SUMMARY")
        print("=" * 50)
        print(f"Frames processed: {self.frame_number}/{self.total_frames}")

        if not self.no_shot_detection:
            stats = self.shot_detector.get_stats()
            print(f"\nShot Detection:")
            print(f"  Shots taken: {stats['shots_taken']}")
            print(f"  Shots made:  {stats['shots_made']}")
            print(f"  Percentage:  {stats['shooting_percentage']:.1f}%")

        for obj_id in self.trajectory.positions:
            summary = self.trajectory.get_summary(obj_id)
            print(f"\nObject {obj_id}:")
            print(f"  Frames tracked: {summary['frames_tracked']}")
            print(f"  Total distance: {summary['total_distance_px']:.1f} px")
            print(f"  Avg speed: {summary['avg_speed_px_per_frame']:.1f} px/frame")
            print(f"  Max speed: {summary['max_speed_px_per_frame']:.1f} px/frame")

        if self.output_path:
            print(f"\nOutput video: {self.output_path}")
        print("=" * 50)
