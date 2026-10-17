import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Download, FileSpreadsheet, Upload } from "lucide-react";
import { useAuth } from "../auth";
import { useQuery } from "../lib/useQuery";
import { skillList } from "../lib/rules";
import type {
  Application,
  Drive,
  Page,
  RosterCommit,
  RosterPreview,
  RosterRow,
  UniversityReport,
} from "../lib/types";
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

const TABS = [
  ["overview", "Overview"],
  ["roster", "Roster"],
  ["drives", "Campus drives"],
  ["applicants", "Campus applicants"],
] as const;
type Tab = (typeof TABS)[number][0];

export default function University() {
  const { me, workspace } = useAuth();
  const permitted = me!.workspaces.some(
    (w) => w.organization_id === workspace && w.role === "admin",
  );
  if (!permitted)
    return (
      <>
        <Heading title="University workspace" />
        <Empty title="Choose a university workspace">
          University admin access is required. Select an authorized university above.
        </Empty>
      </>
    );
  // Keyed by workspace so switching universities clears every table and form.
  return <UniversityWorkspace key={workspace} university={workspace} />;
}

function UniversityWorkspace({ university }: { university: string }) {
  // The tab lives in the URL so refresh, back/forward and shared links keep it.
  const [params, setParams] = useSearchParams();
  const tab: Tab = TABS.some(([v]) => v === params.get("tab")) ? (params.get("tab") as Tab) : "overview";
  const setTab = (value: Tab) => setParams(value === "overview" ? {} : { tab: value }, { replace: true });
  const name =
    useAuth().me!.workspaces.find((w) => w.organization_id === university)?.name ??
    "Your university";
  return (
    <>
      <Heading eyebrow={name} title="University workspace">
        Import your roster, authorize campus drives and follow placement outcomes.
      </Heading>
      <div className="tabs" role="group" aria-label="University sections">
        {TABS.map(([value, label]) => (
          <button
            key={value}
            aria-pressed={tab === value}
            className={tab === value ? "active" : ""}
            onClick={() => setTab(value)}
          >
            {label}
          </button>
        ))}
      </div>
      {tab === "overview" && <Overview university={university} />}
      {tab === "roster" && <Roster university={university} />}
      {tab === "drives" && <Drives university={university} />}
      {tab === "applicants" && <Applicants university={university} />}
    </>
  );
}

function Overview({ university }: { university: string }) {
  const { api } = useAuth();
  const report = useQuery<UniversityReport>(`/university/report?workspace_id=${university}`);
  const [error, setError] = useState<unknown>();
  const [busy, setBusy] = useState(false);
  const kpis: [string, number | undefined][] = [
    ["Campus applications", report.data?.applications],
    ["Shortlisted", report.data?.shortlisted],
    ["Offers", report.data?.offered],
    ["Students with offers", report.data?.students_with_offers],
  ];
  return (
    <>
      <ErrorMessage error={report.error || error} />
      <div className="kpi-grid">
        {kpis.map(([label, value]) => (
          <div className="kpi" key={label}>
            <span>{label}</span>
            <strong>{report.loading ? "—" : (value ?? "—")}</strong>
          </div>
        ))}
      </div>
      <section className="panel">
        <div className="section-heading">
          <div>
            <h2>Placement report</h2>
            <p className="muted">
              Counts only applications made through your campus drives. An offer is not a
              confirmed placement.
            </p>
          </div>
          <button
            className="secondary"
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              setError(null);
              try {
                const blob = await api<Blob>(
                  `/university/report.csv?workspace_id=${university}`,
                  {},
                  "blob",
                );
                const url = URL.createObjectURL(blob);
                const link = Object.assign(document.createElement("a"), {
                  href: url,
                  download: "campus-report.csv",
                });
                link.click();
                URL.revokeObjectURL(url);
              } catch (err) {
                setError(err);
              } finally {
                setBusy(false);
              }
            }}
          >
            <Download size={16} /> {busy ? "Preparing…" : "Export CSV"}
          </button>
        </div>
      </section>
    </>
  );
}

