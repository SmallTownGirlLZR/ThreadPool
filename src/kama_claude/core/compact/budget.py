from __future__ import annotations

from typing import Any

TOOL_RESULT_LIMIT = 8_000
TOOL_RESULT_KEEP = 4_000

"""
Anthropic Message looks like:
[
  {
    "role": "user",
    "content": "Please read notes.txt"
  },
  {
    "role": "assistant",
    "content": [
      {
        "type": "text",
        "text": "I will read that file."
      },
      {
        "type": "tool_use",
        "id": "toolu_123",
        "name": "filesystem__read_file",
        "input": {
          "path": "notes.txt"
        }
      }
    ]
  },
  {
    "role": "user",
    "content": [
      {
        "type": "tool_result",
        "tool_use_id": "toolu_123",
        "content": "This is the contents of notes.txt"
      }
    ]
  }
]
"""


# 对消息列表中超长的 tool_result 内容做内存截断，返回处理后的新列表
def truncate_tool_results(
    messages: list[dict[str, Any]],
    limit: int = TOOL_RESULT_LIMIT,
    keep: int = TOOL_RESULT_KEEP,
) -> list[dict[str, Any]]:
    result = []
    for msg in messages:
        if msg.get("role") != "user":
            result.append(msg)
            continue
        content = msg.get("content")
        if not isinstance(content, list):
            result.append(msg)
            continue
        new_blocks = []
        for block in content:
            if block.get("type") == "tool_result" and isinstance(block.get("content"), str):
                text = block["content"]
                if len(text) > limit:
                    omitted = len(text) - keep
                    block = dict(block)
                    block["content"] = (
                        text[:keep]
                        + f"\n[... {omitted} chars omitted. Full output in run events.]"
                    )
            new_blocks.append(block)
        result.append({**msg, "content": new_blocks})
    return result
