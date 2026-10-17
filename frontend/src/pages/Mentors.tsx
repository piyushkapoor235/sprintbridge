import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useAuth } from "../auth";
import { useQuery } from "../lib/useQuery";
import type { Mentor, MentorRequest, Page } from "../lib/types";
import {
  Heading,
  Badge,
  Tags,
  Loading,
  ErrorMessage,
  Empty,
  Pagination,
} from "../components/ui";
export default function Mentors({ inbox = false }: { inbox?: boolean }) {
  const { me, api } = useAuth();
  const [params, setParams] = useSearchParams();
  const page = params.get("page") || "1";
  const skill = params.get("skill") || "";
  const scope =
    params.get("scope") === "mentor" && me!.capabilities.includes("mentor")
      ? "mentor"
      : "requester";
  const mentors = useQuery<Page<Mentor>>(
    !inbox
      ? `/mentors?skill=${encodeURIComponent(skill)}&page=${page}&page_size=10`
      : null,
  );
  const requests = useQuery<Page<MentorRequest>>(
    inbox ? `/mentor-requests?scope=${scope}&page=${page}&page_size=10` : null,
  );
  const [error, setError] = useState<unknown>();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  return (
    <>
      <Heading
        eyebrow="GROW WITH GOOD COMPANY"
        title={inbox ? "Mentorship requests" : "Find your next mentor"}
        action={
          <Link
            className="secondary"
            to={inbox ? "/mentors" : "/mentor-requests"}
          >
            {inbox ? "Find mentors" : "My requests"}
          </Link>
        }
      >
        {inbox
          ? "Follow your conversations from request to decision."
          : "Connect with someone who knows the path you’re taking."}
      </Heading>
      {!inbox && (
        <form
          className="filters"
          onSubmit={(e) => {
            e.preventDefault();
            setParams({
              skill: String(new FormData(e.currentTarget).get("skill") || ""),
            });
          }}
        >
          <label className="grow">
            Skill to develop
            <input
              name="skill"
              defaultValue={skill}
              placeholder="e.g. React, SQL or Docker"
            />
          </label>
          <button className="primary">Find mentors</button>
        </form>
      )}
      {inbox && me!.capabilities.includes("mentor") && (
        <div className="tabs">
          <button
            onClick={() => setParams({ scope: "requester" })}
            aria-pressed={scope === "requester"}
          >
            My requests
          </button>
          <button
            onClick={() => setParams({ scope: "mentor" })}
            aria-pressed={scope === "mentor"}
          >
            Mentor inbox
          </button>
        </div>
      )}
      <ErrorMessage error={error} />
      <ErrorMessage error={mentors.error || requests.error} />
      {message && (
        <p className="notice success" role="status">
          {message}
        </p>
      )}
      {(mentors.loading || requests.loading) && <Loading />}
      <div className="mentor-grid">
        {mentors.data?.items.map((mentor) => (
          <section className="panel" key={mentor.id}>
            <span className="avatar mentor-avatar">{mentor.name[0]}</span>
            <h2>{mentor.name}</h2>
            <p className="muted">{mentor.niche}</p>
            <p>{mentor.experience_summary}</p>
            <Tags items={mentor.skills} />
            <small className="muted">Self-declared skills</small>
            {mentor.match_reason && (
              <p className="match-reason">{mentor.match_reason}</p>
            )}
            {mentor.user_id !== me!.user_id && (
              <details>
                <summary>Request mentorship</summary>
                <form
                  onSubmit={async (e) => {
                    e.preventDefault();
                    if (busy) return;
                    const note = new FormData(e.currentTarget).get("note");
                    setBusy(true);
                    setError(null);
                    setMessage("");
                    try {
                      await api("/mentor-requests", {
                        method: "POST",
                        body: JSON.stringify({ mentor_id: mentor.id, note }),
                      });
                      setMessage(
                        `Request sent to ${mentor.name}. Follow it in My requests.`,
                      );
                    } catch (err) {
                      setError(err);
                    } finally {
                      setBusy(false);
                    }
                  }}
                >
                  <label>
                    Your note
                    <textarea
                      name="note"
                      required
                      maxLength={1000}
                      rows={3}
                      defaultValue={
                        skill
                          ? `I'd like help developing my ${skill} skills.`
                          : ""
                      }
                    />
                  </label>
                  <button className="primary" disabled={busy}>
                    {busy ? "Sending…" : "Send request"}
                  </button>
                </form>
              </details>
            )}
          </section>
        ))}
      </div>
      {mentors.data?.items.length === 0 && (
        <Empty title="No matching mentors yet">
          Try another skill. A match is never guaranteed.
        </Empty>
      )}
      <div className="stack">
        {requests.data?.items.map((item) => (
          <section className="panel" key={item.id}>
            <div className="section-heading">
              <h2>
                {scope === "mentor" ? item.requester_name : item.mentor_name}
              </h2>
              <Badge>{item.status}</Badge>
            </div>
            <p className="preserve-lines">{item.note}</p>
            {scope === "mentor" && item.status === "pending" && (
              <div className="actions">
                {(["accepted", "declined"] as const).map((status) => (
                  <button
                    className="secondary"
                    key={status}
                    disabled={busy}
                    onClick={async () => {
                      setBusy(true);
                      setError(null);
                      try {
                        await api(`/mentor-requests/${item.id}`, {
                          method: "PATCH",
                          body: JSON.stringify({ status }),
                        });
                      } catch (err) {
                        setError(err);
                      } finally {
                        setBusy(false);
                        requests.reload();
                      }
                    }}
                  >
                    {status === "accepted" ? "Accept" : "Decline"}
                  </button>
                ))}
              </div>
            )}
          </section>
        ))}
      </div>
      {requests.data?.items.length === 0 && (
        <Empty title="No requests yet">
          Your mentorship requests will appear here.
        </Empty>
      )}
      {(mentors.data || requests.data) && (
        <Pagination
          data={(mentors.data || requests.data)!}
          onPage={(page) => {
            const next = new URLSearchParams(params);
            next.set("page", String(page));
            setParams(next);
          }}
        />
      )}
    </>
  );
}
