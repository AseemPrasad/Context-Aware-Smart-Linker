"""Stream response models."""
from dataclasses import dataclass, field
from typing import Any
from datetime import datetime
from enum import Enum

class EventType(str, Enum):
    TOKEN = "token"
    CHUNK = "chunk"
    METADATA = "metadata"
    PROGRESS = "progress"
    COMPLETE = "complete"
    ERROR = "error"

@dataclass
class StreamEvent:
    event_type: EventType
    data: Any
    timestamp: datetime = field(default_factory=datetime.utcnow)
    progress: int = 0

    def to_sse_format(self) -> str:
        """Convert to SSE wire format."""
        import json
        data_str = json.dumps(self.data) if not isinstance(self.data, str) else self.data
        return f"event: {self.event_type.value}\ndata: {data_str}\n\n"

@dataclass
class TokenChunk:
    text: str
    position: int = 0
    progress: int = 0

@dataclass
class StreamMetadata:
    document_id: str
    title: str = ""
    url: str = ""
    total_tokens: int = 0
