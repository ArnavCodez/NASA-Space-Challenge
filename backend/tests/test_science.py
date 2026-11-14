import numpy as np
import pytest

from app.frames import M_BAD, M_SATURATED, M_SOURCE, M_TRANSIENT, display_mask
from app.measure import _line, centroid
from app.views import coadd


def test_coadd_synthetic():
    # 8 frames with background around 10.0 and one bright star at (5, 5)
    shape = (11, 11)
    items = []
    rng = np.random.default_rng(42)
    bkg_values = [10.1, 9.9, 10.0, 10.2, 500.0, 10.0, 9.8, 10.1]
    for i in range(8):
        img = np.full(shape, bkg_values[i], dtype=np.float32)
        img[5, 5] = 50.0 + rng.normal(0, 0.1)
        mask = np.zeros(shape, dtype=np.uint8)
        # In frame 3, add a cosmic ray (transient) at (2, 2)
        if i == 3:
            img[2, 2] = 999.0
            mask[2, 2] = M_TRANSIENT

        items.append(({"id": f"f{i}", "det": "D1"}, {"image": img, "mask": mask, "noise": 1.0}))

    out_img, out_mask, noise = coadd(items)
    # Transient at (2, 2) should be rejected from stacking
    assert out_img[2, 2] == pytest.approx(10.0, abs=0.5)
    # The star at (5, 5) should be ~50.0
    assert out_img[5, 5] == pytest.approx(50.0, abs=0.5)
    # Sigma clipping should reject outlier at (7, 7) (from frame 4 where background was 500)
    assert out_img[7, 7] == pytest.approx(10.0, abs=0.5)
    assert noise > 0


def test_display_mask():
    flags = np.array([[1, 2], [4, 8]], dtype=np.uint32)
    names = {0: "NONFUNC", 1: "OVERFLOW", 2: "STREAK", 3: "SOURCE"}
    mask = display_mask(flags, names)
    # Bit 0 NONFUNC -> BAD (1)
    assert mask[0, 0] & M_BAD != 0
    # Bit 1 OVERFLOW -> SATURATED (16)
    assert mask[0, 1] & M_SATURATED != 0
    # Bit 2 STREAK -> ARTIFACT (4)
    assert mask[1, 0] & 4 != 0
    # Bit 3 SOURCE -> SOURCE (2)
    assert mask[1, 1] & M_SOURCE != 0


def test_centroid_gaussian():
    # Synthetic 2D Gaussian at (12.4, 15.7)
    ny, nx = 31, 31
    yy, xx = np.mgrid[0:ny, 0:nx]
    x_true, y_true, sigma = 12.4, 15.7, 1.8
    amp, bkg = 100.0, 5.0
    img = amp * np.exp(-((xx - x_true) ** 2 + (yy - y_true) ** 2) / (2 * sigma**2)) + bkg

    fit = centroid(img, 12.0, 15.0, reach=4.0, width=sigma)
    assert fit is not None
    fx, fy, ex, ey, f_amp = fit
    assert fx == pytest.approx(x_true, abs=0.1)
    assert fy == pytest.approx(y_true, abs=0.1)
    assert f_amp == pytest.approx(amp, rel=0.1)


def test_motion_line_fit():
    # True motion: slope = 2.5
    t = np.array([0.0, 1.0, 2.0, 3.0])
    v = 2.5 * t + 10.0
    e = np.array([0.1, 0.1, 0.1, 0.1])
    slope, err = _line(t, v, e)
    assert slope == pytest.approx(2.5, abs=0.01)
    assert err > 0
