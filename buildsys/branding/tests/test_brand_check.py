from pathlib import Path

from brand_check import check_binary, scan_repo, write_fixture


def test_fixture_binary_good_bad(tmp_path):
    files = write_fixture(tmp_path)
    bad, missing = check_binary(Path(files["good.elf"]))
    assert bad == [] and missing == []
    bad, missing = check_binary(Path(files["bad.elf"]))
    assert "Google Chrome" in bad
    assert "XR Browser" in missing


def test_scan_finds_endpoint(tmp_path):
    (tmp_path / "buildsys").mkdir()
    (tmp_path / "buildsys" / "x.py").write_text("url = \"https://update.googleapis.com/service\"\n")
    hits = scan_repo(tmp_path)
    assert any("update.googleapis.com" in h for h in hits)


def test_scan_clean_tree(tmp_path):
    (tmp_path / "buildsys").mkdir()
    (tmp_path / "buildsys" / "x.py").write_text("url = \"https://update.xr.example/\"\n")
    assert scan_repo(tmp_path) == []
