#!/usr/bin/env python3
"""MattyBBoundingBoxCropper — NiFi 2.x custom Python processor (processor #2 of 2).

Reads a FlowFile whose CONTENT is an image and whose attribute
`mattyb.bounding.boxes` holds the JSON array produced by MattyBShapeDetector.
Crops each bounding box out of the original image, writes each crop to an output
directory (default /tmp/mattyb), and emits ONE FlowFile whose content is a JSON
MANIFEST array — one object per crop: {id, label, box, path, ...}.

Why one FlowFile and not six: a NiFi Python FlowFileTransform is one-in/one-out
and cannot emit multiple FlowFiles. The idiomatic fan-out is downstream stock
processors: SplitJson splits this manifest into 6 FlowFiles, and FetchFile reads
each crop's `path` back into content. See mattyb-image-prod.md.

`crop_boxes()` is module-level so it runs locally without NiFi (verify_local.py).
"""
import json
import os

try:
    from nifiapi.flowfiletransform import FlowFileTransform, FlowFileTransformResult
    from nifiapi.properties import PropertyDescriptor, StandardValidators
except ImportError:  # local verification without NiFi on the path
    FlowFileTransform = object
    FlowFileTransformResult = None
    PropertyDescriptor = None
    StandardValidators = None


def crop_boxes(image_bytes, boxes, out_dir):
    """Crop each box from the image, write it to out_dir, return the manifest.

    Manifest entry: {id, label, color, box:{x,y,w,h}, path, width, height}.
    """
    import cv2
    import numpy as np

    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if bgr is None:
        raise ValueError("content is not a decodable image")
    os.makedirs(out_dir, exist_ok=True)

    manifest = []
    for b in boxes:
        x, y, w, h = b["x"], b["y"], b["w"], b["h"]
        crop = bgr[y:y + h, x:x + w]
        label = b.get("label", "shape")
        fname = f"shape-{b['id']}-{label}.png"
        path = os.path.join(out_dir, fname)
        cv2.imwrite(path, crop)
        manifest.append({
            "id": b["id"],
            "label": label,
            "color": b.get("color"),
            "box": {"x": x, "y": y, "w": w, "h": h},
            "path": path,
            "width": int(w),
            "height": int(h),
        })
    return manifest


class MattyBBoundingBoxCropper(FlowFileTransform):
    class Java:
        implements = ['org.apache.nifi.python.processor.FlowFileTransform']

    class ProcessorDetails:
        version = '0.0.1'
        description = ('Crops each mattyb.bounding.boxes region out of the image FlowFile, '
                       'writes the crops to an output directory, and emits a JSON manifest '
                       '(one object per crop) as the outgoing FlowFile content.')
        dependencies = ['opencv-python-headless', 'numpy']
        tags = ['image', 'crop', 'bounding-box', 'mattyb']

    def __init__(self, **kwargs):
        if PropertyDescriptor is not None:
            self.OUTPUT_DIR = PropertyDescriptor(
                name='Output Directory',
                description='Directory to write cropped images into (created if missing).',
                required=True,
                default_value='/tmp/mattyb',
                validators=[StandardValidators.NON_EMPTY_VALIDATOR],
            )
            self.descriptors = [self.OUTPUT_DIR]

    def getPropertyDescriptors(self):
        return self.descriptors

    def transform(self, context, flowfile):
        try:
            out_dir = context.getProperty(self.OUTPUT_DIR).getValue()
            raw = flowfile.getAttribute('mattyb.bounding.boxes')
            if not raw:
                self.logger.error("missing mattyb.bounding.boxes attribute")
                return FlowFileTransformResult(relationship='failure')
            boxes = json.loads(raw)
            manifest = crop_boxes(flowfile.getContentsAsBytes(), boxes, out_dir)
            attrs = {
                'mattyb.crop.count': str(len(manifest)),
                'mattyb.output.dir': out_dir,
                'mime.type': 'application/json',
            }
            return FlowFileTransformResult(
                relationship='success',
                attributes=attrs,
                contents=json.dumps(manifest, indent=2).encode('utf-8'),
            )
        except Exception as e:
            self.logger.error(f"MattyBBoundingBoxCropper failed: {e}")
            return FlowFileTransformResult(relationship='failure')
