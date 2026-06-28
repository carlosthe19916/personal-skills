class CliError(Exception):
    """CLI error with optional exit code."""

    def __init__(self, message: str, code: int = 1) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
