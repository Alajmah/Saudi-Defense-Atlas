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
    PROVIDER_COPILOT,
    PROVIDER_ZAI,
    ZAI_BASE_URL_ENV,
    ZAI_CREDENTIAL_ENV,
    ZAI_DEFAULT_BASE_URL,
    ZAI_PREPAID_BASE_URL,
    ZAI_PROVIDER_NAME,
    parse_args,
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


def build_invoker(transport: Any, *, model: str = "glm-5.3", base_url: str = ZAI_DEFAULT_BASE_URL):
    return zai_invoker(
        model=model,
        api_key=SENTINEL_KEY,
        base_url=base_url,
        timeout_seconds=30,
        transport=transport,
    )


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
            url == ZAI_DEFAULT_BASE_URL.rstrip("/") + "/chat/completions",
            f"request URL is not the documented chat-completions endpoint: {url}",
            failures,
        )
        request = json.loads(payload.decode("utf-8"))
        expect(
            set(request) == {"model", "messages", "stream"},
            f"request payload carries keys beyond model/messages/stream: {sorted(request)}",
            failures,
        )
        expect(request["model"] == "glm-5.3", "request payload lost the requested model", failures)
        expect(
            request["messages"] == [{"role": "user", "content": prompt}],
            "request payload input is not the exact rendered SDA trial prompt",
            failures,
        )
        expect(request["stream"] is False, "request payload did not disable streaming", failures)
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
        set(encoded) == {"model", "messages", "stream"},
        "zai_request_payload emits keys beyond model/messages/stream",
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
    ]
    for label, transport_case, must_contain in failure_matrix:
        expect_runtime_error(label, build_invoker(transport_case), failures, must_contain=must_contain)

    # ZP-4: endpoint resolution and validation.
    expect(ZAI_DEFAULT_BASE_URL != ZAI_PREPAID_BASE_URL, "Coding Plan and prepaid endpoints collapsed", failures)
    expect(
        resolve_zai_base_url(None, env={}) == (ZAI_DEFAULT_BASE_URL, "default"),
        "base-URL default is not the Coding Plan endpoint",
        failures,
    )
    expect(
        resolve_zai_base_url(None, env={ZAI_BASE_URL_ENV: ZAI_PREPAID_BASE_URL})
        == (ZAI_PREPAID_BASE_URL, "env"),
        "ZAI_BASE_URL environment override was ignored",
        failures,
    )
    expect(
        resolve_zai_base_url("https://proxy.invalid/v4", env={ZAI_BASE_URL_ENV: ZAI_PREPAID_BASE_URL})
        == ("https://proxy.invalid/v4", "flag"),
        "--base-url flag did not take precedence",
        failures,
    )
    for bad_url in (
        "http://api.z.ai/api/paas/v4",
        "https://user:pass@api.z.ai/api/paas/v4",
        "https://api.z.ai/api/paas/v4?token=x",
        "https://api.z.ai/api/paas/v4#fragment",
        "not-a-url",
        "",
    ):
        try:
            validate_zai_base_url(bad_url)
            failures.append(f"invalid base URL was accepted: {bad_url!r}")
        except SystemExit:
            pass
    try:
        validate_zai_base_url(ZAI_PREPAID_BASE_URL)
    except SystemExit:
        failures.append("valid prepaid base URL was rejected", )

    expect(resolve_requested_model(PROVIDER_ZAI, None) == "glm-5.3", "zai default model is not glm-5.3", failures)
    expect(resolve_requested_model(PROVIDER_COPILOT, None) == "gpt-5.4", "copilot default model changed", failures)
    expect(resolve_requested_model(PROVIDER_ZAI, "glm-4.7") == "glm-4.7", "explicit model override ignored", failures)

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
            patch.dict(os.environ, {ZAI_CREDENTIAL_ENV: SENTINEL_KEY}, clear=True),
            argv("--provider", PROVIDER_ZAI, "--output", str(report_path)),
            patch.object(trial_runner, "zai_http_post_json", corpus_transport),
            redirect_stdout(captured),
        ):
            exit_code = trial_runner.main()
        expect(exit_code == 0, f"zai main() reported integrity failures (exit {exit_code})", failures)
        report_text = report_path.read_text(encoding="utf-8")
        expect(SENTINEL_KEY not in report_text, "credential leaked into the trial report", failures)
        expect(SENTINEL_KEY not in captured.getvalue(), "credential leaked into runner stdout", failures)
        report = json.loads(report_text)
        expect(report["provider"] == ZAI_PROVIDER_NAME, "report provider trace is wrong", failures)
        expect(report["requested_model"] == "glm-5.3", "report requested model is not the zai default", failures)
        expect(report["copilot_cli_version"] is None, "zai report invented a Copilot CLI version", failures)
        edge = report.get("provider_edge", {})
        expect(edge.get("driver") == "zai-openai-compatible-http", "report driver trace is wrong", failures)
        expect(edge.get("base_url") == ZAI_DEFAULT_BASE_URL, "report base URL is not the resolved endpoint", failures)
        expect(edge.get("base_url_source") == "default", "report base-URL source is wrong", failures)
        expect(edge.get("transport") == "python-stdlib-urllib", "report transport trace is wrong", failures)
        expect(edge.get("tools") == "none", "report tool trace is wrong", failures)
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
                {ZAI_CREDENTIAL_ENV: SENTINEL_KEY, ZAI_BASE_URL_ENV: ZAI_PREPAID_BASE_URL},
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
            prepaid_report["provider_edge"]["base_url"] == ZAI_PREPAID_BASE_URL,
            "ZAI_BASE_URL prepaid endpoint was ignored",
            failures,
        )
        expect(
            prepaid_report["provider_edge"]["base_url_source"] == "env",
            "env-resolved base URL source is wrong",
            failures,
        )
        expect(
            prepaid_transport.calls[0][0] == ZAI_PREPAID_BASE_URL.rstrip("/") + "/chat/completions",
            "request did not target the environment-provided endpoint",
            failures,
        )

    # ZP-9: main() fails closed without ZAI_API_KEY even when Copilot tokens are
    # also absent, and without requiring any Copilot credential.
    try:
        with patch.dict(os.environ, {}, clear=True), argv("--provider", PROVIDER_ZAI, "--output", "x"):
            trial_runner.main()
        failures.append("zai main() ran without ZAI_API_KEY")
    except SystemExit:
        pass

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
        "tool surface; environment-only credential with redaction from errors, stdout, and "
        "report; Coding Plan vs prepaid endpoint resolution; fail-closed HTTP/timeout/"
        "malformed-response behavior; identical strict JSON/candidate boundary as Copilot; "
        "backward-compatible copilot path; no canonical mutation, publication, "
        "Resolver/Verifier, or human-review authority."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
