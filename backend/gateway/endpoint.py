"""FastAPI endpoint for multi-model gateway."""

from __future__ import annotations

from fastapi import APIRouter

from backend.gateway.base import ProviderConfig
from backend.gateway.config import get_gateway_config
from backend.gateway.providers.anthropic_provider import get_anthropic_provider
from backend.gateway.providers.openai_provider import get_openai_provider
from backend.gateway.providers.ollama_provider import get_ollama_provider
from backend.gateway.router import get_gateway
from backend.schemas.retrieval import SearchRequest, SearchResponse, SearchHit

router = APIRouter(prefix="/api/v1/gateway")


async def _initialize_gateway() -> None:
    """Initialize gateway with configured providers."""
    config = get_gateway_config()

    if not config.is_gateway_active():
        return

    gateway = get_gateway()
    enabled_providers = config.get_enabled_providers()

    for i, provider_name in enumerate(enabled_providers):
        if provider_name == "openai" and config.openai_api_key:
            provider_config = ProviderConfig(
                provider_name="openai",
                api_key=config.openai_api_key,
                model_name=config.openai_model,
                cost_per_1k_input_tokens=config.openai_cost_input,
                cost_per_1k_output_tokens=config.openai_cost_output,
            )
            provider = get_openai_provider(provider_config)
            gateway.register_provider(provider, priority=i)

        elif provider_name == "anthropic" and config.anthropic_api_key:
            provider_config = ProviderConfig(
                provider_name="anthropic",
                api_key=config.anthropic_api_key,
                model_name=config.anthropic_model,
                cost_per_1k_input_tokens=config.anthropic_cost_input,
                cost_per_1k_output_tokens=config.anthropic_cost_output,
            )
            provider = get_anthropic_provider(provider_config)
            gateway.register_provider(provider, priority=i)

        elif provider_name == "ollama" and config.ollama_enabled:
            provider_config = ProviderConfig(
                provider_name="ollama",
                base_url=config.ollama_base_url,
                model_name=config.ollama_model,
            )
            provider = get_ollama_provider(provider_config)
            gateway.register_provider(provider, priority=i)


@router.post("/generate")
async def generate(request: SearchRequest) -> SearchResponse:
    """Generate response using multi-model gateway.

    Routes request to appropriate provider based on complexity and availability.
    Falls back through provider chain if selected provider fails.
    """
    await _initialize_gateway()

    config = get_gateway_config()

    if not config.is_gateway_active():
        return SearchResponse(
            tenant_id=request.tenant_id,
            query=request.query,
            hits=[],
        )

    gateway = get_gateway()

    # Route request
    response, decision = await gateway.route(
        query=request.query,
        context="",  # Could be populated from previous context
        num_hits=len(request.query.split()),  # Rough estimate
        use_rerank=request.use_rerank,
    )

    if response is None:
        return SearchResponse(
            tenant_id=request.tenant_id,
            query=request.query,
            hits=[],
        )

    # Convert LLM response to SearchResponse (adapting for compatibility)
    return SearchResponse(
        tenant_id=request.tenant_id,
        query=request.query,
        hits=[
            SearchHit(
                document_id="generated",
                passage=response.text,
                score=1.0,
            )
        ],
    )


@router.get("/health")
async def gateway_health() -> dict:
    """Check health of all providers."""
    await _initialize_gateway()

    gateway = get_gateway()
    health_status = await gateway.health_check_all()

    return {"status": "ok", "providers": health_status}


@router.get("/metrics")
async def gateway_metrics() -> dict:
    """Get gateway metrics and statistics."""
    await _initialize_gateway()

    config = get_gateway_config()
    gateway = get_gateway()

    return {
        "config": {
            "gateway_enabled": config.gateway_enabled,
            "gateway_mode": config.gateway_mode,
            "enabled_providers": config.get_enabled_providers(),
            "monthly_budget": config.monthly_budget_usd,
        },
        "gateway_stats": gateway.get_gateway_stats(),
    }
