"""Schema and row-security checks against a throwaway local Postgres.

Run from the repo root (pgserver ships Postgres binaries; it needs Python <= 3.12):

    uv run --python 3.12 --with pgserver --with 'psycopg[binary]' --with pytest \
        pytest database/tests -q

Each test runs inside a transaction that is rolled back, so tests are independent.
"""

import psycopg
from psycopg import errors


# --- core identity ----------------------------------------------------------------


def test_signup_creates_profile_with_metadata_name(db):
    uid = db.new_user("Asha")
    assert db.user(uid, "select name from public.profiles where user_id = %s", (uid,)).fetchone()[0] == "Asha"


def test_profile_skills_are_normalized(db):
    uid = db.new_user()
    db.user(uid, "update public.profiles set skills = %s where user_id = %s",
            ([" Python", "SQL", "python", ""], uid))
    skills = db.admin("select skills from public.profiles where user_id = %s", (uid,)).fetchone()[0]
    assert skills == ["python", "sql"]


def test_user_cannot_edit_another_profile(db):
    me, other = db.new_user(), db.new_user("Other")
    db.user(me, "update public.profiles set name = 'hacked' where user_id = %s", (other,))
    assert db.admin("select name from public.profiles where user_id = %s", (other,)).fetchone()[0] == "Other"


def test_profile_owner_column_is_not_writable(db):
    uid = db.new_user()
    with db.fails(errors.InsufficientPrivilege):
        db.user(uid, "update public.profiles set user_id = gen_random_uuid() where user_id = %s", (uid,))


def test_invalid_portfolio_url_rejected(db):
    uid = db.new_user()
    with db.fails(errors.CheckViolation):
        db.user(uid, "update public.profiles set portfolio_url = 'javascript:alert(1)' where user_id = %s", (uid,))


def test_user_cannot_self_grant_role_or_membership(db):
    uid = db.new_user()
    org = db.new_org("university")
    with db.fails(errors.InsufficientPrivilege):
        db.user(uid, "insert into public.role_grants (user_id, role) values (%s, 'mentor')", (uid,))
    with db.fails(errors.InsufficientPrivilege):
        db.user(uid, "insert into public.memberships (user_id, organization_id, role) values (%s, %s, 'admin')",
                (uid, org))


def test_membership_role_must_match_org_type(db):
    uid = db.new_user()
    company = db.new_org("company")
    with db.fails(errors.CheckViolation):
        db.member(uid, company, "admin")


def test_anon_has_no_table_access(db):
    db.conn.execute("set local role anon")
    with db.fails(errors.InsufficientPrivilege):
        db.conn.execute("select * from public.profiles")
    db.conn.execute("reset role")


# --- opportunities -----------------------------------------------------------------


def test_recruiter_creates_listing_only_for_own_company(db):
    recruiter, student = db.new_user(), db.new_user()
    mine, theirs = db.new_org("company"), db.new_org("company")
    db.member(recruiter, mine, "recruiter")
    insert = """insert into public.opportunities (company_id, title, type, deadline)
                values (%s, 'Role', 'job', now() + interval '1 day')"""
    db.user(recruiter, insert, (mine,))
    with db.fails(errors.InsufficientPrivilege):
        db.user(recruiter, insert, (theirs,))
    with db.fails(errors.InsufficientPrivilege):
        db.user(student, insert, (mine,))


def test_campus_listing_hidden_until_linked_drive_and_verified_student(db):
    recruiter, admin, student, outsider = (db.new_user() for _ in range(4))
    company, uni = db.new_org("company"), db.new_org("university")
    db.member(recruiter, company, "recruiter")
    db.member(admin, uni, "admin")
    opp = db.new_opportunity(company, recruiter, visibility="campus")
    db.admin("""insert into public.student_roster (university_id, student_id, name, email, verified_user_id, branch, batch, cgpa)
                values (%s, 'S1', 'Student', 's@uni.test', %s, 'CSE', 2027, 8.1)""", (uni, student))

    count = "select count(*) from public.opportunities where id = %s"
    assert db.user(student, count, (opp,)).fetchone()[0] == 0
    db.user(admin, """insert into public.campus_drives (university_id, opportunity_id, batch, deadline)
                      values (%s, %s, 2027, now() + interval '3 days')""", (uni, opp))
    assert db.user(student, count, (opp,)).fetchone()[0] == 1
    assert db.user(admin, count, (opp,)).fetchone()[0] == 1
    assert db.user(outsider, count, (opp,)).fetchone()[0] == 0


