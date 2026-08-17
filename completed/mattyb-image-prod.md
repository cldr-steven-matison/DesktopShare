# mattyB Image Processor — test notes

Working notes for issue [#27](https://github.com/cldr-steven-matison/DesktopShare/issues/27) — a
test/demo, not a blog post. How to split one image + N bounding boxes into N cropped images in NiFi.

**Status:** both processors built and verified end-to-end locally on FTF3XR2065 (Python 3.14 venv:
opencv-python-headless 5.0.0, Pillow 12.3.0, numpy 2.5.1). Sample artifacts under
`files/mattyb-image/`. Live-NiFi deploy notes at the end.

I saw a demo where an object-detection model emits a FlowFile whose **content is the original image**
and whose **attribute holds a JSON array of bounding boxes** — one box per detected face. The obvious
next move is to break that image into the individual faces, one per box. So I asked the question that
turns out to have a non-obvious answer: **a NiFi Python processor can't emit multiple FlowFiles — so
how do I turn one image + N boxes into N cropped images?**

This is the mattyB image pipeline. I built it with a flat-background test image of six colored shapes
standing in for the faces, so the whole thing is deterministic and needs no model to reproduce.

## The answer: Python is one-in/one-out — fan out with stock processors

A NiFi 2.x Python `FlowFileTransform` is strictly **one FlowFile in, one FlowFile out**. `transform()`
returns a single `FlowFileTransformResult`; there is no API to emit a second FlowFile. (`RecordTransform`
can emit multiple *records*, but that's record-oriented output, not arbitrary binary image FlowFiles.)
So you do **not** try to make Python fan out. You decompose into a chain of small processors and let
**stock** processors do the fan-out — the same "chain of small native processors" rule the rest of my
NiFi work follows:

- The Python **cropper** writes each crop to disk and emits **one** FlowFile whose content is a JSON
  **manifest** — an array with one object per crop (`id`, `label`, `box`, `path`).
- Stock **`SplitJson`** (`$.*`) splits that manifest array into **one FlowFile per crop**. *This is the
  fan-out.*
- Stock **`FetchFile`** (`${path}`) reads each crop's bytes back into FlowFile content.

The fan-out happens in `SplitJson`, never in Python.

## The flow

```
GetFile                 (1 image FlowFile in)                         [stock]
  → MattyBShapeDetector  content = original image (unchanged)          [custom Python #1]
                         attr  mattyb.bounding.boxes = [ {id,label,color,x,y,w,h} × 6 ]
  → MattyBBoundingBoxCropper  crops each box → /tmp/mattyb/*.png        [custom Python #2]
                         content = manifest JSON [ {id,label,box,path} × 6 ]
  → SplitJson  ($.*)     manifest array → 6 FlowFiles                   [stock]  ← fan-out
  → FetchFile  (${path}) each crop's bytes → FlowFile content           [stock]
  → PutFile              writes the 6 individual crops to /tmp/mattyb-out [stock]
        (failure on the two custom procs + FetchFile → LogFailure sink)
```

Definition: `files/mattyb-image/flow-mattyb-image.json`.

## Processor #1 — MattyBShapeDetector

`files/mattyb-image/ShapeDetector.py`. Reads the image content, finds each solid-color shape, and adds
the bounding boxes as an attribute — mirroring the detector output exactly (image stays content, boxes
go in `mattyb.bounding.boxes`). Detection is OpenCV, no ML: subtract the flat background (the top-left
corner pixel), `findContours`, `boundingRect` per contour, and label each by the mean interior color's
nearest match in a small palette. Boxes are sorted top-to-bottom then left-to-right so `id` is stable.

The real work is in a module-level `detect_boxes(image_bytes)` so it runs with or without NiFi. The
`nifiapi` import is guarded (`try/except ImportError`) for the same reason — that's what lets
`verify_local.py` exercise the exact same code the processor runs.

## Processor #2 — MattyBBoundingBoxCropper

`files/mattyb-image/BoundingBoxCropper.py`. Reads the image content + `mattyb.bounding.boxes`, crops each
box, writes each crop to the **Output Directory** property (default `/tmp/mattyb`), and emits one
FlowFile whose content is the JSON manifest. Same guarded-import / module-level `crop_boxes()` pattern.

## The test image

`files/mattyb-image/generate_test_image.py` draws a 900×600 flat near-white background with six
distinct-color shapes in a 3×2 grid (red circle, green square, blue triangle, orange rectangle, purple
pentagon, teal ellipse). Deterministic, so the detector finds exactly six boxes every run.

If you want a model-generated image instead of the drawn one, here's the **Gemini prompt** I use:

> Generate a single flat 2D image, 900×600 pixels, on a plain solid light-gray background (no gradient,
> no shadow, no texture). Place exactly six simple geometric shapes on it, well separated, none touching
> or overlapping, arranged in a 3-across by 2-down grid. Each shape is a different solid flat color: a
> red circle, a green square, a blue triangle, an orange rectangle, a purple pentagon, and a teal
> ellipse. No outlines, no text, no drop shadows — just flat solid shapes on a flat background, like
> clip art for a shape-detection test.

## Deploy to NiFi

The two processors go where the other custom Python processors already live on `mynifi-0`:
`/opt/nifi/nifi-current/python/extensions`. NiFi installs each processor's `dependencies`
(`opencv-python-headless`, `numpy`) on load.

```bash
# copy onto the extensions volume the way this cluster mounts it (PVC/loader pod or minikube mount),
# then confirm they registered:
kubectl exec mynifi-0 -n cfm-streaming -c nifi -- ls /opt/nifi/nifi-current/python/extensions
```

On every real change, **bump `ProcessorDetails.version`** and explicitly switch each running instance to
the new bundle — dropping a same-version file on disk may not register as a new bundle. Copying the `.py`
in is a redeploy of a live service, so drain any in-flight FlowFiles and confirm one `Running` pod first.

## Verified — the real local run

`files/mattyb-image/verify_local.py` runs `generate → detect → crop` through the exact processor
functions and asserts 6 boxes / 6 crops:

```
$ /tmp/mattyb-venv/bin/python verify_local.py
OK: 6 boxes detected, 6 crops written to .../files/mattyb-image/crops
  #1  red     box={'x': 60, 'y': 60, 'w': 181, 'h': 181}   -> shape-1-red.png
  #2  green   box={'x': 360, 'y': 60, 'w': 181, 'h': 181}  -> shape-2-green.png
  #3  blue    box={'x': 660, 'y': 60, 'w': 181, 'h': 181}  -> shape-3-blue.png
  #4  orange  box={'x': 45, 'y': 385, 'w': 211, 'h': 131}  -> shape-4-orange.png
  #5  purple  box={'x': 364, 'y': 360, 'w': 172, 'h': 163} -> shape-5-purple.png
  #6  teal    box={'x': 660, 'y': 385, 'w': 181, 'h': 131} -> shape-6-teal.png
```

Artifacts: `test-image.png` (original), `crops/shape-1..6.png` (the six individual images),
`manifest.json` (the 6-object array the cropper emits).

## What NOT to do

- **Don't try to emit N FlowFiles from the Python processor.** `FlowFileTransform` is one-in/one-out.
  Emit one manifest FlowFile and fan out with `SplitJson` downstream.
- **Don't auto-terminate `SplitJson`'s `split` or `FetchFile`'s `failure`/`not.found`.** That's where
  crops silently vanish. Route failures to the `LogFailure` sink (the flow already does).
- **A NiFi 2.x flow-definition one-shot import can 500 on a Python-processor snapshot.** Importing
  `flow-mattyb-image.json` in a single `POST .../process-groups` with `versionedFlowSnapshot` created only
  a partial PG (GetFile, no connections). Building the PG processor-by-processor via the API worked; that's
  how the live test below was built.

## Verified live on mynifi-0

Deployed both processors to the running NiFi and tested the core chain end-to-end:

- `kubectl cp` both `.py` into the extensions PVC (`/opt/nifi/nifi-current/python/extensions`) — NiFi
  discovered both **without a restart**; real bundle coords are `org.apache.nifi:python-extensions:0.0.1`
  (this is what `flow-mattyb-image.json` now uses).
- Both processors validated **VALID** in NiFi — the `opencv-python-headless` + `numpy` dependencies
  installed on load with no restart.
- Built `GetFile → MattyBShapeDetector → MattyBBoundingBoxCropper` via the API, staged `test-image.png`
  in `/tmp/mattyb-in`, started the flow. The cropper wrote all 6 crops to `/tmp/mattyb` in the pod,
  **byte-for-byte identical to the local run** (1755/669/1927/574/1753/1299). Each custom processor
  ran once on the image; the flow was left stopped.
