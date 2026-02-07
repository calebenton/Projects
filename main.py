"""CLI entry point for the Basketball Detection & Analytics System."""

import argparse
import os
import sys

import numpy as np

import config
from basketball_analytics.video_processor import VideoProcessor


def parse_hsv(value):
    """Parse an HSV value string like '5,100,100' into a numpy array."""
    try:
        parts = [int(x.strip()) for x in value.split(",")]
        if len(parts) != 3:
            raise ValueError
        return np.array(parts)
    except (ValueError, AttributeError):
        raise argparse.ArgumentTypeError(f"Invalid HSV value: '{value}'. Expected format: H,S,V")


def parse_roi(value):
    """Parse an ROI value string like '100,200,50,60' into a tuple."""
    try:
        parts = [int(x.strip()) for x in value.split(",")]
        if len(parts) != 4:
            raise ValueError
        return tuple(parts)
    except (ValueError, AttributeError):
        raise argparse.ArgumentTypeError(f"Invalid ROI value: '{value}'. Expected format: x,y,w,h")


def main():
    parser = argparse.ArgumentParser(
        description="Basketball Detection & Analytics System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  python main.py --input game.mp4
  python main.py --input game.mp4 --output output/annotated.mp4
  python main.py --input game.mp4 --no-display --hoop-roi 400,100,80,60
  python main.py --input game.mp4 --hsv-lower 3,80,80 --hsv-upper 28,255,255
        """,
    )

    parser.add_argument("--input", "-i", required=True,
                        help="Path to input video file")
    parser.add_argument("--output", "-o", default=None,
                        help="Path to output annotated video (default: output/<input_name>_annotated.mp4)")
    parser.add_argument("--no-display", action="store_true",
                        help="Disable live display window (headless processing)")
    parser.add_argument("--hsv-lower", type=parse_hsv, default=None,
                        help="Lower HSV bound for ball color, e.g. '5,100,100'")
    parser.add_argument("--hsv-upper", type=parse_hsv, default=None,
                        help="Upper HSV bound for ball color, e.g. '25,255,255'")
    parser.add_argument("--min-radius", type=int, default=None,
                        help="Minimum ball radius in pixels")
    parser.add_argument("--max-radius", type=int, default=None,
                        help="Maximum ball radius in pixels")
    parser.add_argument("--hoop-roi", type=parse_roi, default=None,
                        help="Hoop ROI as 'x,y,w,h' (skip interactive selection)")
    parser.add_argument("--no-shot-detection", action="store_true",
                        help="Disable shot detection entirely")
    parser.add_argument("--max-disappeared", type=int, default=None,
                        help="Max frames an object can disappear before deregistering")
    parser.add_argument("--max-track-distance", type=int, default=None,
                        help="Max distance for tracker association")

    args = parser.parse_args()

    # Validate input
    if not os.path.isfile(args.input):
        print(f"Error: Input file not found: {args.input}")
        sys.exit(1)

    # Apply CLI overrides to config
    if args.hsv_lower is not None:
        config.HSV_LOWER = args.hsv_lower
    if args.hsv_upper is not None:
        config.HSV_UPPER = args.hsv_upper
    if args.min_radius is not None:
        config.MIN_RADIUS = args.min_radius
        config.HOUGH_MIN_RADIUS = args.min_radius
    if args.max_radius is not None:
        config.MAX_RADIUS = args.max_radius
        config.HOUGH_MAX_RADIUS = args.max_radius
    if args.max_disappeared is not None:
        config.MAX_DISAPPEARED = args.max_disappeared
    if args.max_track_distance is not None:
        config.MAX_TRACK_DISTANCE = args.max_track_distance

    # Default output path
    output_path = args.output
    if output_path is None:
        input_name = os.path.splitext(os.path.basename(args.input))[0]
        output_path = os.path.join("output", f"{input_name}_annotated.mp4")

    # Run the pipeline
    processor = VideoProcessor(
        input_path=args.input,
        output_path=output_path,
        display=not args.no_display,
        no_shot_detection=args.no_shot_detection,
        hoop_roi=args.hoop_roi,
    )

    try:
        processor.run()
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        sys.exit(0)
    except IOError as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