# --- applications -----------------------------------------------------------------


def _application(db):
    recruiter, student, other_recruiter = db.new_user(), db.new_user(), db.new_user()
    company, other_company = db.new_org("company"), db.new_org("company")
    db.member(recruiter, company, "recruiter")
    db.member(other_recruiter, other_company, "recruiter")
    opp = db.new_opportunity(company, recruiter)
    app = db.admin("""insert into public.applications (opportunity_id, applicant_id, profile_snapshot)
                      values (%s, %s, '{}') returning id""", (opp, student)).fetchone()[0]
    return recruiter, student, other_recruiter, opp, app


def test_applications_cannot_be_inserted_directly(db):
    _, student, _, opp, _ = _application(db)
    with db.fails(errors.InsufficientPrivilege):
        db.user(student, """insert into public.applications (opportunity_id, applicant_id, profile_snapshot)
                            values (%s, %s, '{}')""", (opp, student))


def test_status_transitions_and_ownership(db):
    recruiter, student, other_recruiter, _, app = _application(db)
    status = "select status from public.applications where id = %s"
    set_status = "update public.applications set status = %s where id = %s"

    db.user(student, set_status, ("offered", app))          # applicant: no matching row
    db.user(other_recruiter, set_status, ("offered", app))  # other company: no matching row
    assert db.admin(status, (app,)).fetchone()[0] == "applied"

    db.user(recruiter, set_status, ("shortlisted", app))
    db.user(recruiter, set_status, ("shortlisted", app))    # repeat is a no-op
    with db.fails(sqlstate="PT409"):
        db.user(recruiter, set_status, ("applied", app))
    db.user(recruiter, set_status, ("offered", app))
    with db.fails(sqlstate="PT409"):
        db.user(recruiter, set_status, ("rejected", app))   # offered is terminal
    assert db.admin(status, (app,)).fetchone()[0] == "offered"


def test_eligibility_snapshot_column_not_readable(db):
    _, student, _, _, app = _application(db)
    with db.fails(errors.InsufficientPrivilege):
        db.user(student, "select eligibility_snapshot from public.applications where id = %s", (app,))


def test_duplicate_application_rejected(db):
    _, student, _, opp, _ = _application(db)
    with db.fails(errors.UniqueViolation):
        db.admin("""insert into public.applications (opportunity_id, applicant_id, profile_snapshot)
                    values (%s, %s, '{}')""", (opp, student))


def test_application_drive_must_match_opportunity(db):
    recruiter, admin, student = db.new_user(), db.new_user(), db.new_user()
    company, uni = db.new_org("company"), db.new_org("university")
    db.member(recruiter, company, "recruiter")
    opp_a = db.new_opportunity(company, recruiter)
    opp_b = db.new_opportunity(company, recruiter)
    drive = db.admin("""insert into public.campus_drives (university_id, opportunity_id, batch, deadline, authorized_by)
                        values (%s, %s, 2027, now() + interval '1 day', %s) returning id""",
                     (uni, opp_a, admin)).fetchone()[0]
    with db.fails(errors.ForeignKeyViolation):
        db.admin("""insert into public.applications (opportunity_id, applicant_id, drive_id, profile_snapshot)
                    values (%s, %s, %s, '{}')""", (opp_b, student, drive))


# --- roster -------------------------------------------------------------------------


