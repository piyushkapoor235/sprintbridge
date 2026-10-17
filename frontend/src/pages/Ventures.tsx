import { useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { ArrowLeft, Lock, Rocket } from "lucide-react";
import { useAuth } from "../auth";
import { useQuery } from "../lib/useQuery";
import { skillList } from "../lib/rules";
import type { CollaborationRequest, Page, Venture } from "../lib/types";
import {
  Badge,
  Empty,
  ErrorMessage,
  Heading,
  Loading,
  Pagination,
  Tags,
  date,
} from "../components/ui";

const COMPENSATION: Record<string, string> = {
  paid: "Paid",
  stipend: "Stipend",
  equity: "Equity",
  unpaid: "Unpaid",
  to_discuss: "To discuss",
};
const STAGE: Record<string, string> = { idea: "Idea", prototype: "Prototype", mvp: "MVP", revenue: "Revenue" };
const TABS = [
  ["explore", "Explore ventures"],
  ["mine", "My ventures"],
  ["requests", "My requests"],
  ["new", "Post a venture"],
] as const;
type Tab = (typeof TABS)[number][0];

export default function Ventures() {
  const [params, setParams] = useSearchParams();
  const tab: Tab = TABS.some(([v]) => v === params.get("tab")) ? (params.get("tab") as Tab) : "explore";
  return (
    <>
      <Heading eyebrow="Build something together" title="Venture Launchpad">
        Founders share a public teaser; the full plan is shared only with collaborators they accept.
      </Heading>
      <div className="tabs" role="group" aria-label="Venture sections">
        {TABS.map(([value, label]) => (
          <button
            key={value}
            aria-pressed={tab === value}
            className={tab === value ? "active" : ""}
            onClick={() => setParams(value === "explore" ? {} : { tab: value }, { replace: true })}
          >
            {label}
          </button>
        ))}
      </div>
      {tab === "explore" && <VentureList mine={false} />}
      {tab === "mine" && <VentureList mine />}
      {tab === "requests" && <MyRequests />}
      {tab === "new" && <NewVenture />}
    </>
  );
}

function VentureList({ mine }: { mine: boolean }) {
  const [page, setPage] = useState(1);
  const [skill, setSkill] = useState("");
  const ventures = useQuery<Page<Venture>>(
    `/ventures?page=${page}&page_size=12${mine ? "&mine=true" : ""}${skill ? `&skill=${encodeURIComponent(skill)}` : ""}`,
  );
  return (
    <>
      {!mine && (
        <form
          className="filters"
          onSubmit={(e) => {
            e.preventDefault();
            setPage(1);
            setSkill(String(new FormData(e.currentTarget).get("skill") || "").trim());
          }}
        >
          <label className="grow">
            Skill you can bring
            <input name="skill" defaultValue={skill} placeholder="e.g. React, Python…" autoComplete="off" />
          </label>
          <button className="primary">Filter</button>
        </form>
      )}
      <ErrorMessage error={ventures.error} />
      {ventures.loading && <Loading />}
      <div className="card-grid">
        {ventures.data?.items.map((v) => (
          <Link key={v.id} to={`/ventures/${v.id}`} className="panel card-link">
            <div className="meta-row">
              <Badge tone="blue">{STAGE[v.stage] ?? v.stage}</Badge>
              <Badge>{COMPENSATION[v.compensation_type] ?? v.compensation_type}</Badge>
              {v.is_founder && <Badge tone="green">Your venture</Badge>}
              {v.my_request_status && <Badge tone="amber">Request {v.my_request_status}</Badge>}
            </div>
            <h2>{v.title}</h2>
            <p className="muted">{v.teaser}</p>
            <Tags items={v.needed_skills} />
            <small className="muted">
              {v.founder_name} · {v.industry} · {v.accepted_collaborators} collaborator
              {v.accepted_collaborators === 1 ? "" : "s"}
            </small>
          </Link>
        ))}
      </div>
      {ventures.data?.items.length === 0 && (
        <Empty title={mine ? "You haven’t posted a venture yet" : "No ventures match"}>
          {mine ? "Use “Post a venture” to share your idea." : "Try another skill."}
        </Empty>
      )}
      {ventures.data && <Pagination data={ventures.data} onPage={setPage} />}
    </>
  );
}

function MyRequests() {
  const requests = useQuery<Page<CollaborationRequest>>("/collaboration-requests?scope=requester&page_size=50");
  return (
    <>
      <ErrorMessage error={requests.error} />
      {requests.loading && <Loading />}
      <div className="stack">
        {requests.data?.items.map((r) => (
          <Link key={r.id} to={`/ventures/${r.venture_id}`} className="panel card-link">
            <div className="section-heading">
              <h2>{r.venture_title}</h2>
              <Badge tone={r.status === "accepted" ? "green" : r.status === "declined" ? "red" : "amber"}>
                {r.status}
              </Badge>
            </div>
            <p className="preserve-lines">{r.note}</p>
            <small className="muted">Sent {date(r.created_at)}</small>
          </Link>
        ))}
      </div>
      {requests.data?.items.length === 0 && (
        <Empty title="No requests yet">Find a venture you’d like to help build.</Empty>
      )}
    </>
  );
}

function NewVenture() {
  const { api } = useAuth();
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  return (
    <section className="panel form-panel">
      <h2>Share your idea</h2>
      <p className="small muted">
        Everyone sees the title and teaser. The full plan is visible only to you and the collaborators you accept,
        after they agree to keep it confidential.
      </p>
      <ErrorMessage error={error} />
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          if (busy) return;
          const data = new FormData(e.currentTarget);
          setBusy(true);
          setError(null);
          try {
            const created = await api<Venture>("/ventures", {
              method: "POST",
              body: JSON.stringify({
                title: data.get("title"),
                teaser: data.get("teaser"),
                problem: data.get("problem"),
                industry: data.get("industry"),
                stage: data.get("stage"),
                compensation_type: data.get("compensation_type"),
                needed_skills: skillList(data.get("skills")),
              }),
            });
            navigate(`/ventures/${created.id}`);
          } catch (err) {
            setError(err);
          } finally {
            setBusy(false);
          }
        }}
      >
        <label>
          Venture name
          <input name="title" required maxLength={200} placeholder="e.g. CampusEats…" />
        </label>
        <label>
          Public teaser <small>One line anyone can see · up to 280 characters</small>
          <input name="teaser" required maxLength={280} placeholder="What problem, for whom…" />
        </label>
        <label>
          Full plan <small>Private: problem, traction, what you need</small>
          <textarea name="problem" required maxLength={4000} rows={5} />
        </label>
        <div className="form-grid">
          <label>
            Industry
            <input name="industry" required maxLength={120} placeholder="e.g. Edtech…" />
          </label>
          <label>
            Stage
            <select name="stage" defaultValue="idea">
              {Object.entries(STAGE).map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </select>
          </label>
          <label>
            Compensation
            <select name="compensation_type" defaultValue="to_discuss">
              {Object.entries(COMPENSATION).map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </select>
          </label>
        </div>
        <label>
          Skills you need <small>Comma-separated</small>
          <input name="skills" placeholder="react, python…" autoComplete="off" />
        </label>
        <button className="primary" disabled={busy}>
          {busy ? "Posting…" : "Post venture"}
        </button>
        <p className="small muted">Founder Free includes 1 venture; Founder Pro allows 3.</p>
      </form>
    </section>
  );
}

export function VentureDetail() {
  const { id } = useParams();
  const { api } = useAuth();
  const venture = useQuery<Venture>(`/ventures/${id}`);
  const inbox = useQuery<Page<CollaborationRequest>>(
    venture.data?.is_founder ? "/collaboration-requests?scope=founder&page_size=50" : null,
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [message, setMessage] = useState("");
  const v = venture.data;
  return (
    <>
      <Link className="back-link" to="/ventures">
        <ArrowLeft size={16} /> All ventures
      </Link>
      <ErrorMessage error={venture.error} />
      {venture.loading && <Loading />}
      {v && (
        <>
          <Heading eyebrow={`${v.industry} · ${STAGE[v.stage] ?? v.stage}`} title={v.title}>
            {v.teaser}
          </Heading>
          <ErrorMessage error={error} />
          {message && (
            <p className="notice success" role="status">
              {message}
            </p>
          )}
          <div className="two-column">
            <section className="panel">
              <h2>The plan</h2>
              {v.problem ? (
                <p className="preserve-lines">{v.problem}</p>
              ) : (
                <div className="private-block">
                  <Lock size={16} aria-hidden="true" /> The full plan is shared once the founder accepts your
                  request. You agree to keep it confidential when you ask to join.
                </div>
              )}
              <h3>Skills needed</h3>
              <Tags items={v.needed_skills} />
              <p className="small muted">
                Compensation: {COMPENSATION[v.compensation_type]} · Joining is visible collaboration, not equity or
                employment, unless agreed separately.
              </p>
            </section>
            <aside className="panel">
              {v.is_founder ? (
                <>
                  <h2>Requests to join</h2>
                  <ErrorMessage error={inbox.error} />
                  {inbox.loading && <Loading />}
                  {inbox.data?.items
                    .filter((r) => r.venture_id === v.id)
                    .map((r) => (
                      <div key={r.id} className="evidence">
                        <div className="section-heading">
                          <strong>{r.requester_name}</strong>
                          <Badge tone={r.status === "accepted" ? "green" : r.status === "declined" ? "red" : "amber"}>
                            {r.status}
                          </Badge>
                        </div>
                        <p className="preserve-lines small">{r.note}</p>
                        {r.status === "pending" && (
                          <div className="actions">
                            {(["accepted", "declined"] as const).map((status) => (
                              <button
                                key={status}
                                className={status === "accepted" ? "primary" : "secondary"}
                                disabled={busy}
                                onClick={async () => {
                                  setBusy(true);
                                  setError(null);
                                  try {
                                    await api(`/collaboration-requests/${r.id}`, {
                                      method: "PATCH",
                                      body: JSON.stringify({ status }),
                                    });
                                    setMessage(status === "accepted" ? `${r.requester_name} joined.` : "Request declined.");
                                    inbox.reload();
                                    venture.reload();
                                  } catch (err) {
                                    setError(err);
                                  } finally {
                                    setBusy(false);
                                  }
                                }}
                              >
                                {status === "accepted" ? "Accept" : "Decline"}
                              </button>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  {inbox.data && inbox.data.items.filter((r) => r.venture_id === v.id).length === 0 && (
                    <p className="muted small">No requests yet.</p>
                  )}
                </>
              ) : v.my_request_status ? (
                <>
                  <h2>Your request</h2>
                  <Badge tone={v.my_request_status === "accepted" ? "green" : "amber"}>{v.my_request_status}</Badge>
                  <p className="small muted" style={{ marginTop: 10 }}>
                    {v.my_request_status === "accepted"
                      ? "You’re in. The full plan is now visible."
                      : "The founder will review it."}
                  </p>
                </>
              ) : (
                <>
                  <h2>
                    <Rocket size={18} aria-hidden="true" /> Ask to join
                  </h2>
                  <form
                    onSubmit={async (e) => {
                      e.preventDefault();
                      if (busy) return;
                      const data = new FormData(e.currentTarget);
                      setBusy(true);
                      setError(null);
                      try {
                        await api(`/ventures/${v.id}/requests`, {
                          method: "POST",
                          body: JSON.stringify({ note: data.get("note"), accept_nda: data.get("nda") === "on" }),
                        });
                        setMessage("Request sent to the founder.");
                        venture.reload();
                      } catch (err) {
                        setError(err);
                      } finally {
                        setBusy(false);
                      }
                    }}
                  >
                    <label>
                      What you’d bring
                      <textarea name="note" required maxLength={1000} rows={4} />
                    </label>
                    <label className="checkbox">
                      <input type="checkbox" name="nda" required />I’ll keep the founder’s plan confidential.
                    </label>
                    <button className="primary" disabled={busy}>
                      {busy ? "Sending…" : "Send request"}
                    </button>
                  </form>
                  <p className="small muted" style={{ marginTop: 12 }}>
                    Report a venture that asks you to pay or looks like a scam.
                  </p>
                  <ReportButton targetType="venture" targetId={v.id} />
                </>
              )}
            </aside>
          </div>
        </>
      )}
    </>
  );
}

export function ReportButton({ targetType, targetId }: { targetType: "opportunity" | "venture"; targetId: string }) {
  const { api } = useAuth();
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState("");
  const [error, setError] = useState<unknown>();
  if (done)
    return (
      <p className="notice success" role="status">
        {done}
      </p>
    );
  return (
    <details>
      <summary>Report</summary>
      <ErrorMessage error={error} />
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          if (busy) return;
          const data = new FormData(e.currentTarget);
          setBusy(true);
          setError(null);
          try {
            await api("/reports", {
              method: "POST",
              body: JSON.stringify({
                target_type: targetType,
                target_id: targetId,
                reason: data.get("reason"),
                details: String(data.get("details") || "") || null,
              }),
            });
            setDone("Thanks — our operators will review it. Three separate reports hide a listing until review.");
          } catch (err) {
            setError(err);
          } finally {
            setBusy(false);
          }
        }}
      >
        <label>
          Reason
          <select name="reason" defaultValue="scam">
            <option value="scam">Asks for money / scam</option>
            <option value="fake">Fake or misleading organization</option>
            <option value="misleading">Misleading details</option>
            <option value="abusive">Abusive content</option>
            <option value="other">Other</option>
          </select>
        </label>
        <label>
          Details <small>Optional</small>
          <textarea name="details" maxLength={1000} rows={2} />
        </label>
        <button className="secondary" disabled={busy}>
          {busy ? "Sending…" : "Send report"}
        </button>
      </form>
    </details>
  );
}
