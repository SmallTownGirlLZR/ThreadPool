from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

TaskStatus = Literal["pending", "in_progress", "completed"]


@dataclass
class Task:
    id: int         # Other tasks reference this ID in blocked_by.
    subject: str    # A short task title
    description: str    # More detailed description of the task
    status: TaskStatus  # "pending", "in_progress", or "completed"
    blocked_by: list[int]  # List of task IDs that block this task
    created_at: str
    updated_at: str

    # 序列化为 dict，字段名与 JSON 文件格式一致
    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "subject": self.subject,
            "description": self.description,
            "status": self.status,
            "blocked_by": self.blocked_by,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    # 从 dict 构造 Task
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Task:
        return cls(
            id=int(data["id"]),
            subject=str(data["subject"]),
            description=str(data.get("description", "")),
            status=data.get("status", "pending"),
            blocked_by=[int(x) for x in data.get("blocked_by", [])],
            created_at=str(data.get("created_at", "")),
            updated_at=str(data.get("updated_at", "")),
        )
