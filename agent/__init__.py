"""
Agent Module - Core AI Agent Logic
====================================

This module contains the central AI agent that orchestrates all operations.
It manages the conversation loop, decision-making pipeline, and coordinates
between the planner, browser, memory, and tools subsystems.

Components:
    - base_agent: Abstract base class for all agent types
    - pinterest_agent: Main Pinterest-specific agent implementation
    - agent_state: Agent state management and lifecycle
"""

from agent.base_agent import BaseAgent
from agent.pinterest_agent import PinterestAgent

__all__ = ["BaseAgent", "PinterestAgent"]