function Roster({ university }: { university: string }) {
  const { api } = useAuth();
  const [page, setPage] = useState(1);
  const roster = useQuery<Page<RosterRow>>(
    `/university/roster?workspace_id=${university}&page=${page}&page_size=20`,
  );
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<RosterPreview | null>(null);
  const [result, setResult] = useState<RosterCommit | null>(null);
  const [error, setError] = useState<unknown>();
  const [busy, setBusy] = useState(false);

  const send = async (path: string) => {
    const body = new FormData();
    body.set("workspace_id", university);
    body.set("file", file!);
    return api<unknown>(path, { method: "POST", body });
  };

  return (
    <div className="stack">
      <section className="panel">
        <div className="upload-panel">
          <span className="upload-icon">
            <FileSpreadsheet size={26} />
          </span>
          <div className="grow">
            <h2>Import your roster</h2>
            <p className="muted">
              CSV with the header <code>student_id,name,email,branch,batch,cgpa</code> — up to
              100 rows. Preview first; nothing is saved until you import, and an import with any
              invalid row saves nothing.
            </p>
            <div className="drop-zone" style={{ marginTop: 16 }}>
              <Upload size={20} aria-hidden="true" />
              <label className="grow">
                Roster CSV
                <input
                  type="file"
                  accept=".csv,text/csv"
                  onChange={(e) => {
                    setFile(e.target.files?.[0] ?? null);
                    setPreview(null);
                    setResult(null);
                    setError(null);
                  }}
                />
              </label>
            </div>
            <div className="actions">
              <button
                className="secondary"
                disabled={!file || busy}
                onClick={async () => {
                  setBusy(true);
                  setError(null);
                  try {
                    setPreview((await send("/university/roster/preview")) as RosterPreview);
                  } catch (err) {
                    setError(err);
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                Preview
              </button>
              <button
                className="primary"
                disabled={!preview || preview.errors.length > 0 || busy}
                onClick={async () => {
                  setBusy(true);
                  setError(null);
                  try {
                    setResult((await send("/university/roster/commit")) as RosterCommit);
                    setPreview(null);
                    roster.reload();
                  } catch (err) {
                    setError(err);
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                {busy ? "Working…" : "Import roster"}
              </button>
            </div>
          </div>
        </div>
        <ErrorMessage error={error} />
        {result && (
          <p role="status" className="notice success">
            Imported: {result.inserted} added, {result.updated} updated, {result.unchanged}{" "}
            unchanged.
          </p>
        )}
        {preview && (
          <>
            <p role="status" className={`notice ${preview.errors.length ? "error" : "success"}`}>
              {preview.total_rows} rows checked · {preview.valid_rows.length} valid ·{" "}
              {preview.errors.length} with problems
              {preview.errors.length > 0 && " — fix them and preview again."}
            </p>
            {preview.errors.length > 0 && (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Row</th>
                      <th>Field</th>
                      <th>Problem</th>
                    </tr>
                  </thead>
                  <tbody>
                    {preview.errors.map((e, i) => (
                      <tr key={i} className="row-error">
                        <td>{e.row}</td>
                        <td>{e.field ?? "row"}</td>
                        <td>{e.message}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </section>

      <section>
        <div className="section-heading">
          <div>
            <h2>Students</h2>
            <p className="muted">
              University-claimed records · sample data. Academic data is not externally verified.
            </p>
          </div>
        </div>
        <ErrorMessage error={roster.error} />
        {roster.loading && <Loading />}
        {roster.data && roster.data.items.length > 0 && (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Student ID</th>
                  <th>Name</th>
                  <th>Branch</th>
                  <th>Batch</th>
                  <th>CGPA</th>
                  <th>Account</th>
                </tr>
              </thead>
              <tbody>
                {roster.data.items.map((row) => (
                  <tr key={row.id}>
                    <td>{row.student_id}</td>
                    <td>
                      {row.name}
                      <br />
                      <small className="muted">{row.email}</small>
                    </td>
                    <td>{row.branch.toUpperCase()}</td>
                    <td>{row.batch}</td>
                    <td>{row.cgpa ?? "—"}</td>
                    <td>
                      <Badge tone={row.linked ? "green" : ""}>
                        {row.linked ? "Linked" : "Not claimed"}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {roster.data?.items.length === 0 && (
          <Empty title="No students yet">Import a roster CSV to add your students.</Empty>
        )}
        {roster.data && <Pagination data={roster.data} onPage={setPage} />}
      </section>
    </div>
  );
}

function Drives({ university }: { university: string }) {
  const { api } = useAuth();
  const [page, setPage] = useState(1);
  const drives = useQuery<Page<Drive>>(
    `/university/drives?workspace_id=${university}&page=${page}&page_size=10`,
  );
  const [error, setError] = useState<unknown>();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  return (
    <div className="two-column">
      <section>
        <ErrorMessage error={drives.error} />
        {drives.loading && <Loading />}
        <div className="stack">
          {drives.data?.items.map((d) => (
            <article className="panel" key={d.id}>
              <div className="section-heading">
                <div>
                  <h2>{d.opportunity_title}</h2>
                  <p className="muted">
                    Batch {d.batch} · Closes {date(d.deadline)} · Rules v{d.rules_version ?? 1}
                  </p>
                </div>
                <Badge tone="blue">Campus drive</Badge>
              </div>
              <div className="form-grid">
                <div>
                  <small className="muted">Branches</small>
                  <Tags items={(d.allowed_branches ?? []).map((b) => b.toUpperCase())} />
                  {(d.allowed_branches ?? []).length === 0 && <p className="small">All branches</p>}
                </div>
                <div>
                  <small className="muted">Minimum CGPA</small>
                  <p>{d.min_cgpa ?? "None"}</p>
                </div>
                <div>
                  <small className="muted">Mandatory skills</small>
                  <Tags items={d.required_skills ?? []} />
                  {(d.required_skills ?? []).length === 0 && <p className="small">None</p>}
                </div>
              </div>
            </article>
          ))}
        </div>
        {drives.data?.items.length === 0 && (
          <Empty title="No campus drives yet">
            Authorize a drive to make a company’s campus listing visible to your students.
          </Empty>
        )}
        {drives.data && <Pagination data={drives.data} onPage={setPage} />}
      </section>
      <aside className="panel">
        <h2>Authorize a drive</h2>
        <p className="small muted">
          Rules are frozen once published. Students see the reasons when they don’t qualify.
        </p>
        <ErrorMessage error={error} />
        {message && (
          <p role="status" className="notice success">
            {message}
          </p>
        )}
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            if (busy) return;
            const form = e.currentTarget;
            const data = new FormData(form);
            const minCgpa = String(data.get("min_cgpa") || "");
            setBusy(true);
            setError(null);
            setMessage("");
            try {
              await api("/university/drives", {
                method: "POST",
                body: JSON.stringify({
                  university_id: university,
                  opportunity_id: String(data.get("opportunity_id")).trim(),
                  allowed_branches: skillList(data.get("branches")),
                  batch: Number(data.get("batch")),
                  min_cgpa: minCgpa ? Number(minCgpa) : null,
                  required_skills: skillList(data.get("skills")),
                  deadline: new Date(String(data.get("deadline"))).toISOString(),
                }),
              });
              form.reset();
              setMessage("Drive authorized.");
              drives.reload();
            } catch (err) {
              setError(err);
            } finally {
              setBusy(false);
            }
          }}
        >
          <label>
            Opportunity ID <small>Shared by the hiring company</small>
            <input
              name="opportunity_id"
              required
              pattern="[0-9a-fA-F-]{36}"
              spellCheck={false}
              autoComplete="off"
              placeholder="e.g. 9c1e0000-0000-4000-8000-000000000000"
            />
          </label>
          <label>
            Branches <small>Comma-separated; blank allows all</small>
            <input name="branches" placeholder="CSE, IT…" />
          </label>
          <div className="form-grid">
            <label>
              Batch
              <input name="batch" type="number" min={2000} max={2100} defaultValue={2027} required />
            </label>
            <label>
              Min CGPA
              <input name="min_cgpa" type="number" min={0} max={10} step="0.01" placeholder="7.5" />
            </label>
          </div>
          <label>
            Mandatory skills <small>Comma-separated</small>
            <input name="skills" placeholder="python…" />
          </label>
          <label>
            Deadline
            <input name="deadline" type="datetime-local" required />
          </label>
          <button className="primary" disabled={busy}>
            {busy ? "Authorizing…" : "Authorize drive"}
          </button>
        </form>
      </aside>
    </div>
  );
}

function Applicants({ university }: { university: string }) {
  const [page, setPage] = useState(1);
  const applicants = useQuery<Page<Application>>(
    `/applications?scope=university&workspace_id=${university}&page=${page}&page_size=10`,
  );
  return (
    <>
      <p className="muted" style={{ marginBottom: 12 }}>
        Applications submitted through your drives. Hiring decisions belong to each company.
      </p>
      <ErrorMessage error={applicants.error} />
      {applicants.loading && <Loading />}
      {applicants.data && applicants.data.items.length > 0 && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Student</th>
                <th>Opportunity</th>
                <th>Applied</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {applicants.data.items.map((a) => (
                <tr key={a.id}>
                  <td>{a.profile_snapshot?.name || "Student"}</td>
                  <td>{a.title}</td>
                  <td>{date(a.created_at)}</td>
                  <td>
                    <Badge
                      tone={
                        a.status === "offered"
                          ? "green"
                          : a.status === "shortlisted"
                            ? "blue"
                            : a.status === "rejected"
                              ? "red"
                              : ""
                      }
                    >
                      {a.status}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {applicants.data?.items.length === 0 && (
        <Empty title="No campus applications yet">
          Students’ applications through your drives will appear here.
        </Empty>
      )}
      {applicants.data && <Pagination data={applicants.data} onPage={setPage} />}
    </>
  );
}
