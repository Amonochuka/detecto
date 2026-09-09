#!/usr/bin/env python3
"""Test crowd counting fix on real sample images."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from backend.utils.detector import PersonDetector
from PIL import Image
import numpy as np


def main():
    detector = PersonDetector()

    samples_dir = Path("backend/samples")
    if not samples_dir.exists():
        print(f"Samples directory not found: {samples_dir}")
        return

    image_files = list(samples_dir.glob("*.jpg")) + list(samples_dir.glob("*.png")) + list(samples_dir.glob("*.jpeg"))
    if not image_files:
        print("No images found in backend/samples/")
        return

    print(f"{'Image':<40} {'Count':>6} {'Avg Conf':>10} {'Infer (s)':>10}")
    print("-" * 70)

    for img_path in sorted(image_files):
        try:
            img = np.array(Image.open(img_path).convert("RGB"))
            result = detector.detect(img)
            print(f"{img_path.name:<40} {result['count']:>6} {result['average_confidence']:>10.3f} {result['inference_time']:>10.3f}")
        except Exception as e:
            print(f"{img_path.name:<40} ERROR: {e}")


if __name__ == "__main__":
    main()