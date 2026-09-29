#!/usr/bin/env python3
"""Validate the Z.ai provider edge of the M4 model-extraction trial without network calls.

Covers: env-only credential handling with redaction; exact rendered prompt as the
request input with no tool surface; model/base-URL/provider trace; fail-closed
HTTP/timeout/malformed-response behavior; Copilot backward compatibility; the
same strict JSON/candidate boundary as the Copilot path; and the absence of any
new canonical mutation, publication, Resolver/Verifier, or human-review
authority. CI never calls Z.ai and never consumes model credits.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import urllib.error
from contextlib import contextmanager, redirect_stdout, redirect_stderr
from pathlib import Path
from typing import Any
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import scripts.run_m4_model_extraction_trial as trial_runner  # noqa: E402
from scripts.run_m4_model_extraction_trial import (  # noqa: E402
    MAX_RESPONSE_BYTES,
    PROVIDER_COPILOT,
    PROVIDER_ZAI,
    ZAI_BASE_URL_ENV,
    ZAI_CREDENTIAL_ENV,
    ZAI_ENDPOINT_URLS,
    ZAI_PROVIDER_NAME,
    _capped_read,
    parse_args,
    read_git_head,
    redact_secret,
    require_zai_api_key,
    resolve_requested_model,
    resolve_zai_base_url,
    validate_zai_base_url,
    zai_invoker,
    zai_request_payload,
)
from scripts.validate_m4_model_extraction_trial import (  # noqa: E402
    fake_output,
    schema_errors,
)
from scripts.validate_m4_model_extraction_trial_reconciliation import (  # noqa: E402
    without_manufacturer_validity,
)
from services.intelligence.ai_extraction_boundary import (  # noqa: E402
    AIExtractionBoundaryError,
    validate_ai_extraction_run,
)
from services.intelligence.model_extraction_trial import (  # noqa: E402
    ModelTrace,
    build_trial_prompt,
    execute_trial_case,
)

FIXTURE = ROOT / "tests" / "fixtures" / "m4-model-extraction-eval.json"
SENTINEL_KEY = "zai-sentinel-key-0123456789abcdef"


def expect(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_cases() -> list[dict[str, Any]]:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        raise RuntimeError("evaluation fixture requires non-empty cases array")
    return cases


def content_body(content: Any) -> bytes:
    return json.dumps(
        {"choices": [{"message": {"role": "assistant", "content": content}}]}
    ).encode("utf-8")


def gold_response(case: dict[str, Any]) -> bytes:
    """Deterministic model text that satisfies the case gold expectations.

    The delivery-case gold reflects the reconciled expectation that the
    manufacturer claim carries no unsupported validity scope, so the same
    transformation the reconciliation review applies to the shared fake output
    is applied here.
    """

    raw = fake_output(case)
    if case["id"] == "TRIAL-EN-DELIVERY":
        raw = without_manufacturer_validity(raw)
    return content_body(raw)


class FakeTransport:
    """Records the exact request and returns a canned response or raises."""

    def __init__(self, *, status: int = 200, body: bytes = b"{}", error: Exception | None = None):
        self.status = status
        self.body = body
        self.error = error
        self.calls: list[tuple[str, bytes, dict[str, str], int]] = []

    def __call__(
        self, url: str, payload: bytes, headers: dict[str, str], timeout_seconds: int
    ) -> tuple[int, bytes]:
        self.calls.append((url, payload, dict(headers), timeout_seconds))
        if self.error is not None:
            raise self.error
        return self.status, self.body


class CorpusTransport:
    """Answers each request from the exact rendered prompt it carries."""

    def __init__(self, responses: dict[str, bytes]):
        self.responses = responses
        self.calls: list[tuple[str, bytes, dict[str, str], int]] = []

    def __call__(
        self, url: str, payload: bytes, headers: dict[str, str], timeout_seconds: int
    ) -> tuple[int, bytes]:
        self.calls.append((url, payload, dict(headers), timeout_seconds))
        request = json.loads(payload.decode("utf-8"))
        prompt = request["messages"][0]["content"]
        return 200, self.responses[prompt]


@contextmanager
def argv(*items: str):
    with patch.object(sys, "argv", ["run_m4_model_extraction_trial.py", *items]):
        yield


def expect_runtime_error(
    label: str,
    invoke: Any,
    failures: list[str],
    *,
    must_contain: str | None = None,
    secret: str | None = SENTINEL_KEY,
) -> None:
    try:
        invoke("prompt")
    except RuntimeError as exc:
        message = str(exc)
        expect(bool(message.strip()), f"{label} raised an empty failure reason", failures)
        if secret is not None:
            expect(secret not in message, f"{label} leaked the credential in its error", failures)
        if must_contain is not None:
            expect(
                must_contain in message,
                f"{label} failure reason lacks {must_contain!r}: {message[:200]}",
                failures,
            )
    except Exception:
        failures.append(f"{label} raised a non-RuntimeError exception")
    else:
        failures.append(f"{label} did not fail closed")


def build_invoker(transport: Any, *, model: str = "glm-5.3", base_url: str | None = None):
    return zai_invoker(
        model=model,
        api_key=SENTINEL_KEY,
        base_url=base_url or ZAI_ENDPOINT_URLS["coding-plan"],
        timeout_seconds=30,
        transport=transport,
    )


def minimal_provider_env(extra: dict[str, str]) -> dict[str, str]:
    """Test environment with only the credential plus process-lookup basics."""

    passthrough = {
        name: value
        for name, value in os.environ.items()
        if name in ("PATH", "PATHEXT", "SYSTEMROOT", "SYSTEMDRIVE", "COMSPEC", "WINDIR")
    }
    return {**passthrough, **extra}


def main() -> int:
    failures: list[str] = []
    cases = load_cases()

    # ZP-1: request fidelity — the exact rendered prompt is the only model input
    # and the request carries no tool, function-calling, or MCP surface.
    delivery = next(case for case in cases if case["id"] == "TRIAL-EN-DELIVERY")
    prompt = build_trial_prompt(delivery)
    exact_content = '  {"evidence": [], "entities": [], "claims": [], "events": []}\n'
    transport = FakeTransport(body=content_body(exact_content))
    invoke = build_invoker(transport)
    returned = invoke(prompt)
    expect(returned == exact_content, "invoker did not return the exact assistant text unmodified", failures)

    expect(len(transport.calls) == 1, "invoker did not make exactly one transport call", failures)
    if transport.calls:
        url, payload, headers, timeout = transport.calls[0]
        expect(
            url == ZAI_ENDPOINT_URLS["coding-plan"].rstrip("/") + "/chat/completions",
            f"request URL is not the documented chat-completions endpoint: {url}",
            failures,
        )
        request = json.loads(payload.decode("utf-8"))
        expect(
            set(request) == {"model", "messages", "stream", "thinking", "reasoning_effort"},
            f"request payload carries unexpected keys: {sorted(request)}",
            failures,
        )
        expect(request["model"] == "glm-5.3", "request payload lost the requested model", failures)
        expect(
            request["messages"] == [{"role": "user", "content": prompt}],
            "request payload input is not the exact rendered SDA trial prompt",
            failures,
        )
        expect(request["stream"] is False, "request payload did not disable streaming", failures)
        expect(
            request["thinking"] == {"type": "enabled"},
            "request payload does not pin enabled thinking (IRZ-04)",
            failures,
        )
        expect(
            request["reasoning_effort"] == "max",
            "request payload does not pin reasoning_effort max (IRZ-04)",
            failures,
        )
        for forbidden in ("tools", "functions", "tool_choice", "mcp_servers"):
            expect(forbidden not in request, f"request payload exposes {forbidden}", failures)
        expect(
            headers.get("Authorization") == f"Bearer {SENTINEL_KEY}",
            "Authorization header is not the environment credential",
            failures,
        )
        expect(
            headers.get("Content-Type") == "application/json",
            "request Content-Type is not JSON",
            failures,
        )
        expect(timeout == 30, "invoker did not propagate the configured timeout", failures)

    encoded = json.loads(zai_request_payload("glm-5.3", "p").decode("utf-8"))
    expect(
        set(encoded) == {"model", "messages", "stream", "thinking", "reasoning_effort"},
        "zai_request_payload emits unexpected keys",
        failures,
    )

    # ZP-2: credential handling — environment only, fail closed when missing,
    # redacted from every raised message.
    try:
        require_zai_api_key(env={})
        failures.append("missing ZAI_API_KEY did not fail closed")
    except SystemExit as exc:
        expect(
            ZAI_CREDENTIAL_ENV in str(exc) and SENTINEL_KEY not in str(exc),
            "missing-credential message is wrong or leaks a value",
            failures,
        )
    expect(
        require_zai_api_key(env={ZAI_CREDENTIAL_ENV: "k"}) == "k",
        "present environment credential was not accepted",
        failures,
    )
    # IRZ-01: characters that HTTP rejects or that repr() escaping could alter
    # must never become the sent credential, because exact-substring redaction
    # would then miss the escaped form in diagnostics.
    for label, bad_key in (
        ("trailing newline", "k\n"),
        ("leading space", " k"),
        ("trailing space", "k "),
        ("embedded tab", "k\tk"),
        ("control character", "k\x00k"),
        ("embedded quote", 'k"k'),
        ("embedded backslash", "k\\k"),
        ("non-ASCII latin", "k\xc3\xa9k"),
        ("non-ASCII cyrillic", "kключ"),
    ):
        try:
            require_zai_api_key(env={ZAI_CREDENTIAL_ENV: bad_key})
            failures.append(f"credential containing {label} was accepted")
        except SystemExit:
            pass
    expect(
        require_zai_api_key(env={ZAI_CREDENTIAL_ENV: "clean-key"}) == "clean-key",
        "clean credential was rejected by the IRZ-01 guard",
        failures,
    )
    expect(
        redact_secret(f"prefix {SENTINEL_KEY} suffix", SENTINEL_KEY) == "prefix ***REDACTED*** suffix",
        "redact_secret did not remove the credential",
        failures,
    )
    expect_runtime_error(
        "transport exception echoing the key",
        build_invoker(FakeTransport(error=RuntimeError(f"upstream saw Bearer {SENTINEL_KEY}"))),
        failures,
    )
    expect_runtime_error(
        "HTTP 401 body echoing the key",
        build_invoker(FakeTransport(status=401, body=f'{{"error":"bad key {SENTINEL_KEY}"}}'.encode())),
        failures,
        must_contain="401",
    )
    # A key echoed across the old 300-byte excerpt boundary must not survive
    # partially: redaction runs on the full message before truncation.
    straddling = ("x" * 300 + SENTINEL_KEY + "y" * 64).encode("utf-8")
    expect_runtime_error(
        "HTTP 500 body with key straddling the excerpt boundary",
        build_invoker(FakeTransport(status=500, body=straddling)),
        failures,
        must_contain="500",
    )

    # ZP-3: fail-closed matrix over HTTP, timeout, transport, and response shape.
    failure_matrix: list[tuple[str, FakeTransport, str | None]] = [
        ("http-401", FakeTransport(status=401, body=b'{"error":"unauthorized"}'), "401"),
        ("http-500", FakeTransport(status=500, body=b"internal error"), "500"),
        ("http-300", FakeTransport(status=300, body=b""), "300"),
        ("timeout", FakeTransport(error=TimeoutError("read timed out")), None),
        ("url-error", FakeTransport(error=urllib.error.URLError("connection refused")), None),
        ("generic-exception", FakeTransport(error=ValueError("boom")), None),
        ("malformed-json", FakeTransport(body=b"not-json"), None),
        ("undecodable-body", FakeTransport(body=b"\xff\xfe\x00"), None),
        ("root-not-object", FakeTransport(body=b"[]"), None),
        ("choices-missing", FakeTransport(body=b"{}"), None),
        ("choices-empty", FakeTransport(body=b'{"choices":[]}'), None),
        ("choice-not-object", FakeTransport(body=b'{"choices":["x"]}'), None),
        ("message-missing", FakeTransport(body=b'{"choices":[{}]}'), None),
        ("content-null", FakeTransport(body=b'{"choices":[{"message":{"content":null}}]}'), None),
        ("content-not-text", FakeTransport(body=b'{"choices":[{"message":{"content":[1,2]}}]}'), None),
        # IRZ-03: the provider envelope must reject duplicate keys (no
        # last-key-wins selection) and non-finite JSON numbers/constants.
        (
            "duplicate-choices-keys",
            FakeTransport(
                body=b'{"choices":[{"message":{"content":"{}"}}],"choices":[]}'
            ),
            None,
        ),
        (
            "duplicate-message-keys",
            FakeTransport(
                body=b'{"choices":[{"message":{"content":"{}","content":null}}]}'
            ),
            None,
        ),
        (
            "envelope-nan-constant",
            FakeTransport(body=b'{"choices":[{"message":{"content":NaN}}]}'),
            None,
        ),
        (
            "envelope-nonfinite-float",
            FakeTransport(body=b'{"choices":[{"message":{"content":1e999}}]}'),
            None,
        ),
        # IRZ-06: responses above the byte bound fail closed.
        (
            "oversize-body",
            FakeTransport(body=b"x" * (MAX_RESPONSE_BYTES + 1)),
            None,
        ),
    ]
    for label, transport_case, must_contain in failure_matrix:
        expect_runtime_error(label, build_invoker(transport_case), failures, must_contain=must_contain)

    # IRZ-06: the shared capped-read helper enforces the bound at the transport layer.
    expect(
        _capped_read(io.BytesIO(b"abc"), 10) == b"abc",
        "capped read altered an in-bound response body",
        failures,
    )
    try:
        _capped_read(io.BytesIO(b"a" * 11), 10)
        failures.append("capped read did not enforce the byte bound")
    except RuntimeError:
        pass

    # ZP-3b: the real transport refuses redirects rather than following them,
    # so the bearer credential can never be re-sent to another origin. A refused
    # redirect surfaces as its 3xx status, which the matrix above fails closed on.
    refuse_handler = trial_runner._RefuseRedirectHandler()
    for code in (301, 302, 303, 307, 308):
        expect(
            refuse_handler.redirect_request(None, None, code, "Moved", {}, "https://other.invalid/x") is None,
            f"redirect handler did not refuse HTTP {code}",
            failures,
        )
    redirect_handlers = [
        handler
        for handler in trial_runner._ZAI_OPENER.handlers
        if isinstance(handler, urllib.request.HTTPRedirectHandler)
    ]
    expect(
        len(redirect_handlers) == 1 and isinstance(redirect_handlers[0], trial_runner._RefuseRedirectHandler),
        "transport opener retained a redirect-following handler",
        failures,
    )

    # ZP-4: endpoint resolution and validation (IRZ-02).
    expect(
        ZAI_ENDPOINT_URLS["coding-plan"] != ZAI_ENDPOINT_URLS["prepaid"],
        "documented Coding Plan and prepaid endpoints collapsed",
        failures,
    )
    expect(
        resolve_zai_base_url(None, "coding-plan", env={})
        == (ZAI_ENDPOINT_URLS["coding-plan"], "endpoint:coding-plan"),
        "explicit coding-plan endpoint selection failed",
        failures,
    )
    expect(
        resolve_zai_base_url(None, "prepaid", env={})
        == (ZAI_ENDPOINT_URLS["prepaid"], "endpoint:prepaid"),
        "explicit prepaid endpoint selection failed",
        failures,
    )
    expect(
        resolve_zai_base_url(None, None, env={ZAI_BASE_URL_ENV: ZAI_ENDPOINT_URLS["prepaid"]})
        == (ZAI_ENDPOINT_URLS["prepaid"], "env"),
        "ZAI_BASE_URL environment override was ignored",
        failures,
    )
    expect(
        resolve_zai_base_url(
            ZAI_ENDPOINT_URLS["coding-plan"],
            "prepaid",
            env={ZAI_BASE_URL_ENV: ZAI_ENDPOINT_URLS["prepaid"]},
        )
        == (ZAI_ENDPOINT_URLS["coding-plan"], "flag"),
        "--base-url flag did not take precedence",
        failures,
    )
    try:
        resolve_zai_base_url(None, None, env={})
        failures.append("missing endpoint selection silently defaulted instead of failing closed")
    except SystemExit:
        pass

    for official in (ZAI_ENDPOINT_URLS["coding-plan"], ZAI_ENDPOINT_URLS["prepaid"]):
        try:
            validate_zai_base_url(official)
        except SystemExit:
            failures.append(f"official Z.ai route was rejected: {official}")
    for bad_url in (
        "http://api.z.ai/api/paas/v4",
        "https://user:pass@api.z.ai/api/paas/v4",
        "https://api.z.ai:8443/api/paas/v4",
        "https://proxy.invalid/api/paas/v4",
        "https://evil.example/api/coding/paas/v4",
        "https://api.z.ai/not-api",
        "https://api.z.ai/api/paas/v4?token=x",
        "https://api.z.ai/api/paas/v4#fragment",
        # H1: only the two exact documented routes are credential destinations;
        # near-miss paths on the official host are rejected.
        "https://api.z.ai/api/paas/v4/",
        "https://api.z.ai/api/paas/v5",
        "https://api.z.ai/api/coding/paas/v4/extra",
        "https://api.z.ai/api",
        "not-a-url",
        "",
    ):
        try:
            validate_zai_base_url(bad_url)
            failures.append(f"invalid base URL was accepted: {bad_url!r}")
        except SystemExit:
            pass

    expect(resolve_requested_model(PROVIDER_ZAI, None) == "glm-5.3", "zai default model is not glm-5.3", failures)
    expect(resolve_requested_model(PROVIDER_COPILOT, None) == "gpt-5.4", "copilot default model changed", failures)
    expect(resolve_requested_model(PROVIDER_ZAI, "glm-4.7") == "glm-4.7", "explicit model override ignored", failures)

    # ZP-4b: git provenance plumbing resolves linked worktrees through commondir
    # (C1) and falls back to packed-refs in the common directory.
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        main_git = base / "main" / ".git"
        (main_git / "refs" / "heads").mkdir(parents=True)
        feature_sha = "f" * 40
        (main_git / "refs" / "heads" / "feature").write_text(feature_sha + "\n", encoding="utf-8")
        packed_sha = "c" * 40
        (main_git / "packed-refs").write_text(f"{packed_sha} refs/heads/packed\n", encoding="utf-8")
        worktree_admin = main_git / "worktrees" / "wt"
        worktree_admin.mkdir(parents=True)
        (worktree_admin / "commondir").write_text("../../\n", encoding="utf-8")
        (worktree_admin / "HEAD").write_text("ref: refs/heads/feature\n", encoding="utf-8")
        worktree = base / "wt"
        worktree.mkdir()
        (worktree / ".git").write_text(f"gitdir: {worktree_admin}\n", encoding="utf-8")

        expect(
            read_git_head(worktree) == (feature_sha, "refs/heads/feature"),
            "read_git_head did not resolve a linked worktree ref through commondir",
            failures,
        )
        (worktree_admin / "HEAD").write_text("ref: refs/heads/packed\n", encoding="utf-8")
        expect(
            read_git_head(worktree) == (packed_sha, "refs/heads/packed"),
            "read_git_head did not fall back to packed-refs in the common dir",
            failures,
        )

    # ZP-5: the Z.ai edge feeds the same strict JSON/candidate boundary.
    zai_trace = ModelTrace(
        provider=ZAI_PROVIDER_NAME,
        model="glm-5.3",
        model_version="provider-managed-unknown",
    )
    good_outcome = execute_trial_case(
        case=delivery,
        model_trace=zai_trace,
        invoke=build_invoker(FakeTransport(body=content_body(fake_output(delivery)))),
        clock=lambda: "2026-09-29T12:00:00Z",
    )
    expect(good_outcome.invoked and good_outcome.run is not None, "zai accepted-path case did not run", failures)
    if good_outcome.run is not None:
        run = good_outcome.run
        expect(
            run["validation"]["status"] == "accepted_for_candidate_review",
            "zai model output did not pass the strict candidate boundary",
            failures,
        )
        expect(run["input_sha256"] == sha256_text(prompt), "zai run lost the exact prompt hash", failures)
        expect(
            run["raw_output_sha256"] == sha256_text(fake_output(delivery)),
            "zai run lost the exact response hash",
            failures,
        )
        expect(run["model_trace"]["provider"] == ZAI_PROVIDER_NAME, "zai run lost the provider trace", failures)
        expect(not schema_errors(run), f"zai accepted run is schema-invalid: {schema_errors(run)}", failures)
        try:
            validate_ai_extraction_run(queue_item=delivery["queue_item"], run=run)
        except AIExtractionBoundaryError as exc:
            failures.append(f"zai accepted run failed the extraction boundary: {exc}")
        expect(run["authority"]["canonical_mutation_authority"] is False, "zai run gained mutation authority", failures)
        expect(run["authority"]["publication_authority"] is False, "zai run gained publication authority", failures)

    bad_outcome = execute_trial_case(
        case=delivery,
        model_trace=zai_trace,
        invoke=build_invoker(FakeTransport(body=content_body("not-json"))),
        clock=lambda: "2026-09-29T12:01:00Z",
    )
    expect(bad_outcome.run is not None, "zai malformed-output case produced no run", failures)
    if bad_outcome.run is not None:
        rejected = bad_outcome.run
        expect(rejected["validation"]["status"] == "rejected", "zai malformed JSON was not rejected", failures)
        failed_checks = {
            check.get("check_id")
            for check in rejected.get("evaluation_trace", {}).get("checks", [])
            if isinstance(check, dict) and check.get("status") == "fail"
        }
        expect("strict-json-envelope" in failed_checks, "zai rejection lacks strict-json-envelope reason", failures)
        expect(not any(rejected["candidates"].values()), "zai rejection leaked candidates", failures)

    # ZP-6: Copilot path remains backward compatible.
    with argv("--output", "unused.json") as run_parse:
        parsed = parse_args()
        expect(parsed.provider == PROVIDER_COPILOT, "default provider is no longer copilot", failures)
        expect(parsed.model is None, "copilot default model stopped deferring to resolution", failures)
        expect(
            resolve_requested_model(parsed.provider, parsed.model) == "gpt-5.4",
            "copilot default model resolution changed",
            failures,
        )
        del run_parse
    try:
        with (
            redirect_stderr(io.StringIO()),
            argv("--provider", PROVIDER_COPILOT, "--base-url", "https://api.z.ai/api/paas/v4", "--output", "x"),
        ):
            parse_args()
        failures.append("--base-url was accepted for the copilot provider")
    except SystemExit:
        pass
    try:
        with (
            redirect_stderr(io.StringIO()),
            argv("--provider", PROVIDER_COPILOT, "--zai-endpoint", "prepaid", "--output", "x"),
        ):
            parse_args()
        failures.append("--zai-endpoint was accepted for the copilot provider")
    except SystemExit:
        pass
    try:
        with patch.dict(os.environ, {}, clear=True), argv("--provider", PROVIDER_COPILOT, "--output", "x"):
            trial_runner.main()
        failures.append("copilot path ran without Copilot credentials")
    except SystemExit:
        pass

    # ZP-7: main()-level Z.ai run with a fake transport — report trace, key
    # non-leakage, and unchanged authority flags.
    responses = {
        build_trial_prompt(case): gold_response(case)
        for case in cases
        if case["gold"]["expected_status"] != "blocked_before_invocation"
    }
    corpus_transport = CorpusTransport(responses)
    with tempfile.TemporaryDirectory() as tmpdir:
        report_path = Path(tmpdir) / "zai-report.json"
        captured = io.StringIO()
        with (
            patch.dict(
                os.environ,
                minimal_provider_env({ZAI_CREDENTIAL_ENV: SENTINEL_KEY}),
                clear=True,
            ),
            argv(
                "--provider", PROVIDER_ZAI,
                "--zai-endpoint", "coding-plan",
                "--output", str(report_path),
            ),
            patch.object(trial_runner, "zai_http_post_json", corpus_transport),
            redirect_stdout(captured),
        ):
            exit_code = trial_runner.main()
        expect(exit_code == 0, f"zai main() reported integrity failures (exit {exit_code})", failures)
        report_bytes = report_path.read_bytes()
        expect(b"\r\n" not in report_bytes, "report bytes were newline-translated on write (C3)", failures)
        report_text = report_bytes.decode("utf-8")
        expect(SENTINEL_KEY not in report_text, "credential leaked into the trial report", failures)
        expect(SENTINEL_KEY not in captured.getvalue(), "credential leaked into runner stdout", failures)
        report = json.loads(report_text)
        expect(report["provider"] == ZAI_PROVIDER_NAME, "report provider trace is wrong", failures)
        expect(report["requested_model"] == "glm-5.3", "report requested model is not the zai default", failures)
        expect(report["copilot_cli_version"] is None, "zai report invented a Copilot CLI version", failures)
        expect(
            report["report_version"] == "m4-model-extraction-live-trial-v0.6",
            "report version was not bumped for the contract-revision surface",
            failures,
        )
        # LTR-01: invoked-model quality and policy-gate quality are separate.
        expect(report["invoked_case_count"] == len(cases) - 1, "invoked case count is wrong", failures)
        expect(report["policy_gate_case_count"] == 1, "policy-gate case count is wrong", failures)
        expect(
            report["invoked_quality_case_pass_count"] == report["invoked_case_count"],
            "deterministic invoked outputs did not all pass invoked-model quality",
            failures,
        )
        expect(
            report["invoked_quality_case_pass_rate"] == 1.0,
            "invoked-model quality rate is not 1.0 for the deterministic corpus",
            failures,
        )
        expect(
            report["policy_gate_case_pass_count"] == 1 and report["policy_gate_case_pass_rate"] == 1.0,
            "policy-gate quality metrics are wrong",
            failures,
        )
        edge = report.get("provider_edge", {})
        expect(edge.get("driver") == "zai-openai-compatible-http", "report driver trace is wrong", failures)
        expect(
            edge.get("base_url") == ZAI_ENDPOINT_URLS["coding-plan"],
            "report base URL is not the selected official route",
            failures,
        )
        expect(edge.get("base_url_source") == "endpoint:coding-plan", "report base-URL source is wrong", failures)
        expect(edge.get("endpoint_mode") == "coding-plan", "report endpoint mode is wrong", failures)
        expect(edge.get("transport") == "python-stdlib-urllib", "report transport trace is wrong", failures)
        expect(edge.get("tools") == "none", "report tool trace is wrong", failures)
        expect(edge.get("max_response_bytes") == MAX_RESPONSE_BYTES, "report response bound is missing", failures)
        expect(
            edge.get("reasoning_configuration")
            == {"thinking_type": "enabled", "reasoning_effort": "max", "explicitly_pinned": True},
            "report reasoning configuration is not the pinned IRZ-04 setting",
            failures,
        )
        expect(
            ZAI_CREDENTIAL_ENV in str(edge.get("credential_source", "")),
            "report credential source is not the environment variable",
            failures,
        )
        expect(
            not any(isinstance(value, str) and SENTINEL_KEY in value for value in edge.values()),
            "credential leaked into provider_edge trace",
            failures,
        )
        # IRZ-05: the report is bound to the exact source revision and runtime,
        # and a SHA-256 sidecar pins the final report bytes.
        context = report.get("trial_context", {})
        expected_head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True
        ).stdout.strip()
        expect(context.get("git_head") == expected_head, "report git_head does not match rev-parse HEAD", failures)
        expect(
            read_git_head(ROOT)[0] == expected_head,
            "plumbing-based git reader diverges from git rev-parse",
            failures,
        )
        expect(
            isinstance(context.get("tracked_worktree_clean"), bool),
            "report did not record a boolean tracked-worktree cleanliness state",
            failures,
        )
        expect(
            context.get("runner_sha256") == hashlib.sha256(Path(trial_runner.__file__).read_bytes()).hexdigest(),
            "report runner_sha256 does not match the executing runner file",
            failures,
        )
        expect(
            context.get("corpus_sha256") == hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
            "report corpus_sha256 does not match the fixture file",
            failures,
        )
        sidecar_bytes = report_path.with_name(report_path.name + ".sha256").read_bytes()
        report_digest = hashlib.sha256(report_path.read_bytes()).hexdigest()
        expect(
            sidecar_bytes == f"{report_digest}  {report_path.name}\n".encode("utf-8"),
            "report SHA-256 sidecar does not match the exact bytes on disk (C3)",
            failures,
        )
        expect(SENTINEL_KEY not in sidecar_bytes.decode("utf-8"), "credential leaked into the SHA-256 sidecar", failures)
        summary = json.loads(captured.getvalue())
        expect(summary.get("report_sha256") == report_digest, "stdout summary lost the report SHA-256", failures)
        expect(summary.get("git_head") == expected_head, "stdout summary lost the git head", failures)
        expect(report["integrity_failure_count"] == 0, "fake zai transport run had integrity failures", failures)
        expect(report["invocation_count"] == len(cases) - 1, "zai run invocation count is wrong", failures)
        expect(report["blocked_before_invocation_count"] == 1, "restricted case was not blocked", failures)
        expect(
            report["quality_case_pass_count"] == len(cases),
            "deterministic zai corpus outputs lost quality parity with gold",
            failures,
        )
        qualification = report["qualification"]
        expect(qualification["canonical_mutation_authority"] is False, "report gained mutation authority", failures)
        expect(qualification["publication_authority"] is False, "report gained publication authority", failures)
        expect(qualification["synthetic_corpus_only"] is True, "report stopped claiming synthetic corpus only", failures)
        expect(
            json.loads(captured.getvalue())["provider"] == ZAI_PROVIDER_NAME,
            "stdout summary lost the provider trace",
            failures,
        )

        # ZP-8: environment endpoint override and explicit model flow into the trace.
        prepaid_transport = CorpusTransport(responses)
        with (
            patch.dict(
                os.environ,
                minimal_provider_env(
                    {
                        ZAI_CREDENTIAL_ENV: SENTINEL_KEY,
                        ZAI_BASE_URL_ENV: ZAI_ENDPOINT_URLS["prepaid"],
                    }
                ),
                clear=True,
            ),
            argv("--provider", PROVIDER_ZAI, "--model", "glm-4.7", "--max-cases", "1", "--output", str(report_path)),
            patch.object(trial_runner, "zai_http_post_json", prepaid_transport),
            redirect_stdout(io.StringIO()),
        ):
            exit_code = trial_runner.main()
        expect(exit_code == 0, "zai env-endpoint run had integrity failures", failures)
        prepaid_report = json.loads(report_path.read_text(encoding="utf-8"))
        expect(prepaid_report["requested_model"] == "glm-4.7", "explicit --model was ignored", failures)
        expect(
            prepaid_report["provider_edge"]["base_url"] == ZAI_ENDPOINT_URLS["prepaid"],
            "ZAI_BASE_URL prepaid endpoint was ignored",
            failures,
        )
        expect(
            prepaid_report["provider_edge"]["base_url_source"] == "env",
            "env-resolved base URL source is wrong",
            failures,
        )
        expect(
            prepaid_report["provider_edge"]["endpoint_mode"] == "prepaid",
            "endpoint_mode is not derived from the actually resolved route (C2)",
            failures,
        )
        expect(
            prepaid_transport.calls[0][0] == ZAI_ENDPOINT_URLS["prepaid"].rstrip("/") + "/chat/completions",
            "request did not target the environment-provided endpoint",
            failures,
        )

        # ZP-8b: an explicit endpoint mode that contradicts the resolved URL
        # fails closed instead of recording a losing mode (C2).
        contradicting_transport = CorpusTransport(responses)
        try:
            with (
                patch.dict(
                    os.environ,
                    minimal_provider_env(
                        {
                            ZAI_CREDENTIAL_ENV: SENTINEL_KEY,
                            ZAI_BASE_URL_ENV: ZAI_ENDPOINT_URLS["coding-plan"],
                        }
                    ),
                    clear=True,
                ),
                argv("--provider", PROVIDER_ZAI, "--zai-endpoint", "prepaid", "--output", str(report_path)),
                patch.object(trial_runner, "zai_http_post_json", contradicting_transport),
                redirect_stdout(io.StringIO()),
            ):
                trial_runner.main()
            failures.append("contradictory endpoint selection did not fail closed")
        except SystemExit:
            expect(not contradicting_transport.calls, "contradictory selection reached the transport", failures)

    # ZP-9: main() fails closed without ZAI_API_KEY even when Copilot tokens are
    # also absent, and without requiring any Copilot credential.
    try:
        with patch.dict(os.environ, {}, clear=True), argv("--provider", PROVIDER_ZAI, "--output", "x"):
            trial_runner.main()
        failures.append("zai main() ran without ZAI_API_KEY")
    except SystemExit:
        pass

    # ZP-9b: main() fails closed when no endpoint route is selected (IRZ-02).
    try:
        with (
            patch.dict(os.environ, minimal_provider_env({ZAI_CREDENTIAL_ENV: SENTINEL_KEY}), clear=True),
            argv("--provider", PROVIDER_ZAI, "--output", "x"),
        ):
            trial_runner.main()
        failures.append("zai main() ran without any endpoint selection")
    except SystemExit as exc:
        expect(
            "--zai-endpoint" in str(exc) or ZAI_BASE_URL_ENV in str(exc),
            "missing-endpoint failure does not explain the required selection",
            failures,
        )

    # ZP-10: the provider edge adds no governance/mutation imports to the runner.
    runner_source = Path(trial_runner.__file__).read_text(encoding="utf-8")
    for forbidden_import in ("from services.governance", "import services.governance"):
        expect(
            forbidden_import not in runner_source,
            f"runner acquired a governance import: {forbidden_import}",
            failures,
        )

    if failures:
        print("M4 Z.ai provider-edge validation FAILED:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print(
        "Validated the Z.ai provider edge: exact rendered prompt as sole model input with no "
        "tool surface and pinned reasoning configuration; environment-only credential with "
        "character rejection and redaction from errors, stdout, report, and sidecar; explicit "
        "coding-plan/prepaid endpoint selection restricted to official api.z.ai routes; strict "
        "duplicate-key/non-finite provider-envelope parsing; bounded response size; git-bound "
        "report provenance with SHA-256 sidecar; fail-closed HTTP/timeout/malformed-response "
        "behavior; identical strict JSON/candidate boundary as Copilot; backward-compatible "
        "copilot path; no canonical mutation, publication, Resolver/Verifier, or human-review "
        "authority."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
