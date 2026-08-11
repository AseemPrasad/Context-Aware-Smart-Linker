"""Stream event builders."""
from backend.api.stream_models import StreamEvent, EventType, TokenChunk, StreamMetadata
from datetime import datetime
import json

class EventBuilder:
    @staticmethod
    def token_event(text: str, position: int = 0, progress: int = 0) -> StreamEvent:
        return StreamEvent(
            event_type=EventType.TOKEN,
            data={"text": text, "position": position},
            progress=progress
        )

    @staticmethod
    def metadata_event(doc_id: str, title: str = "", url: str = "") -> StreamEvent:
        return StreamEvent(
            event_type=EventType.METADATA,
            data={"document_id": doc_id, "title": title, "url": url}
        )

    @staticmethod
    def progress_event(percent: int, message: str = "") -> StreamEvent:
        return StreamEvent(
            event_type=EventType.PROGRESS,
            data={"progress": percent, "message": message},
            progress=percent
        )

    @staticmethod
    def complete_event(summary: str = "") -> StreamEvent:
        return StreamEvent(
            event_type=EventType.COMPLETE,
            data={"summary": summary, "timestamp": datetime.utcnow().isoformat()},
            progress=100
        )

    @staticmethod
    def error_event(error_msg: str, recoverable: bool = False) -> StreamEvent:
        return StreamEvent(
            event_type=EventType.ERROR,
            data={"error": error_msg, "recoverable": recoverable}
        )
