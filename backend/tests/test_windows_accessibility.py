from __future__ import annotations

from app.services.windows_accessibility import _normalize_rect, _parse_match


def test_parse_accessibility_match_from_json() -> None:
    match = _parse_match(
        '{"found":true,"name":"Search the web","control_type":"ControlType.Edit","left":400,"top":200,"right":900,"bottom":260,"exact":true,"is_password":false}'
    )
    assert match is not None
    assert match.name == "Search the web"
    assert match.label == "Search the web"
    assert match.control_type == "Edit"
    assert (match.left, match.top, match.right, match.bottom) == (400, 200, 900, 260)
    assert match.exact is True
    assert match.is_password is False


def test_parse_accessibility_semantic_label_can_differ_from_current_name() -> None:
    match = _parse_match(
        '{"found":true,"name":"weather in Phoenix","label":"Address and search bar","control_type":"ControlType.Edit","left":300,"top":80,"right":1200,"bottom":130,"exact":false,"is_password":false}'
    )
    assert match is not None
    assert match.name == "weather in Phoenix"
    assert match.label == "Address and search bar"
    assert match.control_type == "Edit"


def test_parse_accessibility_password_field_metadata() -> None:
    match = _parse_match(
        '{"found":true,"name":"Password","control_type":"ControlType.Edit","left":100,"top":100,"right":500,"bottom":140,"exact":true,"is_password":true}'
    )
    assert match is not None
    assert match.is_password is True


def test_parse_accessibility_not_found_returns_none() -> None:
    assert _parse_match('{"found":false}') is None
    assert _parse_match("") is None


def test_normalize_rect_maps_negative_virtual_desktop_coordinates() -> None:
    # Two 1920x1080 monitors with the secondary monitor to the left.
    desktop = (-1920, 0, 3840, 1080)
    bbox = _normalize_rect((-1600, 100, -800, 300), desktop)
    assert bbox is not None
    left, top, right, bottom = bbox
    assert 0 <= left < right <= 1000
    assert 0 <= top < bottom <= 1000
    assert left < 500
    assert right < 500


def test_normalize_rect_rejects_off_desktop_or_invalid_rectangles() -> None:
    desktop = (0, 0, 1920, 1080)
    assert _normalize_rect((2000, 0, 2200, 100), desktop) is None
    assert _normalize_rect((500, 500, 400, 600), desktop) is None