def test_roster_private_to_own_university_and_link_preserved(db):
    admin, other_admin, student = db.new_user(), db.new_user(), db.new_user()
    uni, other_uni = db.new_org("university"), db.new_org("university")
    db.member(admin, uni, "admin")
    db.member(other_admin, other_uni, "admin")
    row = db.admin("""insert into public.student_roster (university_id, student_id, name, email, verified_user_id, branch, batch)
                      values (%s, 'S1', 'A', 'A@Uni.test', %s, ' CSE ', 2027) returning id""",
                   (uni, student)).fetchone()[0]
    read = "select count(*) from public.student_roster where id = %s"
    assert db.user(admin, read, (row,)).fetchone()[0] == 1
    assert db.user(student, read, (row,)).fetchone()[0] == 1
    assert db.user(other_admin, read, (row,)).fetchone()[0] == 0
    assert db.admin("select branch, email from public.student_roster where id = %s", (row,)).fetchone() == ("cse", "a@uni.test")
    with db.fails(errors.InsufficientPrivilege):
        db.user(admin, "update public.student_roster set cgpa = 9.9 where id = %s", (row,))
    with db.fails(errors.CheckViolation):
        db.admin("update public.student_roster set verified_user_id = null where id = %s", (row,))


# --- mentors ------------------------------------------------------------------------


def test_mentor_request_flow(db):
    mentor_user, other_mentor_user, student = db.new_user(), db.new_user(), db.new_user()
    mentor = db.admin("insert into public.mentors (user_id, niche) values (%s, 'Data') returning id",
                      (mentor_user,)).fetchone()[0]
    db.admin("insert into public.mentors (user_id, niche) values (%s, 'Design')", (other_mentor_user,))

    with db.fails(errors.InsufficientPrivilege):  # cannot request yourself
        db.user(mentor_user, "insert into public.mentor_requests (mentor_id, note) values (%s, 'hi')", (mentor,))
    req = db.user(student, "insert into public.mentor_requests (mentor_id, note) values (%s, 'Help with SQL') returning id",
                  (mentor,)).fetchone()[0]
    with db.fails(errors.UniqueViolation):
        db.user(student, "insert into public.mentor_requests (mentor_id, note) values (%s, 'again')", (mentor,))

    decide = "update public.mentor_requests set status = %s where id = %s"
    db.user(other_mentor_user, decide, ("accepted", req))
    db.user(student, decide, ("accepted", req))
    assert db.admin("select status from public.mentor_requests where id = %s", (req,)).fetchone()[0] == "pending"
    db.user(mentor_user, decide, ("accepted", req))
    with db.fails(sqlstate="PT409"):
        db.user(mentor_user, decide, ("declined", req))
    assert db.user(other_mentor_user, "select count(*) from public.mentor_requests where id = %s", (req,)).fetchone()[0] == 0


# --- skill intelligence ------------------------------------------------------------


def test_skill_evidence_cannot_be_written_by_users(db):
    uid = db.new_user()
    with db.fails(errors.InsufficientPrivilege):
        db.user(uid, """insert into public.skill_evidence (user_id, skill, source, context_type)
                        values (%s, 'python', 'resume', 'project')""", (uid,))


def test_external_jd_is_private_and_hashed(db):
    owner, other = db.new_user(), db.new_user()
    jd = db.user(owner, "insert into public.external_jds (text) values ('We need Python') returning id, sha256",
                 ()).fetchone()
    assert len(jd[1]) == 64
    assert db.user(other, "select count(*) from public.external_jds where id = %s", (jd[0],)).fetchone()[0] == 0


# --- ventures -----------------------------------------------------------------------


def test_only_founder_decides_collaboration(db):
    founder, member, stranger = db.new_user(), db.new_user(), db.new_user()
    venture = db.user(founder, """insert into public.ventures (title, teaser, problem, industry, needed_skills)
                                  values ('V', 'T', 'P', 'Edtech', %s) returning id""", (["React", "react"],)).fetchone()[0]
    assert db.admin("select needed_skills from public.ventures where id = %s", (venture,)).fetchone()[0] == ["react"]
    req = db.user(member, "insert into public.collaboration_requests (venture_id, note, nda_accepted) values (%s, 'Join', true) returning id",
                  (venture,)).fetchone()[0]
    db.user(stranger, "update public.collaboration_requests set status = 'accepted' where id = %s", (req,))
    assert db.admin("select status from public.collaboration_requests where id = %s", (req,)).fetchone()[0] == "pending"
    db.user(founder, "update public.collaboration_requests set status = 'accepted' where id = %s", (req,))
    assert db.admin("select status from public.collaboration_requests where id = %s", (req,)).fetchone()[0] == "accepted"
