from __future__ import annotations

from safeops_agent.llm.provider import (
    DeepSeekProvider,
    LLMProvider,
    OpenAICompatibleProvider,
    RuleBasedProvider,
)

__all__ = [
    "LLMProvider",
    "DeepSeekProvider",
    "OpenAICompatibleProvider",
    "RuleBasedProvider",
    "get_provider",
]


def get_provider() -> LLMProvider:
    """根据配置和环境变量返回合适的 LLM Provider 实例。

    环境变量 SAFEOPS_LLM_DISABLED=1 可强制离线规则模式，
    供测试、CI 与无网络演示环境使用。
    """
    import os

    from safeops_agent.config import load_llm_config, load_tools_config

    tool_defaults = dict(load_tools_config().get("tool_defaults", {}))

    if os.environ.get("SAFEOPS_LLM_DISABLED", "") == "1":
        return RuleBasedProvider(tool_defaults=tool_defaults)

    config = load_llm_config()
    if not config.get("llm_enabled", False):
        return RuleBasedProvider(tool_defaults=tool_defaults)

    api_key = os.environ.get("LLM_API_KEY", "") or str(config.get("llm_api_key", ""))
    if not api_key:
        return RuleBasedProvider(tool_defaults=tool_defaults)

    provider_name = str(config.get("llm_provider", "deepseek")).lower()
    if provider_name == "deepseek":
        return DeepSeekProvider(
            api_key=api_key,
            model=str(config.get("llm_model", "deepseek-chat")),
            base_url=str(config.get("llm_base_url", "https://api.deepseek.com")),
            timeout=int(config.get("llm_timeout", 8)),
        )
    if provider_name.replace("_", "-") in {"openai", "openai-compatible"}:
        return OpenAICompatibleProvider(
            api_key=api_key,
            model=str(config.get("llm_model", "")),
            base_url=str(config.get("llm_base_url", "https://api.openai.com/v1")),
            timeout=int(config.get("llm_timeout", 10)),
        )
    return RuleBasedProvider(tool_defaults=tool_defaults)
