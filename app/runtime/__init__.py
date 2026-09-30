from app.config import Settings
from app.runtime.base import ContainerRuntime, ObservedState
from app.runtime.fake import FakeRuntime

__all__ = ["ContainerRuntime", "FakeRuntime", "ObservedState", "build_runtime"]


def build_runtime(settings: Settings) -> ContainerRuntime:
    if settings.runtime == "fake":
        return FakeRuntime()
    raise ValueError(f"unknown runtime: {settings.runtime}")
