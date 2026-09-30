# cloud-resource-manager

[![CI](https://github.com/Justin-Chevere/cloud-resource-manager/actions/workflows/ci.yml/badge.svg)](https://github.com/Justin-Chevere/cloud-resource-manager/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

A small control plane that manages container resources through a declarative API, modeled on
how Kubernetes works: the API records *desired state*, and a reconciler loop makes reality match it.

## Status

- [x] REST API for resources (create, list, get, update desired state, delete)
- [x] Desired vs. actual state in the data model
- [x] Tests with an isolated in-memory database
- [x] Reconciler loop that converges actual state to desired state (in-memory runtime)
- [x] Auth (JWT), role-based access control and an audit log
- [x] CI: lint and tests on Python 3.11 and 3.14
- [ ] Docker runtime for the reconciler
- [ ] Metrics collection
- [ ] Docker/Terraform deploy

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

## Auth and roles

Every endpoint except `/health` and the login endpoint requires a bearer token.

| Role | Can |
|------|-----|
| `viewer` | List and read resources |
| `operator` | Everything a viewer can, plus create, start, stop and delete resources |
| `admin` | Everything an operator can, plus manage users and read the audit log |

- **Login:** `POST /auth/token` (OAuth2 password flow) returns a signed JWT that expires after
  30 minutes. Wrong passwords and unknown usernames get the same answer in the same time, so
  the endpoint never reveals which accounts exist.
- **Passwords** are hashed with Argon2id and never returned by the API.
- **Tokens carry only the user id.** The user and role are loaded on every request, so
  deactivating someone or changing their role applies at once, even to tokens already issued.
- **Deny by default:** routers require a signed-in user, and a test walks every endpoint in the
  OpenAPI schema and fails if any non-public one answers an anonymous request.
- **Audit log:** each change records who made it, what changed and when, committed in the same
  transaction as the change itself. Admins read it at `GET /audit`.

## Run it

Requires Python 3.11+.

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -e ".[dev]"

python -m app.cli create-user admin --role admin    # prompts for a password
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000/docs, click **Authorize**, and sign in as that user.

Set `JWT_SECRET` (see `.env.example`) for anything beyond local development. Without it, a random
secret is generated at startup and every login resets when the server restarts.

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
| `app/routers/` | HTTP endpoints: health, auth, resources, users, audit |
| `app/security.py` | Password hashing and token signing |
| `app/auth.py` | Login check, current-user and role dependencies |
| `app/audit.py` | Records audit events inside the caller's transaction |
| `app/reconciler.py` | Loop that makes actual state match desired state |
| `app/runtime/` | `ContainerRuntime` interface and an in-memory fake (Docker comes next) |
| `app/cli.py` | Command line: create users, including the first admin |
| `app/main.py` | Application factory |
| `tests/` | Tests against an isolated in-memory database |
