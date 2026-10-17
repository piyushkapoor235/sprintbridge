# SprintBridge — threat model: fakers, bypassers, and failure points

Design draft · 17 October 2026 · Companion to [architecture.md](architecture.md) and [business-model.md](business-model.md)

`architecture.md` protects **who can access what**: Supabase Auth, server-owned `role_grants`, RLS, and constrained RPCs. This document covers a different risk: **authenticated users who are dishonest**. They may fake skills, fabricate academic data, post fake jobs, collude as mentors, steal ideas, scrape candidates, or move payments off the platform. It also covers plain operational failures.

Each threat has a phase:
- **H**: hackathon (12 hours, no new tables)
- **P**: pilot (one university, manual operations)
- **Prod**: production

Owners follow the module ownership in `architecture.md` §5 and §11: P1 frontend, P2 core API and auth, P3 database/university/eligibility, P4 mentors/ventures. **Ops** means a future trust-and-safety or operations role.

---

## 1. Trust model

### 1.1 Evidence ladder

Each piece of evidence keeps its own label. They never merge into one generic "verified" badge.

| Level | Label | Source | Can it unlock hard eligibility? |
|---|---|---|---|
| 0 | `Self-declared` | User edits `profiles.skills[]` | No |
| 1 | `Portfolio linked` | User-supplied URL | No |
| 1.5 | `System-assessed` (level ≤ 3, score) | Automated evidence from the resume / OAuth GitHub / proof artifacts ([skill-intelligence.md](skill-intelligence.md) §4) | No (affects fit and ranking only) |
| 2 | `University-claimed` | University roster CSV | Hackathon demo only (labelled `Sample data`) |
| 3 | `Academic record verified` | External issuer: DigiLocker / NAD / ABC-APAAR, or background-verification fallback | Yes (pilot+) |
| 4 | `Mentor-verified` (skill, level, date, method, expiry; independently assigned) | Externally assigned verifier, audited | Yes, for skill gates |
| 5 | `Recruiter-confirmed` | Post-interview/offer feedback | Strengthens a level-4 badge, or revokes it |

### 1.2 Three rules the whole design rests on

1. **No party verifies itself.** A university does not vouch for its own students. A candidate does not choose their verifier. The payer does not control the outcome.
2. **Money buys an attempt, never a result or a ranking.** Verification fees are the same for pass and fail. Paid plans never change search order or verification outcomes.
3. **Every verified claim is server-owned.** Verified records live in tables the user cannot write through the Supabase Data API. A constrained server function writes them, using the same pattern as `role_grants` and `architecture.md` §6 rules 2, 6 and 7. `profiles.skills[]` stays self-declared forever.

---

## 2. Universities as an untrusted data source

**This is the most important change to `architecture.md`.**

### 2.1 The problem

Today the university roster CSV is the authority for branch, batch and CGPA. Eligibility (§6 rule 4, §9 campus flow) and university reports both read it. A university rewarded for placement numbers can:
- raise CGPAs past drive cutoffs
- relabel branches so students match `allowed_branches`
- keep students who have left or failed in the batch
- add ghost students to inflate counts
- edit the roster right after a drive's cutoff is published

Recruiters then filter on false data. The platform's own "University record verified" label (§4) certifies the fabrication. That destroys recruiter trust, which is the asset recruiters pay for.

### 2.2 The fix: verify academic data outside the university's CSV

