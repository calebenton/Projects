"""Ball detection using HSV color mask, contour analysis, and Hough circles."""

from dataclasses import dataclass
import cv2
import numpy as np

import config
from basketball_analytics.utils import circularity, euclidean_distance


@dataclass
class Detection:
    """A single ball detection."""
    center: tuple  # (x, y)
    radius: float
    confidence: float
    method: str  # "contour", "hough", or "fused"


class BallDetector:
    """Detects basketballs using a three-stage pipeline: color mask, contour, Hough circles."""

    def __init__(self):
        self.hsv_lower = config.HSV_LOWER
        self.hsv_upper = config.HSV_UPPER
        self.min_radius = config.MIN_RADIUS
        self.max_radius = config.MAX_RADIUS
        self.min_contour_area = config.MIN_CONTOUR_AREA
        self.min_circularity = config.MIN_CIRCULARITY
        self.kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE,
            (config.MORPH_KERNEL_SIZE, config.MORPH_KERNEL_SIZE),
        )

    def _create_color_mask(self, frame):
        """Stage 1: BGR -> HSV -> inRange -> blur -> morphological ops."""
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, self.hsv_lower, self.hsv_upper)
        mask = cv2.GaussianBlur(mask, (config.BLUR_KERNEL_SIZE, config.BLUR_KERNEL_SIZE), 0)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, self.kernel,
                                iterations=config.MORPH_CLOSE_ITERATIONS)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, self.kernel,
                                iterations=config.MORPH_OPEN_ITERATIONS)
        return mask

    def _detect_contours(self, mask):
        """Stage 2: Find contours, filter by area/circularity/radius."""
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        detections = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < self.min_contour_area:
                continue
            circ = circularity(contour)
            if circ < self.min_circularity:
                continue
            (x, y), radius = cv2.minEnclosingCircle(contour)
            if radius < self.min_radius or radius > self.max_radius:
                continue
            confidence = min(circ, 1.0) * min(area / (self.min_contour_area * 10), 1.0)
            detections.append(Detection(
                center=(int(x), int(y)),
                radius=float(radius),
                confidence=float(confidence),
                method="contour",
            ))
        return detections

    def _detect_hough_circles(self, mask):
        """Stage 3: Hough circle transform on the color-masked grayscale."""
        circles = cv2.HoughCircles(
            mask,
            cv2.HOUGH_GRADIENT,
            dp=config.HOUGH_DP,
            minDist=config.HOUGH_MIN_DIST,
            param1=config.HOUGH_PARAM1,
            param2=config.HOUGH_PARAM2,
            minRadius=config.HOUGH_MIN_RADIUS,
            maxRadius=config.HOUGH_MAX_RADIUS,
        )
        detections = []
        if circles is not None:
            circles = np.round(circles[0, :]).astype(int)
            for (x, y, r) in circles:
                detections.append(Detection(
                    center=(int(x), int(y)),
                    radius=float(r),
                    confidence=0.5,
                    method="hough",
                ))
        return detections

    def _fuse_detections(self, contour_dets, hough_dets):
        """Fuse contour and Hough detections by proximity matching."""
        if not contour_dets and not hough_dets:
            return []
        if not hough_dets:
            return contour_dets
        if not contour_dets:
            return hough_dets

        fused = []
        used_hough = set()

        for c_det in contour_dets:
            best_match = None
            best_dist = config.FUSION_MATCH_DISTANCE
            for i, h_det in enumerate(hough_dets):
                if i in used_hough:
                    continue
                dist = euclidean_distance(c_det.center, h_det.center)
                if dist < best_dist:
                    best_dist = dist
                    best_match = i

            if best_match is not None:
                h_det = hough_dets[best_match]
                used_hough.add(best_match)
                avg_x = int((c_det.center[0] + h_det.center[0]) / 2)
                avg_y = int((c_det.center[1] + h_det.center[1]) / 2)
                avg_r = (c_det.radius + h_det.radius) / 2
                boosted_conf = min(c_det.confidence + 0.3, 1.0)
                fused.append(Detection(
                    center=(avg_x, avg_y),
                    radius=avg_r,
                    confidence=boosted_conf,
                    method="fused",
                ))
            else:
                fused.append(c_det)

        for i, h_det in enumerate(hough_dets):
            if i not in used_hough:
                fused.append(h_det)

        return fused

    def detect(self, frame):
        """Run the full detection pipeline on a frame.

        Returns list of Detection objects.
        """
        mask = self._create_color_mask(frame)
        contour_dets = self._detect_contours(mask)
        hough_dets = self._detect_hough_circles(mask)
        return self._fuse_detections(contour_dets, hough_dets)
