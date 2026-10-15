"""Request one exact Render deploy or resume GET-only observation of its saved receipt.

A live provider deploy is not application acceptance or promotion authority. Local
observation timeout never cancels Render or confirms a provider failure.
"""

import argparse
import hashlib
import json
import os
import random
import re
import signal
import stat
import sys
import threading
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

REPOSITORY = "DruHustle/onesa-ai-robot"
TARGETS = {
    "Staging": ("srv-db5k9ft9fdbs73d622cg", "staging"),
    "Production": ("srv-db5k88flk1mc73aa9110", "main"),
}
ACTIVE = {
    "created",
    "queued",
    "build_in_progress",
    "pre_deploy_in_progress",
    "update_in_progress",
}
FAILED = {"build_failed", "pre_deploy_failed", "update_failed"}
TERMINAL = FAILED | {"live", "canceled", "deactivated"}
LIMIT = 1024 * 1024


class DeploymentError(Exception):
    def __init__(self, code, http_status=0):
        super().__init__(code)
        self.code, self.http_status = code, http_status


def require(value, code):
    if not value:
        raise DeploymentError(code)


def stamp():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def private_read(path, *, receipt=False):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        require(
            stat.S_ISREG(info.st_mode)
            and info.st_nlink == 1
            and info.st_uid == os.getuid()
            and info.st_size <= LIMIT
            and (not receipt or stat.S_IMODE(info.st_mode) == 0o600),
            "INVALID_RECEIPT_FILE",
        )
        raw = stream.read(LIMIT + 1)
    require(len(raw) <= LIMIT, "INVALID_RECEIPT_FILE")
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def write_receipt(path, value, *, initial=False):
    path = Path(path)
    require(
        not any(parent.is_symlink() for parent in [path, *path.parents]),
        "RECEIPT_SYMLINK",
    )
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    require(
        path.parent.stat().st_uid == os.getuid()
        and path.parent.stat().st_mode & 0o022 == 0,
        "RECEIPT_OWNER",
    )
    raw = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    if initial:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    else:
        info = path.lstat()
        require(
            stat.S_ISREG(info.st_mode)
            and info.st_nlink == 1
            and info.st_uid == os.getuid()
            and stat.S_IMODE(info.st_mode) == 0o600,
            "INVALID_RECEIPT_FILE",
        )
        temporary = path.with_name("." + path.name + "." + os.urandom(8).hex())
        fd = os.open(
            temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
        )
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def preflight_binding(value, candidate, *, observe=False):
    require(
        isinstance(value, dict)
        and value.get("repository") == REPOSITORY
        and value.get("candidate_commit") == candidate
        and value.get("CODE_VERIFIED") == "PASS",
        "PREFLIGHT_SOURCE_MISMATCH",
    )
    if value.get("kind") == "render-deployment-preflight-binding":
        require(
            observe and value.get("deployment_authorized") is False,
            "BINDING_IS_OBSERVATION_ONLY",
        )
        return value
    source = value.get("valid_for_source_sha256")
    require(
        isinstance(source, str)
        and re.fullmatch(r"[a-f0-9]{64}", source)
        and type(value.get("workflow_run_id")) is int
        and value["workflow_run_id"] > 0,
        "PREFLIGHT_PROVENANCE_MISSING",
    )
    selected = value.get("component_plan")
    backend = (
        selected.get("backend_commit") if isinstance(selected, dict) else candidate
    )
    require(
        isinstance(backend, str) and re.fullmatch(r"[a-f0-9]{40}", backend),
        "BACKEND_SOURCE_MISMATCH",
    )
    return {
        "kind": "render-deployment-preflight-binding",
        "repository": REPOSITORY,
        "candidate_commit": candidate,
        "backend_commit": backend,
        "CODE_VERIFIED": "PASS",
        "source_sha256": source,
        "workflow_run_id": value["workflow_run_id"],
        "component_plan_sha256": digest(selected) if selected else None,
        "deployment_authorized": False,
    }


