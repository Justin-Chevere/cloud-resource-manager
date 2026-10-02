import random

from app.runtime.base import ContainerStats, ObservedState

MiB = 1024 * 1024


class FakeRuntime:
    """In-memory stand-in for Docker, for local runs and tests.

    Records every mutating call in `calls` so tests can assert that the reconciler
    did nothing when nothing needed doing. Names in `fail_on` raise on start, stop,
    remove and stats.
    """

    def __init__(self) -> None:
        self._containers: dict[str, ObservedState] = {}
        self._loads: dict[str, _SimulatedLoad] = {}
        self.calls: list[tuple[str, str]] = []
        self.fail_on: set[str] = set()

    def status(self, name: str) -> ObservedState:
        return self._containers.get(name, ObservedState.MISSING)

    def start(self, name: str, image: str) -> None:
        self._record("start", name)
        self._containers[name] = ObservedState.RUNNING

    def stop(self, name: str) -> None:
        self._record("stop", name)
        if name in self._containers:
            self._containers[name] = ObservedState.STOPPED

    def remove(self, name: str) -> None:
        self._record("remove", name)
        self._containers.pop(name, None)
        self._loads.pop(name, None)

    def stats(self, name: str) -> ContainerStats | None:
        if name in self.fail_on:
            raise RuntimeError(f"simulated runtime failure on stats {name}")
        if self._containers.get(name) != ObservedState.RUNNING:
            return None
        return self._loads.setdefault(name, _SimulatedLoad(name)).next()

    def crash(self, name: str) -> None:
        """Simulate a container dying on its own, outside the reconciler's control."""
        if name in self._containers:
            self._containers[name] = ObservedState.STOPPED

    def _record(self, action: str, name: str) -> None:
        if name in self.fail_on:
            raise RuntimeError(f"simulated runtime failure on {action} {name}")
        self.calls.append((action, name))


class _SimulatedLoad:
    """Believable usage for one fake container.

    Each reading drifts a little from the last, the way real load does. Seeded by
    the container's name, so a demo plays out the same way every time.
    """

    def __init__(self, name: str) -> None:
        self._rng = random.Random(name)
        self._cpu = self._rng.uniform(5, 40)
        self._memory = self._rng.randint(64, 512) * MiB

    def next(self) -> ContainerStats:
        self._cpu = min(100.0, max(0.5, self._cpu + self._rng.uniform(-6, 6)))
        self._memory = max(32 * MiB, self._memory + self._rng.randint(-8, 8) * MiB)
        return ContainerStats(cpu_percent=round(self._cpu, 1), memory_bytes=self._memory)