| # | Control | How it works | Phase | Owner |
|---|---|---|---|---|
| 1 | **Issuer fetch with the student's consent** | The student links DigiLocker / NAD / ABC-APAAR. The platform pulls issued marksheets/degree directly from the issuer and checks the issuer signature. CGPA, branch and batch come from that document, never from a file the university or student uploads. | P | P3 |
| 2 | **The CSV becomes a pre-fill and claim list only** | Each roster row is compared with the issuer record. On a mismatch the issuer value wins, the row lands in `roster_discrepancies`, and the university's trust score drops. | P | P3 |
| 3 | **Fallback check** | If no digital record exists, the student uploads a marksheet. The platform verifies it with the issuing exam branch or through a background-verification provider, billed per check. The label stays `University-claimed` until the check passes. | P | Ops |
| 4 | **Statistical anomaly detection** per university and batch | Flags: <ul><li>CGPA distribution far from history or peers</li><li>an unusual share of students just above a drive cutoff</li><li>eligible count jumps after a drive is published</li><li>roster size above AICTE/UGC sanctioned intake</li><li>mass edits near deadlines</li></ul> | Prod | P3 / Ops |
| 5 | **Random audit sampling** | N random applicants per drive go through original-document verification. Above a mismatch threshold: drives pause, recruiters are notified, reports carry an "unverified data" banner. | P | Ops |
| 6 | **Recruiter feedback** | Offer-stage background checks report mismatches. The student's verified label is revoked, and the university's trust score takes the hit. | Prod | P2 |
| 7 | **Eligibility reads verified values only** | Hard drive gates (CGPA, branch, batch) evaluate only `Academic record verified` values. A `University-claimed`-only student sees "Verify your academic record to apply". | P | P3 |
| 8 | **Honest reports** | Headline counts include only applicants with verified academic records. Unverified applicants appear in a separate section. | P | P3 |
| 9 | **Incentives favour honest data** | A high trust score unlocks a "Verified data partner" badge, premium-recruiter drives, and better pricing (see business-model.md). Inflated data loses all three. | Prod | Ops |

**Hackathon:** keep the CSV flow and label it `Sample data · university-claimed, not externally verified`. Rename the §4 label `University record verified` to `University-claimed`.

### 2.3 Residual risk

Issuer records can lag by a semester. Mid-semester CGPA is therefore "last issued" plus a timestamp. A university that falsifies its official NAD uploads is committing document fraud, which is a legal matter. Audit sampling and recruiter background checks catch it after the fact.

---

## 3. Identity and onboarding

| Threat | Attack | Mitigation | Phase | Owner |
|---|---|---|---|---|
| Sybil / duplicate accounts | No email confirmation today, so one person runs many accounts (spam applications, fake reviews, verification retries) | Enforce Supabase email confirmation (H). Phone OTP (P). KYC dedupe on paid or verified paths: one verified human per account (Prod). | H→Prod | P2 |
| Roster hijack | Someone signs up with another student's roster email or student ID | Claim needs a one-time code sent to the roster email, or institution SSO. Disputed claims are resolved with an issuer-record match, not by university say-so. | P | P3 |
| Fake university org | Someone registers a "university" to get admin powers and run fake drives | Domain verification + AISHE/UGC listing + operator review. Memberships stay setup-only (as in §6 rule 2). | P | Ops |
| Fake company / shell recruiter | A scammer registers a company to post jobs | GSTIN/CIN check, work-domain email, operator review before the first listing goes live. New orgs are rate-limited. | P | Ops |
| Fake mentor | Inflated experience claims to earn verifier fees | KYC + employment verification (work email / LinkedIn) + calibration test before any paid work (§4.6). | P | P4 / Ops |
| Verified account sold or shared | A verified profile is handed to someone else | Liveness re-check on high-stakes actions (applying to campus drives, accepting offers). Device/locale anomaly alerts. Badges bound to the KYC identity. | Prod | P2 |
| Account takeover | Credential stuffing | Supabase rate limits, optional TOTP for recruiters and university admins, alerts on new-device logins. | P | P2 |

---

## 4. Skill claims and verification

### 4.1 Your proposal

Paid mentors verify skills. They must come from outside the candidate's college. Universities handle their own students. Job seekers pay for verification.

The direction is right. Below is where it breaks and how to close each gap.

| # | Weak point | Why it fails | Fix |
|---|---|---|---|
| 1 | "Outside college" is the only rule | Friendships cross colleges: school friends, coaching batches, Discord/WhatsApp groups. Rings trade favours (A's friend verifies B's friend, and the reverse). | Random assignment plus a full conflict check (§4.2). Graph detection of reciprocity (§10). |
| 2 | The university verifies its own students | Its placement-stat incentive is the same one behind fabricated CSVs (§2) | The university verifies nothing itself. It may only **sponsor/pay** for external verification. |
| 3 | Mentors are paid per verification | A pass is quicker and draws no dispute, so verifiers drift toward passing everyone | Same pay for pass and fail. Payout held through an audit window. A second verifier re-audits 10–20% of sessions. Disagreement lowers the quality score, then leads to removal and clawback. |
| 4 | The candidate knows the verifier in advance | Bribes and pre-arranged answers become possible | Verifier identity is revealed only when the session starts. All communication stays on-platform and is recorded. |
| 5 | Retry until passing | Retries keep coming until a lenient verifier appears | 30-day cooldown per skill/level. Each retry goes to a different verifier. Full attempt history is visible to recruiters. |
| 6 | Mentor qualifications | Weak verifiers pass weak candidates | Verifiers may only assess levels **at or below** their own verified level. Calibration and probation (§4.6). |
| 7 | Paid path for job seekers | Looks like pay-to-win, and invites chargebacks after a fail | Fee is outcome-independent and non-refundable on fail. A chargeback revokes the badge (§9). |

