import { useState } from "react";
import { Link } from "react-router-dom";
import { Upload } from "lucide-react";
import { useAuth } from "../auth";
import { useQuery } from "../lib/useQuery";
import type { Skills as SkillsResponse } from "../lib/types";
import { Heading, Badge, Loading, ErrorMessage, Empty } from "../components/ui";
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
      <Heading eyebrow="MORE THAN A LIST OF SKILLS" title="Skill evidence">
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
              <Badge tone={skill.label === "system_assessed" ? "blue" : ""}>
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
    </>
  );
}
