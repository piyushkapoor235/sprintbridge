"""0018 onboarding: role applications reviewed by an operator; students linked to their roster by email."""

import psycopg


def operator(db):
    uid = db.new_user("Priya")
    db.admin("insert into public.role_grants (user_id, role) values (%s, 'operator')", (uid,))
    return uid


def apply(db, uid, kind, org=None, niche=None):
    return db.user(uid, "select id, status from public.submit_role_application(%s, %s, 'Talent lead', null, %s, 'Ten years')",
                   (kind, org, niche)).fetchone()


def review(db, op, app_id, approve):
    return db.user(op, "select status, organization_id from public.review_role_application(%s, %s, 'checked')",
                   (app_id, approve)).fetchone()


def test_recruiter_application_approved_creates_company_and_membership(db):
    op, uid = operator(db), db.new_user("Ravi")
    app_id, status = apply(db, uid, "recruiter", org="Initech Labs")
    assert status == "pending"
    assert db.user(uid, "select count(*) from public.memberships").fetchone()[0] == 0  # nothing granted yet

    status, org = review(db, op, app_id, True)
    assert status == "approved"
    assert db.admin("select name, type from public.organizations where id = %s", (org,)).fetchone() == ("Initech Labs", "company")
    assert db.admin("select role from public.memberships where user_id = %s", (uid,)).fetchone() == ("recruiter",)


def test_second_recruiter_joins_the_existing_company(db):
    op, first, second = operator(db), db.new_user(), db.new_user()
    _, org1 = review(db, op, apply(db, first, "recruiter", org="Umbrella Corp")[0], True)
    queue = db.user(op, "select public.operator_role_applications()").fetchone()[0]
    assert queue == []
    app_id = apply(db, second, "recruiter", org="umbrella corp")[0]
    queue = db.user(op, "select public.operator_role_applications()").fetchone()[0]
    assert queue[0]["existing_organization"] == "Umbrella Corp"  # the operator is warned before approving
    _, org2 = review(db, op, app_id, True)
    assert org1 == org2


def test_university_admin_and_mentor_approval(db):
    op, admin, mentor = operator(db), db.new_user(), db.new_user()
    _, org = review(db, op, apply(db, admin, "university_admin", org="Demo Institute")[0], True)
    assert db.admin("select type from public.organizations where id = %s", (org,)).fetchone() == ("university",)
    assert db.admin("select role from public.memberships where user_id = %s", (admin,)).fetchone() == ("admin",)

    review(db, op, apply(db, mentor, "mentor", niche="Cloud & DevOps")[0], True)
    assert db.admin("select role from public.role_grants where user_id = %s", (mentor,)).fetchone() == ("mentor",)
    assert db.admin("select niche from public.mentors where user_id = %s", (mentor,)).fetchone() == ("Cloud & DevOps",)
    # A new mentor has no calibrated expertise, so the system cannot assign them as a verifier yet.
    assert db.admin("select count(*) from public.mentor_expertise e join public.mentors m on m.id = e.mentor_id "
                    "where m.user_id = %s", (mentor,)).fetchone()[0] == 0


def test_rejection_grants_nothing_and_allows_reapplying(db):
    op, uid = operator(db), db.new_user()
    status, _ = review(db, op, apply(db, uid, "recruiter", org="Shady Jobs")[0], False)
    assert status == "rejected"
    assert db.admin("select count(*) from public.memberships where user_id = %s", (uid,)).fetchone()[0] == 0
    assert apply(db, uid, "recruiter", org="Shady Jobs")[1] == "pending"


def test_users_cannot_approve_themselves_or_write_directly(db):
    uid = db.new_user()
    app_id = apply(db, uid, "mentor", niche="Python")[0]
    with db.fails(psycopg.Error, "PT403"):
        db.user(uid, "select public.review_role_application(%s, true)", (app_id,))
    with db.fails(psycopg.errors.InsufficientPrivilege):
        db.user(uid, "update public.role_applications set status = 'approved' where id = %s", (app_id,))
    with db.fails(psycopg.errors.InsufficientPrivilege):
        db.user(uid, "insert into public.role_applications (user_id, kind, niche) values (%s, 'mentor', 'x')", (uid,))
    with db.fails(psycopg.Error, "PT403"):
        db.user(uid, "select public.operator_role_applications()")


def test_duplicate_pending_and_already_granted_are_refused(db):
    op, uid = operator(db), db.new_user()
    app_id = apply(db, uid, "mentor", niche="Python")[0]
    with db.fails(psycopg.Error, "PT409"):
        apply(db, uid, "mentor", niche="Python")
    review(db, op, app_id, True)
    with db.fails(psycopg.Error, "PT409"):
        apply(db, uid, "mentor", niche="Python")
    with db.fails(psycopg.Error, "PT409"):
        review(db, op, app_id, False)  # already decided


def test_applications_are_private(db):
    uid, other = db.new_user(), db.new_user()
    apply(db, uid, "recruiter", org="Acme Rockets")
    assert db.user(other, "select count(*) from public.role_applications").fetchone()[0] == 0
    assert db.user(uid, "select count(*) from public.role_applications").fetchone()[0] == 1


def roster_row(db, university, email):
    db.admin("""insert into public.student_roster (university_id, student_id, name, email, branch, batch, cgpa)
                values (%s, %s, 'Student', %s, 'CSE', 2027, 8.0)""",
             (university, f"S{abs(hash(email)) % 10**6}", email))


def test_confirmed_student_claims_their_roster_record(db):
    uni = db.new_org("university")
    uid = db.new_user("Meera")
    email = db.admin("select email from auth.users where id = %s", (uid,)).fetchone()[0]
    roster_row(db, uni, email.upper())  # stored lower-case by the roster trigger

    assert db.user(uid, "select public.claim_roster_records()").fetchone()[0] == 0  # email not confirmed yet
    db.admin("update auth.users set email_confirmed_at = now() where id = %s", (uid,))
    assert db.user(uid, "select public.claim_roster_records()").fetchone()[0] == 1
    assert db.admin("select verified_user_id from public.student_roster where university_id = %s", (uni,)).fetchone()[0] == uid
    assert db.user(uid, "select public.claim_roster_records()").fetchone()[0] == 0  # idempotent


def test_cannot_claim_someone_elses_roster_record(db):
    uni = db.new_org("university")
    uid = db.new_user()
    db.admin("update auth.users set email_confirmed_at = now() where id = %s", (uid,))
    roster_row(db, uni, "someone.else@example.test")
    assert db.user(uid, "select public.claim_roster_records()").fetchone()[0] == 0