### 4.2 Verifier assignment algorithm

```text
request(candidate, skill, level)
 → pool = mentors where
      verified_level(skill) ≥ level
      AND quality_score ≥ threshold
      AND not on probation (or paired with a senior)
      AND capacity available
      AND NOT conflict(mentor, candidate)
      AND monthly_count(mentor, candidate.institution) < cap
 → pick weighted-random (weight = quality, spread load)
 → levels ≥ "advanced": pick 2 independent verifiers; pass requires both
 → reveal verifier at session start only
```

`conflict(mentor, candidate)` is true if any of these hold:
- they share an institution, past or present (roster + `affiliations`)
- they share an employer, past or present
- there is any prior `mentor_request`, collaboration, referral, or message between them
- they are within 2 hops in the interaction graph
- they share a device or IP fingerprint
- either has verified someone from the other's institution where that person in turn verified someone from the first one's institution (reciprocity)
- either has already verified the candidate for any skill

### 4.3 Candidate-side faking and the controls against it

| Attack | Control | Phase |
|---|---|---|
| Proxy test-taker | ID + liveness at start, face match against KYC/issuer photo, camera on throughout, random mid-session re-checks | P |
| AI or live help during the session | Live interviewer format, not a static test. "Modify your own code" tasks, follow-up "why" questions, parameterized task variants, screen share. | P |
| Leaked questions | Large rotating task bank, per-session randomization, tasks retired after an exposure threshold, verifiers cannot add unreviewed tasks | P→Prod |
| Plagiarized or bought portfolio | Ownership challenge (commit a platform nonce file to the repo), commit-history plausibility check, live walkthrough of the code | P |
| Fake certificates | Accept only issuer-verifiable credentials (issuer URL/API, Open Badges). Anything else stays `Self-declared`. | P |
| Stale skills | Badges carry level + date and expire after 12–24 months | P |
| Coverage gaming | User lists every required skill to reach 100% coverage. Coverage shows `2 verified + 1 declared of 4`, and recruiters can filter by verified only. | H (label) / P |
| Writing a "verified" skill through the Data API | `skill_verifications` is server-owned with no user write grant. Only a constrained RPC that checks the assignment and verifier writes to it. | P |

### 4.5 Gaming the automated assessment

The full design is in [skill-intelligence.md](skill-intelligence.md) §14.

| Attack | Control | Phase |
|---|---|---|
| Resume keyword stuffing | A skills-line-only mention is worth ≤ 5/100. A level needs in-context and project evidence. | H |
| Hidden white or tiny text in the resume | The extracted text is shown back to the user; invisible text is flagged | H / P |
| Prompt injection in resume/README/JD | Delimited data, structured output, **scores computed in Python**, evidence quotes must exist in the source | H |
| LLM-hallucinated skills | Quote/reference verification; unmatched skills go to review | H |
| Copied/forked/bought repos | OAuth ownership, authored commits only, fork exclusion, copy-similarity and burst-commit flags | P |
| AI-generated proof projects | Proof artifacts can raise a skill to System-assessed level 2 at most; above level 3 needs a mentor | P |
| Fabricated claims in outreach drafts | Claim → evidence-ID post-check deletes unsupported sentences | P |
| Outreach spam to recruiters | Daily quotas, 14-day per-recruiter cooldown, mute/report, suspension | P |
| Contact harvesting for outreach | Consented sources only: registered recruiters, the listing poster, contacts the company published. No scraping, guessing or enrichment. | P |

### 4.6 Verifier lifecycle

1. **Apply:** KYC, employment verification, declared affiliations (feed into the conflict check).
2. **Calibrate:** grade 5 recorded "gold" sessions. Agreement with the reference grades must exceed the threshold.
3. **Probation:** first 10 verifications are double-reviewed by a senior verifier.
4. **Active:** quality score combines audit agreement, recruiter-confirmed outcomes, and how far the pass rate sits from the cohort's.
5. **Removal:** below-threshold score or confirmed collusion. Unpaid holdbacks are clawed back, and badges they issued drop to `Under review` pending re-verification.

