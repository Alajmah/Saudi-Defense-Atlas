# M1 Public Projection — First-Pass Review

This review is frozen before the Wikibase read adapter is implemented. Findings here are discovery records, not retrospective justification.

## M1-PF01 — Canonical Entity projection is incomplete for public readback

**Area:** canonical backend / read projection

**Finding:** The M0 seed gives F-15SA, Boeing, and RSAF stable SDA IDs plus native labels/aliases, but it does not persist mandatory SDA Entity semantics such as `entity_type` and `record_status`. A public read adapter therefore cannot reconstruct schema-valid Entity records from canonical backend state alone.

**Severity:** High

**Confidence:** High

**Why it matters:** Filling those fields from frontend constants or a separate catalog would create a second factual truth store and break the knowledge-first architecture.

**Resolution plan:** Add explicit Entity read-projection properties and apply them to the existing domain items through an AMBER, human-approved `metadata_update` proposal. Equivalence must be based on SDA canonical ID, canonical payload hash, and an explicit read-projection version. The reader must reconstruct Entity records from those projected fields and native multilingual labels/aliases/descriptions.

---

## M1-PF02 — Raw Wikibase statement enumeration would leak legacy M0 trial semantics

**Area:** public fact admission / backend isolation

**Finding:** The M0 representation spike contains trial statements that are not valid public SDA facts under the later M1 evidentiary decisions, including a legacy F-15SA operator statement derived from delivery context.

**Severity:** High

**Confidence:** High

**Why it matters:** A reader that treats every Wikibase statement as a public fact would bypass SDA Claim/Event admission and reintroduce semantics already rejected during M1 review.

**Resolution plan:** The public reader may consume only statements/items carrying current SDA projection identity markers. Claim statements must carry an SDA Claim ID, payload hash, and accepted projection version. Event/item records must carry SDA record type and projection markers. Arbitrary unmarked M0 statements remain backend test history and are invisible to the public projector.

---

## M1-PF03 — Event public confidence is not persisted in the current M1 item projection

**Area:** Event projection completeness

**Finding:** The canonical Event schema requires confidence and the public EquipmentView exposes it, but the current M1 Event item projection does not persist Event confidence as a main statement.

**Severity:** High

**Confidence:** High

**Why it matters:** The read adapter must not recover confidence from proposal fixtures or hard-coded assumptions.

**Resolution plan:** Add a public-read projection marker and persist the Event's canonical confidence through a governed metadata update. The public reader fails closed if the current read marker or confidence field is absent.

## Qualification boundary

These findings concern read fidelity only. M1-F15 concurrent-writer uniqueness remains separately open; it does not block this read-only projection work, but production automated canonical writes remain unauthorized until it is resolved.
