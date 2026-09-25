#!/usr/bin/env python3
"""Seed the bounded M0 Wikibase representation trial.

This script intentionally mixes real, source-backed public test records with one
clearly synthetic conflict fixture. Nothing created by this spike is production
or publication-authorized data.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from wikibase_api import WikibaseAPI, item_value, quantity_value, time_value

ROOT = Path(__file__).resolve().parent
STATE_PATH = ROOT / "state.generated.json"

USAF_2011 = (
    "https://www.af.mil/News/Article-Display/Article/111940/"
    "saudi-arabia-to-purchase-84-f-15sa-upgrade-current-f-15-fleet/"
)
USAF_2020 = (
    "https://www.af.mil/News/Article-Display/Article/2444558/"
    "aflcmc-delivers-final-f-15sa-to-royal-saudi-air-force/"
)
ROBINS_2012 = (
    "https://www.robins.af.mil/News/Article-Display/Article/377976/"
    "robins-to-add-jobs-as-part-of-saudi-defense-package/"
)
DSCA_2026 = (
    "https://www.dsca.mil/Press-Media/Major-Arms-Sales/Article-Display/Article/4394629/"
    "kingdom-of-saudi-arabia-patriot-advanced-capability-3-missile-segment-enhanceme"
)
SPA_2026 = "https://www.spa.gov.sa/en/N2489881"


def property_defs() -> dict[str, dict[str, Any]]:
    return {
        "canonical_id": {
            "datatype": "external-id",
            "en": "SDA canonical ID",
            "ar": "معرّف أطلس الدفاع السعودي",
        },
        "claim_id": {
            "datatype": "external-id",
            "en": "SDA claim ID",
            "ar": "معرّف الادعاء في أطلس الدفاع السعودي",
        },
        "variant_of": {"datatype": "wikibase-item", "en": "variant of", "ar": "نسخة من"},
        "operator": {"datatype": "wikibase-item", "en": "operator", "ar": "المشغل"},
        "procurement_quantity": {
            "datatype": "quantity",
            "en": "procurement quantity",
            "ar": "كمية المشتريات",
        },
        "quantity_type": {"datatype": "string", "en": "quantity type", "ar": "نوع الكمية"},
        "point_in_time": {"datatype": "time", "en": "point in time", "ar": "نقطة زمنية"},
        "confidence": {"datatype": "string", "en": "SDA confidence", "ar": "درجة الثقة"},
        "document_id": {
            "datatype": "external-id",
            "en": "SDA document ID",
            "ar": "معرّف الوثيقة",
        },
        "reference_url": {"datatype": "url", "en": "reference URL", "ar": "رابط المصدر"},
        "evidence_locator": {
            "datatype": "string",
            "en": "evidence locator",
            "ar": "موضع الدليل",
        },
        "event_type": {"datatype": "string", "en": "SDA event type", "ar": "نوع الحدث"},
        "event_date": {"datatype": "time", "en": "event date", "ar": "تاريخ الحدث"},
        "participant": {"datatype": "wikibase-item", "en": "participant", "ar": "مشارك"},
        "related_item": {"datatype": "wikibase-item", "en": "related item", "ar": "عنصر مرتبط"},
        "fixture_status": {
            "datatype": "string",
            "en": "test fixture status",
            "ar": "حالة بيانات الاختبار",
        },
    }


def item_defs() -> dict[str, dict[str, Any]]:
    return {
        "rsaf": {
            "id": "SDA-ORG-RSAF",
            "labels": {"en": "Royal Saudi Air Force", "ar": "القوات الجوية الملكية السعودية"},
            "aliases": {"en": ["RSAF"], "ar": ["القوات الجوية السعودية"]},
            "descriptions": {"en": "Saudi military aviation service", "ar": "القوة الجوية العسكرية السعودية"},
        },
        "f15": {
            "id": "SDA-EQUIP-F15-FAMILY",
            "labels": {"en": "F-15 family", "ar": "عائلة إف-15"},
            "aliases": {"en": ["F-15"]},
        },
        "f15sa": {
            "id": "SDA-EQUIP-F15SA",
            "labels": {"en": "F-15SA", "ar": "إف-15 إس إيه"},
            "aliases": {"en": ["Saudi Advanced Eagle"]},
        },
        "boeing": {
            "id": "SDA-ORG-BOEING",
            "labels": {"en": "Boeing", "ar": "بوينغ"},
        },
        "pac3mse": {
            "id": "SDA-EQUIP-PAC3-MSE",
            "labels": {"en": "PAC-3 MSE", "ar": "PAC-3 MSE"},
            "aliases": {"en": ["PATRIOT Advanced Capability-3 Missile Segment Enhancement"]},
        },
        "pac_event": {
            "id": "SDA-EVENT-2026-01-30-PAC3MSE-FMS-NOTIFICATION",
            "labels": {
                "en": "PAC-3 MSE possible FMS approval — 30 January 2026",
                "ar": "إخطار/موافقة بيع عسكري محتمل PAC-3 MSE — 30 يناير 2026",
            },
        },
        "spears2026": {
            "id": "SDA-EXERCISE-SPEARS-OF-VICTORY-2026",
            "labels": {"en": "Spears of Victory 2026", "ar": "رماح النصر 2026"},
        },
        "synthetic_conflict": {
            "id": "SDA-TEST-CONFLICT-001",
            "labels": {
                "en": "Synthetic conflict fixture — not factual data",
                "ar": "بيانات اختبار تعارض اصطناعية — ليست معلومة واقعية",
            },
            "aliases": {"en": ["M0 synthetic conflict fixture"]},
        },
    }


def reference_snaks(api: WikibaseAPI, props: dict[str, str], document_id: str, url: str, locator: str) -> dict[str, list[dict[str, Any]]]:
    return {
        props["document_id"]: [
            api.make_snak(props["document_id"], "external-id", document_id)
        ],
        props["reference_url"]: [
            api.make_snak(props["reference_url"], "url", url)
        ],
        props["evidence_locator"]: [
            api.make_snak(props["evidence_locator"], "string", locator)
        ],
    }


def qualify(
    api: WikibaseAPI,
    props: dict[str, str],
    claim_guid: str,
    claim_id: str,
    *,
    confidence: str,
    point: str | None = None,
    quantity_type: str | None = None,
    fixture_status: str | None = None,
) -> None:
    api.add_qualifier(claim_guid, props["claim_id"], claim_id)
    api.add_qualifier(claim_guid, props["confidence"], confidence)
    if point:
        api.add_qualifier(claim_guid, props["point_in_time"], time_value(point, "day"))
    if quantity_type:
        api.add_qualifier(claim_guid, props["quantity_type"], quantity_type)
    if fixture_status:
        api.add_qualifier(claim_guid, props["fixture_status"], fixture_status)


def main() -> int:
    if STATE_PATH.exists():
        raise SystemExit(
            "state.generated.json already exists. Use ./reset.sh before recreating the spike."
        )

    base_url = os.environ.get("WIKIBASE_URL", "http://localhost:8181")
    username = os.environ.get("MW_ADMIN_NAME", "")
    password = os.environ.get("MW_ADMIN_PASS", "")
    if not username or not password:
        raise SystemExit("MW_ADMIN_NAME and MW_ADMIN_PASS must be exported from the spike .env")

    api = WikibaseAPI(base_url, username, password)
    api.login()

    state: dict[str, Any] = {"properties": {}, "items": {}, "claims": {}, "sources": {}}

    # Schema vocabulary first.
    for key, definition in property_defs().items():
        created = api.create_property(
            labels={"en": definition["en"], "ar": definition["ar"]},
            datatype=definition["datatype"],
        )
        state["properties"][key] = created.entity_id

    props: dict[str, str] = state["properties"]

    # Domain/test items receive a stable SDA ID independent from Q IDs.
    for key, definition in item_defs().items():
        created = api.create_item(
            labels=definition["labels"],
            aliases=definition.get("aliases"),
            descriptions=definition.get("descriptions"),
        )
        state["items"][key] = created.entity_id
        canonical_claim = api.add_claim(
            created.entity_id,
            props["canonical_id"],
            definition["id"],
            summary="SDA M0: map project ID to Wikibase backend ID",
        )
        state["claims"][f"{key}.canonical_id"] = canonical_claim

    items: dict[str, str] = state["items"]

    # F-15SA is a variant in the F-15 family.
    variant_claim = api.add_claim(
        items["f15sa"], props["variant_of"], item_value(items["f15"])
    )
    qualify(api, props, variant_claim, "SDA-CLAIM-F15SA-VARIANT", confidence="high")
    api.add_reference(
        variant_claim,
        reference_snaks(
            api,
            props,
            "SDA-DOC-USAF-2020-F15SA-FINAL-DELIVERY",
            USAF_2020,
            "Article states F-15SA is an advanced F-15S version and describes final deliveries to RSAF.",
        ),
    )
    state["claims"]["f15sa.variant_of"] = variant_claim

    # Publicly documented RSAF operation/delivery context.
    operator_claim = api.add_claim(
        items["f15sa"], props["operator"], item_value(items["rsaf"])
    )
    qualify(api, props, operator_claim, "SDA-CLAIM-F15SA-RSAF", confidence="verified", point="2020-12-10")
    api.add_reference(
        operator_claim,
        reference_snaks(
            api,
            props,
            "SDA-DOC-USAF-2020-F15SA-FINAL-DELIVERY",
            USAF_2020,
            "Final F-15SA aircraft delivered to the Royal Saudi Air Force on 10 December 2020.",
        ),
    )
    state["claims"]["f15sa.operator"] = operator_claim

    # Historical procurement quantity: 84 new F-15SA under the 2011 FMS LOA.
    f15_qty = api.add_claim(
        items["f15sa"], props["procurement_quantity"], quantity_value(84)
    )
    qualify(
        api,
        props,
        f15_qty,
        "SDA-CLAIM-F15SA-2011-FMS-QTY-84",
        confidence="verified",
        point="2011-12-30",
        quantity_type="purchase quantity in signed FMS Letter of Offer and Acceptance",
    )
    api.add_reference(
        f15_qty,
        reference_snaks(
            api,
            props,
            "SDA-DOC-USAF-2011-F15SA-LOA",
            USAF_2011,
            "USAF release: signed $29.4B FMS LOA for 84 F-15SA and upgrades to 70 F-15S.",
        ),
    )
    api.add_reference(
        f15_qty,
        reference_snaks(
            api,
            props,
            "SDA-DOC-ROBINS-2012-F15SA",
            ROBINS_2012,
            "USAF base release independently describes the 84-aircraft F-15SA agreement.",
        ),
    )
    state["claims"]["f15sa.procurement_quantity"] = f15_qty

    # 2026 DSCA notification: possible FMS, requested quantity 730. This is not
    # encoded as a contract or delivery.
    pac_qty = api.add_claim(
        items["pac3mse"], props["procurement_quantity"], quantity_value(730)
    )
    qualify(
        api,
        props,
        pac_qty,
        "SDA-CLAIM-PAC3MSE-2026-DSCA-QTY-730",
        confidence="verified",
        point="2026-01-30",
        quantity_type="requested quantity in approved possible FMS notification",
    )
    api.add_reference(
        pac_qty,
        reference_snaks(
            api,
            props,
            "SDA-DOC-DSCA-2026-26-13-PAC3MSE",
            DSCA_2026,
            "Transmittal 26-13 states possible FMS approval and Saudi request for 730 PAC-3 MSE missiles.",
        ),
    )
    state["claims"]["pac3mse.procurement_quantity"] = pac_qty

    pac_event_type = api.add_claim(
        items["pac_event"], props["event_type"], "procurement_approval_or_notification"
    )
    qualify(api, props, pac_event_type, "SDA-CLAIM-PAC3MSE-EVENT-TYPE", confidence="verified")
    api.add_reference(
        pac_event_type,
        reference_snaks(
            api,
            props,
            "SDA-DOC-DSCA-2026-26-13-PAC3MSE",
            DSCA_2026,
            "DSCA describes State Department determination approving a possible FMS and congressional notification.",
        ),
    )
    state["claims"]["pac_event.type"] = pac_event_type

    pac_event_date = api.add_claim(
        items["pac_event"], props["event_date"], time_value("2026-01-30", "day")
    )
    qualify(api, props, pac_event_date, "SDA-CLAIM-PAC3MSE-EVENT-DATE", confidence="verified")
    api.add_reference(
        pac_event_date,
        reference_snaks(api, props, "SDA-DOC-DSCA-2026-26-13-PAC3MSE", DSCA_2026, "DSCA release date: 30 January 2026."),
    )
    api.add_claim(items["pac_event"], props["related_item"], item_value(items["pac3mse"]))

    # Public exercise fixture, deliberately coarse: named exercise/date/RSAF participation only.
    exercise_type = api.add_claim(items["spears2026"], props["event_type"], "exercise")
    qualify(api, props, exercise_type, "SDA-CLAIM-SPEARS2026-TYPE", confidence="verified")
    api.add_reference(
        exercise_type,
        reference_snaks(api, props, "SDA-DOC-SPA-2026-SPEARS", SPA_2026, "SPA announcement identifies Spears of Victory 2026 as an RSAF-led military exercise."),
    )
    exercise_date = api.add_claim(
        items["spears2026"], props["event_date"], time_value("2026-01-18", "day")
    )
    qualify(api, props, exercise_date, "SDA-CLAIM-SPEARS2026-START", confidence="verified")
    api.add_reference(
        exercise_date,
        reference_snaks(api, props, "SDA-DOC-SPA-2026-SPEARS", SPA_2026, "SPA states the exercise runs from 18 January to 5 February 2026."),
    )
    participant = api.add_claim(
        items["spears2026"], props["participant"], item_value(items["rsaf"])
    )
    qualify(api, props, participant, "SDA-CLAIM-SPEARS2026-RSAF", confidence="verified")
    api.add_reference(
        participant,
        reference_snaks(api, props, "SDA-DOC-SPA-2026-SPEARS", SPA_2026, "SPA states the exercise is led by the Royal Saudi Air Force."),
    )

    # Synthetic contradiction mechanics test. These values are intentionally not factual.
    for suffix, value in (("A", 10), ("B", 12)):
        conflict = api.add_claim(
            items["synthetic_conflict"],
            props["procurement_quantity"],
            quantity_value(value),
            summary="SDA M0: synthetic conflict fixture only",
        )
        qualify(
            api,
            props,
            conflict,
            f"SDA-TEST-CLAIM-CONFLICT-{suffix}",
            confidence="unverified",
            point="2026-01-01",
            quantity_type="synthetic test quantity",
            fixture_status="SYNTHETIC_NON_PUBLIC",
        )
        api.add_reference(
            conflict,
            reference_snaks(
                api,
                props,
                f"SDA-TEST-DOC-{suffix}",
                f"https://example.invalid/sda-m0/{suffix.lower()}",
                "Synthetic evidence locator; not a real-world source.",
            ),
        )
        state["claims"][f"synthetic_conflict.{suffix}"] = conflict

    state["sources"] = {
        "USAF_2011": USAF_2011,
        "USAF_2020": USAF_2020,
        "ROBINS_2012": ROBINS_2012,
        "DSCA_2026": DSCA_2026,
        "SPA_2026": SPA_2026,
    }
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Seed complete. Backend mappings written to {STATE_PATH.name}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
