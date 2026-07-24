"""
Context Builder - Constructs LLM context from multiple memory sources.

Assembles the final prompt context by combining system prompts,
conversation history, retrieved memories, and current task state
within the model's context window limits.
"""

# TODO: Implement ContextBuilder class
# - build_context(task, history, memories) -> assembled context string
# - truncate_to_window(context, max_tokens) -> fit within token limit
# - prioritize_messages(messages) -> rank messages by relevance
