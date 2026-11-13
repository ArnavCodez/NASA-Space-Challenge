from app.search import group_epochs, parse_rows

URI = "ibe/data/spherex/{rel}/level2/2025W19_1B/l2b-v{v}-2026-197/6/level2_2025W19_1B_0116_1D6_spx_l2b-v{v}-2026-197.fits"


def test_epochs_split_on_gaps():
    mjd = [60800.7, 60801.5, 60979.6, 60993.9, 61020.8, 61151.0, 61174.0]
    assert list(group_epochs(mjd)) == [0, 0, 1, 1, 1, 2, 2]


def test_long_stretches_get_chopped():
    mjd = [61000 + d for d in range(0, 150, 5)]
    labels = group_epochs(mjd)
    assert labels.max() == 2
    assert all(labels[i] <= labels[i + 1] for i in range(len(labels) - 1))


def test_dedupe_prefers_release_then_newest_version():
    rows = [
        (URI.format(rel="qr3", v=30), "SPHEREx-D6", 60800.70, 60800.71),
        (URI.format(rel="dr1", v=27), "SPHEREx-D6", 60800.70, 60800.71),
        (URI.format(rel="dr1", v=28), "SPHEREx-D6", 60800.70, 60800.71),
        (URI.format(rel="qr2", v=20), "SPHEREx-D6", 60800.70, 60800.71),
    ]
    frames = parse_rows(rows)
    assert len(frames) == 1
    assert frames[0]["release"] == "dr1"
    assert frames[0]["version"].startswith("l2b-v28")
    assert frames[0]["det"] == "D6"
    assert frames[0]["obs_id"] == "2025W19_1B_0116_1"
