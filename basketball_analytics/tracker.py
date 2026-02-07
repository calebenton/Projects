"""Centroid-based object tracker with persistent IDs."""

from collections import OrderedDict
import numpy as np

import config


class CentroidTracker:
    """Assigns persistent integer IDs to detected objects across frames.

    Uses a greedy closest-pair association strategy with NumPy broadcasting
    for the distance matrix (no scipy dependency).
    """

    def __init__(self):
        self.next_id = 0
        self.objects = OrderedDict()       # id -> (cx, cy)
        self.disappeared = OrderedDict()   # id -> count of consecutive missing frames
        self.max_disappeared = config.MAX_DISAPPEARED
        self.max_distance = config.MAX_TRACK_DISTANCE

    def register(self, centroid):
        """Register a new object with the next available ID."""
        self.objects[self.next_id] = centroid
        self.disappeared[self.next_id] = 0
        self.next_id += 1

    def deregister(self, object_id):
        """Remove a tracked object."""
        del self.objects[object_id]
        del self.disappeared[object_id]

    def update(self, detections):
        """Update tracker with new detections.

        Args:
            detections: list of Detection objects (must have .center attribute)

        Returns:
            OrderedDict of {object_id: (cx, cy)} for currently tracked objects.
        """
        input_centroids = [d.center for d in detections]

        if len(input_centroids) == 0:
            for object_id in list(self.disappeared.keys()):
                self.disappeared[object_id] += 1
                if self.disappeared[object_id] > self.max_disappeared:
                    self.deregister(object_id)
            return self.objects

        if len(self.objects) == 0:
            for centroid in input_centroids:
                self.register(centroid)
            return self.objects

        object_ids = list(self.objects.keys())
        object_centroids = list(self.objects.values())

        # Compute distance matrix using NumPy broadcasting
        existing = np.array(object_centroids, dtype=float)   # (M, 2)
        incoming = np.array(input_centroids, dtype=float)     # (N, 2)
        dist_matrix = np.linalg.norm(existing[:, np.newaxis] - incoming[np.newaxis, :], axis=2)  # (M, N)

        # Greedy association: pick closest pairs first
        used_rows = set()
        used_cols = set()
        assignments = {}

        # Sort all (row, col) pairs by distance
        flat_indices = np.argsort(dist_matrix, axis=None)
        rows, cols = np.unravel_index(flat_indices, dist_matrix.shape)

        for row, col in zip(rows, cols):
            if row in used_rows or col in used_cols:
                continue
            if dist_matrix[row, col] > self.max_distance:
                break
            obj_id = object_ids[row]
            assignments[obj_id] = input_centroids[col]
            used_rows.add(row)
            used_cols.add(col)

        # Update matched objects
        for obj_id, centroid in assignments.items():
            self.objects[obj_id] = centroid
            self.disappeared[obj_id] = 0

        # Handle unmatched existing objects (disappeared)
        for row in range(len(object_ids)):
            if row not in used_rows:
                obj_id = object_ids[row]
                self.disappeared[obj_id] += 1
                if self.disappeared[obj_id] > self.max_disappeared:
                    self.deregister(obj_id)

        # Register new detections that weren't matched
        for col in range(len(input_centroids)):
            if col not in used_cols:
                self.register(input_centroids[col])

        return self.objects