---

## 5. Opportunities and recruiters

| Threat | Mitigation | Phase | Owner |
|---|---|---|---|
| Scam jobs that charge candidates "training/security/kit" fees, phishing, data harvesting | Verified orgs only. Policy: a listing may never charge candidates. Keyword and salary-outlier flags. A "report" button on every listing; auto-hide after N reports pending review. | P | P2 / Ops |
| Bait listings (no real job, collecting resumes), ghosting | Public response-rate figure per company. Recruiter quality score. Auto-close stale listings. | P | P2 |
| Scraping or resale of candidate data through paid seats | Contact credits per seat. Phone/email masked until the candidate applies or accepts contact. Rate limits and bulk-view anomaly detection. Watermarked exports. | P | P2 |
| Seat sharing across an agency | Concurrent-session limit per seat, device fingerprints, seat-based pricing | P | P2 |
| Discriminatory filtering | No filters on protected attributes. Filter usage is audit-logged. | P | P2 |
| Recruiter edits listing requirements after applications arrive | Version the listing. Each application snapshots the version it applied against (extends `profile_snapshot`). | P | P2 |

## 6. Applications and eligibility

| Threat | Mitigation | Phase | Owner |
|---|---|---|---|
| Bot or mass applications | Daily caps per plan, CAPTCHA on bursts, a screening question on high-volume listings | P | P2 |
| CGPA/branch tampering through the profile | Already blocked: academic values never come from `profiles`. Extend so they come only from `academic_records` (§2). | H (keep) / P | P3 |
| Bypass by omitting `drive_id` or using a public twin listing | Already specified in `architecture.md` §3. Keep the tests in §13. | H | P2 / P3 |
| Recruiter backdates or hides status changes | Append-only decision events (§14), with timestamps visible to the candidate | P | P2 |
| Candidate applies, then fabricates a competing offer to pressure recruiters | Out of scope; offers recorded on the platform are the only ones reported | — | — |

## 7. University and reporting

| Threat | Mitigation | Phase | Owner |
|---|---|---|---|
| Fabricated roster CSV | §2 in full | P | P3 / Ops |
| Offers reported as placements; off-platform offers counted | Report only outcomes recorded on the platform. Offer ≠ joined (already a rule). Joining needs confirmation from both company and student. | P | P3 |
| Roster poisoning with ghost students | Roster rows grant nothing until claimed and verified against the issuer. Roster-size anomaly alerts. | P | P3 |
| Former admin keeps access | Periodic re-confirmation of admin memberships, removal workflow, audit log | P | P2 |
| CSV formula injection | Already mitigated (§9). Keep it. | H | P3 |
| Drive rules changed to favour particular students | Rules are frozen after publication (already in `architecture.md`). Pilot: version the rules, and every change shows on the drive. | H / P | P3 |

## 8. Mentors, sessions, and ventures

| Threat | Mitigation | Phase | Owner |
|---|---|---|---|
| Disintermediation (taking students off-platform to avoid commission) | Make the platform worth staying on: escrow protection, reviews and ranking count only on-platform sessions, verification credit. Contact details hidden until booking. Light detection of phone numbers/links in notes. | P | P4 |
| Fake reviews / review trading | Only completed, paid sessions can be reviewed. Graph checks for rings. | P | P4 |
| No-shows (either side) | Escrow + a no-show policy (refund or forfeit) | P | P4 |
| Harassment | Report/block, recorded sessions for disputes, ban process | P | P4 / Ops |
| Venture idea theft | Tiered disclosure: public teaser, full details only after the founder accepts. Timestamped idea log. Optional NDA click-through. | P | P4 |
| Free-labour exploitation ("equity later") | Required compensation-type field (paid / equity / unpaid). "Incorporated" badge needs a CIN check. Report abuse. | P | P4 |
| Fake founders recruiting for scams | Same org verification as companies once a venture hires | P | Ops |

## 9. Payments and subscriptions

Monetization creates new kinds of abuse. See [business-model.md](business-model.md).

