"""Profile extras: sector mix for the pie charts, and managers' photos (only
freely licensed ones, credited; rate limits retried later). No network."""

import json

from stockskill.data import manager_photos as MP
from stockskill.data.market_screen import mix


def test_mix_sums_by_sector_and_folds_the_tail():
    w = {"AAPL": 0.3, "MSFT": 0.2, "XOM": 0.1, "ZZZ": 0.05}
    m = mix(w, {"AAPL": "Technology", "MSFT": "Technology", "XOM": "Energy"})
    assert m[0] == {"name": "Technology", "value": 0.5} and {"name": "Other or unknown", "value": 0.05} in m
    many = mix({f"T{i}": 1.0 for i in range(12)}, {f"T{i}": f"S{i}" for i in range(12)}, top=5)
    assert len(many) == 5 and many[-1] == {"name": "Everything else", "value": 8.0}


class R:
    def __init__(self, code, j=None):
        self.status_code, self._j = code, j or {}

    def json(self):
        return self._j


def _fake(license_name="CC BY 2.0", limited=0):
    calls = {"n": 0}

    def get(url, **kw):
        calls["n"] += 1
        if calls["n"] <= limited:
            return R(429)
        if "rest_v1" in url:
            if "Nobody" in url:
                return R(200, {"type": "standard"})                                  # no photo
            return R(200, {"type": "standard", "content_urls": {"desktop": {"page": "https://en.wikipedia.org/wiki/X"}},
                           "thumbnail": {"source": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/Pat_Q.jpg/330px-Pat_Q.jpg?x=1"}})
        return R(200, {"query": {"pages": {"1": {"imageinfo": [{"extmetadata": {
            "LicenseShortName": {"value": license_name}, "Artist": {"value": "<a href='u'>Jane Photographer</a>"}}}]}}}})
    return get


def test_free_photo_is_used_with_credit():
    p = MP.lookup("Pat Q", _fake())
    assert p["img"].endswith("330px-Pat_Q.jpg") and p["credit"] == "Jane Photographer" and p["license"] == "CC BY 2.0"
    assert p["file_page"] == "https://commons.wikimedia.org/wiki/File:Pat_Q.jpg"
    assert MP.lookup("Pat Q", _fake("Fair use")) is None
    assert MP.lookup("Nobody", _fake()) is None


def test_rate_limits_are_retried_later(tmp_path, monkeypatch):
    monkeypatch.setattr(MP.time, "sleep", lambda s: None)
    monkeypatch.setattr(MP, "_path", lambda cd: str(tmp_path / "photos.json"))
    got = MP.refresh(["Pat Q", "Sam R"], get=_fake(limited=99))
    saved = json.load(open(tmp_path / "photos.json"))
    assert got == {} and saved["incomplete"] is True
    got = MP.refresh(["Pat Q"], get=_fake(), force=True)
    assert "Pat Q" in got and json.load(open(tmp_path / "photos.json"))["incomplete"] is False
