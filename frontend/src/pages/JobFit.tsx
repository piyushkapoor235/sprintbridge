import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useAuth } from "../auth";
import { useQuery } from "../lib/useQuery";
import { AlertTriangle } from "lucide-react";
import type { Fit, JobDescription } from "../lib/types";
import { Heading, Badge, Loading, ErrorMessage } from "../components/ui";
import { evidenceLabel } from "./Skills";
export default function JobFit() {
  const { api } = useAuth();
  const [params, setParams] = useSearchParams();
  const opportunity = params.get("opportunity_id");
  const jd = params.get("jd_id");
  const result = useQuery<Fit>(
    opportunity
      ? `/opportunities/${encodeURIComponent(opportunity)}/fit`
      : jd
        ? `/jds/${encodeURIComponent(jd)}/fit`
        : null,
  );
  const description = useQuery<JobDescription>(jd ? `/jds/${encodeURIComponent(jd)}` : null);
  const [error, setError] = useState<unknown>();
  const [busy, setBusy] = useState(false);
  return (
    <>
      <Heading
        eyebrow="Clarity before your next move"
        title="Explore your job fit"
      >
        Understand the match between a role’s requirements and your skill
        evidence.
      </Heading>
      {!opportunity && (
        <section className="panel form-panel">
          <h2>Bring a job description</h2>
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              if (busy) return;
              const data = new FormData(e.currentTarget);
              setBusy(true);
              setError(null);
              try {
                const saved = await api<{ id: string }>("/jds", {
                  method: "POST",
                  body: JSON.stringify({
                    title: data.get("title") || null,
                    text: data.get("text"),
                  }),
                });
                setParams({ jd_id: saved.id });
              } catch (err) {
                setError(err);
              } finally {
                setBusy(false);
              }
            }}
          >
            <label>
              Role title (optional)
              <input name="title" maxLength={200} />
            </label>
            <label>
              Job description
              <textarea
                name="text"
                required
                rows={7}
                maxLength={20000}
                placeholder="Paste the role, responsibilities and requirements here…"
              />
            </label>
            <button className="primary" disabled={busy}>
              {busy ? "Analyzing requirements…" : "Analyze my fit"}
            </button>
          </form>
        </section>
      )}
      <ErrorMessage error={error} />
      <ErrorMessage error={result.error} />
      {result.loading && <Loading />}
      {(description.data?.red_flags ?? []).length > 0 && (
        <div className="notice warning" role="alert">
          <AlertTriangle size={18} aria-hidden="true" />
          <div>
            <strong>This job description has warning signs:</strong> {description.data!.red_flags.join("; ")}.
            Genuine employers never charge candidates.
          </div>
        </div>
      )}
      {result.data && (
        <section className="panel">
          <p className="eyebrow">
            Your fit report{description.data?.title ? ` · ${description.data.title}` : ""}
          </p>
          <div className="coverage-number">
            {result.data.fit_percent === null
              ? "—"
              : `${result.data.fit_percent}%`}
            <span>
              {result.data.required_met} of {result.data.required_total}{" "}
              required skills met
            </span>
          </div>
          <p className="muted">
            A deterministic comparison of requirements and skill evidence. This
            is not a hiring probability and does not replace campus eligibility.
          </p>
          {result.data.fit_percent === null && (
            <p>No requirements were available to calculate fit.</p>
          )}
          {["missing", "under_evidenced", "strong"].map((bucket) => (
            <div key={bucket}>
              <h2 className="bucket-title">
                {
                  {
                    missing: "Skills to build",
                    under_evidenced: "More evidence needed",
                    strong: "Your strengths",
                  }[bucket]
                }
              </h2>
              {result
                .data!.items.filter((item) => item.bucket === bucket)
                .map((item) => (
                  <div className="fit-row" key={item.skill}>
                    <div>
                      <h3>
                        {item.skill} <Badge>{item.kind}</Badge>
                      </h3>
                      <p className="small muted">
                        Required level {item.min_level} ·{" "}
                        {item.user_level !== null
                          ? `Your level ${item.user_level}${item.label ? ` · ${evidenceLabel(item.label)}` : ""}`
                          : item.label
                            ? "Mentioned, but not enough evidence for a level yet"
                            : "Not in your skills yet"}
                      </p>
                      {item.jd_quote && (
                        <blockquote>{item.jd_quote}</blockquote>
                      )}
                    </div>
                    {bucket !== "strong" && (
                      <Link
                        to={`/mentors?skill=${encodeURIComponent(item.skill)}`}
                      >
                        Find a mentor →
                      </Link>
                    )}
                  </div>
                ))}
              {!result.data!.items.some((item) => item.bucket === bucket) && (
                <p className="small muted">No skills in this group.</p>
              )}
            </div>
          ))}
        </section>
      )}
    </>
  );
}
