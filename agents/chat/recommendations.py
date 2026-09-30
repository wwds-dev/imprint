from services.recommendations import AgentProfile

RECOMMENDATION_PROFILE = AgentProfile(
    "chat", "Chat", ("general", "analysis", "structured"),
    provider_affinity={"anthropic": .94, "openai": .94, "gemini": .88,
                       "deepseek": .88, "qwen": .86, "kimi": .86, "ollama": .72},
)
