import { useState } from "react";
import { useAuth } from "../auth";
import { useQuery } from "../lib/useQuery";
import { nextStatuses, safeLink, skillList } from "../lib/rules";
import type { Opportunity, Application, Page } from "../lib/types";
import {
  Heading,
  Badge,
  Loading,
  ErrorMessage,
  Empty,
  Pagination,
  Tags,
} from "../components/ui";
import { OpportunityRow } from "./Opportunities";

export default function Recruiter() {
  const { me, workspace } = useAuth();
  const permitted = me!.workspaces.some(
    (w) => w.organization_id === workspace && w.role === "recruiter",
  );
  if (!permitted)
    return (
      <>
        <Heading title="Recruiter workspace" />
        <Empty title="Choose a company workspace">
          Recruiter access is required. Select an authorized company above.
        </Empty>
      </>
    );
  return <RecruiterWorkspace key={workspace} company={workspace} />;
}
function RecruiterWorkspace({ company }: { company: string }) {
  const { api } = useAuth();
  const [tab, setTab] = useState("listings");
  const [page, setPage] = useState(1);
  const jobs = useQuery<Page<Opportunity>>(
    tab === "listings"
      ? `/opportunities?company_id=${company}&page=${page}&page_size=10`
      : null,
  );
  const applicants = useQuery<Page<Application>>(
    tab === "applicants"
      ? `/applications?scope=recruiter&workspace_id=${company}&page=${page}&page_size=10`
      : null,
  );
  const [error, setError] = useState<unknown>();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  return (
    <>
      <Heading eyebrow="BUILD YOUR NEXT TEAM" title="Recruiter workspace">
        Create opportunities and move promising applications forward.
      </Heading>
      <div className="tabs">
        {[
          ["listings", "Your listings"],
          ["applicants", "Applicants"],
          ["create", "Create opportunity"],
        ].map(([value, label]) => (
          <button
            key={value}
            className={tab === value ? "active" : ""}
            onClick={() => {
              setTab(value);
              setPage(1);
              setError(null);
              setMessage("");
            }}
            aria-pressed={tab === value}
          >
            {label}
          </button>
        ))}
      </div>
      <ErrorMessage error={error} />
      {message && (
        <p role="status" className="notice success">
          {message}
        </p>
      )}
      {tab === "listings" && (
        <>
          <ErrorMessage error={jobs.error} />
          {jobs.loading && <Loading />}
          <div className="listing-list">
            {jobs.data?.items.map((job) => (
              <OpportunityRow key={job.id} item={job} />
            ))}
            {jobs.data?.items.length === 0 && (
              <Empty title="Make room for new talent">
                Create your first opportunity to get started.
              </Empty>
            )}
          </div>
          {jobs.data && <Pagination data={jobs.data} onPage={setPage} />}
        </>
      )}
      {tab === "applicants" && (
        <>
          <ErrorMessage error={applicants.error} />
          {applicants.loading && <Loading />}
          <div className="stack">
            {applicants.data?.items.map((item) => (
              <section className="panel" key={item.id}>
                <div className="section-heading">
                  <div>
                    <h2>{item.profile_snapshot?.name || "Applicant"}</h2>
                    <p className="muted">{item.title}</p>
                  </div>
                  <Badge>{item.status}</Badge>
                </div>
                <p>{item.profile_snapshot?.education_summary}</p>
                <Tags items={item.profile_snapshot?.skills || []} />
                <small className="muted">
                  Self-declared skills · Profile at time of application
                </small>
                {safeLink(item.profile_snapshot?.portfolio_url || null) && (
                  <p>
                    <a
                      href={safeLink(item.profile_snapshot!.portfolio_url)!}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      Portfolio link supplied ↗
                    </a>
                  </p>
                )}
                <div className="actions">
                  {nextStatuses(item.status).map((status) => (
                    <button
                      className="secondary"
                      disabled={busy}
                      key={status}
                      onClick={async () => {
                        setBusy(true);
                        setError(null);
                        try {
                          await api(`/applications/${item.id}`, {
                            method: "PATCH",
                            body: JSON.stringify({ status }),
                          });
                          setMessage(`Application updated to ${status}.`);
                        } catch (err) {
                          setError(err);
                        } finally {
                          applicants.reload();
                          setBusy(false);
                        }
                      }}
                    >
                      {status === "shortlisted"
                        ? "Shortlist"
                        : status === "offered"
                          ? "Mark offered"
                          : "Reject"}
                    </button>
                  ))}
                </div>
              </section>
            ))}
          </div>
          {applicants.data?.items.length === 0 && (
            <Empty title="No applications yet">
              Applications to your company’s opportunities will appear here.
            </Empty>
          )}
          {applicants.data && (
            <Pagination data={applicants.data} onPage={setPage} />
          )}
        </>
      )}
      {tab === "create" && (
        <section className="panel form-panel">
          <h2>A new opportunity</h2>
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              if (busy) return;
              const data = new FormData(e.currentTarget);
              setBusy(true);
              setError(null);
              const amount = String(data.get("compensation_amount") || "");
              try {
                await api("/opportunities", {
                  method: "POST",
                  body: JSON.stringify({
                    company_id: company,
                    title: data.get("title"),
                    description: data.get("description"),
                    type: data.get("type"),
                    visibility: data.get("visibility"),
                    required_skills: skillList(data.get("skills")),
                    deadline: new Date(
                      String(data.get("deadline")),
                    ).toISOString(),
                    compensation_amount: amount || null,
                    currency: amount ? data.get("currency") : null,
                    pay_period: amount ? data.get("pay_period") : null,
                  }),
                });
                setTab("listings");
                setPage(1);
                setMessage("Opportunity created.");
              } catch (err) {
                setError(err);
              } finally {
                setBusy(false);
              }
            }}
          >
            <label>
              Title
              <input name="title" required maxLength={200} />
            </label>
            <label>
              Description
              <textarea name="description" rows={5} maxLength={10000} />
            </label>
            <div className="form-grid">
              <label>
                Type
                <select name="type">
                  <option value="internship">Internship</option>
                  <option value="job">Job</option>
                </select>
              </label>
              <label>
                Visibility
                <select name="visibility">
                  <option value="public">Public</option>
                  <option value="campus">Campus</option>
                </select>
              </label>
            </div>
            <p className="small muted">
              Campus listings become available to students after a university
              authorizes a drive.
            </p>
            <label>
              Required skills <small>Separate with commas</small>
              <input name="skills" />
            </label>
            <label>
              Application deadline <small>Your local time</small>
              <input type="datetime-local" name="deadline" required />
            </label>
            <div className="form-grid">
              <label>
                Compensation (optional)
                <input
                  name="compensation_amount"
                  type="number"
                  min="0"
                  step="0.01"
                />
              </label>
              <label>
                Currency
                <input
                  name="currency"
                  defaultValue="INR"
                  pattern="[A-Z]{3}"
                  maxLength={3}
                />
              </label>
              <label>
                Pay period
                <select name="pay_period">
                  <option value="month">Monthly</option>
                  <option value="year">Yearly</option>
                  <option value="hour">Hourly</option>
                  <option value="one_time">One-time</option>
                </select>
              </label>
            </div>
            <button className="primary" disabled={busy}>
              {busy ? "Creating…" : "Create opportunity"}
            </button>
            <p className="small muted">
              If a request times out, check Your listings before creating it
              again.
            </p>
          </form>
        </section>
      )}
    </>
  );
}
