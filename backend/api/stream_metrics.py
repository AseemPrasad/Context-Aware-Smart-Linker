"""Stream metrics and monitoring."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

@dataclass
class StreamMetrics:
    active_connections: int = 0
    total_tokens_streamed: int = 0
    total_errors: int = 0
    total_completions: int = 0
    time_to_first_token_ms: float = 0.0
    avg_tokens_per_second: float = 0.0
    last_updated: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "active_connections": self.active_connections,
            "total_tokens": self.total_tokens_streamed,
            "total_errors": self.total_errors,
            "total_completions": self.total_completions,
            "ttft_ms": round(self.time_to_first_token_ms, 2),
            "tokens_per_second": round(self.avg_tokens_per_second, 2),
            "last_updated": self.last_updated.isoformat(),
        }

class MetricsCollector:
    _instance: 'MetricsCollector | None' = None

    def __new__(cls) -> 'MetricsCollector':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.metrics = StreamMetrics()
        return cls._instance

    def record_token(self, token_count: int = 1) -> None:
        self.metrics.total_tokens_streamed += token_count

    def record_completion(self) -> None:
        self.metrics.total_completions += 1

    def record_error(self) -> None:
        self.metrics.total_errors += 1

    def get_metrics(self) -> dict[str, Any]:
        return self.metrics.to_dict()

def get_metrics_collector() -> MetricsCollector:
    return MetricsCollector()
