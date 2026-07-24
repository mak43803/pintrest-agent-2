"""
Planner — Top-level AI planner orchestrating tasks and workflows.
==================================================================

The ``Planner`` is the brain of the agent's execution pipeline.
It composes the ``StateMachine``, ``TaskManager``, ``DecisionEngine``,
and ``Workflow`` system into a single, clean async API.

Responsibilities:
    • Read the current system state (pending tasks, products, errors)
    • Use the DecisionEngine to choose the next action
    • Execute workflows step-by-step with checkpoint/resume
    • Handle failures with retry logic
    • Maintain the planner's state machine
    • Persist every transition to SQLite

Public API:

    plan()       → Decision    Analyse state and decide the next action.
    execute()    → None        Execute the full planning + execution loop.
    resume()     → None        Resume an interrupted workflow.
    retry()      → None        Retry the last failed task/step.
    stop()       → None        Gracefully stop the planner.
    next_step()  → str | None  Advance to the next workflow step.

Architecture::

    ┌──────────────────────────────────────────────────────┐
    │                     Planner                           │
    │  plan(), execute(), resume(), retry(), stop()         │
    ├──────────┬──────────┬──────────────┬─────────────────┤
    │  State   │  Task    │  Decision    │   Workflow      │
    │  Machine │  Manager │  Engine      │   System        │
    ├──────────┴──────────┴──────────────┴─────────────────┤
    │               Database (SQLite)                       │
    └──────────────────────────────────────────────────────┘
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any, Callable

from database.database import Database
from database.models import Product, Status
from database.repository import Repository
from planner.decision_engine import ActionType, Decision, DecisionEngine
from planner.state_machine import PlannerState, StateMachine
from planner.task_manager import TaskManager
from planner.workflow import Workflow, WorkflowStep, create_pin_product_workflow

logger = logging.getLogger("pinterest_agent.planner")


# Type alias for step handler functions
StepHandler = Callable[[WorkflowStep, dict[str, Any]], Any]


class Planner:
    """
    Top-level AI planner that orchestrates the full execution pipeline.

    Composes:
        - ``StateMachine``    — tracks planner lifecycle
        - ``TaskManager``     — persists task state to SQLite
        - ``DecisionEngine``  — chooses the next action
        - ``Workflow``        — manages ordered step sequences

    All subsystems are injected via constructor (Dependency Injection).

    Args:
        db:           An initialized ``Database`` instance.
        repository:   An initialized ``Repository`` instance.
        max_retries:  Maximum retries per task/step before skipping.
    """

    # ── Construction ───────────────────────────────────────────────────

    def __init__(
        self,
        db: Database,
        repository: Repository,
        max_retries: int = 3,
    ) -> None:
        self._db = db
        self._repo = repository
        self._max_retries = max_retries

        # ── Compose subsystems ─────────────────────────────────────────
        self._state_machine = StateMachine(initial_state=PlannerState.IDLE)
        self._task_manager = TaskManager(db=db)
        self._decision_engine = DecisionEngine(max_retries=max_retries)

        # ── Internal state ─────────────────────────────────────────────
        self._current_workflow: Workflow | None = None
        self._current_task_id: int | None = None
        self._stop_requested = False
        self._lock = threading.Lock()
        self._step_handlers: dict[str, StepHandler] = {}

        logger.info(
            "Planner initialized  │  max_retries=%d  state=%s",
            self._max_retries,
            self._state_machine.state.value,
        )

    # ── Properties ─────────────────────────────────────────────────────

    @property
    def state(self) -> PlannerState:
        """Return the current planner state."""
        return self._state_machine.state

    @property
    def state_machine(self) -> StateMachine:
        """Return the state machine (for advanced usage / callbacks)."""
        return self._state_machine

    @property
    def task_manager(self) -> TaskManager:
        """Return the task manager."""
        return self._task_manager

    @property
    def decision_engine(self) -> DecisionEngine:
        """Return the decision engine."""
        return self._decision_engine

    @property
    def current_workflow(self) -> Workflow | None:
        """Return the active workflow, or ``None``."""
        return self._current_workflow

    @property
    def is_running(self) -> bool:
        """Return ``True`` if the planner is actively working."""
        return self._state_machine.is_active

    # ═══════════════════════════════════════════════════════════════════
    #  STEP HANDLER REGISTRATION
    # ═══════════════════════════════════════════════════════════════════

    def register_handler(self, handler_key: str, handler: StepHandler) -> None:
        """
        Register a handler function for a workflow step type.

        Args:
            handler_key: The ``handler`` string from a ``WorkflowStep``
                         (e.g. ``"browser.download_image"``).
            handler:     An async or sync callable
                         ``(step, context) -> result``.
        """
        self._step_handlers[handler_key] = handler
        logger.debug("Step handler registered  │  key=%s", handler_key)

    # ═══════════════════════════════════════════════════════════════════
    #  PLAN — Analyse state and decide next action
    # ═══════════════════════════════════════════════════════════════════

    def plan(self) -> Decision:
        """
        Analyse the current system state and decide the next action.

        Reads pending tasks, products, and failures from the database,
        then feeds them into the ``DecisionEngine``.

        Returns:
            A ``Decision`` describing what the planner should do next.
        """
        logger.info("Planning phase started...")

        # Gather state from database
        pending_tasks = self._task_manager.get_pending_tasks()
        active_task = self._task_manager.get_active_task()
        failed_tasks = self._task_manager.get_failed_tasks()

        # Get pending products from repository
        pending_products = self._get_pending_products()

        # Ask the decision engine
        decision = self._decision_engine.decide(
            pending_tasks=pending_tasks,
            pending_products=pending_products,
            active_task=active_task,
            failed_tasks=failed_tasks,
        )

        logger.info(
            "Plan result  │  action=%s  reason=%s",
            decision.action.value,
            decision.reason,
        )
        return decision

    # ═══════════════════════════════════════════════════════════════════
    #  EXECUTE — Run the full planning + execution loop
    # ═══════════════════════════════════════════════════════════════════

    async def execute(self) -> None:
        """
        Execute the full planning and execution loop.

        The loop:
            1. Transition to PLANNING
            2. Get next decision
            3. If EXECUTE_TASK → create task, build workflow, execute steps
            4. If RETRY_TASK → retry the failed task
            5. If NO_TASKS / STOP → exit loop
            6. Repeat until stop is requested or no work remains

        This is the main entry point for autonomous operation.
        """
        self._stop_requested = False

        logger.info("Planner execution loop started.")

        while not self._stop_requested:
            try:
                # ── PLAN ───────────────────────────────────────────────
                self._state_machine.transition_to(
                    PlannerState.PLANNING, reason="Starting planning phase"
                )
                decision = self.plan()

                # ── DISPATCH ───────────────────────────────────────────
                if decision.action == ActionType.EXECUTE_TASK:
                    await self._execute_task(decision)

                elif decision.action == ActionType.RETRY_TASK:
                    await self._handle_retry(decision)

                elif decision.action == ActionType.SKIP_TASK:
                    self._handle_skip(decision)

                elif decision.action == ActionType.WAIT:
                    self._state_machine.transition_to(
                        PlannerState.EXECUTING,
                        reason="Transitioning to wait state",
                    )
                    self._state_machine.transition_to(
                        PlannerState.WAITING,
                        reason=decision.reason,
                    )
                    # Wait briefly then re-plan
                    await asyncio.sleep(2.0)
                    self._state_machine.transition_to(
                        PlannerState.EXECUTING,
                        reason="Resuming from wait",
                    )
                    self._state_machine.transition_to(
                        PlannerState.COMPLETED,
                        reason="Wait cycle complete",
                    )
                    self._state_machine.transition_to(
                        PlannerState.IDLE,
                        reason="Returning to idle",
                    )

                elif decision.action in {ActionType.NO_TASKS, ActionType.STOP}:
                    logger.info("No more work  │  reason=%s", decision.reason)
                    # Return to IDLE safely
                    if self._state_machine.can_transition_to(PlannerState.FAILED):
                        self._state_machine.transition_to(
                            PlannerState.FAILED,
                            reason="No tasks (graceful exit)",
                        )
                        self._state_machine.transition_to(
                            PlannerState.IDLE,
                            reason="Returning to idle",
                        )
                    break

            except Exception as exc:
                logger.error("Planner loop error  │  error=%s", exc, exc_info=True)
                self._handle_error(str(exc))
                break

        logger.info("Planner execution loop ended  │  state=%s", self.state.value)

    # ═══════════════════════════════════════════════════════════════════
    #  RESUME — Resume an interrupted workflow
    # ═══════════════════════════════════════════════════════════════════

    async def resume(self) -> None:
        """
        Resume an interrupted workflow.

        Checks for a running task in the database, rebuilds the
        workflow, and resumes from the last checkpointed step.
        """
        logger.info("Attempting to resume interrupted workflow...")

        active_task = self._task_manager.get_active_task()
        if active_task is None:
            logger.info("No interrupted task found. Nothing to resume.")
            return

        logger.info(
            "Resuming task  │  id=%d  name=%s  step=%s",
            active_task.id,
            active_task.task_name,
            active_task.current_step,
        )

        # Rebuild workflow
        workflow = create_pin_product_workflow()

        # Resume from checkpointed step
        if active_task.current_step:
            try:
                workflow.resume_from(active_task.current_step)
            except ValueError:
                logger.warning(
                    "Checkpoint step '%s' not found. Starting from beginning.",
                    active_task.current_step,
                )

        self._current_workflow = workflow
        self._current_task_id = active_task.id

        # Execute remaining steps
        self._state_machine.transition_to(
            PlannerState.PLANNING, reason="Resuming interrupted task"
        )
        self._state_machine.transition_to(
            PlannerState.EXECUTING, reason="Executing resumed workflow"
        )

        await self._run_workflow(workflow, active_task.id)

    # ═══════════════════════════════════════════════════════════════════
    #  RETRY — Retry the last failed task
    # ═══════════════════════════════════════════════════════════════════

    async def retry(self) -> None:
        """
        Retry all failed tasks.

        Re-queues each failed task by resetting its status to Pending.
        The next ``execute()`` call will pick them up.
        """
        failed_tasks = self._task_manager.get_failed_tasks()

        if not failed_tasks:
            logger.info("No failed tasks to retry.")
            return

        for task in failed_tasks:
            self._task_manager.retry_task(task.id)
            logger.info("Task re-queued for retry  │  id=%d  name=%s", task.id, task.task_name)

        logger.info("Retried %d failed task(s).", len(failed_tasks))

    # ═══════════════════════════════════════════════════════════════════
    #  STOP — Gracefully stop the planner
    # ═══════════════════════════════════════════════════════════════════

    def stop(self) -> None:
        """
        Request the planner to stop after the current step completes.

        This is a cooperative stop — the planner finishes its current
        step before halting. Thread-safe.
        """
        with self._lock:
            self._stop_requested = True
        logger.info("Stop requested  │  will halt after current step.")

    # ═══════════════════════════════════════════════════════════════════
    #  NEXT_STEP — Advance to the next workflow step
    # ═══════════════════════════════════════════════════════════════════

    def next_step(self) -> str | None:
        """
        Return the name of the next step in the current workflow.

        Returns:
            The step name, or ``None`` if the workflow is done or absent.
        """
        if self._current_workflow is None:
            return None

        step = self._current_workflow.current_step
        return step.name if step else None

    # ═══════════════════════════════════════════════════════════════════
    #  INTERNAL — Task Execution
    # ═══════════════════════════════════════════════════════════════════

    async def _execute_task(self, decision: Decision) -> None:
        """Create a task, build a workflow, and execute it."""
        # Create task in database
        task_name = "pin_product"
        if decision.product:
            task_name = f"pin_product:{decision.product.product_name}"
        elif decision.task:
            task_name = decision.task.task_name

        # Use existing task or create a new one
        if decision.task and decision.task.id:
            task_id = decision.task.id
            self._task_manager.start_task(task_id)
        else:
            task_id = self._task_manager.create_task(task_name)
            self._task_manager.start_task(task_id)

        self._current_task_id = task_id

        # Build workflow
        workflow = create_pin_product_workflow()
        self._current_workflow = workflow

        # Transition to EXECUTING
        self._state_machine.transition_to(
            PlannerState.EXECUTING,
            reason=f"Executing task '{task_name}'",
        )

        # Update product status to Running
        if decision.product and decision.product.id:
            self._repo.update_status(decision.product.id, Status.RUNNING.value)

        # Run workflow
        await self._run_workflow(workflow, task_id, decision.product)

    async def _run_workflow(
        self,
        workflow: Workflow,
        task_id: int,
        product: Product | None = None,
    ) -> None:
        """
        Execute all pending steps in a workflow sequentially.

        Each step is checkpointed to the database before execution.
        On failure, the step is retried or the task is marked as failed.
        """
        context: dict[str, Any] = {}
        if product:
            context["product_id"] = product.id
            context["product_name"] = product.product_name
            context["category"] = product.category
            context["board_name"] = product.board_name

        for step in workflow.pending_steps():
            # Check for stop request
            if self._stop_requested:
                logger.info("Stop requested — halting workflow.")
                self._task_manager.pause_task(task_id)
                self._state_machine.transition_to(
                    PlannerState.COMPLETED,
                    reason="Stop requested",
                )
                self._state_machine.transition_to(
                    PlannerState.IDLE,
                    reason="Returning to idle after stop",
                )
                return

            # Checkpoint current step
            self._task_manager.update_step(task_id, step.name)

            # Start step
            workflow.start_step(step.name)

            try:
                # Execute handler if registered
                handler = self._step_handlers.get(step.handler)
                if handler is not None:
                    result = handler(step, context)
                    # Handle async handlers
                    if asyncio.iscoroutine(result):
                        result = await result
                    workflow.complete_step(step.name, result=result)
                else:
                    # No handler registered — mark as completed (placeholder)
                    logger.warning(
                        "No handler for step '%s' (handler=%s). Skipping.",
                        step.name,
                        step.handler,
                    )
                    workflow.complete_step(step.name, result="no_handler")

                # Log to database
                self._repo.save_log(
                    level="INFO",
                    message=f"Step '{step.name}' completed in workflow '{workflow.name}'.",
                    module="planner",
                )

            except Exception as exc:
                error_msg = str(exc)
                workflow.fail_step(step.name, error_msg)

                # Retry logic
                if step.is_retryable:
                    logger.warning(
                        "Step '%s' failed, retrying  │  attempt=%d/%d  error=%s",
                        step.name,
                        step.retries,
                        step.max_retries,
                        error_msg[:80],
                    )
                    self._state_machine.transition_to(
                        PlannerState.RETRYING,
                        reason=f"Retrying step '{step.name}'",
                    )
                    workflow.retry_step(step.name)
                    self._state_machine.transition_to(
                        PlannerState.EXECUTING,
                        reason=f"Re-executing step '{step.name}'",
                    )
                    # The step will be picked up on the next iteration
                    # of pending_steps() since we reset it to PENDING
                    continue
                else:
                    # Max retries exceeded — fail the task
                    self._task_manager.fail_task(task_id, error_msg)
                    if product and product.id:
                        self._repo.update_status(product.id, Status.FAILED.value)
                        self._repo.increase_retry(product.id)

                    self._state_machine.transition_to(
                        PlannerState.FAILED,
                        reason=f"Step '{step.name}' permanently failed: {error_msg[:50]}",
                    )
                    self._state_machine.transition_to(
                        PlannerState.IDLE,
                        reason="Returning to idle after failure",
                    )

                    self._repo.save_log(
                        level="ERROR",
                        message=f"Task {task_id} failed at step '{step.name}': {error_msg}",
                        module="planner",
                    )
                    return

        # All steps completed successfully
        self._task_manager.complete_task(task_id)
        if product and product.id:
            self._repo.update_status(product.id, Status.COMPLETED.value)

        self._state_machine.transition_to(
            PlannerState.COMPLETED,
            reason=f"Workflow '{workflow.name}' completed successfully",
        )
        self._state_machine.transition_to(
            PlannerState.IDLE,
            reason="Returning to idle after completion",
        )

        logger.info(
            "Workflow completed  │  name=%s  task_id=%d  steps=%d",
            workflow.name,
            task_id,
            workflow.step_count,
        )

    async def _handle_retry(self, decision: Decision) -> None:
        """Handle a RETRY_TASK decision."""
        if decision.task and decision.task.id:
            self._task_manager.retry_task(decision.task.id)
            logger.info("Task re-queued for retry  │  id=%d", decision.task.id)

        # Transition through states
        self._state_machine.transition_to(
            PlannerState.EXECUTING,
            reason="Processing retry decision",
        )
        self._state_machine.transition_to(
            PlannerState.COMPLETED,
            reason="Retry re-queue complete",
        )
        self._state_machine.transition_to(
            PlannerState.IDLE,
            reason="Returning to idle",
        )

    def _handle_skip(self, decision: Decision) -> None:
        """Handle a SKIP_TASK decision."""
        if decision.task and decision.task.id:
            self._task_manager.cancel_task(decision.task.id)
        if decision.product and decision.product.id:
            self._repo.update_status(decision.product.id, Status.SKIPPED.value)

        logger.info("Task skipped  │  reason=%s", decision.reason)

    def _handle_error(self, error: str) -> None:
        """Handle an unexpected error during the planning loop."""
        if self._current_task_id:
            self._task_manager.fail_task(self._current_task_id, error)

        # Force state machine back to IDLE
        try:
            if self._state_machine.can_transition_to(PlannerState.FAILED):
                self._state_machine.transition_to(
                    PlannerState.FAILED, reason=f"Error: {error[:80]}"
                )
            if self._state_machine.can_transition_to(PlannerState.IDLE):
                self._state_machine.transition_to(
                    PlannerState.IDLE, reason="Recovery from error"
                )
        except Exception:
            self._state_machine.reset()

        self._repo.save_log(
            level="ERROR",
            message=f"Planner error: {error}",
            module="planner",
        )

    # ── Internal Helpers ───────────────────────────────────────────────

    def _get_pending_products(self) -> list[Product]:
        """Fetch all pending products from the database."""
        sql = "SELECT * FROM products WHERE status = ? ORDER BY id ASC"
        rows = self._db.fetchall(sql, (Status.PENDING.value,))
        return [Product.from_row(r) for r in rows]

    # ── Dunder ─────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        return (
            f"Planner(state={self.state.value!r}, "
            f"max_retries={self._max_retries}, "
            f"workflow={self._current_workflow})"
        )
