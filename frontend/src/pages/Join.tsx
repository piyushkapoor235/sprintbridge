import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Building2, GraduationCap, Rocket, UsersRound } from "lucide-react";
import { useAuth } from "../auth";
import { useQuery } from "../lib/useQuery";
import type { RoleApplication, RoleKind } from "../lib/types";
import { Badge, ErrorMessage, Heading, Loading, date } from "../components/ui";

export const ROLE_LABEL: Record<RoleKind, string> = {
  recruiter: "Recruiter",
  university_admin: "University placement office",
  mentor: "Mentor",
};

const ROLES: { kind: RoleKind; icon: typeof Building2; title: string; text: string; capability: string }[] = [
  {
    kind: "recruiter",
    icon: Building2,
    title: "Recruiter",
    text: "Post jobs and internships, share campus listings with universities, and manage applicants.",
    capability: "recruiter",
  },
  {
    kind: "university_admin",
    icon: GraduationCap,
    title: "University placement office",
    text: "Import your student roster, authorize campus drives and track placement outcomes.",
    capability: "university_admin",
  },
  {
    kind: "mentor",
    icon: UsersRound,
    title: "Mentor",
    text: "Offer paid or free sessions in your area of expertise. Calibrated mentors can also verify skills.",
    capability: "mentor",
  },
];

const STATUS_TONE = { pending: "amber", approved: "green", rejected: "" } as const;

export default function Join() {
  const { api, me, reload } = useAuth();
  const [params] = useSearchParams();
  const applications = useQuery<RoleApplication[]>("/me/role-applications");
  const wanted = params.get("as");
  const [kind, setKind] = useState<RoleKind>(
    ROLES.some((r) => r.kind === wanted) ? (wanted as RoleKind) : "recruiter",
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [message, setMessage] = useState("");
  const has = (capability: string) => me!.capabilities.includes(capability as never);
  const pending = (k: RoleKind) => applications.data?.some((a) => a.kind === k && a.status === "pending");
  const role = ROLES.find((r) => r.kind === kind)!;

  return (
    <>
      <Heading eyebrow="Roles & access" title="Join as a partner">
        Every account starts as a student or job seeker. Recruiters, universities and mentors apply here; a
        SprintBridge operator checks each application before access is granted, so nobody can pose as a company or
        college.
      </Heading>

      <div className="plan-grid">
        {ROLES.map((r) => (
          <button
            type="button"
            key={r.kind}
            className={`panel plan role-choice ${kind === r.kind ? "current" : ""}`}
            aria-pressed={kind === r.kind}
            onClick={() => {
              setKind(r.kind);
              setMessage("");
              setError(null);
            }}
          >
            <r.icon size={22} />
            <strong>{r.title}</strong>
            <span className="small muted">{r.text}</span>
            {has(r.capability) ? (
              <Badge tone="green">You have this role</Badge>
            ) : pending(r.kind) ? (
              <Badge tone="amber">Under review</Badge>
            ) : null}
          </button>
        ))}
        <Link className="panel plan role-choice" to="/ventures">
          <Rocket size={22} />
          <strong>Founder</strong>
          <span className="small muted">
            No approval needed: post a venture and invite collaborators under NDA right away.
          </span>
        </Link>
      </div>

      <section className="panel" style={{ marginTop: 22 }}>
        <ErrorMessage error={error} />
        {message && (
          <p className="notice success" role="status">
            {message}
          </p>
        )}
        {has(role.capability) ? (
          <p>
            You already have the {role.title.toLowerCase()} role. Find it in the menu on the left.
          </p>
        ) : pending(kind) ? (
          <p>Your {role.title.toLowerCase()} application is being reviewed. You'll get access as soon as it's approved.</p>
        ) : (
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              if (busy) return;
              const data = new FormData(e.currentTarget);
              const text = (name: string) => String(data.get(name) ?? "").trim();
              setBusy(true);
              setError(null);
              setMessage("");
              try {
                await api("/me/role-applications", {
                  method: "POST",
                  body: JSON.stringify(
                    kind === "mentor"
                      ? { kind, niche: text("niche"), job_title: text("job_title"),
                          experience_summary: text("experience_summary"), website: text("website") || null }
                      : { kind, organization_name: text("organization_name"), job_title: text("job_title"),
                          experience_summary: text("experience_summary"), website: text("website") || null },
                  ),
                });
                setMessage("Application sent. An operator will review it; you'll see the decision here.");
                applications.reload();
                reload();
              } catch (err) {
                setError(err);
              } finally {
                setBusy(false);
              }
            }}
          >
            <h2 style={{ marginTop: 0 }}>Apply as {role.title.toLowerCase()}</h2>
            {kind === "mentor" ? (
              <label>
                Area of expertise
                <input name="niche" required minLength={2} maxLength={120} placeholder="e.g. Data engineering…" />
              </label>
            ) : (
              <label>
                {kind === "recruiter" ? "Company name" : "University or college name"}
                <input
                  name="organization_name"
                  required
                  minLength={2}
                  maxLength={200}
                  placeholder={kind === "recruiter" ? "e.g. Acme Analytics…" : "e.g. Demo University A…"}
                />
              </label>
            )}
            <label>
              Your title <small>Optional</small>
              <input
                name="job_title"
                maxLength={120}
                placeholder={
                  kind === "recruiter" ? "e.g. Talent acquisition lead…"
                    : kind === "university_admin" ? "e.g. Training & placement officer…"
                    : "e.g. Senior data engineer…"
                }
              />
            </label>
            <label>
              {kind === "mentor" ? "LinkedIn or portfolio" : "Official website"} <small>Optional, helps us verify you</small>
              <input name="website" type="url" maxLength={300} placeholder="https://…" />
            </label>
            <label>
              {kind === "mentor" ? "Your experience" : "Anything we should know"} <small>Optional</small>
              <textarea name="experience_summary" maxLength={2000} rows={3} />
            </label>
            <p className="small muted">
              Use your work email if you can: it makes verification faster. Joining an organization that already uses
              SprintBridge is checked with extra care.
            </p>
            <button className="primary" disabled={busy}>
              {busy ? "Sending…" : "Send application"}
            </button>
          </form>
        )}
      </section>

      <section style={{ marginTop: 28 }}>
        <h2>Your applications</h2>
        {applications.loading && <Loading />}
        <ErrorMessage error={applications.error} />
        {applications.data?.length === 0 && <p className="muted">No applications yet.</p>}
        {applications.data && applications.data.length > 0 && (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Role</th>
                  <th>For</th>
                  <th>Sent</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {applications.data.map((a) => (
                  <tr key={a.id}>
                    <td>{ROLE_LABEL[a.kind]}</td>
                    <td>{a.organization_name ?? a.niche}</td>
                    <td>{date(a.created_at)}</td>
                    <td>
                      <Badge tone={STATUS_TONE[a.status]}>{a.status}</Badge>
                      {a.decision_note && <div className="small muted">{a.decision_note}</div>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <p className="small muted" style={{ marginTop: 24 }}>
        Students: you don't need to apply. When your university imports its placement roster with your email, your
        account is linked automatically after you confirm that email, and campus drives open up for you.
      </p>
    </>
  );
}