@contextmanager
def request_deadline(seconds):
    require(
        threading.current_thread() is threading.main_thread()
        and hasattr(signal, "setitimer"),
        "REQUEST_DEADLINE_UNAVAILABLE",
    )
    require(signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0), "REQUEST_DEADLINE_BUSY")
    previous = signal.getsignal(signal.SIGALRM)

    def expired(_signum, _frame):
        raise TimeoutError("Bounded Render request expired")

    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class Render:
    def __init__(
        self,
        service,
        token,
        *,
        deadline,
        request_timeout=20,
        observe_only=False,
        monotonic=time.monotonic,
        sleep=time.sleep,
        opener=None,
    ):
        self.service, self.token, self.deadline = service, token, deadline
        self.request_timeout, self.observe_only = request_timeout, observe_only
        self.monotonic, self.sleep = monotonic, sleep
        self.opener = opener or urllib.request.build_opener(NoRedirect())
        self.post_used = False

    def call(self, suffix, payload=None):
        require(
            suffix in {"", "/env-vars?limit=100", "/deploys?limit=20", "/deploys"}
            or re.fullmatch(r"/deploys/dep-[A-Za-z0-9]+", suffix),
            "PROVIDER_PATH_REJECTED",
        )
        if payload is not None:
            require(
                not self.observe_only and not self.post_used and suffix == "/deploys",
                "CREATE_NOT_ALLOWED",
            )
            self.post_used = True
        for attempt in range(3):
            remaining = self.deadline - self.monotonic()
            require(remaining > 0, "OBSERVATION_TIMEOUT")
            request = urllib.request.Request(
                "https://api.render.com/v1/services/" + self.service + suffix,
                data=json.dumps(payload).encode() if payload is not None else None,
                headers={
                    "Authorization": "Bearer " + self.token,
                    "Content-Type": "application/json",
                    "Accept-Encoding": "identity",
                },
                method="POST" if payload is not None else "GET",
            )
            try:
                with (
                    request_deadline(min(self.request_timeout, remaining)),
                    self.opener.open(
                        request, timeout=min(self.request_timeout, remaining)
                    ) as response,
                ):
                    require(
                        response.status
                        in ({200, 201} if payload is not None else {200}),
                        "HTTP_RESPONSE_REJECTED",
                    )
                    require(
                        response.headers.get("Content-Encoding", "identity").lower()
                        == "identity",
                        "ENCODED_REPLY_REJECTED",
                    )
                    raw = response.read(LIMIT + 1)
                require(len(raw) <= LIMIT, "PROVIDER_REPLY_TOO_LARGE")
                return json.loads(raw)
            except urllib.error.HTTPError as error:
                error.close()
                if payload is None and error.code == 429 and attempt < 2:
                    retry = (
                        error.headers.get("Retry-After", "") if error.headers else ""
                    )
                    reset = (
                        error.headers.get("Ratelimit-Reset", "")
                        if error.headers
                        else ""
                    )
                    delay = (
                        float(retry)
                        if retry.isdecimal()
                        else max(0, float(reset) - time.time())
                        if reset.isdecimal()
                        else 2**attempt + random.uniform(0, 1)
                    )
                    delay = min(30, max(1, delay))
                    require(
                        delay < self.deadline - self.monotonic(), "OBSERVATION_TIMEOUT"
                    )
                    self.sleep(delay)
                    continue
                code = (
                    "AUTHENTICATION_DENIED"
                    if error.code == 401
                    else "PERMISSION_DENIED"
                    if error.code == 403
                    else "RATE_LIMITED"
                    if error.code == 429
                    else "PROVIDER_HTTP_ERROR"
                )
                raise DeploymentError(code, error.code) from None
            except (urllib.error.URLError, TimeoutError, OSError):
                raise DeploymentError(
                    "SUBMISSION_UNCERTAIN"
                    if payload is not None
                    else "OBSERVATION_UNAVAILABLE"
                ) from None
            except (ValueError, KeyError, TypeError):
                raise DeploymentError("PROVIDER_REPLY_MALFORMED") from None
        raise DeploymentError("RATE_LIMITED", 429)


