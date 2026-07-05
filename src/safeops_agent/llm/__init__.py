from __future__ import annotations

from safeops_agent.llm.provider import DeepSeekProvider, LLMProvider, RuleBasedProvider

__all__ = ["LLMProvider", "DeepSeekProvider", "RuleBasedProvider", "get_provider"]


def get_provider() -> LLMProvider:
    """根据配置和环境变量返回合适的 LLM Provider 实例。"""
    import os

    from safeops_agent.config import load_llm_config

    config = load_llm_config()
    if not config.get("llm_enabled", False):
        return RuleBasedProvider()

    api_key = os.environ.get("LLM_API_KEY", "") or str(config.get("llm_api_key", ""))
    if not api_key:
        return RuleBasedProvider()

    provider_name = str(config.get("llm_provider", "deepseek")).lower()
    if provider_name == "deepseek":
        return DeepSeekProvider(
            api_key=api_key,
            model=str(config.get("llm_model", "deepseek-chat")),
            base_url=str(config.get("llm_base_url", "https://api.deepseek.com")),
            timeout=int(config.get("llm_timeout", 30)),
        )
    return RuleBasedProvider()
