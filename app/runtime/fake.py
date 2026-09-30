from app.runtime.base import ObservedState


class FakeRuntime:
    """In-memory stand-in for Docker, for local runs and tests.

    Records every mutating call in `calls` so tests can assert that the reconciler
    did nothing when nothing needed doing. Names in `fail_on` raise on start/stop/remove.
    """

    def __init__(self) -> None:
        self._containers: dict[str, ObservedState] = {}
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

    def crash(self, name: str) -> None:
        """Simulate a container dying on its own, outside the reconciler's control."""
        if name in self._containers:
            self._containers[name] = ObservedState.STOPPED

    def _record(self, action: str, name: str) -> None:
        if name in self.fail_on:
            raise RuntimeError(f"simulated runtime failure on {action} {name}")
        self.calls.append((action, name))
