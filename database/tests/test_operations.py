"""Transactional operations from 0010_operations.sql, called as real authenticated users."""

import json

import pytest


@pytest.fixture
def campus(db):
    """University A with a CSE-2027 drive (min CGPA 7.5, python required) on Acme's campus listing."""
    recruiter, admin, other_admin = db.new_user("Ravi"), db.new_user("Kavya"), db.new_user("Imran")
    company, uni, other_uni = db.new_org("company"), db.new_org("university"), db.new_org("university")
    db.member(recruiter, company, "recruiter")
    db.member(admin, uni, "admin")
    db.member(other_admin, other_uni, "admin")
    opp = db.new_opportunity(company, recruiter, visibility="campus", skills=("python",))
    drive = db.admin(
        """insert into public.campus_drives
             (university_id, opportunity_id, allowed_branches, batch, min_cgpa, required_skills, deadline, authorized_by)
           values (%s, %s, '{cse,it}', 2027, 7.5, '{python}', now() + interval '3 days', %s) returning id""",
        (uni, opp, admin),
    ).fetchone()[0]

    def student(name, branch="cse", batch=2027, cgpa="8.0", skills=("python",)):
        uid = db.new_user(name)
        db.admin("update public.profiles set skills = %s where user_id = %s", (list(skills), uid))
        db.admin(
            """insert into public.student_roster (university_id, student_id, name, email, verified_user_id, branch, batch, cgpa)
               values (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (uni, f"S-{uid.hex[:6]}", name, f"{uid.hex[:6]}@uni.test", uid, branch, batch, cgpa),
        )
        return uid

    return dict(recruiter=recruiter, admin=admin, other_admin=other_admin, company=company, uni=uni,
                other_uni=other_uni, opp=opp, drive=drive, student=student)


def eligibility(db, uid, drive):
    return db.user(uid, "select public.evaluate_drive_eligibility(%s)", (drive,)).fetchone()[0]


def codes(result):
    return sorted(r["code"] for r in result["reasons"])


# --- eligibility ------------------------------------------------------------------


def test_exact_threshold_is_eligible(db, campus):
    uid = campus["student"]("Vikram", cgpa="7.50")
    result = eligibility(db, uid, campus["drive"])
    assert result["eligible"] is True and result["matching_skills"] == ["python"]


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({"cgpa": "7.49"}, ["CGPA_BELOW_MINIMUM"]),
        ({"cgpa": None}, ["CGPA_MISSING"]),
        ({"branch": "ece"}, ["BRANCH_NOT_ALLOWED"]),
        ({"batch": 2028}, ["BATCH_MISMATCH"]),
        ({"skills": ("sql",)}, ["MISSING_REQUIRED_SKILL"]),
    ],
)
def test_each_failed_rule_has_a_reason(db, campus, kwargs, expected):
    uid = campus["student"]("Case", **kwargs)
    result = eligibility(db, uid, campus["drive"])
    assert result["eligible"] is False and codes(result) == expected


def test_outsider_cannot_see_drive(db, campus):
    outsider = db.new_user()
    with db.fails(sqlstate="PT404"):
        eligibility(db, outsider, campus["drive"])


def test_admin_gets_not_on_roster(db, campus):
    assert "NOT_ON_ROSTER" in codes(eligibility(db, campus["admin"], campus["drive"]))


# --- submit_application -------------------------------------------------------------


def submit(db, uid, opp, drive=None):
    return db.user(uid, "select public.submit_application(%s, %s)", (opp, drive)).fetchone()[0]


def test_eligible_student_applies_once_with_snapshots(db, campus):
    uid = campus["student"]("Asha")
    app = submit(db, uid, campus["opp"], campus["drive"])
    assert app["status"] == "applied" and app["drive_id"] == str(campus["drive"])
    snap, elig = db.admin(
        "select profile_snapshot, eligibility_snapshot from public.applications where id = %s", (app["id"],)
    ).fetchone()
    assert snap["skills"] == ["python"] and elig["eligible"] is True and elig["record"]["branch"] == "cse"
    with db.fails(sqlstate="PT409"):
        submit(db, uid, campus["opp"], campus["drive"])


def test_campus_listing_requires_drive(db, campus):
    uid = campus["student"]("Asha")
    with db.fails(sqlstate="PT403") as caught:
        submit(db, uid, campus["opp"])


def test_ineligible_student_is_refused(db, campus):
    uid = campus["student"]("Low", cgpa="6.0")
    with db.fails(sqlstate="PT403"):
        submit(db, uid, campus["opp"], campus["drive"])
    assert db.admin("select count(*) from public.applications").fetchone()[0] == 0


def test_unaffiliated_user_cannot_apply_to_campus_listing(db, campus):
    with db.fails(sqlstate="PT404"):
        submit(db, db.new_user(), campus["opp"], campus["drive"])


def test_public_listing_needs_no_university(db, campus):
    public_opp = db.new_opportunity(campus["company"], campus["recruiter"])
    assert submit(db, db.new_user(), public_opp)["status"] == "applied"


def test_closed_or_expired_listing_refused(db, campus):
    closed = db.new_opportunity(campus["company"], campus["recruiter"])
    db.admin("update public.opportunities set status = 'closed' where id = %s", (closed,))
    expired = db.new_opportunity(campus["company"], campus["recruiter"])
    db.admin("update public.opportunities set deadline = now() - interval '1 minute' where id = %s", (expired,))
    uid = db.new_user()
    with db.fails(sqlstate="PT409"):
        submit(db, uid, closed)
    with db.fails(sqlstate="PT409"):
        submit(db, uid, expired)


def test_drive_for_another_opportunity_rejected(db, campus):
    other = db.new_opportunity(campus["company"], campus["recruiter"])
    uid = campus["student"]("Asha")
    with db.fails(sqlstate="PT422"):
        submit(db, uid, other, campus["drive"])


# --- commit_roster ------------------------------------------------------------------


ROWS = [
    {"student_id": "CSE27-001", "name": "Asha", "email": "Asha@Uni.test", "branch": "CSE", "batch": 2027, "cgpa": "8.1"},
    {"student_id": "CSE27-002", "name": "Vikram", "email": "v@uni.test", "branch": "CSE", "batch": 2027, "cgpa": ""},
]


def commit(db, uid, uni, rows):
    return db.user(uid, "select public.commit_roster(%s, %s)", (uni, json.dumps(rows))).fetchone()[0]


def test_roster_commit_counts_and_is_idempotent(db, campus):
    assert commit(db, campus["admin"], campus["uni"], ROWS) == {"inserted": 2, "updated": 0, "unchanged": 0}
    changed = [ROWS[0], {**ROWS[1], "cgpa": "7.9"}]
    assert commit(db, campus["admin"], campus["uni"], changed) == {"inserted": 0, "updated": 1, "unchanged": 1}


def test_roster_commit_preserves_account_link(db, campus):
    uid = campus["student"]("Linked")
    sid = db.admin("select student_id from public.student_roster where verified_user_id = %s", (uid,)).fetchone()[0]
    commit(db, campus["admin"], campus["uni"],
           [{"student_id": sid, "name": "Renamed", "email": "r@uni.test", "branch": "cse", "batch": 2027, "cgpa": "9"}])
    assert db.admin("select verified_user_id, name from public.student_roster where student_id = %s", (sid,)).fetchone() == (uid, "Renamed")


def test_roster_commit_is_all_or_nothing(db, campus):
    bad = ROWS + [{"student_id": "X", "name": "Bad", "email": "b@uni.test", "branch": "cse", "batch": 2027, "cgpa": "11"}]
    with db.fails():
        commit(db, campus["admin"], campus["uni"], bad)
    assert db.admin("select count(*) from public.student_roster where student_id like 'CSE27-%%'").fetchone()[0] == 0


def test_other_university_admin_cannot_commit(db, campus):
    with db.fails(sqlstate="PT403"):
        commit(db, campus["other_admin"], campus["uni"], ROWS)


# --- reports ------------------------------------------------------------------------


def test_report_counts_only_drive_applications(db, campus):
    a, b = campus["student"]("A"), campus["student"]("B")
    app_a = submit(db, a, campus["opp"], campus["drive"])["id"]
    submit(db, b, campus["opp"], campus["drive"])
    public_opp = db.new_opportunity(campus["company"], campus["recruiter"])
    submit(db, a, public_opp)  # public application: never in campus reports
    db.user(campus["recruiter"], "update public.applications set status = 'offered' where id = %s", (app_a,))

    report = db.user(campus["admin"], "select public.university_report(%s)", (campus["uni"],)).fetchone()[0]
    assert (report["applications"], report["offered"], report["students_with_offers"]) == (2, 1, 1)
    branch = db.user(campus["admin"], "select public.university_report(%s, 'ECE')", (campus["uni"],)).fetchone()[0]
    assert branch["applications"] == 0
    with db.fails(sqlstate="PT403"):
        db.user(campus["other_admin"], "select public.university_report(%s)", (campus["uni"],))


def test_drive_admin_sees_drive_applications_only(db, campus):
    uid = campus["student"]("A")
    submit(db, uid, campus["opp"], campus["drive"])
    count = "select count(*) from public.applications"
    assert db.user(campus["admin"], count).fetchone()[0] == 1
    assert db.user(campus["other_admin"], count).fetchone()[0] == 0


# --- mentors and names --------------------------------------------------------------


def test_mentor_directory_filters_and_projects(db):
    m1, m2, viewer = db.new_user("Arjun"), db.new_user("Sara"), db.new_user()
    db.admin("update public.profiles set skills = '{docker,python}', is_public = false where user_id = %s", (m1,))
    db.admin("insert into public.mentors (user_id, niche) values (%s, 'Data engineering'), (%s, 'Frontend')", (m1, m2))
    result = db.user(viewer, "select public.list_mentors(null, 'Docker')").fetchone()[0]
    assert result["total"] == 1
    item = result["items"][0]
    assert item["name"] == "Arjun" and item["match_reason"] == "Matches skill: docker"
    assert db.user(viewer, "select public.list_mentors('front')").fetchone()[0]["total"] == 1


def test_display_names_only_for_related_people(db):
    hidden, stranger = db.new_user("Hidden"), db.new_user()
    db.admin("update public.profiles set is_public = false where user_id = %s", (hidden,))
    rows = db.user(stranger, "select name from public.display_names(%s)", ([hidden],)).fetchall()
    assert rows == []
