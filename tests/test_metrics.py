import asyncio
import time
from contextlib import suppress
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app import metrics
from app.metrics import collect_once, run_collector
from app.models import DesiredState, MetricSample, Resource
from app.reconciler import reconcile_once
from app.runtime import FakeRuntime

RETENTION = timedelta(hours=24)
MiB = 1024 * 1024


def _add(db, name, desired=DesiredState.RUNNING):
    resource = Resource(name=name, image="nginx", desired_state=desired)
    db.add(resource)
    db.commit()
    return resource.id


def _samples(db):
    return db.scalars(select(MetricSample).order_by(MetricSample.id)).all()


def _store(session_factory, resource_id, minutes_ago, cpu, memory_mib):
    with session_factory() as db:
        db.add(
            MetricSample(
                resource_id=resource_id,
                collected_at=datetime.now(UTC) - timedelta(minutes=minutes_ago),
                cpu_percent=cpu,
                memory_bytes=memory_mib * MiB,
            )
        )
        db.commit()


# The fake runtime's readings


def test_fake_runtime_reports_stats_only_for_running_containers():
    runtime = FakeRuntime()
    assert runtime.stats("web-1") is None

    runtime.start("web-1", "nginx")
    assert runtime.stats("web-1") is not None

    runtime.stop("web-1")
    assert runtime.stats("web-1") is None


def test_fake_readings_are_believable_and_repeatable():
    first, second = FakeRuntime(), FakeRuntime()
    first.start("web-1", "nginx")
    second.start("web-1", "nginx")

    readings = [first.stats("web-1") for _ in range(200)]

    assert readings == [second.stats("web-1") for _ in range(200)]
    assert all(0 < r.cpu_percent <= 100 for r in readings)
    assert all(r.memory_bytes >= 32 * MiB for r in readings)
    assert len({r.cpu_percent for r in readings}) > 1  # it moves, like real load


# Collecting


def test_collects_running_resources_only(session_factory, runtime):
    with session_factory() as db:
        running = _add(db, "web-1")
        _add(db, "web-2", desired=DesiredState.STOPPED)
        reconcile_once(db, runtime)

        assert collect_once(db, runtime, RETENTION) == 1
        assert [s.resource_id for s in _samples(db)] == [running]


def test_readings_from_one_pass_share_a_timestamp(session_factory, runtime):
    with session_factory() as db:
        _add(db, "web-1")
        _add(db, "web-2")
        reconcile_once(db, runtime)

        collect_once(db, runtime, RETENTION)

        assert len({s.collected_at for s in _samples(db)}) == 1


def test_readings_older_than_retention_are_dropped(session_factory, runtime):
    first_pass = datetime(2026, 1, 1, tzinfo=UTC)
    later_pass = first_pass + RETENTION + timedelta(minutes=1)
    with session_factory() as db:
        _add(db, "web-1")
        reconcile_once(db, runtime)

        collect_once(db, runtime, RETENTION, now=first_pass)
        collect_once(db, runtime, RETENTION, now=later_pass)

        assert [s.collected_at for s in _samples(db)] == [later_pass]


def test_one_unreadable_container_does_not_cost_the_others_their_reading(
    session_factory, runtime
):
    with session_factory() as db:
        _add(db, "bad")
        good = _add(db, "good")
        reconcile_once(db, runtime)
        runtime.fail_on = {"bad"}

        assert collect_once(db, runtime, RETENTION) == 1
        assert [s.resource_id for s in _samples(db)] == [good]


def test_collector_loop_survives_a_failed_pass_and_stops_on_cancel(monkeypatch, runtime):
    passes = []

    def flaky_tick(*args):
        passes.append(args)
        if len(passes) == 1:
            raise RuntimeError("database briefly unavailable")

    monkeypatch.setattr(metrics, "tick", flaky_tick)

    async def scenario():
        task = asyncio.create_task(run_collector(runtime, 0.01, RETENTION))
        deadline = time.monotonic() + 3
        while len(passes) < 3 and time.monotonic() < deadline:
            await asyncio.sleep(0.01)
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
        return task

    assert asyncio.run(scenario()).cancelled()
    assert len(passes) >= 3


# Serving


@pytest.fixture
def web(operator_client):
    return operator_client.post("/resources", json={"name": "web-1", "image": "nginx"}).json()["id"]


def test_history_returns_the_window_oldest_first(viewer_client, web, session_factory):
    _store(session_factory, web, minutes_ago=90, cpu=50.0, memory_mib=300)
    _store(session_factory, web, minutes_ago=10, cpu=20.0, memory_mib=200)
    _store(session_factory, web, minutes_ago=30, cpu=30.0, memory_mib=250)

    points = viewer_client.get(f"/resources/{web}/metrics", params={"minutes": 60}).json()

    assert [p["cpu_percent"] for p in points] == [30.0, 20.0]
    assert [p["memory_bytes"] for p in points] == [250 * MiB, 200 * MiB]


def test_history_window_is_bounded(viewer_client, web):
    path = f"/resources/{web}/metrics"
    assert viewer_client.get(path, params={"minutes": 0}).status_code == 422
    assert viewer_client.get(path, params={"minutes": 24 * 60 + 1}).status_code == 422


def test_history_for_unknown_resource_is_404(viewer_client):
    assert viewer_client.get("/resources/nope/metrics").status_code == 404


def test_latest_is_the_newest_reading_of_each_resource(
    viewer_client, operator_client, session_factory
):
    def create(name):
        return operator_client.post("/resources", json={"name": name, "image": "x"}).json()["id"]

    web, api = create("web-1"), create("api-1")
    create("idle-1")  # never sampled, so not listed
    _store(session_factory, web, minutes_ago=5, cpu=10.0, memory_mib=100)
    _store(session_factory, web, minutes_ago=1, cpu=15.0, memory_mib=110)
    _store(session_factory, api, minutes_ago=2, cpu=70.0, memory_mib=400)

    latest = viewer_client.get("/metrics/latest").json()

    assert [(m["name"], m["cpu_percent"]) for m in latest] == [("api-1", 70.0), ("web-1", 15.0)]


def test_timestamps_are_sent_as_utc(viewer_client, web, session_factory):
    _store(session_factory, web, minutes_ago=1, cpu=10.0, memory_mib=100)

    point = viewer_client.get(f"/resources/{web}/metrics").json()[0]

    # The "Z" marks UTC. Without it, a browser would read the time as local time.
    assert point["collected_at"].endswith("Z")


def test_from_reconciler_to_chart(operator_client, session_factory, runtime):
    web = operator_client.post("/resources", json={"name": "web-1", "image": "nginx"}).json()["id"]
    now = datetime.now(UTC)
    with session_factory() as db:
        reconcile_once(db, runtime)
        for seconds_ago in (30, 15, 0):
            collect_once(db, runtime, RETENTION, now=now - timedelta(seconds=seconds_ago))

    assert len(operator_client.get(f"/resources/{web}/metrics").json()) == 3
    latest = operator_client.get("/metrics/latest").json()
    assert [m["name"] for m in latest] == ["web-1"]
