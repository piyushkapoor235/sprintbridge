import { useState } from "react";
import { AlertTriangle } from "lucide-react";
import { useAuth } from "../auth";
import { useQuery } from "../lib/useQuery";
import type { OperatorQueue, PendingRoleApplication } from "../lib/types";
import { ROLE_LABEL } from "./Join";
import { Badge, Empty, ErrorMessage, Heading, Loading, date, inr } from "../components/ui";

export default function Operator() {
  const { api } = useAuth();
  const queue = useQuery<OperatorQueue>("/operator/queue");
  const roles = useQuery<PendingRoleApplication[]>("/operator/role-applications");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [message, setMessage] = useState("");
  const act = async (path: string, body: object | undefined, done: string) => {
    setBusy(true);
    setError(null);
    setMessage("");
    try {
      await api(path, { method: "POST", body: body ? JSON.stringify(body) : undefined });
      setMessage(done);
      queue.reload();
      roles.reload();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };
  const moderate = (target_type: string, target_id: string, action: string) =>
    act("/operator/moderate", { target_type, target_id, action }, `Done: ${action}.`);
  const q = queue.data;

  return (
    <>
      <Heading eyebrow="Trust & safety" title="Operator console">
        Review reports and automatic scam flags, settle held payouts, and see the audit trail of sensitive actions.
      </Heading>
      <ErrorMessage error={queue.error || error} />
      {message && (
        <p className="notice success" role="status">
          {message}
        </p>
      )}
      {queue.loading && <Loading />}
      {q && (
        <div className="stack">
          <div className="kpi-grid">
            <div className="kpi">
              <span>Reported items</span>
              <strong>{q.reports.length}</strong>
            </div>
            <div className="kpi">
              <span>Flagged listings</span>
              <strong>{q.flagged.length}</strong>
            </div>
            <div className="kpi">
              <span>Payouts to settle</span>
              <strong>{q.payouts.length}</strong>
            </div>
            <div className="kpi">
              <span>Recent audit events</span>
              <strong>{q.audit.length}</strong>
            </div>
          </div>

          <section>
            <h2 style={{ marginBottom: 4 }}>Role applications</h2>
            <p className="muted" style={{ marginBottom: 12 }}>
              Check that the person really works at the company or college (work email, website, LinkedIn) before
              approving. Approval creates their workspace or mentor profile.
            </p>
            <ErrorMessage error={roles.error} />
            {roles.data?.length === 0 && (
              <Empty title="No applications waiting">New recruiter, university and mentor applications appear here.</Empty>
            )}
            <div className="stack">
              {roles.data?.map((a) => (
                <article className="panel" key={a.id}>
                  <div className="section-heading">
                    <div>
                      <h2>
                        {a.applicant_name} · {ROLE_LABEL[a.kind]}
                      </h2>
                      <p className="muted">
                        {a.applicant_email} · {a.organization_name ?? a.niche}
                        {a.job_title && ` · ${a.job_title}`} · sent {date(a.created_at)}
                      </p>
                    </div>
                    <Badge tone="amber">Pending</Badge>
                  </div>
                  {a.existing_organization && (
                    <p className="notice warning">
                      <AlertTriangle size={16} aria-hidden="true" /> Approving adds them to the existing organization
                      “{a.existing_organization}”. Confirm they really work there.
                    </p>
                  )}
                  {a.website && (
                    <p className="small">
                      <a href={a.website} target="_blank" rel="noreferrer noopener">
                        {a.website}
                      </a>
                    </p>
                  )}
                  {a.experience_summary && <blockquote>{a.experience_summary}</blockquote>}
                  <div className="actions">
                    <button
                      className="primary"
                      disabled={busy}
                      onClick={() =>
                        act(`/operator/role-applications/${a.id}`, { approve: true }, `${a.applicant_name} approved.`)
                      }
                    >
                      Approve
                    </button>
                    <button
                      className="secondary"
                      disabled={busy}
                      onClick={() =>
                        act(
                          `/operator/role-applications/${a.id}`,
                          { approve: false, note: "We couldn't verify this. Reply from your work email and apply again." },
                          `${a.applicant_name} rejected.`,
                        )
                      }
                    >
                      Reject
                    </button>
                  </div>
                </article>
              ))}
            </div>
          </section>

          <section>
            <h2 style={{ marginBottom: 12 }}>Reports</h2>
            {q.reports.length === 0 && <Empty title="No open reports">Reports from users appear here.</Empty>}
            <div className="stack">
              {q.reports.map((r) => (
                <article className="panel" key={r.target_id}>
                  <div className="section-heading">
                    <div>
                      <h2>{r.title}</h2>
                      <p className="muted">
                        {r.target_type} · {r.open_reports} report{r.open_reports === 1 ? "" : "s"} · {r.reasons.join(", ")}
                      </p>
                    </div>
                    {r.moderation_status && (
                      <Badge tone={r.moderation_status === "visible" ? "" : "amber"}>
                        {r.moderation_status.replaceAll("_", " ")}
                      </Badge>
                    )}
                  </div>
                  {(r.red_flags ?? []).length > 0 && (
                    <p className="notice warning">
                      <AlertTriangle size={16} aria-hidden="true" /> {r.red_flags!.join(" · ")}
                    </p>
                  )}
                  {(r.details ?? []).map((d, i) => (
                    <blockquote key={i}>{d}</blockquote>
                  ))}
                  <div className="actions">
                    {r.target_type === "opportunity" && (
                      <>
                        <button className="primary" disabled={busy} onClick={() => moderate(r.target_type, r.target_id, "remove")}>
                          Remove listing
                        </button>
                        <button className="secondary" disabled={busy} onClick={() => moderate(r.target_type, r.target_id, "restore")}>
                          Restore & dismiss
                        </button>
                      </>
                    )}
                    <button className="secondary" disabled={busy} onClick={() => moderate(r.target_type, r.target_id, "dismiss")}>
                      Dismiss
                    </button>
                  </div>
                </article>
              ))}
            </div>
          </section>

          <section>
            <h2 style={{ marginBottom: 4 }}>Automatically flagged listings</h2>
            <p className="muted" style={{ marginBottom: 12 }}>
              Listings whose text asks candidates to pay, take deposits, or move off-platform.
            </p>
            {q.flagged.length === 0 ? (
              <Empty title="Nothing flagged">Scam-phrase detection runs on every listing.</Empty>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Listing</th>
                      <th>Company</th>
                      <th>Flags</th>
                      <th>Status</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {q.flagged.map((f) => (
                      <tr key={f.id}>
                        <td>{f.title}</td>
                        <td>{f.company}</td>
                        <td>{f.red_flags.join(", ")}</td>
                        <td>
                          <Badge tone={f.moderation_status === "visible" ? "amber" : ""}>
                            {f.moderation_status.replaceAll("_", " ")}
                          </Badge>
                        </td>
                        <td>
                          {f.moderation_status === "visible" ? (
                            <button className="secondary" disabled={busy} onClick={() => moderate("opportunity", f.id, "hide")}>
                              Hide for review
                            </button>
                          ) : (
                            <button className="secondary" disabled={busy} onClick={() => moderate("opportunity", f.id, "restore")}>
                              Restore
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section>
            <div className="section-heading">
              <div>
                <h2>Payouts to settle</h2>
                <p className="muted">Held through the 7-day window, or disputed by a student. Test mode.</p>
              </div>
              <button
                className="secondary"
                disabled={busy}
                onClick={() => act("/operator/payouts/release-due", undefined, "Released payouts past their window.")}
              >
                Release all due
              </button>
            </div>
            {q.payouts.length === 0 ? (
              <Empty title="Nothing to settle">Held and disputed payouts appear here.</Empty>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Mentor</th>
                      <th>For</th>
                      <th>Amount</th>
                      <th>Status</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {q.payouts.map((p) => (
                      <tr key={p.id}>
                        <td>{p.mentor}</td>
                        <td>{p.source === "verification" ? "Verification" : "Session"}</td>
                        <td>{inr(p.net_inr)}</td>
                        <td>
                          <Badge tone={p.status === "disputed" ? "amber" : "blue"}>
                            {p.status === "held" ? `held until ${date(p.release_after)}` : p.status}
                          </Badge>
                        </td>
                        <td className="actions" style={{ marginTop: 0 }}>
                          <button className="secondary" disabled={busy} onClick={() => act(`/operator/payouts/${p.id}`, { action: "release" }, "Payout released.")}>
                            Release
                          </button>
                          <button className="secondary" disabled={busy} onClick={() => act(`/operator/payouts/${p.id}`, { action: "refund" }, "Refunded to the student.")}>
                            Refund
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section>
            <h2 style={{ marginBottom: 12 }}>Audit log</h2>
            {q.audit.length === 0 ? (
              <Empty title="No events yet">Payments, decisions and moderation are recorded here.</Empty>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>When</th>
                      <th>Who</th>
                      <th>Action</th>
                      <th>Details</th>
                    </tr>
                  </thead>
                  <tbody>
                    {q.audit.map((a) => (
                      <tr key={a.id}>
                        <td>{new Date(a.created_at).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })}</td>
                        <td>{a.actor}</td>
                        <td>
                          <code>{a.action}</code>
                        </td>
                        <td className="small muted">
                          {Object.entries(a.details)
                            .filter(([, v]) => v !== null && v !== "")
                            .map(([k, v]) => `${k}: ${String(v)}`)
                            .join(" · ")}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </div>
      )}
    </>
  );
}
