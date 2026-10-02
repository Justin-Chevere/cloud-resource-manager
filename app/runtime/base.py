import enum
from dataclasses import dataclass
from typing import Protocol


class ObservedState(enum.StrEnum):
    RUNNING = "running"
    STOPPED = "stopped"
    MISSING = "missing"


@dataclass(frozen=True)
class ContainerStats:
    # Percent of one CPU core, as in `docker stats`: 250 means two and a half cores busy.
    cpu_percent: float
    memory_bytes: int


class ContainerRuntime(Protocol):
    """What the reconciler and the metrics collector need from whatever runs containers.

    Every method must be safe to call repeatedly: starting a running container
    or removing a missing one is a no-op, not an error.
    """

    def status(self, name: str) -> ObservedState: ...

    def start(self, name: str, image: str) -> None:
        """Create the container if needed, then make sure it is running."""

    def stop(self, name: str) -> None: ...

    def remove(self, name: str) -> None: ...

    def stats(self, name: str) -> ContainerStats | None:
        """Current CPU and memory use, or None if the container isn't running."""
