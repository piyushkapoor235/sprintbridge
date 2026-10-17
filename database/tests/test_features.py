"""Ventures disclosure, plans/quotas/test payments, mentor skill verification, trust & safety."""

import json

import pytest
from psycopg import errors


def fn(db, uid, sql, params=()):
    return db.user(uid, sql, params).fetchone()[0]


def mentor(db, name, skills=(), price=None, expertise=None):
    uid = db.new_user(name)
    db.admin("update public.profiles set skills = %s where user_id = %s", (list(skills), uid))
    db.admin("insert into public.role_grants (user_id, role) values (%s, 'mentor')", (uid,))
    mid = db.admin("insert into public.mentors (user_id, niche, session_price_inr) values (%s, 'Data', %s) returning id",
                   (uid, price)).fetchone()[0]
    for skill, level in (expertise or {}).items():
        db.admin("insert into public.mentor_expertise (mentor_id, skill, level) values (%s, %s, %s)", (mid, skill, level))
    return uid, mid


# --- ventures: tiered disclosure + NDA -------------------------------------------------


def test_venture_details_only_for_founder_and_accepted(db):
    founder, member, stranger = db.new_user("F"), db.new_user("M"), db.new_user("S")
    vid = fn(db, founder, """insert into public.ventures (title, teaser, problem, industry, compensation_type)
                             values ('Food app', 'Cut hostel food waste', 'Secret plan', 'Food', 'equity') returning id""")
    with db.fails(errors.InsufficientPrivilege):
        db.user(stranger, "select problem from public.ventures where id = %s", (vid,))
    assert fn(db, stranger, "select teaser from public.ventures where id = %s", (vid,)) == "Cut hostel food waste"
    assert fn(db, stranger, "select public.venture_private_details(%s)", (vid,)) is None
    assert fn(db, founder, "select public.venture_private_details(%s)", (vid,)) == "Secret plan"

    with db.fails(errors.CheckViolation):
        db.user(member, "insert into public.collaboration_requests (venture_id, note, nda_accepted) values (%s, 'hi', false)", (vid,))
    req = fn(db, member, "insert into public.collaboration_requests (venture_id, note, nda_accepted) values (%s, 'hi', true) returning id", (vid,))
    assert fn(db, member, "select public.venture_private_details(%s)", (vid,)) is None
    db.user(founder, "update public.collaboration_requests set status = 'accepted' where id = %s", (req,))
    assert fn(db, member, "select public.venture_private_details(%s)", (vid,)) == "Secret plan"


def test_founder_free_plan_allows_one_venture(db):
    founder = db.new_user()
    insert = "insert into public.ventures (title, teaser, problem, industry) values ('V', 'T', 'P', 'I')"
    db.user(founder, insert)
    with db.fails(sqlstate="PT402"):
        db.user(founder, insert)


# --- plans, quotas, test payments ------------------------------------------------------


def test_free_quota_then_paid_upgrade(db):
    student = db.new_user()
    mids = [mentor(db, f"M{i}")[1] for i in range(3)]
    for mid in mids[:2]:
        db.user(student, "insert into public.mentor_requests (mentor_id, note) values (%s, 'hi')", (mid,))
    with db.fails(sqlstate="PT402"):
        db.user(student, "insert into public.mentor_requests (mentor_id, note) values (%s, 'hi')", (mids[2],))

    with db.fails(sqlstate="PT402"):  # paid plan needs an explicit test-payment confirmation
        fn(db, student, "select public.subscribe('job_seeker_pro')")
    result = fn(db, student, "select public.subscribe('job_seeker_pro', null, true)")
    assert result["amount_inr"] == 299
    assert db.admin("select provider, status from public.payments where id = %s", (result["payment_id"],)).fetchone() == ("test", "captured")
    db.user(student, "insert into public.mentor_requests (mentor_id, note) values (%s, 'hi')", (mids[2],))


def test_student_plan_requires_roster_link(db):
    with db.fails(sqlstate="PT403"):
        fn(db, db.new_user(), "select public.subscribe('student_pro', null, true)")


