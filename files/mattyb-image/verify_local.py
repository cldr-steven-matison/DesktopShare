#!/usr/bin/env python3
"""Run the full mattyB pipeline locally (no NiFi) and produce the sample artifacts.

Chains the same pure functions the two processors use:
    generate_test_image  ->  ShapeDetector.detect_boxes  ->  BoundingBoxCropper.crop_boxes

Asserts exactly 6 boxes and 6 crop files, then writes the committed artifacts:
    test-image.png, crops/shape-*.png, manifest.json

Usage (from files/mattyb-image/):
    /tmp/mattyb-venv/bin/python verify_local.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from generate_test_image import make_test_image, SHAPES
from ShapeDetector import detect_boxes
from BoundingBoxCropper import crop_boxes

EXPECTED = len(SHAPES)  # 6


def main():
    crops_dir = os.path.join(HERE, "crops")
    os.makedirs(crops_dir, exist_ok=True)

    # 1. Generate the test image (also the committed "original image").
    image_bytes = make_test_image()
    with open(os.path.join(HERE, "test-image.png"), "wb") as f:
        f.write(image_bytes)

    # 2. Processor #1 logic: detect bounding boxes.
    boxes = detect_boxes(image_bytes)
    assert len(boxes) == EXPECTED, f"expected {EXPECTED} boxes, got {len(boxes)}: {boxes}"

    # 3. Processor #2 logic: crop each box, write crops, build manifest.
    manifest = crop_boxes(image_bytes, boxes, crops_dir)
    assert len(manifest) == EXPECTED, f"expected {EXPECTED} crops, got {len(manifest)}"
    for m in manifest:
        assert os.path.exists(m["path"]), f"missing crop file {m['path']}"

    # Rewrite manifest paths to the committed /tmp default so the sample matches
    # what the deployed flow (Output Directory=/tmp/mattyb) would emit.
    sample = []
    for m in manifest:
        e = dict(m)
        e["path"] = f"/tmp/mattyb/{os.path.basename(m['path'])}"
        sample.append(e)
    with open(os.path.join(HERE, "manifest.json"), "w") as f:
        json.dump(sample, f, indent=2)

    print(f"OK: {len(boxes)} boxes detected, {len(manifest)} crops written to {crops_dir}")
    for m in sample:
        print(f"  #{m['id']:<2} {m['label']:<7} box={m['box']}  -> {os.path.basename(m['path'])}")


if __name__ == "__main__":
    main()
