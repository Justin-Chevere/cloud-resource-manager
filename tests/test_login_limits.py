import pytest

from app.throttle import LoginGuard

ACCOUNT_LIMIT = 3
CLIENT_LIMIT = 5
WINDOW_SECONDS = 60


@pytest.fixture
def login_guard(clock):
    # Overrides the shared fixture so this file states the limits it tests.
    return LoginGuard(ACCOUNT_LIMIT, CLIENT_LIMIT, WINDOW_SECONDS, clock=clock)


def _login(client, username, password):
    return client.post("/auth/token", data={"username": username, "password": password})


def test_account_is_paused_even_for_the_right_password(client, make_user):
    make_user("alice", password="alice-password-123")
    for _ in range(ACCOUNT_LIMIT):
        assert _login(client, "alice", "wrong-password").status_code == 401

    response = _login(client, "alice", "alice-password-123")

    assert response.status_code == 429
    assert response.headers["Retry-After"] == str(WINDOW_SECONDS)


def test_pause_ends_once_the_window_has_passed(client, make_user, clock):
    make_user("alice", password="alice-password-123")
    for _ in range(ACCOUNT_LIMIT):
        _login(client, "alice", "wrong-password")

    clock.advance(WINDOW_SECONDS)

    assert _login(client, "alice", "alice-password-123").status_code == 200


def test_successful_login_resets_the_account_count(client, make_user):
    make_user("alice", password="alice-password-123")
    for _ in range(2):
        for _ in range(ACCOUNT_LIMIT - 1):
            _login(client, "alice", "wrong-password")
        assert _login(client, "alice", "alice-password-123").status_code == 200


def test_a_paused_account_does_not_affect_other_accounts(client, make_user):
    make_user("bob", password="bob-password-1234")
    for _ in range(ACCOUNT_LIMIT):
        _login(client, "alice", "wrong-password")

    assert _login(client, "bob", "bob-password-1234").status_code == 200


def test_unknown_usernames_are_paused_like_real_ones(client):
    # Otherwise a 429 would confirm that an account exists.
    for _ in range(ACCOUNT_LIMIT):
        _login(client, "ghost", "wrong-password")

    assert _login(client, "ghost", "wrong-password").status_code == 429


def test_one_client_trying_many_accounts_is_paused(client, make_user):
    make_user("zoe", password="zoe-password-1234")
    for i in range(CLIENT_LIMIT):
        assert _login(client, f"user-{i}", "wrong-password").status_code == 401

    assert _login(client, "zoe", "zoe-password-1234").status_code == 429


def test_logging_into_your_own_account_does_not_reset_the_client_count(client, make_user):
    make_user("mallory", password="mallory-password-1")
    for i in range(CLIENT_LIMIT - 1):
        _login(client, f"victim-{i}", "guess")
    assert _login(client, "mallory", "mallory-password-1").status_code == 200

    _login(client, "victim-x", "guess")

    assert _login(client, "victim-y", "guess").status_code == 429
