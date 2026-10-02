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
- [x] Login rate limiting and password reset with one-time tokens
- [x] Metrics: CPU and memory per resource, sampled every 15 seconds and kept for 24 hours
- [x] CI: lint and tests on Python 3.11 and 3.14

## Next steps

1. **Docker runtime:** implement `ContainerRuntime` on the Docker Engine, so the reconciler
   starts, stops and removes real containers instead of in-memory stand-ins.

After that: deploy with Docker and Terraform.

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

## Metrics

A collector reads the CPU and memory use of every running resource every 15 seconds and keeps 24
hours of readings, ready for a dashboard:

- `GET /metrics/latest`: the newest reading of each resource, for an overview screen.
- `GET /resources/{id}/metrics?minutes=60`: one resource's readings, oldest first, for a chart
  (up to 24 hours back).

How it's built:

- **Its own loop:** collection runs apart from the reconciler, so slow or failing metrics can
  never delay the work of keeping resources in their desired state.
- **Bounded storage:** each pass deletes readings older than the retention window, and an index
  on (resource, time) keeps chart queries fast as the table grows.
- **Failures stay contained:** a container whose stats can't be read is logged and skipped; every
  other resource still gets its reading.
- **Unambiguous time:** timestamps are stored and sent as UTC with a `Z`, so a browser can't
  mistake them for local time and shift a chart.
- **CPU** is a percentage of one core, as in `docker stats`. Until the Docker runtime lands, the
  in-memory runtime simulates believable load that repeats the same way on every run.

At larger scale, the same readings would go to a time-series database such as Prometheus instead
of the application database.

## Auth and roles

Every endpoint requires a bearer token except `/health`, logging in, and completing a password
reset.

| Role | Can |
|------|-----|
| `viewer` | List and read resources and their metrics |
| `operator` | Everything a viewer can, plus create, start, stop and delete resources |
| `admin` | Everything an operator can, plus manage users and read the audit log |

- **Login:** `POST /auth/token` (OAuth2 password flow) returns a signed JWT that expires after
  30 minutes. Wrong passwords and unknown usernames get the same answer in the same time, so
  the endpoint never reveals which accounts exist.
- **Passwords** are hashed with Argon2id and never returned by the API.
- **Tokens carry only the user id and a version number.** The user and role are loaded on every
  request, so deactivating someone or changing their role applies at once, even to tokens
  already issued. A password reset bumps the version, which ends every older session.
- **Login rate limiting:** after 5 failed logins for one account, or 20 from one client address,
  within 15 minutes, further attempts get `429` with a `Retry-After` header and the password
  isn't even checked. Unknown usernames are limited the same way, so a `429` reveals nothing
  about which accounts exist. The counters live in process memory, which matches the
  single-process design; running several instances would mean sharing them through Redis.
- **Password reset:** an admin issues a one-time token (`POST /users/{id}/password-reset`) and
  hands it to the user, who sets a new password with it (`POST /auth/password-reset`). Tokens
  expire after 30 minutes, work once, and are stored only as a SHA-256 hash, and the admin never
  learns the new password. A reset also lifts any login pause on the account.
- **Lost the only admin password?** Create another admin from the command line
  (`python -m app.cli create-user rescue --role admin`), then issue a reset.
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

Behind a reverse proxy, start uvicorn with `--proxy-headers` (and `--forwarded-allow-ips` set to
the proxy's address) so login rate limits see each real client, not the proxy.

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
| `app/routers/` | HTTP endpoints: health, auth, resources, metrics, users, audit |
| `app/security.py` | Password hashing and token signing |
| `app/auth.py` | Login check, current-user and role dependencies |
| `app/throttle.py` | Sliding-window failure counters behind login rate limiting |
| `app/audit.py` | Records audit events inside the caller's transaction |
| `app/reconciler.py` | Loop that makes actual state match desired state |
| `app/metrics.py` | Loop that samples CPU and memory and enforces retention |
| `app/runtime/` | `ContainerRuntime` interface and an in-memory fake that simulates load (Docker comes next) |
| `app/cli.py` | Command line: create users, including the first admin |
| `app/main.py` | Application factory |
| `tests/` | Tests against an isolated in-memory database |