def test_recruiter_listing_limit_by_company_plan(db):
    recruiter, other = db.new_user(), db.new_user()
    company = db.new_org("company")
    db.member(recruiter, company, "recruiter")
    insert = """insert into public.opportunities (company_id, title, type, deadline)
                values (%s, 'Role', 'job', now() + interval '5 days')"""
    db.user(recruiter, insert, (company,))
    with db.fails(sqlstate="PT402"):
        db.user(recruiter, insert, (company,))
    with db.fails(sqlstate="PT403"):  # only the company's recruiters can buy its plan
        fn(db, other, "select public.subscribe('recruiter_starter', %s, true)", (company,))
    fn(db, recruiter, "select public.subscribe('recruiter_starter', %s, true)", (company,))
    db.user(recruiter, insert, (company,))


def test_paid_mentor_escrow_refund_complete_dispute(db):
    student, other = db.new_user("Asha"), db.new_user("Ravi")
    m_uid, mid = mentor(db, "Arjun", price=500)
    op = db.new_user("Op")
    db.admin("insert into public.role_grants (user_id, role) values (%s, 'operator')", (op,))

    with db.fails(sqlstate="PT402"):  # paid mentor cannot be requested by a direct insert
        db.user(student, "insert into public.mentor_requests (mentor_id, note) values (%s, 'hi')", (mid,))
    with db.fails(sqlstate="PT402"):
        fn(db, student, "select public.request_mentor(%s, 'hi')", (mid,))

    declined = fn(db, other, "select public.request_mentor(%s, 'hi', true)", (mid,))
    db.user(m_uid, "update public.mentor_requests set status = 'declined' where id = %s", (declined["id"],))
    assert db.admin("select status from public.payments where id = %s", (declined["payment_id"],)).fetchone()[0] == "refunded"

    req = fn(db, student, "select public.request_mentor(%s, 'Docker help', true)", (mid,))
    with db.fails(sqlstate="PT409"):  # cannot complete before accepting
        fn(db, m_uid, "select public.complete_mentor_session(%s)", (req["id"],))
    db.user(m_uid, "update public.mentor_requests set status = 'accepted' where id = %s", (req["id"],))
    done = fn(db, m_uid, "select public.complete_mentor_session(%s)", (req["id"],))
    payout = db.admin("select gross_inr, commission_inr, net_inr, status from public.payouts where id = %s",
                      (done["payout_id"],)).fetchone()
    assert payout == (500, 100, 400, "held")  # free mentor plan: 20% commission, held 7 days

    with db.fails(sqlstate="PT404"):  # only the requester can dispute
        fn(db, other, "select public.dispute_mentor_session(%s, 'no-show')", (req["id"],))
    fn(db, student, "select public.dispute_mentor_session(%s, 'no-show')", (req["id"],))
    with db.fails(sqlstate="PT403"):
        fn(db, student, "select public.operator_resolve_payout(%s, 'refund')", (done["payout_id"],))
    fn(db, op, "select public.operator_resolve_payout(%s, 'refund')", (done["payout_id"],))
    assert db.admin("select status from public.payments where id = %s", (req["payment_id"],)).fetchone()[0] == "refunded"


def test_my_billing_reports_usage(db):
    student = db.new_user()
    mid = mentor(db, "M")[1]
    db.user(student, "insert into public.mentor_requests (mentor_id, note) values (%s, 'hi')", (mid,))
    billing = fn(db, student, "select public.my_billing()")
    assert billing["plans"]["seeker"] == "job_seeker_free"
    assert billing["usage"]["mentor_requests"] == {"used": 1, "limit": 2}


# --- mentor skill verification -------------------------------------------------------


