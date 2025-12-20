import json

import streamingjson  # pyright: ignore[reportMissingTypeStubs]

from loop.types import JsonType
from utils.string import shorten_middle

__all__ = ["extract_tool_args"]


def extract_tool_args(
    json_content: str | streamingjson.Lexer,
    tool_name: str,
    *,
    max_value_width: int = 120,
) -> dict[str, str]:
    """
    Extract tool arguments as a dictionary with formatted string values.

    Args:
        json_content: Raw JSON string or streaming lexer
        tool_name: Name of the tool (used for special handling)
        max_value_width: Maximum width for each value (will be shortened if exceeded)

    Returns:
        Dictionary of parameter names to formatted string values.
        Returns empty dict if parsing fails or no arguments.
    """
    if isinstance(json_content, streamingjson.Lexer):
        json_str = json_content.complete_json()
    else:
        json_str = json_content

    try:
        curr_args: JsonType = json.loads(json_str)
    except json.JSONDecodeError:
        return {}

    if not curr_args or not isinstance(curr_args, dict):
        return {}

    # Special handling for certain tools
    if tool_name == "TodoList":
        return {}

    result: dict[str, str] = {}
    for key, value in curr_args.items():
        if value is None:
            continue
        # Convert value to string representation
        if isinstance(value, str):
            str_value = value
        elif isinstance(value, bool):
            str_value = "true" if value else "false"
        elif isinstance(value, (int, float)):
            str_value = str(value)
        else:
            # For complex types (list, dict), use compact JSON
            str_value = json.dumps(value, ensure_ascii=False, separators=(",", ":"))

        # Shorten long values
        str_value = shorten_middle(str_value, width=max_value_width)
        result[key] = str_value

    return result
