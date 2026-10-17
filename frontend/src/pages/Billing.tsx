import { useState } from "react";
import { useAuth } from "../auth";
import { useQuery } from "../lib/useQuery";
import type { Billing as BillingData, Plan } from "../lib/types";
import { Badge, Empty, ErrorMessage, Heading, Loading, TestPaymentNote, date, inr } from "../components/ui";

const METRIC: Record<string, string> = {
  mentor_requests: "Mentor requests",
  resume_analyses: "Resume analyses",
  jd_reports: "Job-fit reports",
};
const PURPOSE: Record<string, string> = {
  subscription: "Plan",
  mentor_session: "Mentor session",
  verification: "Skill verification",
};

export default function Billing() {
  const { me } = useAuth();
  const billing = useQuery<BillingData>("/billing");
  const plans = useQuery<Plan[]>("/plans");
  const b = billing.data;
  const byAudience = (a: string) => (plans.data ?? []).filter((p) => p.audience === a);
  const refresh = () => billing.reload();

  return (
    <>
      <Heading eyebrow="Plans & billing" title="Your plans">
        Plans buy more room and tools — never a higher ranking or an easier verification. Payments here are simulated
        (test mode).
      </Heading>
      <ErrorMessage error={billing.error || plans.error} />
      {(billing.loading || plans.loading) && <Loading />}
      {b && plans.data && (
        <div className="stack">
          <section>
            <div className="section-heading">
              <div>
                <h2>This month’s usage</h2>
                <p className="muted">Resets on the 1st. Counted only when an action succeeds.</p>
              </div>
            </div>
            <div className="kpi-grid">
              {Object.entries(b.usage).map(([metric, u]) => {
                const pct = u.limit ? Math.min(100, (100 * u.used) / u.limit) : 0;
                return (
                  <div className="kpi" key={metric}>
                    <span>{METRIC[metric] ?? metric}</span>
                    <strong>
                      {u.used}
                      <small className="muted"> / {u.limit ?? "∞"}</small>
                    </strong>
                    {u.limit !== null && (
                      <div className={`meter ${u.used >= u.limit ? "full" : ""}`} aria-hidden="true">
                        <span style={{ width: `${pct}%` }} />
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </section>

          <PlanGroup
            title={b.seeker_audience === "student" ? "Student plans" : "Job seeker plans"}
            note={
              b.seeker_audience === "student"
                ? "You’re on a university roster, so student pricing applies."
                : "Link to a university roster to unlock student pricing."
            }
            plans={byAudience(b.seeker_audience)}
            current={b.plans.seeker}
            onChange={refresh}
          />
          <PlanGroup
            title="Founder plans"
            note="For posting ventures on the Launchpad."
            plans={byAudience("founder")}
            current={b.plans.founder}
            onChange={refresh}
          />
          {me!.capabilities.includes("mentor") && (
            <>
              <PlanGroup
                title="Mentor plans"
                note="Mentor Pro lowers the platform commission on paid sessions."
                plans={byAudience("mentor")}
                current={b.plans.mentor}
                onChange={refresh}
              />
              <MentorPrice />
            </>
          )}
          {b.organizations.map((org) => (
            <PlanGroup
              key={org.organization_id}
              title={`${org.name} · ${org.audience === "recruiter" ? "Recruiter" : "University"} plans`}
              note={
                org.audience === "university"
                  ? "Campus plans are priced per enrolled student per year."
                  : "Company plans set how many listings can be open at once."
              }
              plans={byAudience(org.audience)}
              current={org.plan}
              organizationId={org.organization_id}
              onChange={refresh}
            />
          ))}

          <section>
            <h2 style={{ marginBottom: 12 }}>Payments</h2>
            {b.payments.length ? (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>For</th>
                      <th>Amount</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {b.payments.map((p) => (
                      <tr key={p.id}>
                        <td>{date(p.created_at)}</td>
                        <td>{PURPOSE[p.purpose] ?? p.purpose}</td>
                        <td>{inr(p.amount_inr)}</td>
                        <td>
                          <Badge tone={p.status === "refunded" ? "amber" : "green"}>
                            {p.status === "captured" ? "Paid (test)" : "Refunded"}
                          </Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <Empty title="No payments yet">Test payments for plans, sessions and verification appear here.</Empty>
            )}
          </section>

          {me!.capabilities.includes("mentor") && (
            <section>
              <h2 style={{ marginBottom: 4 }}>Earnings</h2>
              <p className="muted" style={{ marginBottom: 12 }}>
                Payouts are held for 7 days (dispute and audit window), then released by an operator.
              </p>
              {b.payouts.length ? (
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>From</th>
                        <th>Gross</th>
                        <th>Commission</th>
                        <th>You receive</th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {b.payouts.map((p) => (
                        <tr key={p.id}>
                          <td>{p.source === "verification" ? "Skill verification" : "Mentor session"}</td>
                          <td>{inr(p.gross_inr)}</td>
                          <td>{inr(p.commission_inr)}</td>
                          <td>{inr(p.net_inr)}</td>
                          <td>
                            <Badge
                              tone={
                                p.status === "released" ? "green" : p.status === "held" ? "blue" : p.status === "disputed" ? "amber" : "red"
                              }
                            >
                              {p.status === "held" ? `Held until ${date(p.release_after)}` : p.status.replace("_", " ")}
                            </Badge>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <Empty title="No earnings yet">Completed paid sessions and verifications appear here.</Empty>
              )}
            </section>
          )}
        </div>
      )}
    </>
  );
}

function PlanGroup({
  title,
  note,
  plans,
  current,
  organizationId,
  onChange,
}: {
  title: string;
  note: string;
  plans: Plan[];
  current?: string;
  organizationId?: string;
  onChange: () => void;
}) {
  const { api } = useAuth();
  const [pending, setPending] = useState<Plan | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [message, setMessage] = useState("");
  const choose = async (plan: Plan, confirm: boolean) => {
    setBusy(true);
    setError(null);
    try {
      await api("/subscriptions", {
        method: "POST",
        body: JSON.stringify({
          plan_code: plan.code,
          organization_id: organizationId ?? null,
          confirm_test_payment: confirm,
        }),
      });
      setPending(null);
      setMessage(`You’re now on ${plan.name}.`);
      onChange();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };
  return (
    <section>
      <div className="section-heading">
        <div>
          <h2>{title}</h2>
          <p className="muted">{note}</p>
        </div>
      </div>
      <ErrorMessage error={error} />
      {message && (
        <p className="notice success" role="status">
          {message}
        </p>
      )}
      <div className="plan-grid">
        {plans.map((plan) => (
          <article key={plan.code} className={`panel plan ${plan.code === current ? "current" : ""}`}>
            <div className="meta-row">
              <h3>{plan.name}</h3>
              {plan.code === current && <Badge tone="blue">Current</Badge>}
            </div>
            <div className="price">
              {plan.price_inr ? inr(plan.price_inr) : "Free"}
              {plan.price_inr > 0 && <small> / {plan.period === "student_year" ? "student / year" : "month"}</small>}
            </div>
            <ul>
              {plan.features.map((f) => (
                <li key={f}>{f}</li>
              ))}
            </ul>
            {plan.code !== current &&
              (pending?.code === plan.code ? (
                <>
                  <TestPaymentNote
                    amount={plan.price_inr}
                    what={plan.period === "student_year" ? "This plan (per enrolled student)" : "This plan"}
                  />
                  <div className="actions" style={{ marginTop: 0 }}>
                    <button className="primary" disabled={busy} onClick={() => choose(plan, true)}>
                      {busy ? "Processing…" : "Confirm test payment"}
                    </button>
                    <button className="secondary" disabled={busy} onClick={() => setPending(null)}>
                      Cancel
                    </button>
                  </div>
                </>
              ) : (
                <button
                  className={plan.price_inr ? "primary" : "secondary"}
                  disabled={busy}
                  onClick={() => (plan.price_inr ? setPending(plan) : choose(plan, false))}
                >
                  {plan.price_inr ? `Upgrade to ${plan.name}` : `Switch to ${plan.name}`}
                </button>
              ))}
          </article>
        ))}
      </div>
    </section>
  );
}

function MentorPrice() {
  const { api } = useAuth();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [message, setMessage] = useState("");
  return (
    <section className="panel">
      <h2>Your session price</h2>
      <p className="small muted">
        Students pay into escrow when they request you. Declines are refunded automatically. Leave 0 to mentor for free.
      </p>
      <ErrorMessage error={error} />
      {message && (
        <p className="notice success" role="status">
          {message}
        </p>
      )}
      <form
        className="inline-form"
        onSubmit={async (e) => {
          e.preventDefault();
          const price = Number(new FormData(e.currentTarget).get("price") || 0);
          setBusy(true);
          setError(null);
          try {
            await api("/mentors/me", { method: "PATCH", body: JSON.stringify({ session_price_inr: price || null }) });
            setMessage(price ? `Sessions now cost ${inr(price)}.` : "Your sessions are now free.");
          } catch (err) {
            setError(err);
          } finally {
            setBusy(false);
          }
        }}
      >
        <label>
          Price per session (INR)
          <input name="price" type="number" min={0} max={100000} step={50} inputMode="numeric" placeholder="500" />
        </label>
        <button className="primary" disabled={busy}>
          {busy ? "Saving…" : "Save price"}
        </button>
      </form>
    </section>
  );
}
