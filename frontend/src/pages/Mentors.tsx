import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { BadgeCheck } from "lucide-react";
import { useAuth } from "../auth";
import { useQuery } from "../lib/useQuery";
import { ApiError } from "../lib/http";
import type { Mentor, MentorRequest, Page } from "../lib/types";
import {
  Heading,
  Badge,
  Tags,
  Loading,
  ErrorMessage,
  Empty,
  Pagination,
  TestPaymentNote,
  inr,
} from "../components/ui";

export default function Mentors({ inbox = false }: { inbox?: boolean }) {
  const { me } = useAuth();
  const [params, setParams] = useSearchParams();
  const page = params.get("page") || "1";
  const skill = params.get("skill") || "";
  const scope =
    params.get("scope") === "mentor" && me!.capabilities.includes("mentor") ? "mentor" : "requester";
  const mentors = useQuery<Page<Mentor>>(
    !inbox ? `/mentors?skill=${encodeURIComponent(skill)}&page=${page}&page_size=10` : null,
  );
  const requests = useQuery<Page<MentorRequest>>(
    inbox ? `/mentor-requests?scope=${scope}&page=${page}&page_size=10` : null,
  );
  const [message, setMessage] = useState("");
  return (
    <>
      <Heading
        eyebrow="Grow with good company"
        title={inbox ? "Mentorship requests" : "Find your next mentor"}
        action={
          <Link className="secondary" to={inbox ? "/mentors" : "/mentor-requests"}>
            {inbox ? "Find mentors" : "My requests"}
          </Link>
        }
      >
        {inbox
          ? "Follow your conversations from request to decision."
          : "Mentors with verified expertise in your skill are shown first. Price never affects the order."}
      </Heading>
      {!inbox && (
        <form
          className="filters"
          onSubmit={(e) => {
            e.preventDefault();
            setParams({ skill: String(new FormData(e.currentTarget).get("skill") || "") });
          }}
        >
          <label className="grow">
            Skill to develop
            <input name="skill" defaultValue={skill} placeholder="e.g. React, SQL or Docker…" autoComplete="off" />
          </label>
          <button className="primary">Find mentors</button>
        </form>
      )}
      {inbox && me!.capabilities.includes("mentor") && (
        <div className="tabs" role="group" aria-label="Request views">
          <button onClick={() => setParams({ scope: "requester" })} aria-pressed={scope === "requester"}>
            My requests
          </button>
          <button onClick={() => setParams({ scope: "mentor" })} aria-pressed={scope === "mentor"}>
            Mentor inbox
          </button>
        </div>
      )}
      <ErrorMessage error={mentors.error || requests.error} />
      {message && (
        <p className="notice success" role="status">
          {message}
        </p>
      )}
      {(mentors.loading || requests.loading) && <Loading />}
      <div className="mentor-grid">
        {mentors.data?.items.map((mentor) => (
          <MentorCard key={mentor.id} mentor={mentor} skill={skill} onSent={setMessage} />
        ))}
      </div>
      {mentors.data?.items.length === 0 && (
        <Empty title="No matching mentors yet">Try another skill. A match is never guaranteed.</Empty>
      )}
      <div className="stack">
        {requests.data?.items.map((item) => (
          <RequestCard key={item.id} item={item} scope={scope} onChange={requests.reload} />
        ))}
      </div>
      {requests.data?.items.length === 0 && (
        <Empty title="No requests yet">Your mentorship requests will appear here.</Empty>
      )}
      {(mentors.data || requests.data) && (
        <Pagination
          data={(mentors.data || requests.data)!}
          onPage={(p) => {
            const next = new URLSearchParams(params);
            next.set("page", String(p));
            setParams(next);
          }}
        />
      )}
    </>
  );
}

