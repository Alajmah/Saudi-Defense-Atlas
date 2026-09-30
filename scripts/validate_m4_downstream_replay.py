#!/usr/bin/env python3
"""Offline downstream-preservation replay of the accepted v0.7 live-trial candidates.

Replays the preserved, hash-verified v0.7 evidence artifacts through the existing
Resolver/Verifier and the human-review boundary without any live model call, any
canonical backend, or any publication path. Proves: accepted candidate semantics
survive into AMBER human-review proposals; a correctly typed equipment_variant
manufacturer claim survives Resolver/Verifier semantics under the reconciled
predicate signature (while the actual v0.7 model output's mistyped claim is shown
honestly as blocked_unresolved, not hidden); rejected runs are isolated before the
resolver; and the replay itself grants zero canonical-mutation or publication
authority.
"""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_schemas import build_registry  # noqa: E402
from services.governance.editorial_decision_binding import (  # noqa: E402
    build_editorial_decision_binding,
)
from services.governance.proposal_auth import canonical_sha256  # noqa: E402
from services.intelligence.editorial_review_packet import (  # noqa: E402
    build_editorial_review_packet,
)
from services.intelligence.model_extraction_trial import (  # noqa: E402
    ModelTrace,
    build_extraction_run_from_model_output,
    build_trial_prompt,
)
from services.intelligence.resolver_verifier import (  # noqa: E402
    ResolverVerifierError,
    build_resolution_verification,
)

EVIDENCE = ROOT / "docs" / "evidence" / "m4" / "2026-09-30" / "m4-zai-live-rerun-v0.7.json"
SIDECAR = EVIDENCE.with_name(EVIDENCE.name + ".sha256")
FIXTURE = ROOT / "tests" / "fixtures" / "m4-model-extraction-eval.json"


