import { useState } from "react";
import { Link } from "react-router-dom";
import { Upload } from "lucide-react";
import { useAuth } from "../auth";
import { useQuery } from "../lib/useQuery";
import type { Skills as SkillsResponse, Verification } from "../lib/types";
import { ApiError } from "../lib/http";
import { Heading, Badge, Loading, ErrorMessage, Empty, TestPaymentNote, date } from "../components/ui";
export const evidenceLabel = (label: string) =>
  ({
    self_declared: "Self-declared",
    system_assessed: "System-assessed",
    mentor_verified: "Mentor-verified",
  })[label] || label;
export default function Skills() {
  const { api } = useAuth();
  const result = useQuery<SkillsResponse>("/me/skills");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [message, setMessage] = useState("");
  return (
    <>
      <Heading eyebrow="More than a list of skills" title="Skill evidence">
        See the experience behind your skills, and where to grow next.
      </Heading>
      <section className="panel upload-panel">
        <span className="upload-icon">
          <Upload size={26} />
        </span>
        <div>
          <h2>Bring your experience into focus</h2>
          <p className="muted">
            Upload a PDF resume, up to 5 MB. Assessment uses evidence in your
            document; it does not independently verify your experience.
          </p>
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              if (busy) return;
              const file = new FormData(e.currentTarget).get("file");
              if (!(file instanceof File) || !file.size) {
                setError(new Error("Choose a PDF resume."));
                return;
              }
              if (
                file.size > 5 * 1024 * 1024 ||
                !file.name.toLowerCase().endsWith(".pdf")
              ) {
                setError(new Error("Choose a PDF of 5 MB or smaller."));
                return;
              }
              const body = new FormData();
              body.set("file", file);
              setBusy(true);
              setError(null);
              setMessage("");
              try {
                const data = await api<{
                  skills_found: number;
                  skills_rejected: number;
                }>("/me/resume", { method: "POST", body });
                setMessage(
                  `${data.skills_found} skills assessed. ${data.skills_rejected} unsupported evidence items excluded.`,
                );
                result.reload();
              } catch (err) {
                setError(err);
              } finally {
                setBusy(false);
              }
            }}
          >
            <label>
              Resume PDF
              <input
                name="file"
                type="file"
                accept="application/pdf,.pdf"
                required
              />
            </label>
            <button className="primary" disabled={busy}>
              {busy ? "Assessing your resume…" : "Upload and assess"}
            </button>
          </form>
          <p className="small muted">
            A successful new resume replaces earlier resume evidence. Analysis
            may take a moment. Manual skills remain available if analysis is
            unavailable.
          </p>
        </div>
      </section>
      <ErrorMessage error={error} />
      {message && (
        <p className="notice success" role="status">
          {message}
        </p>
      )}
      <div className="section-heading">
        <h2>Your skill profile</h2>
        <Link className="text-link" to="/profile">
          Edit self-declared skills →
        </Link>
      </div>
      <ErrorMessage error={result.error} />
      {result.loading && <Loading />}
      <div className="stack">
        {result.data?.items.map((skill) => (
          <section className="panel" key={skill.skill}>
            <div className="section-heading">
              <h2>{skill.skill}</h2>
              <Badge
                tone={
                  skill.label === "mentor_verified"
                    ? "green"
                    : skill.label === "system_assessed"
                      ? "blue"
                      : ""
                }
              >
                {evidenceLabel(skill.label)}
              </Badge>
            </div>
            <p className="muted">
              {skill.level !== null
                ? `Level ${skill.level}`
                : "No assessed level"}
              {skill.evidence_score !== null
                ? ` · Evidence score ${skill.evidence_score}/100`
                : ""}
              {skill.verified_until
                ? ` · Verified until ${date(skill.verified_until)}`
                : ""}
            </p>
            {skill.evidence.length > 0 && (
              <details>
                <summary>Why this assessment?</summary>
                {skill.evidence.map((evidence) => (
                  <div className="evidence" key={evidence.id}>
                    <small>
                      {evidence.source} ·{" "}
                      {evidence.context_type.replaceAll("_", " ")} ·{" "}
                      {evidence.points} points
                    </small>
                    {evidence.quote && (
                      <blockquote>{evidence.quote}</blockquote>
                    )}
                  </div>
                ))}
              </details>
            )}
          </section>
        ))}
      </div>
      {result.data?.items.length === 0 && (
        <Empty title="Start with what you know">
          Add manual skills to your profile or upload a resume.
        </Empty>
      )}
      <MentorVerification
        skills={result.data?.items.map((s) => s.skill) ?? []}
        onVerified={result.reload}
      />
    </>
  );
}

