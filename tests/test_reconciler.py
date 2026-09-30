import asyncio
import time
from contextlib import suppress

from app.models import ActualState, DesiredState, Resource
from app.reconciler import reconcile_once, run_reconciler
from app.runtime import ObservedState


def _add(db, name="web-1", desired=DesiredState.RUNNING):
    resource = Resource(name=name, image="nginx:latest", desired_state=desired)
    db.add(resource)
    db.commit()
    return resource.id


def _actual(db, resource_id):
    db.expire_all()
    return db.get(Resource, resource_id).actual_state


def test_starts_a_resource_that_should_be_running(session_factory, runtime):
    with session_factory() as db:
        rid = _add(db)
        reconcile_once(db, runtime)

        assert runtime.status("web-1") == ObservedState.RUNNING
        assert _actual(db, rid) == ActualState.RUNNING


def test_resource_that_should_be_stopped_is_never_started(session_factory, runtime):
    with session_factory() as db:
        rid = _add(db, desired=DesiredState.STOPPED)
        reconcile_once(db, runtime)

        assert runtime.calls == []
        assert _actual(db, rid) == ActualState.STOPPED


def test_stops_a_running_resource_when_desired_changes(session_factory, runtime):
    with session_factory() as db:
        rid = _add(db)
        reconcile_once(db, runtime)

        db.get(Resource, rid).desired_state = DesiredState.STOPPED
        db.commit()
        reconcile_once(db, runtime)

        assert runtime.status("web-1") == ObservedState.STOPPED
        assert _actual(db, rid) == ActualState.STOPPED


def test_delete_removes_the_container_and_the_row(session_factory, runtime):
    with session_factory() as db:
        rid = _add(db)
        reconcile_once(db, runtime)

        db.get(Resource, rid).desired_state = DesiredState.DELETED
        db.commit()
        reconcile_once(db, runtime)

        assert runtime.status("web-1") == ObservedState.MISSING
        assert db.get(Resource, rid) is None


def test_second_pass_with_nothing_to_do_makes_no_calls(session_factory, runtime):
    with session_factory() as db:
        _add(db)
        reconcile_once(db, runtime)
        runtime.calls.clear()

        reconcile_once(db, runtime)

        assert runtime.calls == []


def test_heals_a_container_that_crashed(session_factory, runtime):
    with session_factory() as db:
        rid = _add(db)
        reconcile_once(db, runtime)

        runtime.crash("web-1")
        assert runtime.status("web-1") == ObservedState.STOPPED

        reconcile_once(db, runtime)

        assert runtime.status("web-1") == ObservedState.RUNNING
        assert _actual(db, rid) == ActualState.RUNNING


def test_one_failing_resource_does_not_block_the_others_and_recovers(session_factory, runtime):
    runtime.fail_on = {"bad"}
    with session_factory() as db:
        bad = _add(db, name="bad")
        good = _add(db, name="good")

        reconcile_once(db, runtime)

        assert _actual(db, bad) == ActualState.ERROR
        assert _actual(db, good) == ActualState.RUNNING

        runtime.fail_on.clear()
        reconcile_once(db, runtime)

        assert _actual(db, bad) == ActualState.RUNNING


def test_api_changes_converge_through_the_reconciler(operator_client, session_factory, runtime):
    api = operator_client
    created = api.post("/resources", json={"name": "web-1", "image": "nginx"}).json()
    assert created["actual_state"] == "pending"

    with session_factory() as db:
        reconcile_once(db, runtime)
    assert api.get(f"/resources/{created['id']}").json()["actual_state"] == "running"

    api.patch(f"/resources/{created['id']}", json={"desired_state": "stopped"})
    with session_factory() as db:
        reconcile_once(db, runtime)
    assert api.get(f"/resources/{created['id']}").json()["actual_state"] == "stopped"

    api.delete(f"/resources/{created['id']}")
    with session_factory() as db:
        reconcile_once(db, runtime)
    assert api.get(f"/resources/{created['id']}").status_code == 404


def test_background_loop_converges_and_stops_on_cancel(session_factory, runtime):
    with session_factory() as db:
        _add(db)

    async def scenario():
        task = asyncio.create_task(run_reconciler(runtime, 0.01, session_factory))
        deadline = time.monotonic() + 3
        while runtime.status("web-1") != ObservedState.RUNNING and time.monotonic() < deadline:
            await asyncio.sleep(0.01)
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
        assert task.cancelled()

    asyncio.run(scenario())

    assert runtime.status("web-1") == ObservedState.RUNNING
