"""Explicitly allow only the data models used by GUSTAV's chat completions.

Why: A scanner-clean package name does not make pickle safe. Every disk cache
must use the restricted reader, even when callers omit restrict_pickle.
Provider model classes are reviewed with the pinned LiteLLM/OpenAI versions;
unknown response types are deliberately not persisted.
"""
from functools import lru_cache

from diskcache_community import SafeDisk


@lru_cache(maxsize=1)
def safe_disk():
    """Return a restricted disk class; corrupt entries are cache misses."""
    from litellm.types.utils import (
        ChatCompletionMessageToolCall,
        Choices,
        Function,
        Message,
        ModelResponse,
        Usage,
    )
    from openai.types.completion_usage import CompletionTokensDetails, PromptTokensDetails

    return SafeDisk.with_types(
        ModelResponse, Choices, Message, Usage, Function, ChatCompletionMessageToolCall,
        PromptTokensDetails, CompletionTokensDetails,
    ).with_options(on_error='miss')
