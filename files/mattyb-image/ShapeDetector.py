#!/usr/bin/env python3
"""MattyBShapeDetector — NiFi 2.x custom Python processor (processor #1 of 2).

Stands in for an object-detection model. Reads a FlowFile whose CONTENT is an
image, finds each solid-color shape on the flat background, and emits the SAME
image unchanged as content plus an ATTRIBUTE `mattyb.bounding.boxes` holding a
JSON array of bounding boxes — exactly the shape a real detector's output takes
(image as content, boxes as an attribute).

The heavy lifting lives in the module-level `detect_boxes()` so it can be unit-
tested / run locally without NiFi (see verify_local.py). The `nifiapi` import is
guarded for the same reason: inside NiFi it resolves; locally it falls back to a
plain object base so the module still imports.
"""
import json

try:
    from nifiapi.flowfiletransform import FlowFileTransform, FlowFileTransformResult
except ImportError:  # local verification without NiFi on the path
    FlowFileTransform = object
    FlowFileTransformResult = None

# Reference palette: label a detected region by its nearest color here. Matches
# the six colors generate_test_image.py draws; extend for real-world classes.
PALETTE = {
    "red":    (220, 30, 30),
    "green":  (30, 160, 30),
    "blue":   (30, 60, 200),
    "orange": (240, 140, 20),
    "purple": (140, 30, 160),
    "teal":   (20, 150, 150),
}
MIN_AREA = 500          # ignore specks / anti-aliasing noise
BG_DELTA = 25           # per-pixel distance from background to count as "shape"


def _nearest_label(rgb):
    r, g, b = rgb
    return min(PALETTE, key=lambda k: (PALETTE[k][0] - r) ** 2
               + (PALETTE[k][1] - g) ** 2 + (PALETTE[k][2] - b) ** 2)


def detect_boxes(image_bytes):
    """Detect solid-color shapes; return a list of bounding-box dicts.

    Each box: {id, label, color:[r,g,b], x, y, w, h}. Boxes are ordered
    top-to-bottom then left-to-right so `id` is stable across runs.
    """
    import cv2
    import numpy as np

    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if bgr is None:
        raise ValueError("content is not a decodable image")

    # Background = the top-left corner pixel (flat background by construction).
    bg = bgr[0, 0].astype(np.int16)
    dist = np.abs(bgr.astype(np.int16) - bg).sum(axis=2)
    mask = (dist > BG_DELTA).astype(np.uint8) * 255

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    raw = []
    for c in contours:
        if cv2.contourArea(c) < MIN_AREA:
            continue
        x, y, w, h = cv2.boundingRect(c)
        # Mean color of the shape's own pixels (not the bbox, which includes bg).
        cmask = np.zeros(mask.shape, dtype=np.uint8)
        cv2.drawContours(cmask, [c], -1, 255, thickness=cv2.FILLED)
        mean_bgr = cv2.mean(bgr, mask=cmask)[:3]
        rgb = [int(round(mean_bgr[2])), int(round(mean_bgr[1])), int(round(mean_bgr[0]))]
        raw.append({"label": _nearest_label(rgb), "color": rgb,
                    "x": int(x), "y": int(y), "w": int(w), "h": int(h)})

    raw.sort(key=lambda b: (b["y"] // 50, b["x"]))   # row-band then left-to-right
    for i, b in enumerate(raw, start=1):
        b["id"] = i
    return [{"id": b["id"], "label": b["label"], "color": b["color"],
             "x": b["x"], "y": b["y"], "w": b["w"], "h": b["h"]} for b in raw]


class MattyBShapeDetector(FlowFileTransform):
    class Java:
        implements = ['org.apache.nifi.python.processor.FlowFileTransform']

    class ProcessorDetails:
        version = '0.0.1'
        description = ('Detects solid-color shapes in an image FlowFile and adds a '
                       'mattyb.bounding.boxes attribute (JSON array of boxes); passes '
                       'the image through unchanged.')
        dependencies = ['opencv-python-headless', 'numpy']
        tags = ['image', 'object-detection', 'bounding-box', 'mattyb']

    def __init__(self, **kwargs):
        pass

    def transform(self, context, flowfile):
        try:
            content = flowfile.getContentsAsBytes()
            boxes = detect_boxes(content)
            attrs = {
                'mattyb.bounding.boxes': json.dumps(boxes),
                'mattyb.box.count': str(len(boxes)),
                'mime.type': 'image/png',
            }
            # Pass the ORIGINAL image through unchanged (contents=None keeps it).
            return FlowFileTransformResult(relationship='success', attributes=attrs)
        except Exception as e:
            self.logger.error(f"MattyBShapeDetector failed: {e}")
            return FlowFileTransformResult(relationship='failure')
