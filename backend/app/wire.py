import json
import struct

import numpy as np

MAGIC = b"SPXF"


def encode(meta: dict, images: np.ndarray, masks: np.ndarray) -> bytes:
    """
    Layout: "SPXF", uint32 header length, JSON header (space padded so the
    floats start on a 4-byte boundary), float32 images, uint8 masks.
    Rows go top to bottom with north up, so the browser can draw them as-is.
    """
    n, ny, nx = images.shape
    meta = {**meta, "n": n, "ny": ny, "nx": nx}
    head = json.dumps(meta, separators=(",", ":")).encode()
    head += b" " * (-(8 + len(head)) % 4)
    images = np.ascontiguousarray(images[:, ::-1, :], dtype="<f4")
    masks = np.ascontiguousarray(masks[:, ::-1, :], dtype=np.uint8)
    return MAGIC + struct.pack("<I", len(head)) + head + images.tobytes() + masks.tobytes()


def decode(buf: bytes) -> tuple[dict, np.ndarray, np.ndarray]:
    assert buf[:4] == MAGIC
    (size,) = struct.unpack("<I", buf[4:8])
    meta = json.loads(buf[8 : 8 + size])
    n, ny, nx = meta["n"], meta["ny"], meta["nx"]
    start = 8 + size
    images = np.frombuffer(buf, "<f4", n * ny * nx, start).reshape(n, ny, nx)
    masks = np.frombuffer(buf, np.uint8, n * ny * nx, start + 4 * n * ny * nx).reshape(n, ny, nx)
    return meta, images[:, ::-1, :], masks[:, ::-1, :]
