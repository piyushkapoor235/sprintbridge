import { useState } from "react";
import { useAuth } from "../auth";
import { Heading, ErrorMessage, Badge } from "../components/ui";
import { safeLink, skillList } from "../lib/rules";
import type { Me } from "../lib/types";
export default function Profile() {
  const { me, api, reload } = useAuth();
  const profile = me!.profile;
  const [error, setError] = useState<unknown>();
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  return (
    <>
      <Heading eyebrow="Introduce yourself" title="Your profile">
        Give your experience a place to speak for itself.
      </Heading>
      <div className="two-column">
        <section className="panel">
          <h2>The essentials</h2>
          <ErrorMessage error={error} />
          {saved && (
            <p role="status" className="notice success">
              Your profile has been saved.
            </p>
          )}
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              if (busy) return;
              const data = new FormData(e.currentTarget);
              const url = String(data.get("portfolio_url") || "").trim();
              if (url && !safeLink(url)) {
                setError(
                  new Error("Use an http:// or https:// portfolio link."),
                );
                return;
              }
              setBusy(true);
              setSaved(false);
              setError(null);
              try {
                await api<Me>("/me", {
                  method: "PATCH",
                  body: JSON.stringify({
                    name: String(data.get("name")).trim(),
                    specialization: data.get("specialization") || null,
                    education_summary: data.get("education_summary") || null,
                    skills: skillList(data.get("skills")),
                    portfolio_url: url || null,
                    is_public: data.get("is_public") === "on",
                  }),
                });
                setSaved(true);
                reload();
              } catch (err) {
                setError(err);
              } finally {
                setBusy(false);
              }
            }}
          >
            <label>
              Full name
              <input
                name="name"
                defaultValue={profile.name}
                required
                maxLength={120}
              />
            </label>
            <label>
              Specialization
              <input
                name="specialization"
                defaultValue={profile.specialization || ""}
                maxLength={120}
                placeholder="e.g. Frontend development"
              />
            </label>
            <label>
              Education summary
              <textarea
                name="education_summary"
                defaultValue={profile.education_summary || ""}
                maxLength={1000}
                rows={3}
                placeholder="Your course, university and graduation year"
              />
            </label>
            <label>
              Skills <small>Separate with commas · up to 50 skills</small>
              <textarea
                name="skills"
                defaultValue={profile.skills.join(", ")}
                rows={3}
                placeholder="React, TypeScript, Python"
              />
            </label>
            <label>
              Portfolio URL
              <input
                type="url"
                name="portfolio_url"
                defaultValue={profile.portfolio_url || ""}
                placeholder="https://your-portfolio.com"
              />
            </label>
            <label className="checkbox">
              <input
                type="checkbox"
                name="is_public"
                defaultChecked={profile.is_public}
              />
              Make my profile public
            </label>
            <button className="primary" disabled={busy}>
              {busy ? "Saving…" : "Save profile"}
            </button>
          </form>
        </section>
        <aside className="panel profile-note">
          <Badge>Self-declared skills</Badge>
          <h2>Your experience, clearly represented.</h2>
          <p>
            Skills entered here are self-declared. A portfolio link supplies
            context; it does not verify a skill.
          </p>
          <p>
            Upload a resume in Skill evidence to see system-assessed skills and
            the evidence behind them.
          </p>
          <p className="small muted">
            Academic records and organization permissions are managed
            separately.
          </p>
        </aside>
      </div>
    </>
  );
}
