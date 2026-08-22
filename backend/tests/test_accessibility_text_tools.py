from __future__ import annotations

import asyncio

from app.agent.accessibility_text_tools import _parse_result, _validated_arguments, accessibility_text_tools
from app.agent.contracts import ToolInvocation
from app.agent.permissions import default_policy
from app.agent.tool_registry import ToolRegistry


def test_uia_text_result_parser_accepts_success_without_exposing_value() -> None:
    result = _parse_result(
        '{"ok":true,"name":"Address and search bar","control_type":"ControlType.Edit","character_count":18}'
    )
    assert result["ok"] is True
    assert result["name"] == "Address and search bar"
    assert result["character_count"] == 18
    assert "value" not in result


def test_uia_text_arguments_reject_control_characters() -> None:
    query, text, x, y = _validated_arguments(
        {
            "target_query": "Address and search bar",
            "text": "weather in Phoenix",
            "expected_x": 500,
            "expected_y": 40,
        }
    )
    assert (query, text, x, y) == ("Address and search bar", "weather in Phoenix", 500, 40)

    try:
        _validated_arguments(
            {
                "target_query": "Address and search bar",
                "text": "weather\nPhoenix",
                "expected_x": 500,
                "expected_y": 40,
            }
        )
    except ValueError as exc:
        assert "Control characters" in str(exc)
    else:
        raise AssertionError("newline should have been rejected")


def test_uia_text_tool_is_model_hidden_and_requires_confirmation() -> None:
    registry = ToolRegistry(default_policy())
    registry.register_many(accessibility_text_tools())

    assert registry.list_tools() == []
    internal = {tool.name: tool for tool in registry.list_tools(include_internal=True)}
    assert set(internal) == {"replace_text_value"}
    assert internal["replace_text_value"].model_visible is False
    assert internal["replace_text_value"].requires_confirmation is True

    result = asyncio.run(
        registry.invoke(
            ToolInvocation(
                tool_name="replace_text_value",
                arguments={
                    "target_query": "Address and search bar",
                    "text": "weather in Phoenix",
                    "expected_x": 500,
                    "expected_y": 40,
                },
            )
        )
    )
    assert not result.ok
    assert "requires user confirmation" in (result.error or "")
