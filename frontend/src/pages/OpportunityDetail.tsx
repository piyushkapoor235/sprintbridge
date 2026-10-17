import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { ArrowLeft, ArrowRight } from "lucide-react";
import { useAuth } from "../auth";
import { useQuery } from "../lib/useQuery";
import type {
  Opportunity,
  Drive,
  Eligibility,
  Page,
  Application,
} from "../lib/types";
import {
  Heading,
  Badge,
  Tags,
  Loading,
  ErrorMessage,
  date,
} from "../components/ui";
import { ApiError } from "../lib/http";

export default function OpportunityDetail() {
  const { id } = useParams();
  return <Detail key={id} id={id!} />;
}
function Detail({ id }: { id: string }) {
  const { api } = useAuth();
  const result = useQuery<Opportunity>(`/opportunities/${id}`);
  const [params, setParams] = useSearchParams();
  const driveId = params.get("drive_id") || "";
  const [drives, setDrives] = useState<Drive[]>([]);
  const [driveError, setDriveError] = useState<unknown>();
  const [driveLoading, setDriveLoading] = useState(true);
  const knownDrive = drives.some((d) => d.id === driveId);
  const eligibility = useQuery<Eligibility>(
    knownDrive ? `/drives/${driveId}/eligibility` : null,
  );
  const applications = useQuery<Page<Application>>(
    `/applications?scope=student&opportunity_id=${id}`,
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [submitted, setSubmitted] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      try {
        const all: Drive[] = [];
        for (let page = 1; ; page++) {
          const data = await api<Page<Drive>>(
            `/university/drives?page=${page}&page_size=100`,
            { signal: controller.signal },
          );
          all.push(...data.items.filter((d) => d.opportunity_id === id));
          if (
            data.items.length < 100 ||
            (data.total !== null && page * 100 >= data.total)
          )
            break;
        }
        if (!controller.signal.aborted) setDrives(all);
      } catch (err) {
        if (!controller.signal.aborted) setDriveError(err);
      } finally {
        if (!controller.signal.aborted) setDriveLoading(false);
      }
    }
    void load();
    return () => controller.abort();
  }, [id, api]);
  if (result.loading) return <Loading />;
  if (!result.data)
    return (
      <>
        <ErrorMessage error={result.error} />
        <Link to="/opportunities">Back to opportunities</Link>
      </>
    );
  const job = result.data;
  const coverage = job.skill_coverage;
  const applied = submitted || Boolean(applications.data?.items.length);
  const closed =
    job.status === "closed" || new Date(job.deadline) <= new Date();
  const allowed =
    !closed &&
    (!driveId
      ? job.visibility === "public"
      : knownDrive && eligibility.data?.eligible === true);
  async function apply() {
    if (busy || applied || !allowed || uncertain) return;
    setBusy(true);
    setError(null);
    try {
      await api(`/opportunities/${id}/applications`, {
        method: "POST",
        body: JSON.stringify({ drive_id: driveId || null }),
      });
      setSubmitted(true);
      applications.reload();
    } catch (err) {
      setError(err);
      if (err instanceof ApiError && err.code === "ALREADY_APPLIED") {
        setSubmitted(true);
        applications.reload();
      } else if (
        !(err instanceof ApiError) ||
        err.status === 0 ||
        err.status >= 500
      ) {
        setUncertain(true);
        applications.reload();
      }
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <Link className="back-link" to="/opportunities">
        <ArrowLeft size={16} />
        All opportunities
      </Link>
      <Heading
        eyebrow={job.company_name}
        title={job.title}
        action={
          <Badge tone="blue">
            {job.visibility === "campus"
              ? "Campus opportunity"
              : "Public opportunity"}
          </Badge>
        }
      >
        {job.type === "internship" ? "Internship" : "Job"} · Closes{" "}
        {date(job.deadline)}
      </Heading>
      <div className="two-column">
        <div className="stack">
          <section className="panel">
            <h2>About this opportunity</h2>
            <p className="preserve-lines">
              {job.description || "No additional description provided."}
            </p>
            <h3>Required skills</h3>
            <Tags items={job.required_skills} />
            {job.compensation && (
              <p className="muted">
                {job.compensation.currency}{" "}
                {Number(job.compensation.amount).toLocaleString("en-IN")} /{" "}
                {job.compensation.pay_period.replace("_", " ")}
              </p>
            )}
          </section>
          <section className="panel">
            <p className="eyebrow">KNOW WHERE YOU STAND</p>
            <h2>Your skill coverage</h2>
            {coverage ? (
              <>
                <div className="coverage-number">
                  {coverage.coverage_percent === null
                    ? "—"
                    : `${coverage.coverage_percent}%`}
                  <span>
                    {coverage.matched_count} of {coverage.required_count}{" "}
                    required skills
                  </span>
                </div>
                <p className="small muted">
                  Based on self-declared skills. This is not a hiring
                  probability or campus eligibility decision.
                </p>
                {coverage.required_count === 0 && (
                  <p>No required skills specified.</p>
                )}
                <Tags items={coverage.matching_skills} />
                {coverage.missing_skills.length > 0 && (
                  <>
                    <h3>Room to grow</h3>
                    {coverage.missing_skills.map((skill) => (
                      <div className="skill-gap" key={skill}>
                        <span>{skill}</span>
                        <Link
                          to={`/mentors?skill=${encodeURIComponent(skill)}`}
                        >
                          Find a mentor <ArrowRight size={15} />
                        </Link>
                      </div>
                    ))}
                  </>
                )}{" "}
              </>
            ) : (
              <p className="muted">
                Skill coverage is not available for this view.
              </p>
            )}
            <Link className="text-link" to={`/job-fit?opportunity_id=${id}`}>
              Explore evidence-based fit <ArrowRight size={16} />
            </Link>
          </section>
        </div>
        <aside className="stack">
          <section className="panel">
            <h2>Your next step</h2>
            <ErrorMessage error={applications.error} />
            <ErrorMessage error={driveError} />
            {driveLoading && <p className="muted">Checking campus drives…</p>}
            {drives.length > 0 && (
              <label>
                Application route
                <select
                  value={driveId}
                  onChange={(e) => {
                    const next = new URLSearchParams(params);
                    e.target.value
                      ? next.set("drive_id", e.target.value)
                      : next.delete("drive_id");
                    setParams(next);
                  }}
                >
                  <option value="">
                    {job.visibility === "public"
                      ? "General public application"
                      : "Choose a campus drive"}
                  </option>
                  {drives.map((d) => (
                    <option value={d.id} key={d.id}>
                      {d.university_name} · {d.batch}
                    </option>
                  ))}
                </select>
              </label>
            )}
            {driveId && !knownDrive && !driveLoading && (
              <p className="notice error">
                This drive is not available for this opportunity.
              </p>
            )}
            {job.visibility === "campus" && !drives.length && !driveLoading && (
              <p className="notice">
                No authorized campus drive is available for your account.
              </p>
            )}
            {knownDrive && (
              <>
                <h3>Campus eligibility</h3>
                <Badge>University-claimed record</Badge>
                {eligibility.loading && <Loading />}
                <ErrorMessage error={eligibility.error} />
                {eligibility.data && (
                  <>
                    <p>
                      <Badge
                        tone={eligibility.data.eligible ? "green" : "amber"}
                      >
                        {eligibility.data.eligible
                          ? "Eligible for this drive"
                          : "Not eligible"}
                      </Badge>
                    </p>
                    <ul>
                      {eligibility.data.reasons.map((r, i) => (
                        <li key={`${r.code}-${i}`}>{r.message}</li>
                      ))}
                    </ul>
                    <small className="muted">
                      Rules version {eligibility.data.rules_version}. Rechecked
                      when you apply.
                    </small>
                  </>
                )}
              </>
            )}
            <ErrorMessage error={error} />
            {closed && (
              <p className="notice">
                This opportunity is closed or its deadline has passed.
              </p>
            )}
            {applied ? (
              <div className="notice success" role="status">
                Application received.{" "}
                <Link to="/applications">View your tracker</Link>
              </div>
            ) : (
              <button
                className="primary full"
                disabled={
                  busy ||
                  !allowed ||
                  uncertain ||
                  applications.loading ||
                  !applications.data
                }
                onClick={apply}
              >
                {busy ? "Submitting…" : "Apply for this opportunity"}
                <ArrowRight size={17} />
              </button>
            )}
            {uncertain && !applied && (
              <div className="notice">
                The outcome is uncertain.{" "}
                <Link to="/applications">Check your tracker</Link> before
                submitting again.{" "}
                {applications.data &&
                  !applications.loading &&
                  !applications.data.items.length && (
                    <button
                      className="secondary"
                      onClick={() => {
                        setUncertain(false);
                        setError(null);
                      }}
                    >
                      No saved application found — enable retry
                    </button>
                  )}
              </div>
            )}
            <p className="small muted">
              Your profile is saved with your application. Review it before
              applying.
            </p>
            <Link className="text-link" to="/profile">
              Review my profile
            </Link>
          </section>
        </aside>
      </div>
    </>
  );
}
