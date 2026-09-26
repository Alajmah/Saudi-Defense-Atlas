# M1 Public Projection — First-Pass Review

This review records findings discovered before and during implementation of the Wikibase public read adapter and the bounded F-15SA public page.

## M1-PF01 — Canonical Entity projection incomplete for public readback — RESOLVED

**Area:** canonical backend / read projection

The M0 seed gave F-15SA, Boeing, and RSAF stable SDA IDs plus native labels/aliases, but did not persist mandatory SDA Entity semantics such as `entity_type` and `record_status`.

**Resolution:** governed AMBER `metadata_update` mutations now project the mandatory Entity read fields into Wikibase. The public reader reconstructs SDA Entity records from those fields and native multilingual labels/aliases/descriptions rather than frontend constants.

---

## M1-PF02 — Raw Wikibase statement enumeration could leak M0 trial semantics — RESOLVED

**Area:** public fact admission / backend isolation

The M0 representation spike contains trial statements that are not valid public SDA facts under later M1 evidentiary decisions, including a legacy F-15SA operator statement derived from delivery context.

**Resolution:** public readback admits only current SDA-projected records carrying the required projection markers. The clean-stack verification asserts that the public F-15SA operator field remains `unknown` and that the legacy operator statement does not appear as a public Claim.

---

## M1-PF03 — Event public confidence absent from projection — RESOLVED

**Area:** Event projection completeness

The canonical Event schema requires confidence and `EquipmentView` exposes it, while the original M1 Event projection omitted it.

**Resolution:** governed Event public-read metadata persists confidence and the reader fails closed if required public-read Event metadata is incomplete.

---

## M1-PF04 — Legacy Entity migration timestamps were synthetic — RESOLVED

**Area:** temporal semantics

Using migration time as historical Entity `created_at` / `updated_at` would manufacture lifecycle facts.

**Resolution:** legacy Entity metadata migration payloads intentionally omit lifecycle timestamps when the historical values are not known.

---

## M1-PF05 — Material public facts could publish without supporting Evidence — RESOLVED

**Area:** publication admission

A non-empty Evidence list was insufficient because `contradicts` or `contextualizes` links alone could satisfy it.

**Resolution:** every material Claim/Event rendered publicly must resolve a complete Evidence → Document → Source chain and include at least one Evidence link whose role is `supports`. Regression tests prove context-only and contradiction-only records fail closed.

---

## M1-PF06 — Canonical payload hash was overloaded as public read-projection hash — RESOLVED

**Area:** projection integrity

The public reader reconstructs only the explicitly projected public subset, so comparing that subset against a canonical `payload_sha256` over a richer domain record is semantically invalid.

**Resolution:** `read_projection_sha256` is a distinct Wikibase property. Entity/Event public-read writes and readback validate the normalized public projection independently of canonical payload identity. Regression tests prove that changing a canonical field intentionally outside the public subset changes canonical identity without changing the public read-projection hash.

---

## M1-PF07 — Inbound manufacturer fact rendered as unknown — RESOLVED

**Area:** localized public rendering

The admitted manufacturer relation is inbound from the equipment page perspective (`Boeing → manufactures → F-15SA`). Rendering only the Claim object therefore selected F-15SA itself instead of Boeing.

**Resolution:** the web shell renders the Claim subject for inbound relational facts and the object for outbound entity facts. Static and clean-stack tests explicitly require `Boeing` / `بوينغ` on the respective localized pages.

## Qualification boundary

M1-F15 concurrent-writer canonical-ID uniqueness remains separately open. It does not block the read-only projection/public-page milestone, but production automated canonical mutation workers remain unauthorized until that coordination mechanism is selected and independently verified.