def expect(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def main() -> int:
    failures: list[str] = []

    # Provenance gate (hard): replay only the frozen reviewed bytes, bound to
    # the generation-time corpus. The report must equal the preserved frozen
    # digest, its sidecar, and the corpus_sha256 its trial_context recorded at
    # generation time - so later drift of the report, sidecar, or fixture
    # cannot pass the gate together.
    FROZEN_REPORT_SHA256 = "06d9e8c7a60f70c3098886ae1076966047fef23fd74039df9377cb83380ba463"
    evidence_bytes = EVIDENCE.read_bytes()
    digest = hashlib.sha256(evidence_bytes).hexdigest()
    sidecar_digest = SIDECAR.read_text(encoding="utf-8").split()[0]
    expect(digest == sidecar_digest, "replayed evidence does not match its sidecar digest", failures)
    expect(digest == FROZEN_REPORT_SHA256, "replayed evidence is not the frozen v0.7 report", failures)
    report = json.loads(evidence_bytes.decode("utf-8"))
    corpus_bytes = FIXTURE.read_bytes()
    corpus = json.loads(corpus_bytes.decode("utf-8"))
    recorded_corpus_sha = report.get("trial_context", {}).get("corpus_sha256")
    # The report was generated from a CRLF Windows checkout; a Linux CI
    # checkout holds the same fixture with LF bytes. Compare the recorded
    # digest against both line-ending representations of the current content
    # so the gate binds to corpus content, not to one platform's checkout.
    normalized = corpus_bytes.replace(b"\r\n", b"\n")
    corpus_digests = {
        hashlib.sha256(normalized).hexdigest(),
        hashlib.sha256(normalized.replace(b"\n", b"\r\n")).hexdigest(),
    }
    expect(
        recorded_corpus_sha in corpus_digests,
        "current corpus fixture does not match the report's generation-time corpus_sha256",
        failures,
    )
    if failures:
        # Fail fast: the replay refuses to run on any provenance-gate failure
        # rather than accumulating findings while replaying unverified bytes.
        print("M4 downstream-preservation replay FAILED (provenance gate):")
        for failure in failures:
            print(f"- {failure}")
        return 1
    queue_by_case = {case["id"]: case["queue_item"] for case in corpus["cases"]}
    case_by_id = {case["id"]: case for case in corpus["cases"]}

    schemas, registry = build_registry()
    validators = {
        name: Draft202012Validator(
            schemas[name], registry=registry, format_checker=FormatChecker()
        )
        for name in (
            "ai-extraction-run.schema.json",
            "ai-resolution-verification-run.schema.json",
            "change-proposal.schema.json",
            "editorial-review-packet.schema.json",
            "review-decision.schema.json",
            "editorial-decision-binding.schema.json",
        )
    }

    def validate(schema_name: str, value: dict[str, Any]) -> None:
        errors = [error.message for error in validators[schema_name].iter_errors(value)]
        expect(not errors, f"{schema_name} rejected replayed artifact: {errors[:2]}", failures)

    # Canonical registry for the synthetic corpus, typed per the merged annotation
    # conventions (designation typing: Falcon-X is equipment_variant).
    def entity(entity_id: str, entity_type: str, names: dict[str, str]) -> dict[str, Any]:
        return {
            "id": entity_id,
            "entity_type": entity_type,
            "names": names,
            "aliases": [],
            "record_status": "active",
        }

    canonical_entities = [
        entity("SDA-ORG-ATLAS", "organization", {"en": "Atlas Aerospace"}),
        entity("SDA-EQUIP-FALCONX", "equipment_variant", {"en": "Falcon-X"}),
        entity("SDA-ORG-REAF", "organization", {"en": "Royal Example Air Force"}),
        entity("SDA-ORG-NOOR", "organization", {"ar": "شركة النور للصناعات"}),
        entity("SDA-PROC-SAQER", "procurement_program", {"ar": "برنامج الصقر"}),
        entity("SDA-EQUIP-ALPHA", "equipment", {"ar": "منظومة التدريب ألفا"}),
        entity("SDA-PROC-CEDAR", "procurement_program", {"en": "Project Cedar"}),
        entity("SDA-ORG-AIR-COLLEGE", "organization", {"en": "Example Air College"}),
    ]

    accepted_runs: dict[str, dict[str, Any]] = {}
    rejected_runs: dict[str, dict[str, Any]] = {}
    for result in report["results"]:
        run = result.get("run")
        if not isinstance(run, dict):
            continue
        if run.get("validation", {}).get("status") == "accepted_for_candidate_review":
            accepted_runs[result["case_id"]] = run
        elif run.get("validation", {}).get("status") == "rejected":
            rejected_runs[result["case_id"]] = run
    expect(len(accepted_runs) == 4, f"expected 4 accepted v0.7 runs, found {len(accepted_runs)}", failures)
    expect(len(rejected_runs) == 1, f"expected 1 rejected v0.7 run, found {len(rejected_runs)}", failures)

    # Rejection isolation: a rejected run never crosses the resolver boundary.
    for case_id, run in rejected_runs.items():
        try:
            build_resolution_verification(
                extraction_run=run,
                canonical_entities=canonical_entities,
                canonical_claims=[],
                canonical_events=[],
            )
            failures.append(f"rejected run {case_id} crossed the resolver boundary")
        except ResolverVerifierError:
            pass

    claim_outcomes: dict[str, dict[str, str]] = {}
    proposals: dict[str, dict[str, Any]] = {}
    for case_id, run in accepted_runs.items():
        validate("ai-extraction-run.schema.json", run)
        expect(
            run["authority"]["canonical_mutation_authority"] is False
            and run["authority"]["publication_authority"] is False,
            f"{case_id} replayed run carries canonical authority",
            failures,
        )
        resolution, proposal = build_resolution_verification(
            extraction_run=run,
            canonical_entities=canonical_entities,
            canonical_claims=[],
            canonical_events=[],
        )
        validate("ai-resolution-verification-run.schema.json", resolution)
        resolution_authority = resolution.get("authority", {})
        expect(
            resolution_authority.get("mode") == "proposal_preparation_only"
            and resolution_authority.get("approval_authority") is False
            and resolution_authority.get("canonical_mutation_authority") is False
            and resolution_authority.get("publication_authority") is False,
            f"{case_id} resolution run carries more than proposal-preparation authority",
            failures,
        )
        claim_outcomes[case_id] = {
            str(item["candidate_claim_id"]): str(item["outcome"])
            for item in resolution.get("claim_assessments", [])
        }
        if proposal is not None:
            proposals[case_id] = proposal
            validate("change-proposal.schema.json", proposal)
            expect(proposal["risk_class"] == "AMBER", f"{case_id} proposal is not AMBER", failures)
            expect(
                proposal["policy_outcome"] == "human_review_required",
                f"{case_id} proposal bypassed human review",
                failures,
            )
            packet = build_editorial_review_packet(
                queue_item=queue_by_case[case_id],
                extraction_run=run,
                resolution_run=resolution,
                proposal=proposal,
                created_at="2026-10-01T00:00:00Z",
            )
            validate("editorial-review-packet.schema.json", packet)
            expect(
                set(packet["source_document_ids"]) == {run["source_document_ids"][0]},
                f"{case_id} review packet lost Document provenance",
                failures,
            )
            decision = {
                "id": f"SDA-DECISION-REPLAY-{case_id}",
                "proposal_id": proposal["id"],
                "proposal_sha256": canonical_sha256(proposal),
                "decision": "approve",
                "decided_at": "2026-10-01T00:01:00Z",
                "decided_by": {
                    "kind": "human",
                    "id": "editor-replay-fixture",
                    "provider": None,
                    "model": None,
                    "version": None,
                },
                "reason_codes": ["evidence_sufficient"],
                "rationale": "offline downstream-preservation replay decision",
                "policy_references": ["AI_GOVERNANCE", "SOURCE_POLICY"],
            }
            validate("review-decision.schema.json", decision)
            binding = build_editorial_decision_binding(
                review_packet=packet,
                proposal=proposal,
                decision=decision,
                bound_at="2026-10-01T00:02:00Z",
            )
            validate("editorial-decision-binding.schema.json", binding)

    # Honest downstream consequence of the v0.7 typing miss: the model typed
    # Falcon-X as equipment, which does not resolve against the correctly typed
    # canonical registry, so its manufacturer claim is blocked unresolved.
    delivery_outcomes = claim_outcomes.get("TRIAL-EN-DELIVERY", {})
    expect(
        "blocked_unresolved" in delivery_outcomes.values(),
        "actual v0.7 delivery manufacturer claim was not blocked_unresolved "
        "(the mistyped-Falcon-X consequence must be shown, not hidden)",
        failures,
    )
    quantity_outcomes = claim_outcomes.get("TRIAL-EN-PROCUREMENT-QUANTITY", {})
    expect(
        list(quantity_outcomes.values()) == ["blocked_ambiguous"],
        f"quantity claim did not hit the resolver's corroboration-policy block: {quantity_outcomes}",
        failures,
    )

    # Corrected-typing regression (the PR #36 review obligation). The
    # counterfactual is a clearly labeled DERIVED SYNTHETIC run built through
    # the deterministic extraction boundary: the preserved delivery run's
    # candidate envelope with Falcon-X typed per the merged designation
    # convention, re-processed end to end so the synthetic run carries its own
    # extraction-run identity, input/raw-output hashes, model trace, and
    # timestamps - never the preserved run's audit identity.
    preserved_delivery = accepted_runs.get("TRIAL-EN-DELIVERY")
    expect(preserved_delivery is not None, "delivery run missing from v0.7 evidence", failures)
    if preserved_delivery is not None:
        import copy as _copy

        corrected_envelope = _copy.deepcopy(preserved_delivery["candidates"])
        falcon = next(
            (
                item
                for item in corrected_envelope["entities"]
                if "Falcon-X" in (item.get("names") or {}).values()
            ),
            None,
        )
        expect(falcon is not None, "corrected replay could not find the Falcon-X candidate", failures)
        if falcon is not None:
            falcon["entity_type"] = "equipment_variant"
            delivery_case = case_by_id["TRIAL-EN-DELIVERY"]
            synthetic_trace = ModelTrace(
                provider="downstream-replay",
                model="synthetic-corrected-delivery",
                model_version="derived-from-v0.7-evidence",
            )
            corrected = build_extraction_run_from_model_output(
                case=delivery_case,
                model_trace=synthetic_trace,
                prompt=build_trial_prompt(delivery_case),
                raw_output=json.dumps(corrected_envelope, ensure_ascii=False, separators=(",", ":")),
                started_at="2026-10-01T00:00:00Z",
                completed_at="2026-10-01T00:00:01Z",
            )
            expect(
                corrected["validation"]["status"] == "accepted_for_candidate_review",
                "derived synthetic corrected run did not pass the extraction boundary",
                failures,
            )
            expect(
                corrected["id"] != preserved_delivery["id"],
                "derived synthetic run reused the preserved run's audit identity",
                failures,
            )
            expect(
                corrected["model_trace"]["provider"] == "downstream-replay",
                "derived synthetic run lost its synthetic provenance label",
                failures,
            )
            validate("ai-extraction-run.schema.json", corrected)
            resolution, proposal = build_resolution_verification(
                extraction_run=corrected,
                canonical_entities=canonical_entities,
                canonical_claims=[],
                canonical_events=[],
            )
            validate("ai-resolution-verification-run.schema.json", resolution)
            corrected_authority = resolution.get("authority", {})
            expect(
                corrected_authority.get("mode") == "proposal_preparation_only"
                and corrected_authority.get("canonical_mutation_authority") is False,
                "corrected replay resolution gained authority",
                failures,
            )
            corrected_outcomes = {
                str(item["candidate_claim_id"]): str(item["outcome"])
                for item in resolution.get("claim_assessments", [])
            }
            manufacturer_outcomes = [
                outcome
                for candidate in corrected_envelope["claims"]
                if candidate.get("predicate_id") == "manufacturer.manufactures.equipment"
                for outcome in [corrected_outcomes.get(str(candidate.get("candidate_id")))]
            ]
            expect(
                manufacturer_outcomes == ["new"],
                f"correctly typed variant manufacturer claim did not survive the resolver: "
                f"{manufacturer_outcomes}",
                failures,
            )
            expect(proposal is not None, "corrected replay produced no AMBER proposal", failures)
            if proposal is not None:
                validate("change-proposal.schema.json", proposal)
                expect(proposal["risk_class"] == "AMBER", "corrected proposal is not AMBER", failures)
                predicates = [
                    mutation.get("payload", {}).get("predicate_id")
                    for mutation in proposal.get("mutations", [])
                ]
                expect(
                    "manufacturer.manufactures.equipment" in predicates,
                    "corrected AMBER proposal does not carry the variant manufacturer claim",
                    failures,
                )

    # The replay grants no canonical or publication authority: no canonical
    # backend is invoked or instantiated anywhere in this script, and every
    # replayed artifact remains proposal/decision data bound to human review.
    expect(
        all(not run["authority"]["canonical_mutation_authority"] for run in accepted_runs.values()),
        "a replayed run claimed canonical mutation authority",
        failures,
    )

    if failures:
        print("M4 downstream-preservation replay FAILED:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print(
        "Validated offline downstream preservation of the v0.7 live-trial candidates: "
        "hash-verified evidence replay; rejected run isolated before the resolver; "
        "accepted runs resolved with per-claim outcomes recorded (quantity claim blocked by "
        "corroboration policy; mistyped Falcon-X claim blocked_unresolved and shown, not hidden); "
        "AMBER human-review proposals, packets, human decisions, and exact bindings schema-valid "
        "with Document provenance preserved; correctly typed equipment_variant manufacturer claim "
        "survives the reconciled Resolver/Verifier signature into the AMBER proposal; zero "
        "canonical-mutation or publication authority exercised."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
