from gen_version import build_version


def test_deterministic_same_input():
    a = build_version("152", "0.7977.82", "dev")
    b = build_version("152", "0.7977.82", "dev")
    assert a == b


def test_channel_endpoint_placeholder():
    v = build_version("152", "0.7977.82", "stable")
    assert v["update_url"] == "https://update.xr.example/"
    assert v["pending_ops"].startswith("update_url is an RFC 2606 placeholder")


def test_invalid_channel_rejected():
    import pytest
    with pytest.raises(Exception):
        build_version("152", "0.7977.82", "production")