def validate_service(client, environment):
    service = client.call("")
    require(
        isinstance(service, dict)
        and service.get("id") == TARGETS[environment][0]
        and isinstance(service.get("repo"), str)
        and service["repo"].removesuffix(".git") == "https://github.com/" + REPOSITORY
        and service.get("branch") == TARGETS[environment][1]
        and service.get("rootDir") == "onesa-ai-robot-backend"
        and service.get("type") == "web_service"
        and service.get("autoDeployTrigger") == "off",
        "SERVICE_ENVIRONMENT_MISMATCH",
    )
    entries = client.call("/env-vars?limit=100")
    require(
        isinstance(entries, list) and len(entries) < 100, "ENVIRONMENT_REPLY_REJECTED"
    )
    try:
        values = {entry["envVar"]["key"]: entry["envVar"]["value"] for entry in entries}
    except (KeyError, TypeError):
        raise DeploymentError("ENVIRONMENT_REPLY_REJECTED") from None
    require(
        len(values) == len(entries)
        and values.get("ROBOT_DEPLOYMENT_ENVIRONMENT") == environment.lower()
        and values.get("ROBOT_ACTUATION_ENABLED") == "false",
        "SERVICE_ENVIRONMENT_MISMATCH",
    )


def deployment_identity(value, identifier, commit):
    require(
        isinstance(value, dict)
        and value.get("id") == identifier
        and isinstance(value.get("commit"), dict)
        and value["commit"].get("id") == commit,
        "DEPLOYMENT_IDENTITY_MISMATCH",
    )
    require(
        isinstance(value.get("status"), str) and value["status"] in ACTIVE | TERMINAL,
        "UNKNOWN_PROVIDER_STATE",
    )
    for field in ["createdAt", "startedAt", "updatedAt", "finishedAt"]:
        item = value.get(field)
        require(
            item is None
            or isinstance(item, str)
            and len(item) <= 40
            and re.fullmatch(r"[0-9TZ:+.\-]+", item),
            "PROVIDER_TIMESTAMP_REJECTED",
        )
    return value["status"]


def list_deployments(client):
    values = client.call("/deploys?limit=20")
    require(
        isinstance(values, list) and 0 < len(values) <= 20, "DEPLOYMENT_LIST_REJECTED"
    )
    require(
        all(isinstance(x, dict) and isinstance(x.get("deploy"), dict) for x in values),
        "DEPLOYMENT_LIST_REJECTED",
    )
    rows = [x["deploy"] for x in values]
    for row in rows:
        require(
            isinstance(row.get("id"), str)
            and re.fullmatch(r"dep-[A-Za-z0-9]+", row["id"])
            and isinstance(row.get("status"), str)
            and row["status"] in ACTIVE | TERMINAL
            and isinstance(row.get("commit"), dict)
            and isinstance(row["commit"].get("id"), str)
            and re.fullmatch(r"[a-f0-9]{40}", row["commit"]["id"]),
            "DEPLOYMENT_LIST_REJECTED",
        )
    return rows


