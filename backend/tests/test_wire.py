import numpy as np

from app.wire import decode, encode


def test_round_trip():
    rng = np.random.default_rng(1)
    images = rng.normal(size=(3, 5, 7)).astype(np.float32)
    images[0, 0, 0] = np.nan
    masks = rng.integers(0, 32, size=(3, 5, 7), dtype=np.uint8)

    buf = encode({"view": "raw", "frames": [{"id": "a"}] * 3}, images, masks)
    meta, im2, m2 = decode(buf)

    assert meta["n"] == 3 and meta["ny"] == 5 and meta["nx"] == 7
    np.testing.assert_array_equal(im2, images)
    np.testing.assert_array_equal(m2, masks)


def test_float_block_is_aligned():
    for name in ["x", "xy", "xyz", "wxyz"]:
        buf = encode({"name": name}, np.zeros((1, 2, 2), np.float32), np.zeros((1, 2, 2), np.uint8))
        size = int.from_bytes(buf[4:8], "little")
        assert (8 + size) % 4 == 0
