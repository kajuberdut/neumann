from .base import BaseStrategy
from .qwen import QwenStrategy

__all__ = ["BaseStrategy", "QwenStrategy"]

# Simple registry (could be expanded)
STRATEGIES = {
    "qwen": QwenStrategy(),
}


def get_strategy(name: str) -> BaseStrategy:
    return STRATEGIES.get(name, STRATEGIES["qwen"])
