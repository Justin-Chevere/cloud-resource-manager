import enum
from typing import Protocol


class ObservedState(enum.StrEnum):
    RUNNING = "running"
    STOPPED = "stopped"
    MISSING = "missing"


class ContainerRuntime(Protocol):
    """What the reconciler needs from whatever actually runs containers.

    Every method must be safe to call repeatedly: starting a running container
    or removing a missing one is a no-op, not an error.
    """

    def status(self, name: str) -> ObservedState: ...

    def start(self, name: str, image: str) -> None:
        """Create the container if needed, then make sure it is running."""

    def stop(self, name: str) -> None: ...

    def remove(self, name: str) -> None: ...
