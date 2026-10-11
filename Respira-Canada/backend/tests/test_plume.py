from app.science.plume import cone_polygon, plume_tip


def _run(hours, **kw):
    res = cone_polygon(lat=51.0, lon=-114.0, wind_speed_m_s=5.0, wind_dir_from_deg=270.0, hours=hours,
                       fwi=20, ffmc=90, suppress_small_fires=False, **kw)
    assert res is not None
    return res


def test_plume_travels_downwind():
    _, meta = _run(2)
    lat, lon = plume_tip(meta)
    assert lon > -114.0            # west wind pushes smoke east
    assert abs(lat - 51.0) < 0.05


def test_plume_grows_with_time_and_intensity():
    _, short = _run(1)
    _, long_ = _run(4)
    assert long_["plume_length_m"] > short["plume_length_m"]
    _, mild = _run(2, frp_mw=0)
    _, hot = _run(2, frp_mw=400)
    assert hot["plume_length_m"] > mild["plume_length_m"]


def test_small_cool_detection_is_suppressed():
    assert cone_polygon(lat=51, lon=-114, wind_speed_m_s=3, wind_dir_from_deg=0, hours=1,
                        fwi=3, ffmc=70, area_m2=1000, suppress_small_fires=True) is None


def test_polygon_valid_everywhere():
    # Regression: the origin point used to produce a self-intersection at some coordinates.
    for lat in (43.7, 49.3, 51.4, 53.5, 58.8, 62.5):
        for lon in (-135.0, -123.1, -114.8, -106.6, -79.4, -63.6):
            for wd in (0.0, 90.0, 225.0, 270.0):
                assert cone_polygon(lat=lat, lon=lon, wind_speed_m_s=6, wind_dir_from_deg=wd, hours=2,
                                    fwi=25, ffmc=91, area_m2=8.5e6, suppress_small_fires=False) is not None
