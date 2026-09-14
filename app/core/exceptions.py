"""Application-level exception hierarchy.

UI code should catch these and show a friendly message; never surface
raw database or stack-trace details to end users.
"""


class HOSException(Exception):
    """Base exception for all application errors."""
    def __init__(self, message: str = "An error occurred. Please try again."):
        self.message = message
        super().__init__(message)


class NotFoundError(HOSException):
    pass


class ValidationError(HOSException):
    pass


class AuthenticationError(HOSException):
    pass


class AuthorizationError(HOSException):
    pass


class ConflictError(HOSException):
    """Raised for uniqueness/duplicate/concurrency conflicts."""
    pass


class BusinessRuleError(HOSException):
    """Raised when a hard constraint or business rule is violated."""
    pass


class OptimizationError(HOSException):
    pass


class DatabaseConnectionError(HOSException):
    pass
