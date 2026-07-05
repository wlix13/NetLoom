"""Fault-injection component errors."""

from netloom.core.errors import FaultError


class UnknownFaultType(FaultError):
    def __init__(self, type_id: str, available: list[str]) -> None:
        super().__init__(f"Unknown fault type '{type_id}'. Available: {', '.join(available)}")


class FaultNotApplicable(FaultError):
    def __init__(self, type_id: str, detail: str) -> None:
        super().__init__(f"Fault '{type_id}' is not applicable: {detail}")


class FaultSpecInvalid(FaultError):
    def __init__(self, path: str, detail: str) -> None:
        super().__init__(f"Invalid faults spec '{path}': {detail}")


class NotEnoughFaultCandidates(FaultError):
    def __init__(self, requested: int, available: int) -> None:
        super().__init__(
            f"Requested {requested} random fault(s) but only {available} applicable candidate(s) "
            f"exist for this topology."
        )


class NoFaultsApplied(FaultError):
    def __init__(self, path: str) -> None:
        super().__init__(f"No answer key found at '{path}'. Deploy with --faults first.")
