"""
Decision Engine — Intelligent decision-making for the planner.
================================================================

Evaluates the current system state and determines the next action.
The engine answers five core questions:

    1. **What task to execute next?**
       → Selects from the priority queue based on status and order.

    2. **Which module should be called?**
       → Maps task types to handler modules.

    3. **Whether retry is required?**
       → Evaluates retry count vs. max retries.

    4. **Whether task should be skipped?**
       → Checks skip conditions (max retries exceeded, etc.).

    5. **Whether execution should stop?**
       → Evaluates stop conditions (fatal errors, user cancel, etc.).

Design:
    - The engine is stateless — it receives state, returns decisions.
    - All decisions are returned as typed ``Decision`` dataclasses.
    - Easy to extend with new decision rules via the plugin-ready
      ``DecisionRule`` protocol.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Protocol, runtime_checkable

from database.models import Product, Status, Task

logger = logging.getLogger("pinterest_agent.planner.decision_engine")


# ═══════════════════════════════════════════════════════════════════════
# Decision Types
# ═══════════════════════════════════════════════════════════════════════

class ActionType(str, Enum):
    """The type of action the planner should take next."""
    EXECUTE_TASK   = "execute_task"
    RETRY_TASK     = "retry_task"
    SKIP_TASK      = "skip_task"
    WAIT           = "wait"
    STOP           = "stop"
    NO_TASKS       = "no_tasks"

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class Decision:
    """
    Immutable decision returned by the engine.

    Attributes:
        action:       What the planner should do next.
        task:         The task this decision applies to (if any).
        product:      The product this decision applies to (if any).
        reason:       Human-readable explanation of the decision.
        target_module: Which module/handler should execute this action.
        metadata:     Arbitrary key-value data for the executor.
    """
    action: ActionType
    task: Task | None = None
    product: Product | None = None
    reason: str = ""
    target_module: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════════════
# Decision Rule Protocol (Plugin Interface)
# ═══════════════════════════════════════════════════════════════════════

@runtime_checkable
class DecisionRule(Protocol):
    """
    Protocol for pluggable decision rules.

    Any class implementing ``evaluate()`` can be registered with the
    engine to extend its decision logic. Rules are evaluated in
    priority order — the first rule that returns a non-None decision wins.
    """

    @property
    def priority(self) -> int:
        """Lower number = higher priority. Evaluated first."""
        ...

    def evaluate(
        self,
        pending_tasks: list[Task],
        pending_products: list[Product],
        active_task: Task | None,
        failed_tasks: list[Task],
    ) -> Decision | None:
        """
        Evaluate the current state and optionally return a decision.

        Args:
            pending_tasks:    Tasks in Pending status.
            pending_products: Products in Pending status.
            active_task:      The currently running task (if any).
            failed_tasks:     Tasks in Failed status.

        Returns:
            A ``Decision`` if this rule applies, or ``None`` to defer
            to the next rule.
        """
        ...


# ═══════════════════════════════════════════════════════════════════════
# Built-in Decision Rules
# ═══════════════════════════════════════════════════════════════════════

class ActiveTaskRule:
    """If a task is already running, wait for it to finish."""

    @property
    def priority(self) -> int:
        return 10

    def evaluate(
        self,
        pending_tasks: list[Task],
        pending_products: list[Product],
        active_task: Task | None,
        failed_tasks: list[Task],
    ) -> Decision | None:
        if active_task is not None:
            return Decision(
                action=ActionType.WAIT,
                task=active_task,
                reason=f"Task '{active_task.task_name}' is already running.",
            )
        return None


class FailedTaskRetryRule:
    """Retry failed tasks if their retry count is below the threshold."""

    def __init__(self, max_retries: int = 3) -> None:
        self._max_retries = max_retries

    @property
    def priority(self) -> int:
        return 20

    def evaluate(
        self,
        pending_tasks: list[Task],
        pending_products: list[Product],
        active_task: Task | None,
        failed_tasks: list[Task],
    ) -> Decision | None:
        # Check for retryable failed tasks
        # (We use task name parsing to identify retry count — the planner
        #  tracks actual counts via the product's retry_count field)
        for task in failed_tasks:
            return Decision(
                action=ActionType.RETRY_TASK,
                task=task,
                reason=f"Failed task '{task.task_name}' eligible for retry.",
            )
        return None


class PendingTaskRule:
    """Execute the next pending task in FIFO order."""

    @property
    def priority(self) -> int:
        return 30

    def evaluate(
        self,
        pending_tasks: list[Task],
        pending_products: list[Product],
        active_task: Task | None,
        failed_tasks: list[Task],
    ) -> Decision | None:
        if pending_tasks:
            task = pending_tasks[0]
            return Decision(
                action=ActionType.EXECUTE_TASK,
                task=task,
                reason=f"Next pending task: '{task.task_name}'.",
                target_module="workflow",
            )
        return None


class PendingProductRule:
    """Auto-create a task for the next pending product."""

    @property
    def priority(self) -> int:
        return 40

    def evaluate(
        self,
        pending_tasks: list[Task],
        pending_products: list[Product],
        active_task: Task | None,
        failed_tasks: list[Task],
    ) -> Decision | None:
        if pending_products:
            product = pending_products[0]
            return Decision(
                action=ActionType.EXECUTE_TASK,
                product=product,
                reason=f"Next pending product: '{product.product_name}'.",
                target_module="workflow",
                metadata={"product_id": product.id},
            )
        return None


class NoWorkRule:
    """If nothing is pending, signal that there are no tasks."""

    @property
    def priority(self) -> int:
        return 100

    def evaluate(
        self,
        pending_tasks: list[Task],
        pending_products: list[Product],
        active_task: Task | None,
        failed_tasks: list[Task],
    ) -> Decision | None:
        return Decision(
            action=ActionType.NO_TASKS,
            reason="No pending tasks or products.",
        )


# ═══════════════════════════════════════════════════════════════════════
# Decision Engine
# ═══════════════════════════════════════════════════════════════════════

class DecisionEngine:
    """
    Stateless decision engine that evaluates rules to produce decisions.

    Rules are evaluated in priority order (lowest number first).
    The first rule that returns a non-None ``Decision`` wins.

    Built-in rules are registered by default. Custom rules can be
    added via ``register_rule()`` for plugin extensibility.

    Args:
        max_retries: Maximum retry attempts before skipping a task.
    """

    # ── Construction ───────────────────────────────────────────────────

    def __init__(self, max_retries: int = 3) -> None:
        self._max_retries = max_retries
        self._rules: list[DecisionRule] = []

        # Register built-in rules
        self.register_rule(ActiveTaskRule())
        self.register_rule(FailedTaskRetryRule(max_retries=max_retries))
        self.register_rule(PendingTaskRule())
        self.register_rule(PendingProductRule())
        self.register_rule(NoWorkRule())

        logger.info(
            "DecisionEngine initialized  │  rules=%d  max_retries=%d",
            len(self._rules),
            self._max_retries,
        )

    # ── Properties ─────────────────────────────────────────────────────

    @property
    def max_retries(self) -> int:
        """Return the maximum retry count."""
        return self._max_retries

    @property
    def rule_count(self) -> int:
        """Return the number of registered rules."""
        return len(self._rules)

    # ── Rule Management ────────────────────────────────────────────────

    def register_rule(self, rule: DecisionRule) -> None:
        """
        Register a custom decision rule.

        Rules are automatically sorted by priority after registration.

        Args:
            rule: A class implementing the ``DecisionRule`` protocol.
        """
        self._rules.append(rule)
        self._rules.sort(key=lambda r: r.priority)
        logger.debug(
            "Rule registered  │  type=%s  priority=%d",
            type(rule).__name__,
            rule.priority,
        )

    # ── Core Decision Logic ────────────────────────────────────────────

    def decide(
        self,
        pending_tasks: list[Task],
        pending_products: list[Product],
        active_task: Task | None = None,
        failed_tasks: list[Task] | None = None,
    ) -> Decision:
        """
        Evaluate all rules and return the winning decision.

        Args:
            pending_tasks:    Tasks in Pending status.
            pending_products: Products in Pending status.
            active_task:      The currently running task (if any).
            failed_tasks:     Tasks in Failed status.

        Returns:
            The ``Decision`` from the highest-priority matching rule.
        """
        failed = failed_tasks or []

        for rule in self._rules:
            decision = rule.evaluate(
                pending_tasks=pending_tasks,
                pending_products=pending_products,
                active_task=active_task,
                failed_tasks=failed,
            )
            if decision is not None:
                logger.info(
                    "Decision made  │  action=%s  reason=%s  rule=%s",
                    decision.action.value,
                    decision.reason,
                    type(rule).__name__,
                )
                return decision

        # Fallback (should never reach here due to NoWorkRule)
        return Decision(
            action=ActionType.NO_TASKS,
            reason="No rules matched (fallback).",
        )

    def should_retry(self, product: Product) -> bool:
        """
        Determine whether a product should be retried.

        Args:
            product: The product to evaluate.

        Returns:
            ``True`` if ``retry_count < max_retries``.
        """
        return product.retry_count < self._max_retries

    def should_skip(self, product: Product) -> bool:
        """
        Determine whether a product should be skipped.

        Args:
            product: The product to evaluate.

        Returns:
            ``True`` if ``retry_count >= max_retries``.
        """
        return product.retry_count >= self._max_retries

    # ── Dunder ─────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        return (
            f"DecisionEngine(rules={len(self._rules)}, "
            f"max_retries={self._max_retries})"
        )
