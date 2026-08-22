from app.services.visual_interaction_verified import parse_verified_type_request


def test_quoted_literal_with_in_word_keeps_full_text_and_target() -> None:
    request = parse_verified_type_request('Type "weather in Phoenix" into Address and search bar')
    assert request is not None
    assert request.action == "type"
    assert request.text == "weather in Phoenix"
    assert request.target == "Address and search bar"


def test_quoted_literal_can_contain_into_without_changing_target() -> None:
    request = parse_verified_type_request('Type "sign in to portal and go into settings" into Address and search bar')
    assert request is not None
    assert request.text == "sign in to portal and go into settings"
    assert request.target == "Address and search bar"


def test_unquoted_literal_uses_final_separator() -> None:
    request = parse_verified_type_request("Type weather in Phoenix into Address and search bar")
    assert request is not None
    assert request.text == "weather in Phoenix"
    assert request.target == "Address and search bar"


def test_generic_target_is_rejected() -> None:
    assert parse_verified_type_request('Type "hello" into it') is None
