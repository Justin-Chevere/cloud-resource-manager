# cloud-control-plane

A small control plane that manages container resources through a declarative API, modeled on
how Kubernetes works: the API records *desired state*, and a reconciler loop makes reality match it.

## Status

- [x] REST API for resources (create, list, get, update desired state, delete)
- [x] Desired vs. actual state in the data model
- [x] Tests with an isolated in-memory database
- [x] Reconciler loop that converges actual state to desired state (in-memory runtime)
- [ ] Docker runtime for the reconciler
- [ ] Auth (JWT) and roles
- [ ] Metrics collection
- [ ] Docker/Terraform deploy and CI

## How it works

The API never starts or stops anything. `POST`, `PATCH` and `DELETE` only change a resource's
`desired_state`. A background reconciler wakes every few seconds, asks the runtime what is
actually running, and fixes any difference, then records the result in `actual_state`.

- **Level-triggered:** each pass recomputes from scratch, so crashed containers are restarted
  and a restart of the control plane loses nothing.
- **Idempotent:** a pass over an already-correct resource changes nothing.
- **Isolated failures:** a resource that fails is marked `error` and retried next pass; the rest
  are unaffected.
- **Clean ownership:** the API writes only `desired_state`, the reconciler only `actual_state`,
  so neither can overwrite the other's updates.

## Run it

Requires Python 3.11+.

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -e ".[dev]"

uvicorn app.main:app --reload
```

Interactive API docs are at http://127.0.0.1:8000/docs.

## Test

```bash
pytest
ruff check .
```

## Layout

| Path | Responsibility |
|------|----------------|
| `app/config.py` | Settings from environment variables |
| `app/db.py` | Engine, session factory, per-request session dependency |
| `app/models.py` | Database tables |
| `app/schemas.py` | Request and response shapes, validation |
| `app/routers/` | HTTP endpoints |
| `app/reconciler.py` | Loop that makes actual state match desired state |
| `app/runtime/` | `ContainerRuntime` interface and an in-memory fake (Docker comes next) |
| `app/main.py` | Application factory |
| `tests/` | API tests against an in-memory database |