@pytest.fixture
def verification(db):
    uni = db.new_org("university")
    candidate = db.new_user("Asha")
    db.admin("""insert into public.student_roster (university_id, student_id, name, email, verified_user_id, branch, batch)
                values (%s, 'S1', 'Asha', 'a@u.test', %s, 'cse', 2027)""", (uni, candidate))
    same_college, same_mid = mentor(db, "Same College", expertise={"python": 3})
    db.admin("insert into public.memberships (user_id, organization_id, role) values (%s, %s, 'admin')", (same_college, uni))
    low_uid, low_mid = mentor(db, "Too Junior", expertise={"python": 1})
    v1_uid, v1 = mentor(db, "Verifier One", expertise={"python": 3})
    v2_uid, v2 = mentor(db, "Verifier Two", expertise={"python": 3})
    return dict(uni=uni, candidate=candidate, same_mid=same_mid, low_mid=low_mid,
                verifiers={v1: v1_uid, v2: v2_uid})


def request(db, uid, skill="python", level=2, pay=True):
    return fn(db, uid, "select public.request_skill_verification(%s, %s, %s)", (skill, level, pay))


def assigned_to(db, req_id):
    return db.admin("select verifier_id from public.verification_requests where id = %s", (req_id,)).fetchone()[0]


def test_assignment_is_random_eligible_and_conflict_free(db, verification):
    with db.fails(sqlstate="PT402"):  # no charge without explicit confirmation
        request(db, verification["candidate"], pay=False)
    assert db.admin("select count(*) from public.payments").fetchone()[0] == 0
    req = request(db, verification["candidate"])
    assert req["fee_inr"] == 499  # on a roster -> student fee
    chosen = assigned_to(db, req["id"])
    assert chosen in verification["verifiers"]  # never the same-college or under-levelled mentor
    with db.fails(sqlstate="PT409"):  # one open request per skill
        request(db, verification["candidate"])


def test_no_eligible_verifier_means_no_charge(db, verification):
    with db.fails(sqlstate="PT409"):
        request(db, verification["candidate"], skill="rust")
    assert db.admin("select count(*) from public.payments").fetchone()[0] == 0


def test_identity_revealed_at_session_and_pass_badge(db, verification):
    cand = verification["candidate"]
    req = request(db, cand)
    vid = assigned_to(db, req["id"])
    v_uid = verification["verifiers"][vid]
    assert fn(db, cand, "select public.my_verifications()")[0]["verifier"] is None
    with db.fails(sqlstate="PT404"):  # another mentor cannot act on it
        other = next(u for m, u in verification["verifiers"].items() if m != vid)
        fn(db, other, "select public.start_verification_session(%s)", (req["id"],))
    with db.fails(sqlstate="PT409"):  # result before session start
        fn(db, v_uid, "select public.submit_verification_result(%s, true, 2, 'ok')", (req["id"],))
    fn(db, v_uid, "select public.start_verification_session(%s)", (req["id"],))
    assert fn(db, cand, "select public.my_verifications()")[0]["verifier"]["name"].startswith("Verifier")
    with db.fails(sqlstate="PT422"):  # cannot certify above own level
        fn(db, v_uid, "select public.submit_verification_result(%s, true, 4, 'ok')", (req["id"],))
    db.conn.execute("select set_config('sprintbridge.audit_rate', '0', true)")
    fn(db, v_uid, "select public.submit_verification_result(%s, true, 2, 'Solid SQL + Python ETL')", (req["id"],))
    assert db.user(cand, "select skill, level from public.my_verified_skills()").fetchall() == [("python", 2)]
    payout = db.admin("select net_inr, status from public.payouts where payment_id = (select payment_id from public.verification_requests where id = %s)",
                      (req["id"],)).fetchone()
    assert payout == (299, "held")  # 60% of 499, same for pass or fail


def test_fail_starts_cooldown_and_retry_gets_new_verifier(db, verification):
    cand = verification["candidate"]
    req = request(db, cand)
    first = assigned_to(db, req["id"])
    v_uid = verification["verifiers"][first]
    fn(db, v_uid, "select public.start_verification_session(%s)", (req["id"],))
    db.conn.execute("select set_config('sprintbridge.audit_rate', '0', true)")
    fn(db, v_uid, "select public.submit_verification_result(%s, false, null, 'Needs practice')", (req["id"],))
    with db.fails(sqlstate="PT409"):
        request(db, cand)
    db.admin("update public.verification_requests set decided_at = now() - interval '31 days' where id = %s", (req["id"],))
    retry = request(db, cand)
    assert assigned_to(db, retry["id"]) != first