| Threat | Mitigation | Phase | Owner |
|---|---|---|---|
| Free-trial cycling | One trial per phone, KYC, or card fingerprint | Prod | P2 |
| Chargeback after a failed verification | Fee terms state the fee is outcome-independent. A chargeback revokes the badge and locks paid features. | Prod | P2 |
| Stolen cards | Razorpay/Stripe with 3-D Secure. No card data stored. | Prod | P2 |
| Pay-to-win | Published policy: paid plans never affect ranking or verification outcomes. Ranking code has no plan input (test it). | P | P2 |
| Entitlement bypass through the Data API | `subscriptions` / `entitlements` / `usage_counters` are server-owned and checked inside the RPC, never only in the frontend | P | P2 |
| Webhook spoofing or replay | Verify signatures. Process idempotently by provider event ID. | Prod | P2 |
| Verifier payout fraud (fake sessions with a friend) | Conflict rules (§4.2), payout held through the audit window, KYC on both sides | Prod | Ops |

## 10. Platform and operational failures

| Failure | Mitigation | Phase | Owner |
|---|---|---|---|
| RLS gaps / IDOR on every new table | Every new table ships with grants, policies, and a direct-Data-API negative test (§13 pattern) | All | P2 / P3 |
| `SECURITY DEFINER` misuse | Follow §6 rule 7. Each new function gets a review checklist item. | All | P2 |
| No rate limiting | Per-user and per-IP limits on auth, applications, search, and contact reveal | P | P2 |
| No audit log | Append-only `audit_events` for verification, eligibility, payments, admin actions | P | P2 |
| PII in logs | Already forbidden (§5). Extend to KYC references, recordings, academic records. | All | P2 |
| Free-tier sleep and limits with paying users | Paid Render/Supabase tiers before any paid launch | Prod | P2 |
| Backups and retention | Point-in-time recovery. Retention schedule for recordings and KYC data. | Prod | Ops |
| Privacy law (India DPDP Act 2023) | Explicit consent for recording, KYC, and DigiLocker access. Purpose limitation. Deletion on request. Named grievance officer. | P | Ops |

## 11. Detection and response loop

**Signals:**
- verifier pass rate vs. cohort
- audit disagreement rate
- reciprocal or clustered verification graphs
- university data-trust score and roster discrepancies
- report counts on listings and users
- recruiter outcome feedback ("verified, but failed basics")
- bulk-view and scraping patterns
- chargebacks

**Response ladder:** `under_review` → re-verify / re-audit → downgrade or revoke → payout clawback → suspension → ban.

Every step writes to `audit_events`. Affected users are notified and can appeal once, to a different reviewer.

## 12. New data model (pilot+, all server-owned)

| Table | Purpose |
|---|---|
| `academic_records` | user, issuer, source (`digilocker` / `nad` / `bgv` / `university_csv`), cgpa, branch, batch, document_hash, verified_at, status |
| `roster_discrepancies`, `university_trust_scores`, `audit_samples` | §2 controls |
| `affiliations` | user, org, from, to (conflict checks) |
| `verifier_profiles` | KYC status, verified levels, quality score, calibration results, probation |
| `verification_requests`, `verification_assignments` | Request → assigned verifier(s), revealed_at |
| `skill_verifications` | user, skill, level, status, method, verifier_ids, rubric_scores, evidence_ref, issued_at, expires_at, revoked_reason |
| `verification_audits` | Second-review results and disagreement |
| `identity_checks` | KYC provider reference only. No raw ID images. |
| `plans`, `subscriptions`, `entitlements`, `usage_counters`, `payments`, `payouts` | See business-model.md |
| `reports_abuse`, `audit_events` | Trust and safety |
| `resumes`, `skill_evidence`, `skill_scores`, `job_requirements`, `external_jds`, `github_connections`, `proof_plans`, `recruiter_contacts`, `outreach_*` | Skill intelligence ([skill-intelligence.md](skill-intelligence.md) §11). Four of these are in the hackathon slice. |

The ten-table hackathon core (`architecture.md` §15) is unchanged. None of these tables is a hackathon dependency.

## 13. What to do during the hackathon

1. Enforce email confirmation in Supabase Auth.
2. Rename the `University record verified` label to `University-claimed`, and label seed data `Sample data`.
3. Keep `Self-declared` labels and show `verified + declared` in the coverage display (all declared for now).
4. Put one pitch slide on the trust ladder and "no party verifies itself". This is the differentiator against job boards.
