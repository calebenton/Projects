"""Central configuration for basketball detection and analytics."""

import numpy as np

# --- HSV Color Range for Orange Basketball ---
HSV_LOWER = np.array([5, 100, 100])
HSV_UPPER = np.array([25, 255, 255])

# --- Ball Size Constraints ---
MIN_RADIUS = 10
MAX_RADIUS = 80
MIN_CONTOUR_AREA = 300

# --- Morphological Operation Params ---
MORPH_KERNEL_SIZE = 5
MORPH_CLOSE_ITERATIONS = 3
MORPH_OPEN_ITERATIONS = 2

# --- Gaussian Blur ---
BLUR_KERNEL_SIZE = 11

# --- Hough Circle Transform Params ---
HOUGH_DP = 1.2
HOUGH_MIN_DIST = 50
HOUGH_PARAM1 = 100
HOUGH_PARAM2 = 30
HOUGH_MIN_RADIUS = 10
HOUGH_MAX_RADIUS = 80

# --- Contour Filtering ---
MIN_CIRCULARITY = 0.5

# --- Tracker Params ---
MAX_DISAPPEARED = 15
MAX_TRACK_DISTANCE = 100

# --- Shot Detection Params ---
HOOP_ROI = None  # (x, y, w, h) — set interactively or via CLI
MIN_SHOT_SPEED = 5.0

# --- Trajectory Params ---
TRAJECTORY_HISTORY_LENGTH = 64
TRAIL_COLOR = (0, 255, 255)  # Yellow in BGR
TRAIL_THICKNESS = 2
POLYFIT_DEGREE = 2

# --- Video Output Params ---
OUTPUT_CODEC = "mp4v"
OUTPUT_FPS = 30.0
WINDOW_NAME = "Basketball Analytics"

# --- Processing ---
PROCESS_WIDTH = 960  # Resize frames to this width for processing (None = no resize)

# --- Detection Fusion ---
FUSION_MATCH_DISTANCE = 30  # Max distance to consider contour + Hough as same detection
