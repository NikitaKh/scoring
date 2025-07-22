import datetime
import hashlib
from functools import wraps

import pytest

from scoring.api import (
    ADMIN_LOGIN,
    ADMIN_SALT,
    FORBIDDEN,
    INVALID_REQUEST,
    OK,
    SALT,
    method_handler,
)


def cases(cases_list):
    def decorator(test_func):
        @pytest.mark.parametrize("case_data", cases_list)
        @wraps(test_func)
        def wrapper(case_data, context, fake_store):
            return test_func(case_data, context, fake_store)

        return wrapper

    return decorator


class FakeStore:
    def __init__(self, interests_map=None, cache_data=None):
        self._interests = interests_map or {}
        self._cache_data = cache_data or {}

    def space(self, name):
        return self

    def call(self, method, args):
        print(method, args)
        if method == "interests_get":
            return FakeResult(self._interests.get(args, []))
        elif method == "cache_get":
            print(self._cache_data.get(args))
            return FakeResult(self._cache_data.get(args))
        elif method == "cache_set":
            key, value, _ = args
            self._cache_data[key] = value
            return FakeResult(True)
        return FakeResult(None)


class FakeResult:
    def __init__(self, data):
        self.data = data


@pytest.fixture
def context():
    return {}


@pytest.fixture
def fake_store():
    return FakeStore(
        interests_map={
            1: ["sport", "travel"],
            2: ["pets", "books"],
        },
        cache_data={},
    )


def set_valid_auth(request):
    if request.get("login") == ADMIN_LOGIN:
        request["token"] = hashlib.sha512((datetime.datetime.now().strftime("%Y%m%d%H") + ADMIN_SALT).encode("utf-8")).hexdigest()
    else:
        msg = (request.get("account", "") + request.get("login", "") + SALT).encode("utf-8")
        request["token"] = hashlib.sha512(msg).hexdigest()


@cases(
    [
        {"account": "horns&hoofs", "login": "h&f", "method": "online_score", "token": "", "arguments": {}},
        {"account": "horns&hoofs", "login": "h&f", "method": "online_score", "token": "sdd", "arguments": {}},
        {"account": "horns&hoofs", "login": "admin", "method": "online_score", "token": "", "arguments": {}},
    ]
)
def test_invalid_auth(case_data, context, fake_store):
    response, code = method_handler({"body": case_data}, context, fake_store)
    assert code == FORBIDDEN


@cases(
    [
        {"first_name": "Ivan"},  # невалидно
        {"email": "ivanov@test.ru"},  # невалидно
        {},  # пусто
    ]
)
def test_invalid_score_request(case_data, context, fake_store):
    request = {
        "account": "horns&hoofs",
        "login": "h&f",
        "method": "online_score",
        "arguments": case_data,
    }
    set_valid_auth(request)
    response, code = method_handler({"body": request}, context, fake_store)
    assert code == INVALID_REQUEST


def test_clients_interests_known_clients(context, fake_store):
    request = {
        "account": "horns&hoofs",
        "login": "h&f",
        "method": "clients_interests",
        "token": "55cc9ce545bcd144300fe9efc28e65d415b923ebb6be1e19d2750a2c03e80dd209a27954dca045e5bb12418e7d89b6d718a9e35af34e14e1d5bcd5a08f21fc95",
        "arguments": {"client_ids": [1, 2], "date": "20.07.2017"},
    }
    response, code = method_handler({"body": request}, context, fake_store)
    assert code == OK
    assert response == {
        1: ["sport", "travel"],
        2: ["pets", "books"],
    }


def test_clients_interests_unknown_client_returns_empty(context, fake_store):
    request = {
        "account": "horns&hoofs",
        "login": "h&f",
        "method": "clients_interests",
        "token": "55cc9ce545bcd144300fe9efc28e65d415b923ebb6be1e19d2750a2c03e80dd209a27954dca045e5bb12418e7d89b6d718a9e35af34e14e1d5bcd5a08f21fc95",
        "arguments": {"client_ids": [3], "date": "20.07.2017"},
    }
    response, code = method_handler({"body": request}, context, fake_store)
    assert code == OK
    assert response == {3: []}
