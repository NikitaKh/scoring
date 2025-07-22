#!/usr/bin/env python
# -*- coding: utf-8 -*-

import datetime
import hashlib
import json
import logging
import re
import uuid
from argparse import ArgumentParser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import tarantool

from scoring.service.scoring import Scoring

SALT = "Otus"
ADMIN_LOGIN = "admin"
ADMIN_SALT = "42"
OK = 200
BAD_REQUEST = 400
FORBIDDEN = 403
NOT_FOUND = 404
INVALID_REQUEST = 422
INTERNAL_ERROR = 500
ERRORS = {
    BAD_REQUEST: "Bad Request",
    FORBIDDEN: "Forbidden",
    NOT_FOUND: "Not Found",
    INVALID_REQUEST: "Invalid Request",
    INTERNAL_ERROR: "Internal Server Error",
}
UNKNOWN = 0
MALE = 1
FEMALE = 2
GENDERS = {
    UNKNOWN: "unknown",
    MALE: "male",
    FEMALE: "female",
}

config = {
    # "LOG_FILE_PATH": "../app.log",
    "T_HOST": "localhost",
    "T_PORT": 3301,
    "T_USERNAME": "sampleuser",
    "T_PASSWORD": "123456",
    "RECONNECT_MAX_ATTEMPTS": 5,
    "CONNECTION_TIMEOUT": 60,
}

if config.get("LOG_FILE_PATH"):
    log_path: Path = Path(__file__).parent / str(config.get("LOG_FILE_PATH"))
    logging.basicConfig(filename=log_path, level=logging.INFO, format="[%(asctime)s]  %(levelname)s  %(message)s")
else:
    logging.basicConfig(level=logging.INFO, format="[%(asctime)s]  %(levelname)s  %(message)s")

logger = logging.getLogger(__name__)


class Field:
    def __init__(self, required=False, nullable=False):
        self.required = required
        self.nullable = nullable
        self._name = None

    def validate(self, value):
        if value is None:
            if self.required:
                logger.error(f"Field '{self._name}' is required but None given")
                raise ValueError(f"{self._name} is required")
        elif not self.nullable and (value == "" or value == []):
            logger.error(f"Field '{self._name}' is not nullable but empty value given")
            raise ValueError(f"{self._name} cannot be empty")


class CharField(Field):
    def validate(self, value):
        super().validate(value)
        if value is not None and not isinstance(value, str):
            logger.error(f"Field {self._name} has type {type(value)} but must be string")
            raise ValueError(f"{self._name} must be a string")


class ArgumentsField(Field):
    def validate(self, value):
        super().validate(value)
        if value is not None and not isinstance(value, dict):
            logger.error(f"Field {self._name} has type {type(value)} but must be dict")
            raise ValueError(f"{self._name} must be a dict")


class EmailField(CharField):
    def validate(self, value):
        super().validate(value)
        if value is not None and not re.match(r"^[a-zA-Z0-9.+_-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", value):
            logger.error(f"Invalid email format: {value}")
            raise ValueError("Invalid email format")


class PhoneField(Field):
    def validate(self, value):
        super().validate(value)
        if value is not None and not re.match(r"^7\d{10}$", str(value)):
            logger.error(f"Invalid phone number format: {value}")
            raise ValueError("Invalid phone number format")


class DateField(Field):
    def validate(self, value):
        super().validate(value)
        if value is not None:
            try:
                datetime.datetime.strptime(value, "%d.%m.%Y")
            except ValueError:
                raise ValueError(f"{self._name} must be in format DD.MM.YYYY")


class BirthDayField(Field):
    def validate(self, value):
        super().validate(value)
        if value is not None:
            try:
                birth_date = datetime.datetime.strptime(value, "%d.%m.%Y")
                today = datetime.datetime.today()
                if (today - birth_date).days > 70 * 365:
                    raise ValueError(f"{self._name} must be less than 70 years ago")
            except ValueError:
                raise ValueError(f"{self._name} must be in format DD.MM.YYYY")


class GenderField(Field):
    def validate(self, value):
        super().validate(value)
        if value is not None and value not in (0, 1, 2):
            raise ValueError(f"{self._name} must be 0, 1, or 2")


class ClientIDsField(Field):
    def validate(self, value):
        super().validate(value)
        if not isinstance(value, list) or not all(isinstance(i, int) for i in value):
            raise ValueError(f"{self._name} must be a list of integers")


class BaseRequest:
    def __init__(self, **kwargs):
        logger.info(f"Initializing {self.__class__.__name__} with data: {kwargs}")
        self.errors = {}
        self.cleaned_data = {}

        for name, field in self.fields().items():
            field._name = name
            value = kwargs.get(name)
            try:
                field.validate(value)
                self.cleaned_data[name] = value
            except ValueError as e:
                logger.error(f"Validation error in field '{name}': {e}")
                self.errors[name] = str(e)

    def is_valid(self):
        logger.info(f"{self.__class__.__name__} validation failed with errors: {self.errors}")
        return not self.errors

    @classmethod
    def fields(cls):
        return {name: attr for name, attr in cls.__dict__.items() if isinstance(attr, Field)}


class MethodRequest(BaseRequest):
    account = CharField(required=False, nullable=True)
    login = CharField(required=True, nullable=True)
    token = CharField(required=True, nullable=True)
    arguments = ArgumentsField(required=True, nullable=True)
    method = CharField(required=True, nullable=False)

    @property
    def is_admin(self):
        return self.cleaned_data.get("login") == ADMIN_LOGIN


class ClientsInterestsRequest(MethodRequest):
    client_ids = ClientIDsField(required=True)
    date = DateField(required=False, nullable=True)


