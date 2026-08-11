"""SSE streaming configuration."""
import os
from dataclasses import dataclass

@dataclass
class StreamConfig:
    stream_enabled: bool = os.getenv("STREAM_ENABLED", "false").lower() == "true"
    stream_chunk_size: int = int(os.getenv("STREAM_CHUNK_SIZE", "128"))
    stream_buffer_size: int = int(os.getenv("STREAM_BUFFER_SIZE", "8192"))
    stream_timeout: int = int(os.getenv("STREAM_TIMEOUT", "300"))
    stream_heartbeat_interval: int = int(os.getenv("STREAM_HEARTBEAT_INTERVAL", "15"))

def get_stream_config() -> StreamConfig:
    if not hasattr(get_stream_config, "_instance"):
        get_stream_config._instance = StreamConfig()
    return get_stream_config._instance