const STATUS: Record<string, [string, string]> = {
  assigned: ["Verifier assigned", "amber"],
  in_session: ["In session", "blue"],
  passed: ["Mentor-verified", "green"],
  failed: ["Not yet", ""],
  under_review: ["Under review", "amber"],
};

function MentorVerification({
  skills,
  onVerified,
}: {
  skills: string[];
  onVerified: () => void;
}) {
  const { api } = useAuth();
  const list = useQuery<Verification[]>("/verifications");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [quote, setQuote] = useState<{ skill: string; level: number; detail: string } | null>(null);
  const [message, setMessage] = useState("");
  const send = async (skill: string, level: number, confirm: boolean) => {
    setBusy(true);
    setError(null);
    setMessage("");
    try {
      await api("/verifications", {
        method: "POST",
        body: JSON.stringify({ skill, level, confirm_test_payment: confirm }),
      });
      setQuote(null);
      setMessage(
        `Requested. An independent mentor with no connection to you has been assigned to ${skill}.`,
      );
      list.reload();
      onVerified();
    } catch (err) {
      if (err instanceof ApiError && err.code === "PAYMENT_REQUIRED") {
        setQuote({ skill, level, detail: err.message });
      } else {
        setError(err);
      }
    } finally {
      setBusy(false);
    }
  };
  return (
    <section style={{ marginTop: 36 }}>
      <div className="section-heading">
        <div>
          <h2>Get mentor-verified</h2>
          <p className="muted">
            A mentor you’ve never interacted with, from outside your college, is picked at random to verify you
            live. You can’t choose them. Same fee whether you pass or not; badges last 18 months.
          </p>
        </div>
      </div>
      <div className="panel">
        <ErrorMessage error={error || list.error} />
        {message && (
          <p className="notice success" role="status">
            {message}
          </p>
        )}
        {quote ? (
          <>
            <TestPaymentNote
              amount={Number(/₹(\d+)/.exec(quote.detail)?.[1] ?? 0)}
              what={`Verifying ${quote.skill} at level ${quote.level}`}
            />
            <div className="actions" style={{ marginTop: 0 }}>
              <button className="primary" disabled={busy} onClick={() => send(quote.skill, quote.level, true)}>
                {busy ? "Assigning…" : "Confirm test payment"}
              </button>
              <button className="secondary" disabled={busy} onClick={() => setQuote(null)}>
                Cancel
              </button>
            </div>
          </>
        ) : (
          <form
            className="inline-form"
            onSubmit={(e) => {
              e.preventDefault();
              const data = new FormData(e.currentTarget);
              send(String(data.get("skill")).trim().toLowerCase(), Number(data.get("level")), false);
            }}
          >
            <label>
              Skill
              <input name="skill" list="my-skills" required maxLength={80} placeholder="e.g. python…" autoComplete="off" />
              <datalist id="my-skills">
                {skills.map((s) => (
                  <option key={s} value={s} />
                ))}
              </datalist>
            </label>
            <label>
              Level to prove
              <select name="level" defaultValue="2">
                <option value="1">1 · Aware</option>
                <option value="2">2 · Working</option>
                <option value="3">3 · Proficient</option>
                <option value="4">4 · Expert</option>
              </select>
            </label>
            <button className="primary" disabled={busy}>
              {busy ? "Checking…" : "Request verification"}
            </button>
          </form>
        )}
        {list.data && list.data.length > 0 && (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Skill</th>
                  <th>Status</th>
                  <th>Verifier</th>
                  <th>Details</th>
                </tr>
              </thead>
              <tbody>
                {list.data.map((v) => {
                  const [label, tone] = STATUS[v.status] ?? [v.status, ""];
                  return (
                    <tr key={v.id}>
                      <td>
                        {v.skill} · L{v.level_requested}
                      </td>
                      <td>
                        <Badge tone={tone}>
                          {v.status === "passed" ? `${label} · L${v.result_level}` : label}
                        </Badge>
                      </td>
                      <td>
                        {v.verifier ? (
                          `${v.verifier.name} · ${v.verifier.niche}`
                        ) : (
                          <span className="muted">Revealed when the session starts</span>
                        )}
                      </td>
                      <td className="small muted">
                        {v.status === "passed" && v.expires_at && `Valid until ${date(v.expires_at)}. `}
                        {v.status === "failed" && v.retry_after && `Retry after ${date(v.retry_after)}. `}
                        {v.notes}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  );
}
