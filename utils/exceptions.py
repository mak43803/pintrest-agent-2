"""
Exceptions - Custom exception hierarchy for the application.

Defines domain-specific exceptions for cleaner error handling
and more informative error messages across all modules.
"""


class PinterestAgentError(Exception):
    """Base exception for all Pinterest AI Agent errors."""
    pass


# ── LLM Errors ─────────────────────────────────────────────────────────
class LLMConnectionError(PinterestAgentError):
    """Raised when the Ollama LLM server is unreachable."""
    pass


class LLMResponseParseError(PinterestAgentError):
    """Raised when the LLM response cannot be parsed into an action."""
    pass


class LLMTimeoutError(PinterestAgentError):
    """Raised when the LLM request exceeds the configured timeout."""
    pass


class LLMModelNotFoundError(PinterestAgentError):
    """Raised when the requested Ollama model is not available."""
    pass


# ── Browser Errors ─────────────────────────────────────────────────────
class BrowserLaunchError(PinterestAgentError):
    """Raised when the Playwright browser fails to launch."""
    pass


class BrowserNavigationError(PinterestAgentError):
    """Raised when a page navigation fails or times out."""
    pass


class ElementNotFoundError(PinterestAgentError):
    """Raised when a target DOM element cannot be found."""
    pass


# ── Database Errors ────────────────────────────────────────────────────
class DatabaseConnectionError(PinterestAgentError):
    """Raised when the SQLite database cannot be opened."""
    pass


class DatabaseQueryError(PinterestAgentError):
    """Raised when a database query fails."""
    pass


class DatabaseIntegrityError(PinterestAgentError):
    """Raised when a database constraint is violated (unique, FK, etc.)."""
    pass


class DatabaseMigrationError(PinterestAgentError):
    """Raised when a schema migration fails."""
    pass


# ── Agent Errors ───────────────────────────────────────────────────────
class TaskPlanningError(PinterestAgentError):
    """Raised when the planner fails to generate a valid plan."""
    pass


class TaskExecutionError(PinterestAgentError):
    """Raised when a planned action step fails during execution."""
    pass


class MaxStepsExceededError(PinterestAgentError):
    """Raised when the agent exceeds the maximum step count for a task."""
    pass


# ── Configuration Errors ───────────────────────────────────────────────
class ConfigurationError(PinterestAgentError):
    """Raised when a required configuration value is missing or invalid."""
    pass
