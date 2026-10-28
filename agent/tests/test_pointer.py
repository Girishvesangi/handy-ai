import json

from livekit import rtc

from handy.checker import parse_pointer
from handy.frames import LatestFrame


def test_parse_pointer_scales_box():
    p = parse_pointer(json.dumps({"found": True, "label": "RAM", "box_2d": [100, 200, 500, 800]}), 300)
    assert p.found and p.label == "RAM"
    assert p.box == [0.1, 0.2, 0.5, 0.8]
    assert p.latency_ms == 300


def test_parse_pointer_rejects_bad_boxes():
    assert not parse_pointer(json.dumps({"found": False, "label": "x"})).found
    assert not parse_pointer(json.dumps({"found": True, "label": "x", "box_2d": [1, 2]})).found
    assert not parse_pointer(json.dumps({"found": True, "label": "x", "box_2d": [500, 0, 100, 10]})).found
    assert not parse_pointer("nope").found


def test_parse_pointer_clamps():
    p = parse_pointer(json.dumps({"found": True, "label": "x", "box_2d": [-20, 0, 1200, 1000]}))
    assert p.box == [0.0, 0.0, 1.0, 1.0]


class FakeRoom:
    remote_participants: dict = {}

    def on(self, *a, **k):
        pass


def _frame(w: int, h: int) -> rtc.VideoFrame:
    return rtc.VideoFrame(w, h, rtc.VideoBufferType.RGBA, bytearray(w * h * 4))


def test_frame_rotation_makes_images_upright():
    from PIL import Image
    import io

    lf = LatestFrame(FakeRoom())
    assert lf.jpeg() is None and lf.size() is None

    lf._frame = _frame(64, 32)  # landscape pixels...
    lf._rotation = rtc.VideoRotation.VIDEO_ROTATION_90  # ...that should be shown portrait
    assert lf.size() == (32, 64)
    w, h = Image.open(io.BytesIO(lf.jpeg())).size
    assert w * 2 == h  # portrait, same 1:2 shape (the encoder also scales it up)

    lf._rotation = rtc.VideoRotation.VIDEO_ROTATION_0
    assert lf.size() == (64, 32)
    w, h = Image.open(io.BytesIO(lf.jpeg())).size
    assert w == h * 2