def observe(
    client,
    record,
    receipt,
    *,
    deadline,
    monotonic=time.monotonic,
    sleep=time.sleep,
    initial_poll=5,
    max_poll=30,
    summary_seconds=90,
    announce=print,
):
    started, last_summary, previous, delay = (
        monotonic(),
        monotonic(),
        None,
        initial_poll,
    )
    while monotonic() < deadline:
        value = client.call("/deploys/" + record["deployment_id"])
        status = deployment_identity(value, record["deployment_id"], record["commit"])
        elapsed = round(monotonic() - started, 3)
        record.update(
            status=status,
            last_observed_at=stamp(),
            observation_elapsed_seconds=elapsed,
            provider_failure_confirmed=status in FAILED,
            provider_may_continue=status in ACTIVE,
            provider_times={
                k: value.get(k)
                for k in ["createdAt", "startedAt", "updatedAt", "finishedAt"]
            },
        )
        if status != previous:
            record["transitions"].append(
                {"status": status, "observed_at": stamp(), "elapsed_seconds": elapsed}
            )
            require(len(record["transitions"]) <= 128, "STATUS_TRANSITION_LIMIT")
        if status in FAILED:
            record["observation_outcome"] = "PROVIDER_TERMINAL_FAILURE"
        elif status in {"canceled", "deactivated"}:
            record["observation_outcome"] = (
                "PROVIDER_CANCELED"
                if status == "canceled"
                else "PROVIDER_DEACTIVATED_NOT_CURRENT"
            )
        elif status == "live":
            latest = list_deployments(client)
            record["observation_outcome"] = (
                "LIVE_CURRENT_ACCEPTANCE_PENDING"
                if latest[0].get("id") == record["deployment_id"]
                and latest[0].get("status") == "live"
                else "LIVE_BUT_SUPERSEDED_PROMOTION_BLOCKED"
            )
            record["verified_at"] = stamp()
        else:
            record["observation_outcome"] = "OBSERVING_PROVIDER_ACTIVE"
        write_receipt(receipt, record)
        if (
            status != previous
            or monotonic() - last_summary >= summary_seconds
            or status in TERMINAL
        ):
            announce(
                json.dumps(
                    {
                        "deployment": record["deployment_id"],
                        "status": status,
                        "elapsed_seconds": elapsed,
                        "outcome": record["observation_outcome"],
                    }
                )
            )
            last_summary = monotonic()
        if status in TERMINAL:
            return record["observation_outcome"] == "LIVE_CURRENT_ACCEPTANCE_PENDING"
        previous = status
        wait = min(delay, max(0, deadline - monotonic()))
        if wait:
            sleep(wait)
        delay = min(max_poll, delay * 1.5)
    raise DeploymentError("OBSERVATION_TIMEOUT")


def receipt_schema(record):
    required = {
        "schema_version",
        "repository",
        "service_id",
        "environment",
        "candidate_commit",
        "commit",
        "deployment_id",
        "request_timestamp",
        "status",
        "observation_outcome",
        "preflight_binding_sha256",
        "request_context",
        "transitions",
        "observation_continuations",
        "application_acceptance",
        "promotion_authorized",
        "automatic_cancel_or_retry",
        "create_attempted",
    }
    optional = {
        "accepted_at",
        "last_observed_at",
        "observation_elapsed_seconds",
        "provider_times",
        "verified_at",
        "provider_failure_confirmed",
        "provider_may_continue",
        "http_status",
    }
    require(
        isinstance(record, dict) and required <= record.keys() <= required | optional,
        "RECEIPT_SCHEMA_REJECTED",
    )
    require(
        record["promotion_authorized"] is False
        and record["automatic_cancel_or_retry"] is False
        and record["application_acceptance"] == "NOT_TESTED"
        and type(record["create_attempted"]) is bool,
        "RECEIPT_IS_NOT_ACCEPTANCE",
    )
    require(
        type(record["observation_continuations"]) is int
        and 0 <= record["observation_continuations"] < 1000,
        "RECEIPT_SCHEMA_REJECTED",
    )
    require(
        record["status"] is None
        or isinstance(record["status"], str)
        and record["status"] in ACTIVE | TERMINAL,
        "RECEIPT_SCHEMA_REJECTED",
    )
    require(
        isinstance(record["observation_outcome"], str)
        and re.fullmatch(r"[A-Z_]{1,80}", record["observation_outcome"]),
        "RECEIPT_SCHEMA_REJECTED",
    )
    context = record["request_context"]
    require(
        isinstance(context, dict)
        and context.keys() == {"repository", "ref", "workflow_run_id", "run_attempt"}
        and context["repository"] == REPOSITORY
        and context["ref"] in {"refs/heads/staging", "refs/heads/main"},
        "RECEIPT_PROVENANCE_MISMATCH",
    )
    for key in ["workflow_run_id", "run_attempt"]:
        item = context[key]
        require(
            item is None
            or isinstance(item, str)
            and re.fullmatch(r"[0-9]{1,20}", item),
            "RECEIPT_PROVENANCE_MISMATCH",
        )
    for key in ["request_timestamp", "accepted_at", "last_observed_at", "verified_at"]:
        if key in record:
            item = record[key]
            require(
                isinstance(item, str)
                and len(item) <= 40
                and re.fullmatch(r"[0-9TZ:+.\-]+", item),
                "RECEIPT_SCHEMA_REJECTED",
            )
    times = record.get("provider_times", {})
    require(
        isinstance(times, dict)
        and times.keys() <= {"createdAt", "startedAt", "updatedAt", "finishedAt"},
        "RECEIPT_SCHEMA_REJECTED",
    )
    for item in times.values():
        require(
            item is None
            or isinstance(item, str)
            and len(item) <= 40
            and re.fullmatch(r"[0-9TZ:+.\-]+", item),
            "RECEIPT_SCHEMA_REJECTED",
        )
    transitions = record["transitions"]
    require(
        isinstance(transitions, list) and len(transitions) <= 128,
        "RECEIPT_SCHEMA_REJECTED",
    )
    for item in transitions:
        require(
            isinstance(item, dict)
            and item.keys() == {"status", "observed_at", "elapsed_seconds"}
            and isinstance(item["status"], str)
            and item["status"] in ACTIVE | TERMINAL
            and isinstance(item["observed_at"], str)
            and re.fullmatch(r"[0-9TZ:+.\-]{1,40}", item["observed_at"])
            and type(item["elapsed_seconds"]) in {float, int}
            and 0 <= item["elapsed_seconds"] <= 1830,
            "RECEIPT_SCHEMA_REJECTED",
        )