def test_audit_disagreement_suspends_badge_and_lowers_quality(db, verification):
    cand = verification["candidate"]
    req = request(db, cand)
    vid = assigned_to(db, req["id"])
    v_uid = verification["verifiers"][vid]
    fn(db, v_uid, "select public.start_verification_session(%s)", (req["id"],))
    db.conn.execute("select set_config('sprintbridge.audit_rate', '1', true)")
    assert fn(db, v_uid, "select public.submit_verification_result(%s, true, 3, 'ok')", (req["id"],))["audited"] is True
    audit_id, auditor = db.admin("select id, auditor_id from public.verification_audits where request_id = %s", (req["id"],)).fetchone()
    assert auditor != vid
    queue = fn(db, verification["verifiers"][auditor], "select public.verifier_queue()")
    assert "result_level" not in queue["audits"][0]  # blind second review
    fn(db, verification["verifiers"][auditor], "select public.submit_verification_audit(%s, false, null)", (audit_id,))
    assert db.admin("select status from public.verification_requests where id = %s", (req["id"],)).fetchone()[0] == "under_review"
    assert db.user(cand, "select count(*) from public.my_verified_skills()").fetchone()[0] == 0
    assert db.admin("select quality_score from public.mentors where id = %s", (vid,)).fetchone()[0] == 0


def test_verified_experts_rank_first(db, verification):
    viewer = db.new_user()
    mentor(db, "Aaron Declared", skills=("python",))
    items = fn(db, viewer, "select public.list_mentors(null, 'python')")["items"]
    assert items[0]["mentor_verified"] is True and items[-1]["name"] == "Aaron Declared"


# --- trust & safety ------------------------------------------------------------------


def test_red_flags_reports_auto_hide_and_operator(db):
    recruiter, op = db.new_user(), db.new_user("Op")
    company = db.new_org("company")
    db.member(recruiter, company, "recruiter")
    db.admin("insert into public.role_grants (user_id, role) values (%s, 'operator')", (op,))
    opp = db.admin("""insert into public.opportunities (company_id, title, description, type, deadline, created_by)
                      values (%s, 'Data Intern', 'Pay a registration fee of Rs 2000. WhatsApp only.', 'internship',
                              now() + interval '5 days', %s) returning id""", (company, recruiter)).fetchone()[0]
    flags = db.admin("select red_flags from public.opportunities where id = %s", (opp,)).fetchone()[0]
    assert "asks candidates to pay a fee" in flags and "moves contact off-platform" in flags

    reporters = [db.new_user() for _ in range(3)]
    for i, uid in enumerate(reporters):
        db.user(uid, "insert into public.content_reports (target_type, target_id, reason) values ('opportunity', %s, 'scam')", (opp,))
        if i == 0:
            with db.fails(errors.UniqueViolation):
                db.user(uid, "insert into public.content_reports (target_type, target_id, reason) values ('opportunity', %s, 'scam')", (opp,))
    visible = "select count(*) from public.opportunities where id = %s"
    assert fn(db, reporters[0], visible, (opp,)) == 0  # auto-hidden after 3 distinct reports
    assert fn(db, recruiter, visible, (opp,)) == 1  # company still sees it
    with db.fails(sqlstate="PT404"):
        fn(db, db.new_user(), "select public.submit_application(%s)", (opp,))

    with db.fails(sqlstate="PT403"):
        fn(db, recruiter, "select public.operator_queue()")
    queue = fn(db, op, "select public.operator_queue()")
    assert queue["reports"][0]["open_reports"] == 3 and queue["flagged"][0]["id"] == str(opp)
    fn(db, op, "select public.operator_moderate('opportunity', %s, 'remove', 'scam confirmed')", (opp,))
    actions = [a["action"] for a in fn(db, op, "select public.operator_queue()")["audit"]]
    assert "moderation.remove" in actions and "opportunity.auto_hidden" in actions
    # Row security hides the audit log from ordinary users entirely.
    assert fn(db, recruiter, "select count(*) from public.audit_events") == 0
