"""Geometry helpers and utility functions."""

import math
import cv2
import numpy as np


def euclidean_distance(p1, p2):
    """Compute Euclidean distance between two points (x, y)."""
    return math.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)


def compute_velocity(p1, p2):
    """Compute velocity vector from p1 to p2 (dx, dy)."""
    return (p2[0] - p1[0], p2[1] - p1[1])


def compute_speed(p1, p2):
    """Compute scalar speed between two points."""
    return euclidean_distance(p1, p2)


def circularity(contour):
    """Compute circularity of a contour: 4 * pi * area / perimeter^2.

    Returns a value between 0 and 1, where 1 is a perfect circle.
    """
    area = cv2.contourArea(contour)
    perimeter = cv2.arcLength(contour, True)
    if perimeter == 0:
        return 0.0
    return (4 * math.pi * area) / (perimeter ** 2)


def resize_frame(frame, target_width):
    """Resize frame to target width while maintaining aspect ratio.

    Returns (resized_frame, scale_factor).
    """
    if target_width is None:
        return frame, 1.0
    h, w = frame.shape[:2]
    if w == target_width:
        return frame, 1.0
    scale = target_width / w
    new_h = int(h * scale)
    resized = cv2.resize(frame, (target_width, new_h), interpolation=cv2.INTER_AREA)
    return resized, scale