def run(args, env=None, *, client_factory=Render, monotonic=time.monotonic):
    env = os.environ if env is None else env
    candidate = args.candidate if args.observe_id else env.get("GITHUB_SHA", "")
    require(
        isinstance(candidate, str) and re.fullmatch(r"[a-f0-9]{40}", candidate),
        "EXACT_CANDIDATE_REQUIRED",
    )
    require(
        args.environment in TARGETS
        and env.get("RENDER_SERVICE_ID") == TARGETS[args.environment][0],
        "SERVICE_ENVIRONMENT_MISMATCH",
    )
    require(
        env.get("GITHUB_REF") == "refs/heads/" + TARGETS[args.environment][1],
        "SOURCE_BRANCH_MISMATCH",
    )
    require(bool(env.get("RENDER_API_KEY")), "RENDER_CREDENTIAL_REQUIRED")
    require(
        5 <= args.wait_seconds <= 1800
        and 1 <= args.request_timeout <= 30
        and 1 <= args.poll_seconds <= args.max_poll_seconds <= 60,
        "INVALID_OBSERVATION_BUDGET",
    )
    preflight, _ = private_read(args.preflight)
    binding = preflight_binding(preflight, candidate, observe=bool(args.observe_id))
    if env.get("GITHUB_ACTIONS") == "true":
        require(
            env.get("GITHUB_REPOSITORY") == REPOSITORY
            and env.get("GITHUB_ACTOR") == "DruHustle"
            and env.get("GITHUB_TRIGGERING_ACTOR") == "DruHustle"
            and (args.observe_id or env.get("GITHUB_RUN_ATTEMPT") == "1"),
            "OWNER_RUN_REQUIRED",
        )
    record = None
    started = monotonic()
    deadline = started + args.wait_seconds
    client = client_factory(
        env["RENDER_SERVICE_ID"],
        env["RENDER_API_KEY"],
        deadline=deadline,
        request_timeout=args.request_timeout,
        observe_only=bool(args.observe_id),
    )
    if args.observe_id:
        record, receipt_sha = private_read(args.receipt, receipt=True)
        receipt_schema(record)
        require(
            args.receipt_sha256 == receipt_sha
            and record.get("schema_version") == 2
            and record.get("repository") == REPOSITORY
            and record.get("service_id") == env["RENDER_SERVICE_ID"]
            and record.get("environment") == args.environment
            and record.get("candidate_commit") == candidate
            and record.get("commit") == binding["backend_commit"]
            and record.get("deployment_id") == args.observe_id
            and record.get("preflight_binding_sha256") == digest(binding)
            and record.get("request_context", {}).get("repository") == REPOSITORY,
            "RECEIPT_PROVENANCE_MISMATCH",
        )
        require(
            re.fullmatch(r"dep-[A-Za-z0-9]+", args.observe_id), "DEPLOYMENT_ID_REQUIRED"
        )
        require(
            record["request_context"]["ref"] == env["GITHUB_REF"],
            "RECEIPT_PROVENANCE_MISMATCH",
        )
        record["observation_continuations"] += 1
    else:
        require(
            preflight.get("kind") != "render-deployment-preflight-binding",
            "BINDING_IS_OBSERVATION_ONLY",
        )
        if args.environment == "Production":
            require(
                preflight.get("qualification_status") == "APPROVED"
                and all(
                    preflight.get(k) == "PASS"
                    for k in [
                        "STAGING_VERIFIED",
                        "OPERATIONS_VERIFIED",
                    ]
                )
                and not preflight.get("component_plan"),
                "PRODUCTION_PREFLIGHT_REQUIRED",
            )
            if preflight.get("CONTENT_LEGAL_APPROVED") != "PASS":
                require(
                    not env.get("GITHUB_ACTIONS")
                    and preflight.get("CONTENT_LEGAL_APPROVED")
                    == "DEFERRED_BY_OWNER_UNTIL_LAUNCH"
                    and type(preflight.get("external_authorization_run")) is int,
                    "PRODUCTION_PRIVACY_DECISION_REQUIRED",
                )
                sys.path.insert(0, str(Path(__file__).resolve().parent / "release"))
                import evidence
                import free_gate

                github = evidence.GitHub()
                free_gate.verify_development_preflight(
                    github,
                    candidate,
                    preflight["external_authorization_run"],
                    preflight,
                )
        if preflight.get("component_plan"):
            sys.path.insert(0, str(Path(__file__).resolve().parent / "release"))
            import cloud

            selected = cloud.selected_components(
                Path(args.preflight).parent.parent, "Staging"
            )
            cloud.preflight("Staging")
            require(
                selected["backend_commit"] == binding["backend_commit"],
                "BACKEND_SOURCE_MISMATCH",
            )
        record = {
            "schema_version": 2,
            "repository": REPOSITORY,
            "service_id": env["RENDER_SERVICE_ID"],
            "environment": args.environment,
            "candidate_commit": candidate,
            "commit": binding["backend_commit"],
            "deployment_id": None,
            "request_timestamp": stamp(),
            "status": None,
            "observation_outcome": "REQUEST_PREFLIGHT_PENDING",
            "preflight_binding_sha256": digest(binding),
            "request_context": {
                "repository": REPOSITORY,
                "ref": env.get("GITHUB_REF"),
                "workflow_run_id": env.get("GITHUB_RUN_ID"),
                "run_attempt": env.get("GITHUB_RUN_ATTEMPT"),
            },
            "transitions": [],
            "observation_continuations": 0,
            "application_acceptance": "NOT_TESTED",
            "promotion_authorized": False,
            "automatic_cancel_or_retry": False,
            "create_attempted": False,
        }
        receipt_schema(record)
        write_receipt(args.receipt, record, initial=True)
        write_receipt(
            Path(args.receipt).with_name("render-preflight.json"), binding, initial=True
        )
    try:
        validate_service(client, args.environment)
        if not args.observe_id:
            latest = list_deployments(client)
            require(
                not any(x.get("status") in ACTIVE for x in latest),
                "EXISTING_ACTIVE_DEPLOYMENT_RECONCILE_FIRST",
            )
            require(
                bool(preflight.get("component_plan"))
                or not any(
                    (x.get("commit") or {}).get("id") == record["commit"]
                    for x in latest
                ),
                "EXISTING_CANDIDATE_RECONCILE_FIRST",
            )
            record["observation_outcome"] = "SUBMISSION_INTENT_PROVIDER_MAY_ACCEPT"
            record["create_attempted"] = True
            write_receipt(args.receipt, record)
            value = client.call(
                "/deploys", {"commitId": record["commit"], "clearCache": "do_not_clear"}
            )
            identifier = value.get("id") if isinstance(value, dict) else None
            require(
                isinstance(identifier, str)
                and re.fullmatch(r"dep-[A-Za-z0-9]+", identifier),
                "DEPLOYMENT_REPLY_ID_MISSING",
            )
            record["deployment_id"] = identifier
            record["accepted_at"] = stamp()
            record["status"] = deployment_identity(value, identifier, record["commit"])
            record["observation_outcome"] = "DEPLOYMENT_ACCEPTED_OBSERVATION_PENDING"
            write_receipt(args.receipt, record)
        return observe(
            client,
            record,
            args.receipt,
            deadline=deadline,
            monotonic=monotonic,
            sleep=client.sleep,
            initial_poll=args.poll_seconds,
            max_poll=args.max_poll_seconds,
        )
    except (
        DeploymentError,
        KeyboardInterrupt,
        InterruptedError,
        ValueError,
        TypeError,
        KeyError,
    ) as error:
        code = (
            error.code
            if isinstance(error, DeploymentError)
            else "OBSERVATION_INTERRUPTED"
            if isinstance(error, (KeyboardInterrupt, InterruptedError))
            else "PROVIDER_REPLY_MALFORMED"
        )
        record["observation_outcome"] = code
        record["provider_failure_confirmed"] = record.get("status") in FAILED
        record["provider_may_continue"] = (
            record.get("status") in ACTIVE
            or record.get("create_attempted") is True
            and record.get("status") not in TERMINAL
        )
        record["http_status"] = (
            error.http_status if isinstance(error, DeploymentError) else 0
        )
        record["last_observed_at"] = stamp()
        write_receipt(args.receipt, record)
        print(
            json.dumps(
                {
                    "outcome": code,
                    "http_status": record["http_status"],
                    "provider_failure_confirmed": record["provider_failure_confirmed"],
                    "provider_may_continue": record["provider_may_continue"],
                    "promotion_authorized": False,
                }
            )
        )
        return False


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preflight", type=Path, required=True)
    parser.add_argument("--environment", choices=list(TARGETS), required=True)
    parser.add_argument(
        "--receipt", type=Path, default=os.getenv("RENDER_RECEIPT_PATH")
    )
    parser.add_argument("--observe-id")
    parser.add_argument("--receipt-sha256")
    parser.add_argument("--candidate")
    parser.add_argument("--wait-seconds", type=int, default=1800)
    parser.add_argument("--request-timeout", type=int, default=20)
    parser.add_argument("--poll-seconds", type=int, default=5)
    parser.add_argument("--max-poll-seconds", type=int, default=30)
    args = parser.parse_args(argv)
    require(args.receipt is not None, "DURABLE_RECEIPT_REQUIRED")
    require(not args.candidate or args.observe_id, "CANDIDATE_OVERRIDE_IS_OBSERVE_ONLY")
    if args.observe_id:
        require(
            args.candidate
            and args.receipt_sha256
            and re.fullmatch(r"[a-f0-9]{64}", args.receipt_sha256),
            "PINNED_RECEIPT_REQUIRED",
        )
    return 0 if run(args) else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (DeploymentError, OSError, ValueError, TypeError, KeyError):
        raise SystemExit(
            "Render operation blocked by scope, receipt or response validation; no promotion"
        ) from None
