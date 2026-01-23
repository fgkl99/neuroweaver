def test_bandpower_has_compute():
    from features.bandpower import feature
    assert callable(getattr(feature, "compute", None))