class OnlineScoreRequest(MethodRequest):
    first_name = CharField(required=False, nullable=True)
    last_name = CharField(required=False, nullable=True)
    email = EmailField(required=False, nullable=True)
    phone = PhoneField(required=False, nullable=True)
    birthday = BirthDayField(required=False, nullable=True)
    gender = GenderField(required=False, nullable=True)

    @property
    def has_valid_pair(self):
        return any(
            [
                self.cleaned_data.get("phone") and self.cleaned_data.get("email"),
                self.cleaned_data.get("first_name") and self.cleaned_data.get("last_name"),
                self.cleaned_data.get("gender") is not None and self.cleaned_data.get("birthday"),
            ]
        )


def check_auth(request):
    logger.info(f"Checking auth for user: {request.cleaned_data.get('login')}")
    if request.is_admin:
        digest = hashlib.sha512((datetime.datetime.now().strftime("%Y%m%d%H") + ADMIN_SALT).encode("utf-8")).hexdigest()
    else:
        digest = hashlib.sha512((request.cleaned_data.get("account") + request.cleaned_data.get("login") + SALT).encode("utf-8")).hexdigest()
    return digest == request.cleaned_data.get("token")


def method_handler(request, ctx, store):
    method_request = MethodRequest(**request["body"])

    if not method_request.is_valid():
        logger.error(f"Invalid method request: {method_request.errors}")
        return method_request.errors, INVALID_REQUEST

    if not check_auth(method_request):
        logger.error("Authentication failed")
        return ERRORS[FORBIDDEN], FORBIDDEN

    method_name = method_request.cleaned_data.get("method")

    logger.info(f"Processing method: {method_name}")

    if method_name == "clients_interests":

        sc = Scoring(store.space("interests"))

        clients_interests_req = ClientsInterestsRequest(**request["body"]["arguments"])
        if not clients_interests_req.is_valid():
            logger.error(f"Invalid clients_interests request: {clients_interests_req.errors}")
            return clients_interests_req.errors, INVALID_REQUEST

        client_ids = clients_interests_req.cleaned_data.get("client_ids")
        ctx["nclients"] = len(client_ids)

        response = {cid: sc.get_interests(cid) for cid in clients_interests_req.cleaned_data.get("client_ids")}
        logger.info(f"clients_interests response: {response}")
        return response, OK
    elif method_name == "online_score":

        sc = Scoring(store.space("scoring"))

        online_score_req = OnlineScoreRequest(**request["body"]["arguments"])
        if not online_score_req.is_valid():
            logger.error(f"Invalid online_score request: {online_score_req.errors}")
            return online_score_req.errors, INVALID_REQUEST

        if not online_score_req.has_valid_pair:
            logger.error("online_score request missing required pairs")
            return ERRORS[INVALID_REQUEST], INVALID_REQUEST

        ctx["has"] = [name for name, value in online_score_req.cleaned_data.items() if value is not None]
        logger.info(f"online_score valid fields: {ctx['has']}")

        if request["body"].get("login") == ADMIN_LOGIN:
            score = 42
        else:
            score = sc.get_score(**online_score_req.cleaned_data)
        logger.info(f"online_score result: {score}")
        return {"score": score}, OK

    logger.error(f"Invalid method: {method_name}")
    return ERRORS[INVALID_REQUEST], INVALID_REQUEST


class MainHTTPHandler(BaseHTTPRequestHandler):
    router = {"method": method_handler}

    store = tarantool.Connection(
        config.get("T_HOST"),
        config.get("T_PORT"),
        user=config.get("T_USERNAME"),
        password=config.get("T_PASSWORD"),
        reconnect_max_attempts=config.get("RECONNECT_MAX_ATTEMPTS"),
        connection_timeout=config.get("CONNECTION_TIMEOUT"),
    )

    def get_request_id(self, headers):
        return headers.get("HTTP_X_REQUEST_ID", uuid.uuid4().hex)

    def do_POST(self):
        response, code = {}, OK
        context = {"request_id": self.get_request_id(self.headers)}
        try:
            data_string = self.rfile.read(int(self.headers["Content-Length"]))
            request = json.loads(data_string)
        except Exception as e:
            logging.exception("Failed to parse request: %s", e)
            code = BAD_REQUEST
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            r = {"error": ERRORS.get(code), "code": code}
            context.update(r)
            logging.info(context)
            self.wfile.write(json.dumps(r).encode("utf-8"))
            return

        path = self.path.strip("/")
        logging.info("%s: %s %s", self.path, data_string, context["request_id"])

        if path in self.router:
            try:
                response, code = self.router[path]({"body": request, "headers": self.headers}, context, self.store)
            except Exception as e:
                logging.exception("Unexpected error: %s", e)
                code = INTERNAL_ERROR
        else:
            code = NOT_FOUND

        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        if code not in ERRORS:
            r = {"response": response, "code": code}
        else:
            r = {"error": response or ERRORS.get(code), "code": code}
        context.update(r)
        logging.info(context)
        self.wfile.write(json.dumps(r).encode("utf-8"))


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("-p", "--port", action="store", type=int, default=8080)
    parser.add_argument("-l", "--log", action="store", default=None)
    args = parser.parse_args()
    logging.basicConfig(
        filename=args.log,
        level=logging.INFO,
        format="[%(asctime)s] %(levelname).1s %(message)s",
        datefmt="%Y.%m.%d %H:%M:%S",
    )
    server = HTTPServer(("localhost", args.port), MainHTTPHandler)
    logging.info("Starting server at %s" % args.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    server.server_close()