function MentorCard({ mentor, skill, onSent }: { mentor: Mentor; skill: string; onSent: (m: string) => void }) {
  const { me, api } = useAuth();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [pendingNote, setPendingNote] = useState<string | null>(null);
  const price = mentor.session_price_inr ?? 0;
  const send = async (note: string, confirm: boolean) => {
    setBusy(true);
    setError(null);
    try {
      await api("/mentor-requests", {
        method: "POST",
        body: JSON.stringify({ mentor_id: mentor.id, note, confirm_test_payment: confirm }),
      });
      setPendingNote(null);
      onSent(
        price
          ? `Request sent to ${mentor.name}. ${inr(price)} is held in escrow and refunded if they decline.`
          : `Request sent to ${mentor.name}. Follow it in My requests.`,
      );
    } catch (err) {
      if (err instanceof ApiError && err.code === "PAYMENT_REQUIRED") setPendingNote(note);
      else setError(err);
    } finally {
      setBusy(false);
    }
  };
  return (
    <section className="panel">
      <div className="section-heading">
        <span className="avatar mentor-avatar">{mentor.name[0]}</span>
        <div className="meta-row">
          {mentor.mentor_verified && (
            <Badge tone="green">
              <BadgeCheck size={13} aria-hidden="true" /> Verified expert
            </Badge>
          )}
          <Badge tone={price ? "blue" : ""}>{price ? `${inr(price)} / session` : "Free"}</Badge>
        </div>
      </div>
      <h2>{mentor.name}</h2>
      <p className="muted">{mentor.niche}</p>
      <p>{mentor.experience_summary}</p>
      {(mentor.expertise ?? []).length > 0 && (
        <>
          <Tags items={mentor.expertise!.map((e) => `${e.skill} · L${e.level}`)} />
          <small className="muted">Calibrated expertise (levels 1–4) · can verify up to these levels</small>
        </>
      )}
      {(mentor.expertise ?? []).length === 0 && (
        <>
          <Tags items={mentor.skills} />
          <small className="muted">Self-declared skills</small>
        </>
      )}
      {mentor.match_reason && <p className="match-reason">{mentor.match_reason}</p>}
      <ErrorMessage error={error} />
      {mentor.user_id !== me!.user_id &&
        (pendingNote !== null ? (
          <>
            <TestPaymentNote amount={price} what={`A session with ${mentor.name}`} />
            <div className="actions" style={{ marginTop: 0 }}>
              <button className="primary" disabled={busy} onClick={() => send(pendingNote, true)}>
                {busy ? "Sending…" : "Confirm test payment & send"}
              </button>
              <button className="secondary" disabled={busy} onClick={() => setPendingNote(null)}>
                Cancel
              </button>
            </div>
          </>
        ) : (
          <details>
            <summary>Request mentorship</summary>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                if (!busy) send(String(new FormData(e.currentTarget).get("note")), false);
              }}
            >
              <label>
                Your note
                <textarea
                  name="note"
                  required
                  maxLength={1000}
                  rows={3}
                  defaultValue={skill ? `I'd like help developing my ${skill} skills.` : ""}
                />
              </label>
              <button className="primary" disabled={busy}>
                {busy ? "Sending…" : price ? `Continue · ${inr(price)}` : "Send request"}
              </button>
            </form>
          </details>
        ))}
    </section>
  );
}

function RequestCard({
  item,
  scope,
  onChange,
}: {
  item: MentorRequest;
  scope: "mentor" | "requester";
  onChange: () => void;
}) {
  const { api } = useAuth();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const call = async (path: string, init: RequestInit) => {
    setBusy(true);
    setError(null);
    try {
      await api(path, init);
      onChange();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };
  const paid = Boolean(item.payment_status);
  return (
    <section className="panel">
      <div className="section-heading">
        <h2>{scope === "mentor" ? item.requester_name : item.mentor_name}</h2>
        <div className="meta-row">
          {paid && (
            <Badge tone={item.payment_status === "refunded" ? "amber" : "blue"}>
              {item.payment_status === "refunded"
                ? "Refunded"
                : item.price_inr
                  ? `${inr(item.price_inr)} in escrow`
                  : "Paid session"}
            </Badge>
          )}
          {item.session_status && item.session_status !== "pending" && (
            <Badge tone={item.session_status === "completed" ? "green" : "amber"}>Session {item.session_status}</Badge>
          )}
          <Badge tone={item.status === "accepted" ? "green" : item.status === "declined" ? "red" : ""}>{item.status}</Badge>
        </div>
      </div>
      <p className="preserve-lines">{item.note}</p>
      <ErrorMessage error={error} />
      {scope === "mentor" && item.status === "pending" && (
        <div className="actions">
          {(["accepted", "declined"] as const).map((status) => (
            <button
              className={status === "accepted" ? "primary" : "secondary"}
              key={status}
              disabled={busy}
              onClick={() => call(`/mentor-requests/${item.id}`, { method: "PATCH", body: JSON.stringify({ status }) })}
            >
              {status === "accepted" ? "Accept" : paid ? "Decline & refund" : "Decline"}
            </button>
          ))}
        </div>
      )}
      {scope === "mentor" && item.status === "accepted" && item.session_status === "pending" && (
        <div className="actions">
          <button className="primary" disabled={busy} onClick={() => call(`/mentor-requests/${item.id}/complete`, { method: "POST" })}>
            Mark session completed
          </button>
          {paid && <small className="muted">Your payout is then held 7 days for disputes.</small>}
        </div>
      )}
      {scope === "requester" && paid && item.session_status === "completed" && (
        <details>
          <summary>Report a problem with this session</summary>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              call(`/mentor-requests/${item.id}/dispute`, {
                method: "POST",
                body: JSON.stringify({ reason: new FormData(e.currentTarget).get("reason") }),
              });
            }}
          >
            <label>
              What happened?
              <textarea name="reason" required maxLength={500} rows={2} />
            </label>
            <button className="secondary" disabled={busy}>
              Open dispute
            </button>
          </form>
        </details>
      )}
    </section>
  );
}
