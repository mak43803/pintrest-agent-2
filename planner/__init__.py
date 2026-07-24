"""
Planner Module — AI-powered task planning, decision-making, and workflow execution.
=====================================================================================

Provides the intelligent decision layer that determines what the
agent should do next, manages task lifecycles, and executes ordered
workflows with checkpoint/resume support.

Quick Start::

    from planner import Planner
    from database import Database, Repository

    db = Database("database/pinterest_ai_agent.db")
    db.connect()
    repo = Repository(db)

    planner = Planner(db=db, repository=repo)
    await planner.execute()  # autonomous loop

Public API:
    - Planner          — Top-level orchestrator
    - TaskManager      — Task lifecycle CRUD
    - DecisionEngine   — Rule-based decision maker
    - Workflow          — Ordered step sequences
    - WorkflowStep     — Individual step in a workflow
    - StateMachine     — Finite state machine
    - PlannerState     — State enumeration
"""

from planner.planner import Planner
from planner.task_manager import TaskManager
from planner.decision_engine import ActionType, Decision, DecisionEngine
from planner.workflow import Workflow, WorkflowStep, StepStatus, create_pin_product_workflow
from planner.state_machine import PlannerState, StateMachine, InvalidStateTransition

__all__ = [
    "Planner",
    "TaskManager",
    "DecisionEngine",
    "ActionType",
    "Decision",
    "Workflow",
    "WorkflowStep",
    "StepStatus",
    "StateMachine",
    "PlannerState",
    "InvalidStateTransition",
    "create_pin_product_workflow",
]
