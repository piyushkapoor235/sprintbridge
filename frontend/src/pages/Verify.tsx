import { useState } from "react";
import { ShieldCheck } from "lucide-react";
import { useAuth } from "../auth";
import { useQuery } from "../lib/useQuery";
import type { VerifierQueue } from "../lib/types";
import { Badge, Empty, ErrorMessage, Heading, Loading, Tags, date } from "../components/ui";

const LEVELS = ["", "Aware", "Working", "Proficient", "Expert"];

export default function Verify() {
  const { api } = useAuth();
  const queue = useQuery<VerifierQueue>("/verifications/queue");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [message, setMessage] = useState("");
  const q = queue.data;
  const levelFor = (skill: string) => q?.expertise.find((e) => e.skill === skill)?.level ?? 1;
  const act = async (path: string, body?: object, done?: string) => {
    setBusy(true);
    setError(null);
    setMessage("");
    try {
      await api(path, { method: "POST", body: body ? JSON.stringify(body) : undefined });
      if (done) setMessage(done);
      queue.reload();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };
  const open = q?.assignments.filter((a) => a.status === "assigned" || a.status === "in_session") ?? [];
  const decided = q?.assignments.filter((a) => a.status !== "assigned" && a.status !== "in_session") ?? [];
  const audits = q?.audits.filter((a) => !a.decided_at) ?? [];

  return (
    <>
      <Heading eyebrow="Independent verification" title="Verifier desk">
        You are assigned at random to candidates you have no connection with. Your pay is the same for a pass or a
        fail, and some results get a blind second review.
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
              <span>Open sessions</span>
              <strong>{open.length}</strong>
            </div>
            <div className="kpi">
              <span>Blind reviews waiting</span>
              <strong>{audits.length}</strong>
            </div>
            <div className="kpi">
              <span>Agreement score</span>
              <strong>{q.quality_score !== null ? `${Math.round(q.quality_score * 100)}%` : "—"}</strong>
            </div>
            <div className="kpi">
              <span>You can verify</span>
              <Tags items={q.expertise.map((e) => `${e.skill} ≤ L${e.level}`)} />
            </div>
          </div>

          <section>
            <h2 style={{ marginBottom: 12 }}>Assigned to you</h2>
            {open.length === 0 && <Empty title="Nothing assigned right now">New assignments appear here.</Empty>}
            <div className="stack">
              {open.map((a) => (
                <article className="panel" key={a.id}>
                  <div className="section-heading">
                    <div>
                      <h2>
                        {a.skill} · level {a.level_requested} requested
                      </h2>
                      <p className="muted">
                        {a.candidate_name} · assigned {date(a.created_at)}
                      </p>
                    </div>
                    <Badge tone={a.status === "in_session" ? "blue" : "amber"}>
                      {a.status === "in_session" ? "In session" : "Waiting to start"}
                    </Badge>
                  </div>
                  {a.status === "assigned" ? (
                    <>
                      <ol className="step-list">
                        <li>Start the session — this reveals your name to the candidate.</li>
                        <li>Run a live task: have them explain and modify real code in this skill.</li>
                        <li>Record a pass with a level (up to your own) or a fail.</li>
                      </ol>
                      <div className="actions">
                        <button
                          className="primary"
                          disabled={busy}
                          onClick={() => act(`/verifications/${a.id}/start`, undefined, "Session started.")}
                        >
                          Start session
                        </button>
                      </div>
                    </>
                  ) : (
                    <form
                      onSubmit={(e) => {
                        e.preventDefault();
                        const data = new FormData(e.currentTarget);
                        const passed = data.get("outcome") === "pass";
                        act(
                          `/verifications/${a.id}/result`,
                          {
                            passed,
                            level: passed ? Number(data.get("level")) : null,
                            notes: String(data.get("notes") || ""),
                          },
                          passed ? "Pass recorded." : "Result recorded.",
                        );
                      }}
                    >
                      <div className="form-grid">
                        <label>
                          Outcome
                          <select name="outcome" defaultValue="pass">
                            <option value="pass">Pass</option>
                            <option value="fail">Not yet</option>
                          </select>
                        </label>
                        <label>
                          Level demonstrated
                          <select name="level" defaultValue={Math.min(a.level_requested, levelFor(a.skill))}>
                            {[1, 2, 3, 4]
                              .filter((l) => l <= levelFor(a.skill))
                              .map((l) => (
                                <option key={l} value={l}>
                                  {l} · {LEVELS[l]}
                                </option>
                              ))}
                          </select>
                        </label>
                      </div>
                      <label>
                        Notes for the candidate <small>What they showed, what to work on</small>
                        <textarea name="notes" rows={3} maxLength={2000} />
                      </label>
                      <button className="primary" disabled={busy}>
                        {busy ? "Saving…" : "Record result"}
                      </button>
                    </form>
                  )}
                </article>
              ))}
            </div>
          </section>

          {audits.length > 0 && (
            <section>
              <h2 style={{ marginBottom: 4 }}>Blind second reviews</h2>
              <p className="muted" style={{ marginBottom: 12 }}>
                You don’t see the first verifier’s result. Disagreement suspends the badge and is reviewed.
              </p>
              <div className="stack">
                {audits.map((a) => (
                  <article className="panel" key={a.id}>
                    <h2>
                      <ShieldCheck size={18} aria-hidden="true" /> {a.skill} · level {a.level_requested} · {a.candidate_name}
                    </h2>
                    <form
                      className="inline-form"
                      style={{ marginTop: 12 }}
                      onSubmit={(e) => {
                        e.preventDefault();
                        const data = new FormData(e.currentTarget);
                        const passed = data.get("outcome") === "pass";
                        act(
                          `/verification-audits/${a.id}`,
                          { passed, level: passed ? Number(data.get("level")) : null },
                          "Review recorded.",
                        );
                      }}
                    >
                      <label>
                        Your outcome
                        <select name="outcome" defaultValue="pass">
                          <option value="pass">Pass</option>
                          <option value="fail">Not yet</option>
                        </select>
                      </label>
                      <label>
                        Level
                        <select name="level" defaultValue={a.level_requested}>
                          {[1, 2, 3, 4].map((l) => (
                            <option key={l} value={l}>
                              {l} · {LEVELS[l]}
                            </option>
                          ))}
                        </select>
                      </label>
                      <button className="primary" disabled={busy}>
                        Record review
                      </button>
                    </form>
                  </article>
                ))}
              </div>
            </section>
          )}

          {decided.length > 0 && (
            <section>
              <h2 style={{ marginBottom: 12 }}>Completed</h2>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Candidate</th>
                      <th>Skill</th>
                      <th>Result</th>
                    </tr>
                  </thead>
                  <tbody>
                    {decided.map((a) => (
                      <tr key={a.id}>
                        <td>{a.candidate_name}</td>
                        <td>{a.skill}</td>
                        <td>
                          <Badge tone={a.status === "passed" ? "green" : a.status === "under_review" ? "amber" : ""}>
                            {a.status === "passed" ? `Passed · L${a.result_level}` : a.status.replace("_", " ")}
                          </Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}
        </div>
      )}
    </>
  );
}
