#!/usr/bin/env python3
"""Run the bounded M4 real-model extraction trial through a provider edge.

Supported trial providers:

- ``copilot``: GitHub Copilot CLI subprocess (the original trial driver);
- ``zai``: Z.ai OpenAI-compatible HTTP API using only the Python standard
  library, with the credential read solely from the ``ZAI_API_KEY``
  environment variable.

The runner uses only the synthetic evaluation corpus. It captures AIExtractionRun
artifacts and aggregate quality/latency evidence; it does not read or write the
canonical knowledge backend and does not publish anything.

Both provider edges return only the exact assistant response text to the
provider-independent extraction boundary in
``services/intelligence/model_extraction_trial.py``. Neither edge adds tools,
function calling, repository/file/shell access, retrieval, MCPs, or autonomous
actions, and neither holds canonical mutation, publication, Resolver/Verifier,
or human-review authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable, Mapping

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_schemas import build_registry  # noqa: E402
from services.intelligence.ai_extraction_boundary import (  # noqa: E402
    AIExtractionBoundaryError,
    validate_ai_extraction_run,
)
from services.intelligence.model_extraction_trial import (  # noqa: E402
    ADAPTER_VERSION,
    ModelExtractionTrialError,
    ModelTrace,
    execute_trial_case,
    reject_schema_invalid_run,
)

DEFAULT_FIXTURE = ROOT / "tests" / "fixtures" / "m4-model-extraction-eval.json"

PROVIDER_COPILOT = "copilot"
PROVIDER_ZAI = "zai"
COPILOT_PROVIDER_NAME = "github-copilot-cli"
ZAI_PROVIDER_NAME = "zai-openai-compatible-api"
DEFAULT_MODELS = {PROVIDER_COPILOT: "gpt-5.4", PROVIDER_ZAI: "glm-5.3"}
# Z.ai documents separate OpenAI-compatible endpoints per account type and they
# are not interchangeable: the Coding Plan route serves coding scenarios, the
# prepaid/resource-package route serves general API usage. There is no silent
# default (IRZ-02): the operator must select a route explicitly, and the
# credential is only ever sent to the official api.z.ai host.
ZAI_ENDPOINT_URLS = {
    "coding-plan": "https://api.z.ai/api/coding/paas/v4",
    "prepaid": "https://api.z.ai/api/paas/v4",
}
ZAI_ALLOWED_HOST = "api.z.ai"
ZAI_CREDENTIAL_ENV = "ZAI_API_KEY"
ZAI_BASE_URL_ENV = "ZAI_BASE_URL"
# Any single provider response above this bound fails closed (IRZ-06). Expected
# assistant JSON is small; provider diagnostic bodies do not need more than this.
MAX_RESPONSE_BYTES = 1_048_576
# GLM-5.3 reasoning is pinned explicitly (IRZ-04) so the effective inference
# configuration is recorded in the report trace rather than left to a provider
# default: thinking is enabled and reasoning_effort defaults to max per current
# Z.ai documentation, so this pin preserves today's effective behavior.
ZAI_REASONING_CONFIGURATION = {"thinking_type": "enabled", "reasoning_effort": "max"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument(
        "--provider",
        choices=(PROVIDER_COPILOT, PROVIDER_ZAI),
        default=PROVIDER_COPILOT,
        help="trial provider edge (default: copilot)",
    )
    parser.add_argument(
        "--model",
        default=None,
        help=(
            "requested model "
            f"(default: {DEFAULT_MODELS[PROVIDER_COPILOT]} for copilot, "
            f"{DEFAULT_MODELS[PROVIDER_ZAI]} for zai)"
        ),
    )
    parser.add_argument("--copilot-command", default="copilot")
    parser.add_argument(
        "--zai-endpoint",
        choices=tuple(ZAI_ENDPOINT_URLS),
        default=None,
        help=(
            "required Z.ai route selection unless --base-url/ZAI_BASE_URL is "
            f"given: coding-plan={ZAI_ENDPOINT_URLS['coding-plan']} (Coding Plan "
            f"keys, coding scenarios), prepaid={ZAI_ENDPOINT_URLS['prepaid']} "
            "(resource packages / prepaid balance, general API usage)"
        ),
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help=(
            "explicit Z.ai base URL restricted to https://api.z.ai/ routes; "
            "resolved from this flag, then the ZAI_BASE_URL environment variable"
        ),
    )
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument("--max-cases", type=int, default=0, help="0 means all fixture cases")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.provider != PROVIDER_ZAI:
        if args.base_url is not None:
            parser.error("--base-url applies only to --provider zai")
        if args.zai_endpoint is not None:
            parser.error("--zai-endpoint applies only to --provider zai")
    return args


def load_cases(path: Path) -> tuple[str, list[dict[str, Any]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    version = payload.get("version")
    cases = payload.get("cases")
    if not isinstance(version, str) or not version:
        raise RuntimeError("evaluation fixture requires version")
    if not isinstance(cases, list) or not cases:
        raise RuntimeError("evaluation fixture requires non-empty cases")
    return version, cases


def build_schema_validator() -> Draft202012Validator:
    schemas, registry = build_registry()
    return Draft202012Validator(
        schemas["ai-extraction-run.schema.json"],
        registry=registry,
        format_checker=FormatChecker(),
    )


def cli_version(command: str) -> str:
    result = subprocess.run(
        [command, "--version"],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    rendered = (result.stdout or result.stderr).strip()
    if not rendered:
        raise RuntimeError("Copilot CLI returned empty version string")
    return rendered[:128]


def copilot_command_args(command: str, model: str, prompt: str) -> list[str]:
    """Return a prompt-mode command with no usable data-access/action tools."""

    return [
        command,
        "-p",
        prompt,
        "-s",
        "--stream=off",
        "--available-tools=ask_user",
        "--no-ask-user",
        "--deny-tool=read,write,shell,url,memory",
        "--disable-builtin-mcps",
        "--no-custom-instructions",
        "--no-remote",
        "--no-remote-export",
        "--no-experimental",
        "--no-auto-update",
        f"--model={model}",
    ]


def copilot_invoker(command: str, model: str, timeout_seconds: int) -> Callable[[str], str]:
    def invoke(prompt: str) -> str:
        result = subprocess.run(
            copilot_command_args(command, model, prompt),
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=os.environ.copy(),
        )
        if result.returncode != 0:
            stderr = result.stderr.strip()
            raise RuntimeError(
                f"Copilot CLI exited {result.returncode}: {stderr[:300] or 'no stderr'}"
            )
        return result.stdout

    return invoke


def resolve_requested_model(provider: str, model: str | None) -> str:
    if model is not None and model.strip():
        return model
    return DEFAULT_MODELS[provider]


def require_zai_api_key(env: Mapping[str, str] | None = None) -> str:
    """Read the credential from the environment only; never a CLI argument.

    The credential is sent verbatim in the Authorization header and redacted
    from diagnostics by exact substring replacement. Characters that HTTP
    rejects or that exception repr() would escape (control characters,
    whitespace at the edges, quotes, backslashes) could defeat that redaction
    (IRZ-01), so any such credential is rejected before a request exists.
    """

    source = os.environ if env is None else env
    api_key = source.get(ZAI_CREDENTIAL_ENV, "")
    if not api_key or not api_key.strip():
        raise SystemExit(
            "Z.ai credential missing; set the ZAI_API_KEY environment variable "
            "(credentials are never accepted as command-line arguments)"
        )
    if api_key != api_key.strip():
        raise SystemExit(
            "ZAI_API_KEY has leading or trailing whitespace; fix the "
            "environment variable rather than the runner"
        )
    rejected = [
        char
        for char in api_key
        if ord(char) < 0x20 or ord(char) == 0x7F or char in "\"'\\"
    ]
    if rejected:
        raise SystemExit(
            "ZAI_API_KEY contains control, quote, or backslash characters "
            f"({len(rejected)} found); fix the environment variable before "
            "running the trial"
        )
    return api_key


def validate_zai_base_url(base_url: str) -> None:
    """Fail closed on anything but an official api.z.ai HTTPS route (IRZ-02)."""

    parsed = urllib.parse.urlsplit(base_url)
    if parsed.scheme != "https":
        raise SystemExit("Z.ai base URL must use https")
    if parsed.username or parsed.password or "@" in (parsed.netloc or ""):
        raise SystemExit("Z.ai base URL must not embed credentials")
    if parsed.hostname != ZAI_ALLOWED_HOST:
        raise SystemExit(
            f"Z.ai base URL host must be the official {ZAI_ALLOWED_HOST} service; "
            "custom endpoints require a separate reviewed forcing function"
        )
    if parsed.port is not None:
        raise SystemExit("Z.ai base URL must use the default HTTPS port")
    if not (parsed.path or "").startswith("/api/"):
        raise SystemExit("Z.ai base URL path must be an /api/ route")
    if parsed.query or parsed.fragment:
        raise SystemExit("Z.ai base URL must not include a query or fragment")


def resolve_zai_base_url(
    base_url_arg: str | None,
    endpoint_mode: str | None,
    env: Mapping[str, str] | None = None,
) -> tuple[str, str]:
    """Resolve the endpoint as (url, source) with no silent default (IRZ-02).

    Precedence: ``--base-url`` flag, then the ``ZAI_BASE_URL`` environment
    variable, then the explicit ``--zai-endpoint`` route selection. Reaching
    none of them fails closed: the documented Coding Plan and prepaid routes
    are not interchangeable and the account type is the operator's fact to
    state, not the runner's to assume.
    """

    source = os.environ if env is None else env
    if base_url_arg:
        return base_url_arg, "flag"
    from_env = source.get(ZAI_BASE_URL_ENV, "").strip()
    if from_env:
        return from_env, "env"
    if endpoint_mode:
        return ZAI_ENDPOINT_URLS[endpoint_mode], f"endpoint:{endpoint_mode}"
    raise SystemExit(
        "Z.ai endpoint must be explicit; pass --zai-endpoint coding-plan|prepaid "
        "or set --base-url / ZAI_BASE_URL to an official https://api.z.ai/ route "
        "(the two documented routes are not interchangeable and there is no default)"
    )


def redact_secret(text: str, secret: str | None) -> str:
    rendered = str(text)
    if secret:
        rendered = rendered.replace(secret, "***REDACTED***")
    return rendered


class _RefuseRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Refuse every redirect so the bearer credential is never re-sent anywhere."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102
        return None


_ZAI_OPENER = urllib.request.build_opener(_RefuseRedirectHandler)


def zai_request_payload(model: str, prompt: str) -> bytes:
    """Encode the exact rendered trial prompt as one user message with no tool surface.

    The GLM-5.3 reasoning configuration is pinned explicitly (IRZ-04): thinking
    enabled with reasoning_effort max matches the documented provider default,
    so the pin records the effective behavior rather than changing it.
    """

    return json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "thinking": {"type": ZAI_REASONING_CONFIGURATION["thinking_type"]},
            "reasoning_effort": ZAI_REASONING_CONFIGURATION["reasoning_effort"],
        },
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _capped_read(fp: Any, limit: int = MAX_RESPONSE_BYTES) -> bytes:
    """Read at most ``limit`` bytes and fail closed above the bound (IRZ-06)."""

    data = fp.read(limit + 1)
    if data is None:
        data = b""
    if len(data) > limit:
        raise RuntimeError(f"Z.ai response exceeded the {limit}-byte bound")
    return data


def zai_http_post_json(
    url: str, payload: bytes, headers: dict[str, str], timeout_seconds: int
) -> tuple[int, bytes]:
    """Stdlib HTTPS POST returning (status, body) even for non-2xx statuses.

    Redirects are refused rather than followed: the request carries a bearer
    credential, so no 3xx may ever cause a re-POST to another origin. A refused
    redirect surfaces here as its 3xx status, which the caller fails closed on.
    Response bodies are read under the bounded-response limit (IRZ-06).
    """

    request = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    try:
        with _ZAI_OPENER.open(request, timeout=timeout_seconds) as response:
            return int(response.status), _capped_read(response)
    except urllib.error.HTTPError as exc:
        try:
            body = _capped_read(exc)
        except RuntimeError:
            body = b"<response exceeded bound>"
        except Exception:  # noqa: BLE001 - body is best-effort diagnostic context
            body = b""
        return int(exc.code), body


def _envelope_reject_constant(value: str) -> Any:
    raise ValueError(f"non-finite JSON constant is not allowed: {value}")


def _envelope_finite_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError(f"non-finite JSON number is not allowed: {value}")
    return parsed


def _envelope_object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    rendered: dict[str, Any] = {}
    for key, value in pairs:
        if key in rendered:
            raise ValueError(f"duplicate JSON object key is not allowed: {key}")
        rendered[key] = value
    return rendered


def zai_response_content(status: int, body: bytes) -> str:
    """Return the exact assistant text or fail closed with a specific reason.

    The provider envelope is parsed with the same strict semantics as the
    candidate boundary (IRZ-03): duplicate object keys and non-finite numbers
    are rejected so the selected assistant content is never ambiguous. The
    response size bound is enforced here as well, so injected transports cannot
    bypass it.
    """

    if len(body) > MAX_RESPONSE_BYTES:
        raise RuntimeError(f"Z.ai response exceeded the {MAX_RESPONSE_BYTES}-byte bound")
    if not 200 <= status < 300:
        excerpt = body[:4096].decode("utf-8", "replace")
        raise RuntimeError(
            f"Z.ai API returned HTTP {status}: {excerpt or 'empty body'}"
        )
    try:
        envelope = json.loads(
            body.decode("utf-8"),
            parse_constant=_envelope_reject_constant,
            parse_float=_envelope_finite_float,
            object_pairs_hook=_envelope_object_pairs,
        )
    except (UnicodeDecodeError, ValueError) as exc:
        raise RuntimeError(f"Z.ai response is not valid strict JSON: {exc}") from exc
    choices = envelope.get("choices") if isinstance(envelope, dict) else None
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("Z.ai response contains no choices")
    first = choices[0]
    message = first.get("message") if isinstance(first, dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if content is None:
        raise RuntimeError("Z.ai response has no assistant content")
    if not isinstance(content, str):
        raise RuntimeError(
            f"Z.ai assistant content has unexpected type {type(content).__name__}"
        )
    return content


def zai_invoker(
    *,
    model: str,
    api_key: str,
    base_url: str,
    timeout_seconds: int,
    transport: Callable[[str, bytes, dict[str, str], int], tuple[int, bytes]] | None = None,
) -> Callable[[str], str]:
    """Build a prompt invoker for the Z.ai OpenAI-compatible chat-completions endpoint.

    The invoker sends only the rendered trial prompt as model input, carries no
    tools, function calling, repository/file/shell access, retrieval, MCP, or
    autonomous-action surface, and fails closed on every transport, HTTP,
    parsing, and response-shape error. The credential appears only in the
    Authorization header and is redacted from every raised message.
    """

    resolved_transport = zai_http_post_json if transport is None else transport
    url = base_url.rstrip("/") + "/chat/completions"

    def invoke(prompt: str) -> str:
        payload = zai_request_payload(model, prompt)
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        try:
            status, body = resolved_transport(url, payload, headers, timeout_seconds)
            return zai_response_content(status, body)
        except RuntimeError as exc:
            # Redact the full message before bounding it, so a credential echoed
            # across a truncation boundary cannot survive partially.
            redacted = redact_secret(str(exc), api_key)
            raise RuntimeError(redacted[:512]) from exc
        except Exception as exc:  # noqa: BLE001 - provider edge fails closed on anything
            redacted = redact_secret(f"Z.ai transport failure: {exc!r}", api_key)
            raise RuntimeError(redacted[:512]) from exc

    return invoke


def normalize_name(value: str) -> str:
    return " ".join(value.casefold().split())


_HEX = "0123456789abcdef"


def _valid_commit_sha(value: str) -> bool:
    return len(value) in (40, 64) and all(char in _HEX for char in value.lower())


def read_git_head(root: Path) -> tuple[str, str]:
    """Resolve (head_sha, ref) from .git plumbing without a subprocess (IRZ-05)."""

    git_path = root / ".git"
    if git_path.is_file():
        marker = git_path.read_text(encoding="utf-8").strip()
        if not marker.startswith("gitdir:"):
            raise RuntimeError("unsupported .git file layout")
        git_dir = Path(marker[len("gitdir:"):].strip())
        if not git_dir.is_absolute():
            git_dir = root / git_dir
    elif git_path.is_dir():
        git_dir = git_path
    else:
        raise RuntimeError("no .git directory at the repository root")

    head = (git_dir / "HEAD").read_text(encoding="utf-8").strip()
    if head.startswith("ref: "):
        ref = head[len("ref: "):].strip()
        ref_file = git_dir / ref
        sha = ""
        if ref_file.is_file():
            sha = ref_file.read_text(encoding="utf-8").strip()
        else:
            packed = git_dir / "packed-refs"
            if packed.is_file():
                for line in packed.read_text(encoding="utf-8").splitlines():
                    parts = line.split()
                    if len(parts) == 2 and parts[1] == ref:
                        sha = parts[0]
                        break
        if not _valid_commit_sha(sha):
            raise RuntimeError(f"git ref {ref} did not resolve to a commit SHA")
        return sha, ref
    if _valid_commit_sha(head):
        return head, "detached"
    raise RuntimeError("git HEAD is neither a ref nor a commit SHA")


def tracked_worktree_clean(root: Path) -> bool | None:
    """Report tracked-worktree cleanliness, or None when git is unavailable."""

    try:
        result = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain", "--untracked-files=no"],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return not result.stdout.strip()


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_trial_context(root: Path, fixture: Path) -> dict[str, Any]:
    """Bind the report to the exact source revision and runtime (IRZ-05)."""

    sha, ref = read_git_head(root)
    clean = tracked_worktree_clean(root)
    return {
        "git_head": sha,
        "git_ref": ref,
        "tracked_worktree_clean": clean,
        "tracked_worktree_clean_source": (
            "git-status-porcelain-tracked-only" if clean is not None else "git-unavailable"
        ),
        "python_version": platform.python_version(),
        "platform": platform.platform(terse=True),
        "runner_sha256": _file_sha256(Path(__file__).resolve()),
        "boundary_sha256": _file_sha256(
            root / "services" / "intelligence" / "model_extraction_trial.py"
        ),
        "corpus_sha256": _file_sha256(fixture),
    }


def _entity_names_by_id(run: dict[str, Any]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for entity in run.get("candidates", {}).get("entities", []):
        if not isinstance(entity, dict):
            continue
        candidate_id = entity.get("candidate_id")
        names = entity.get("names")
        if not isinstance(candidate_id, str) or not isinstance(names, dict):
            continue
        result[candidate_id] = {
            normalize_name(value)
            for value in names.values()
            if isinstance(value, str) and value.strip()
        }
    return result


def _ref_has_name(ref: Any, expected_name: str, names_by_id: dict[str, set[str]]) -> bool:
    if not isinstance(ref, dict) or ref.get("kind") != "candidate_entity":
        return False
    candidate_id = ref.get("candidate_id")
    return (
        isinstance(candidate_id, str)
        and normalize_name(expected_name) in names_by_id.get(candidate_id, set())
    )


def _localized_names_match(actual: Any, expected: Any) -> bool:
    if not isinstance(actual, dict) or not isinstance(expected, dict):
        return False
    if set(actual) != set(expected):
        return False
    return all(
        isinstance(actual.get(locale), str)
        and isinstance(value, str)
        and normalize_name(actual[locale]) == normalize_name(value)
        for locale, value in expected.items()
    )


def _evidence_matches(actual: Any, expected: Any, _: dict[str, set[str]]) -> bool:
    if not isinstance(actual, dict) or not isinstance(expected, dict):
        return False
    for key in ("document_id", "locator", "excerpt_sha256", "capture_assessment"):
        if actual.get(key) != expected.get(key):
            return False
    return True


def _entity_matches(actual: Any, expected: Any, _: dict[str, set[str]]) -> bool:
    if not isinstance(actual, dict) or not isinstance(expected, dict):
        return False
    return (
        actual.get("entity_type") == expected.get("entity_type")
        and actual.get("subtype") == expected.get("subtype")
        and _localized_names_match(actual.get("names"), expected.get("names"))
        and actual.get("aliases", []) == expected.get("aliases", [])
    )


def _value_matches(actual: Any, expected: Any, names_by_id: dict[str, set[str]]) -> bool:
    if not isinstance(actual, dict) or not isinstance(expected, dict):
        return False
    expected_kind = expected.get("kind")
    if actual.get("kind") != expected_kind:
        return False
    if expected_kind == "candidate_entity":
        entity_name = expected.get("entity_name")
        return isinstance(entity_name, str) and _ref_has_name(actual, entity_name, names_by_id)
    return actual == expected


def _claim_matches(actual: Any, expected: Any, names_by_id: dict[str, set[str]]) -> bool:
    if not isinstance(actual, dict) or not isinstance(expected, dict):
        return False
    if actual.get("predicate_id") != expected.get("predicate_id"):
        return False
    subject_name = expected.get("subject_name")
    if not isinstance(subject_name, str) or not _ref_has_name(
        actual.get("subject"), subject_name, names_by_id
    ):
        return False
    if not _value_matches(actual.get("value"), expected.get("value"), names_by_id):
        return False

    if "validity" in expected:
        expected_validity = expected.get("validity")
        if expected_validity is None:
            if "validity" in actual:
                return False
        elif actual.get("validity") != expected_validity:
            return False

    if "extraction_assessment" in expected and (
        actual.get("extraction_assessment") != expected.get("extraction_assessment")
    ):
        return False
    return True


def _event_matches(actual: Any, expected: Any, names_by_id: dict[str, set[str]]) -> bool:
    if not isinstance(actual, dict) or not isinstance(expected, dict):
        return False
    if actual.get("event_type") != expected.get("event_type"):
        return False
    if actual.get("occurred_at") != expected.get("occurred_at"):
        return False
    if "ended_at" in expected and actual.get("ended_at") != expected.get("ended_at"):
        return False
    if "extraction_assessment" in expected and (
        actual.get("extraction_assessment") != expected.get("extraction_assessment")
    ):
        return False

    actual_participants = actual.get("participants")
    expected_participants = expected.get("participants", [])
    if not isinstance(actual_participants, list) or not isinstance(expected_participants, list):
        return False
    if len(actual_participants) != len(expected_participants):
        return False
    unmatched = list(range(len(actual_participants)))
    for wanted in expected_participants:
        if not isinstance(wanted, dict):
            return False
        wanted_name = wanted.get("entity_name")
        wanted_role = wanted.get("role")
        match_index = next(
            (
                index
                for index in unmatched
                if isinstance(actual_participants[index], dict)
                and actual_participants[index].get("role") == wanted_role
                and isinstance(wanted_name, str)
                and _ref_has_name(
                    actual_participants[index].get("entity"), wanted_name, names_by_id
                )
            ),
            None,
        )
        if match_index is None:
            return False
        unmatched.remove(match_index)

    actual_related = actual.get("related_entities")
    expected_related = expected.get("related_entity_names", [])
    if not isinstance(actual_related, list) or not isinstance(expected_related, list):
        return False
    if len(actual_related) != len(expected_related):
        return False
    unmatched_related = list(range(len(actual_related)))
    for wanted_name in expected_related:
        match_index = next(
            (
                index
                for index in unmatched_related
                if isinstance(wanted_name, str)
                and _ref_has_name(actual_related[index], wanted_name, names_by_id)
            ),
            None,
        )
        if match_index is None:
            return False
        unmatched_related.remove(match_index)
    return True


def _all_expected_records_match(
    actual_records: Any,
    expected_records: Any,
    matcher: Callable[[Any, Any, dict[str, set[str]]], bool],
    names_by_id: dict[str, set[str]],
) -> tuple[bool, list[int]]:
    if not isinstance(actual_records, list) or not isinstance(expected_records, list):
        return False, []
    if len(actual_records) != len(expected_records):
        return False, list(range(len(expected_records)))
    unmatched_actual = list(range(len(actual_records)))
    missing_expected: list[int] = []
    for expected_index, expected in enumerate(expected_records):
        match_index = next(
            (
                index
                for index in unmatched_actual
                if matcher(actual_records[index], expected, names_by_id)
            ),
            None,
        )
        if match_index is None:
            missing_expected.append(expected_index)
        else:
            unmatched_actual.remove(match_index)
    return not missing_expected and not unmatched_actual, missing_expected


def evaluate_case(
    case: dict[str, Any],
    *,
    invoked: bool,
    blocked: bool,
    run: dict[str, Any] | None,
) -> dict[str, Any]:
    gold = case.get("gold")
    if not isinstance(gold, dict):
        return {"pass": False, "checks": [{"id": "gold-present", "pass": False}]}
    expected_status = gold.get("expected_status")
    checks: list[dict[str, Any]] = []

    if expected_status == "blocked_before_invocation":
        checks.append(
            {
                "id": "blocked-before-invocation",
                "pass": blocked and not invoked and run is None,
            }
        )
        return {"pass": all(check["pass"] for check in checks), "checks": checks}

    if run is None:
        return {"pass": False, "checks": [{"id": "run-present", "pass": False}]}

    observed_status = run.get("validation", {}).get("status")
    checks.append(
        {
            "id": "status",
            "pass": observed_status == expected_status,
            "observed": observed_status,
            "expected": expected_status,
        }
    )

    if expected_status == "rejected":
        expected_check = gold.get("expected_rejection_check")
        failed_checks = {
            check.get("check_id")
            for check in run.get("evaluation_trace", {}).get("checks", [])
            if isinstance(check, dict) and check.get("status") == "fail"
        }
        candidates = run.get("candidates")
        candidate_arrays_empty = (
            isinstance(candidates, dict)
            and all(
                candidates.get(name) == []
                for name in ("evidence", "entities", "claims", "events")
            )
        )
        checks.extend(
            [
                {
                    "id": "expected-rejection-check",
                    "pass": isinstance(expected_check, str) and expected_check in failed_checks,
                    "expected": expected_check,
                    "observed": sorted(
                        value for value in failed_checks if isinstance(value, str)
                    ),
                },
                {
                    "id": "rejected-candidates-empty",
                    "pass": candidate_arrays_empty,
                },
            ]
        )
        return {"pass": all(check["pass"] for check in checks), "checks": checks}

    if expected_status != "accepted_for_candidate_review" or observed_status != expected_status:
        return {"pass": False, "checks": checks}

    candidates = run.get("candidates")
    if not isinstance(candidates, dict):
        checks.append({"id": "candidate-object", "pass": False})
        return {"pass": False, "checks": checks}

    names_by_id = _entity_names_by_id(run)
    expected_specs = {
        "evidence": (gold.get("expected_evidence"), _evidence_matches),
        "entities": (gold.get("expected_entities"), _entity_matches),
        "claims": (gold.get("expected_claims"), _claim_matches),
        "events": (gold.get("expected_events"), _event_matches),
    }
    for name, (expected_records, matcher) in expected_specs.items():
        actual_records = candidates.get(name)
        matched, missing = _all_expected_records_match(
            actual_records,
            expected_records,
            matcher,
            names_by_id,
        )
        checks.append(
            {
                "id": f"{name}-semantics",
                "pass": matched,
                "missing_expected_indexes": missing,
                "observed_count": len(actual_records) if isinstance(actual_records, list) else None,
                "expected_count": len(expected_records) if isinstance(expected_records, list) else None,
            }
        )

    return {"pass": all(check["pass"] for check in checks), "checks": checks}


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * fraction)))
    return ordered[index]


def main() -> int:
    args = parse_args()
    if args.timeout_seconds < 1:
        raise SystemExit("--timeout-seconds must be positive")
    if args.max_cases < 0:
        raise SystemExit("--max-cases must be >= 0")

    corpus_version, cases = load_cases(args.fixture)
    if args.max_cases:
        cases = cases[: args.max_cases]

    try:
        trial_context = build_trial_context(ROOT, args.fixture)
    except (OSError, RuntimeError) as exc:
        raise SystemExit(
            f"unable to bind trial report to the source revision (IRZ-05): {exc}"
        ) from exc
    if trial_context["tracked_worktree_clean"] is False:
        print(
            "WARNING: tracked worktree is dirty; live evidence must come from a "
            "clean checkout of the independently reviewed tip",
            file=sys.stderr,
        )

    requested_model = resolve_requested_model(args.provider, args.model)

    if args.provider == PROVIDER_ZAI:
        api_key = require_zai_api_key()
        base_url, base_url_source = resolve_zai_base_url(args.base_url, args.zai_endpoint)
        validate_zai_base_url(base_url)
        version = None
        trace = ModelTrace(
            provider=ZAI_PROVIDER_NAME,
            model=requested_model,
            model_version="provider-managed-unknown",
            adapter_version=ADAPTER_VERSION,
        )
        invoke = zai_invoker(
            model=requested_model,
            api_key=api_key,
            base_url=base_url,
            timeout_seconds=args.timeout_seconds,
        )
        provider_edge = {
            "driver": "zai-openai-compatible-http",
            "base_url": base_url,
            "base_url_source": base_url_source,
            "endpoint_mode": args.zai_endpoint,
            "credential_source": f"{ZAI_CREDENTIAL_ENV} environment variable",
            "transport": "python-stdlib-urllib",
            "tools": "none",
            "max_response_bytes": MAX_RESPONSE_BYTES,
            "reasoning_configuration": {
                **ZAI_REASONING_CONFIGURATION,
                "explicitly_pinned": True,
            },
        }
    else:
        if not any(
            os.environ.get(name)
            for name in ("COPILOT_GITHUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN")
        ):
            raise SystemExit(
                "Copilot CLI credential missing; set COPILOT_GITHUB_TOKEN "
                "(preferred for this personal-repository trial), GH_TOKEN, or GITHUB_TOKEN"
            )

        version = cli_version(args.copilot_command)
        trace = ModelTrace(
            provider=COPILOT_PROVIDER_NAME,
            model=requested_model,
            model_version="provider-managed-unknown",
            adapter_version=ADAPTER_VERSION,
        )
        invoke = copilot_invoker(args.copilot_command, requested_model, args.timeout_seconds)
        provider_edge = {
            "driver": "github-copilot-cli-subprocess",
            "base_url": None,
            "base_url_source": None,
            "endpoint_mode": None,
            "credential_source": (
                "COPILOT_GITHUB_TOKEN / GH_TOKEN / GITHUB_TOKEN environment"
            ),
            "transport": "copilot-cli-subprocess",
            "tools": "ask_user only and disabled; read/write/shell/url/memory denied",
        }
    try:
        trace.as_dict()
    except ModelExtractionTrialError as exc:
        raise SystemExit(f"invalid model trace: {exc}") from exc

    validator = build_schema_validator()

    results: list[dict[str, Any]] = []
    latencies: list[float] = []
    total_started = time.monotonic()
    invocation_count = 0
    validated_run_count = 0
    accepted = 0
    rejected = 0
    blocked = 0
    integrity_failures = 0

    for case in cases:
        case_started = time.monotonic()
        try:
            outcome = execute_trial_case(case=case, model_trace=trace, invoke=invoke)
        except (ModelExtractionTrialError, RuntimeError, subprocess.SubprocessError) as exc:
            results.append(
                {
                    "case_id": case.get("id"),
                    "invoked": True,
                    "blocked_reason": None,
                    "execution_error": str(exc)[:512],
                    "quality": {
                        "pass": False,
                        "checks": [{"id": "execution", "pass": False}],
                    },
                    "run": None,
                }
            )
            invocation_count += 1
            integrity_failures += 1
            continue

        latency = time.monotonic() - case_started
        if outcome.invoked:
            invocation_count += 1
            latencies.append(latency)
        else:
            blocked += 1

        run = outcome.run
        schema_failures: list[str] = []
        run_integrity_valid = False
        if run is not None:
            schema_failures = [error.message for error in validator.iter_errors(run)]
            if schema_failures:
                run = reject_schema_invalid_run(run, schema_failures)

            second_pass = [error.message for error in validator.iter_errors(run)]
            if second_pass:
                integrity_failures += 1
                schema_failures.extend(
                    f"rejected-run-invalid: {error}" for error in second_pass
                )
            else:
                try:
                    validate_ai_extraction_run(queue_item=case["queue_item"], run=run)
                except AIExtractionBoundaryError as exc:
                    integrity_failures += 1
                    schema_failures.append(f"boundary: {exc}")
                else:
                    run_integrity_valid = True
                    validated_run_count += 1

            if run_integrity_valid:
                if run["validation"]["status"] == "accepted_for_candidate_review":
                    accepted += 1
                else:
                    rejected += 1

        quality = evaluate_case(
            case,
            invoked=outcome.invoked,
            blocked=not outcome.invoked,
            run=run,
        )
        results.append(
            {
                "case_id": case["id"],
                "invoked": outcome.invoked,
                "blocked_reason": outcome.blocked_reason,
                "latency_seconds": round(latency, 6),
                "run_integrity_valid": run_integrity_valid,
                "schema_or_boundary_failures": schema_failures,
                "quality": quality,
                "run": run,
            }
        )

    total_seconds = time.monotonic() - total_started
    quality_passes = sum(1 for result in results if result["quality"]["pass"])
    throughput = invocation_count / total_seconds if total_seconds > 0 else None

    report = {
        "report_version": "m4-model-extraction-live-trial-v0.5",
        "corpus_version": corpus_version,
        "provider": trace.provider,
        "requested_model": requested_model,
        "provider_checkpoint_version": None,
        "copilot_cli_version": version,
        "provider_edge": provider_edge,
        "trial_context": trial_context,
        "adapter_version": ADAPTER_VERSION,
        "case_count": len(cases),
        "invocation_count": invocation_count,
        "validated_run_count": validated_run_count,
        "accepted_run_count": accepted,
        "rejected_run_count": rejected,
        "blocked_before_invocation_count": blocked,
        "integrity_failure_count": integrity_failures,
        "quality_case_pass_count": quality_passes,
        "quality_case_pass_rate": quality_passes / len(results) if results else None,
        "latency_seconds": {
            "median": statistics.median(latencies) if latencies else None,
            "p95_observed": percentile(latencies, 0.95),
            "max": max(latencies) if latencies else None,
        },
        "observed_throughput_invocations_per_second": throughput,
        "cost": {
            "measured": False,
            "value": None,
            "reason": (
                "Copilot CLI trial runner does not expose a stable per-invocation "
                "monetary-cost field; no cost claim is made."
            )
            if args.provider == PROVIDER_COPILOT
            else (
                "Z.ai trial driver does not expose a stable per-invocation "
                "monetary-cost field; no cost claim is made."
            ),
        },
        "qualification": {
            "candidate_only_boundary_exercised": validated_run_count > 0,
            "trial_integrity_clean": integrity_failures == 0,
            "quality_expectations_all_pass": bool(results)
            and quality_passes == len(results),
            "synthetic_corpus_only": True,
            "representative_batch_scale_qualified": False,
            "production_model_pipeline_qualified": False,
            "canonical_mutation_authority": False,
            "publication_authority": False,
        },
        "results": results,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    report_text = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    args.output.write_text(report_text, encoding="utf-8")
    report_sha256 = hashlib.sha256(report_text.encode("utf-8")).hexdigest()
    sidecar_path = args.output.with_name(args.output.name + ".sha256")
    sidecar_path.write_text(f"{report_sha256}  {args.output.name}\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "case_count": report["case_count"],
                "provider": report["provider"],
                "git_head": trial_context["git_head"],
                "report_sha256": report_sha256,
                "invocation_count": invocation_count,
                "validated_runs": validated_run_count,
                "accepted": accepted,
                "rejected": rejected,
                "blocked": blocked,
                "integrity_failures": integrity_failures,
                "quality_pass_rate": report["quality_case_pass_rate"],
                "output": str(args.output),
            },
            sort_keys=True,
            allow_nan=False,
        )
    )
    return 1 if integrity_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
