"""Streaming generator functions."""
from typing import AsyncGenerator
from backend.api.stream_builder import EventBuilder
from backend.api.stream_models import StreamEvent

async def stream_extraction(
    url: str,
    context: str = "",
) -> AsyncGenerator[StreamEvent, None]:
    """Stream extraction results."""
    yield EventBuilder.metadata_event("doc_1", "Extracted Page", url)
    yield EventBuilder.progress_event(10, "Starting extraction")

    # Simulate streaming tokens
    text = "Extracted content streaming in real-time for fast UI updates..."
    for i, word in enumerate(text.split()):
        progress = min(100, 10 + int((i / len(text.split())) * 80))
        yield EventBuilder.token_event(word + " ", progress=progress)

    yield EventBuilder.complete_event("Extraction complete")

async def stream_with_timeout(
    generator: AsyncGenerator[StreamEvent, None],
    timeout: int = 300,
) -> AsyncGenerator[StreamEvent, None]:
    """Wrap generator with timeout protection."""
    import asyncio
    try:
        async for event in generator:
            yield event
    except asyncio.TimeoutError:
        yield EventBuilder.error_event("Stream timeout", recoverable=False)
    except Exception as e:
        yield EventBuilder.error_event(str(e), recoverable=True)

async def stream_with_cancellation(
    generator: AsyncGenerator[StreamEvent, None],
    cancel_signal: bool = False,
) -> AsyncGenerator[StreamEvent, None]:
    """Wrap generator with cancellation support."""
    async for event in generator:
        if cancel_signal:
            yield EventBuilder.error_event("Stream cancelled by user", recoverable=False)
            break
        yield event
