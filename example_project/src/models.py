"""
Data models for the Task Manager.
"""

import hashlib
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class User:
    id: Optional[int] = None
    email: str = ""
    password_hash: str = ""
    name: str = ""
    created_at: float = 0.0

    def verify_password(self, password: str) -> bool:
        """Check if password matches the stored hash."""
        return self.password_hash == hashlib.sha256(password.encode()).hexdigest()

    @classmethod
    def from_row(cls, row) -> "User":
        return cls(
            id=row["id"],
            email=row["email"],
            password_hash=row["password_hash"],
            name=row["name"],
            created_at=row["created_at"],
        )


@dataclass
class Task:
    id: Optional[int] = None
    user_id: int = 0
    title: str = ""
    description: str = ""
    priority: str = "medium"
    completed: bool = False
    created_at: float = 0.0
    updated_at: float = 0.0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "description": self.description,
            "priority": self.priority,
            "completed": self.completed,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_row(cls, row) -> "Task":
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            title=row["title"],
            description=row["description"],
            priority=row["priority"],
            completed=bool(row["completed"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
