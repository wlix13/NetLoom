"""Infrastructure component errors."""

from netloom.core.errors import InfrastructureError


class VMNotCreated(InfrastructureError):
    def __init__(self, name: str) -> None:
        super().__init__(f"VM '{name}' is not created. Run 'netloom up' or 'netloom steps create' first.")


class VMNotRunning(InfrastructureError):
    def __init__(self, name: str, state: str) -> None:
        super().__init__(f"VM '{name}' is {state}. Start it with 'netloom steps start'.")


class NoConsoleConnection(InfrastructureError):
    def __init__(self, name: str) -> None:
        super().__init__(f"No console connection available for VM '{name}'.")
