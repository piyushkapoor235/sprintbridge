import { useState } from "react";
import { Link, Navigate, useSearchParams } from "react-router-dom";
import { ArrowUpRight, ArrowRight, Layers3, Check, MailCheck } from "lucide-react";
import { useAuth } from "../auth";
import { configured, supabase } from "../lib/supabase";
import { ErrorMessage } from "../components/ui";

type Mode = "signin" | "signup" | "sent";

// Supabase Auth error codes -> plain, actionable messages.
const AUTH_MESSAGES: Record<string, string> = {
  invalid_credentials: "That email and password don’t match. Check them and try again.",
  user_already_exists: "An account with this email already exists. Sign in instead.",
  email_exists: "An account with this email already exists. Sign in instead.",
  email_address_invalid: "Use a real email address you can open — we send a confirmation link to it.",
  over_email_send_rate_limit: "We’ve sent too many emails in the last hour. Please try again in a few minutes.",
  over_request_rate_limit: "Too many attempts. Please wait a moment and try again.",
  weak_password: "Choose a stronger password: at least 8 characters, mixing letters and numbers.",
  signup_disabled: "New sign-ups are paused right now.",
};
function friendly(err: unknown): unknown {
  const code = (err as { code?: string } | null)?.code;
  return code && AUTH_MESSAGES[code] ? new Error(AUTH_MESSAGES[code]) : err;
}

export default function Login() {
  const { session } = useAuth();
  const [params, setParams] = useSearchParams();
  const mode: Mode = params.get("mode") === "signup" ? "signup" : "signin";
  const [sentTo, setSentTo] = useState("");
  const [error, setError] = useState<unknown>();
  const [notice, setNotice] = useState("");
  const [unconfirmed, setUnconfirmed] = useState("");
  const [busy, setBusy] = useState(false);
  if (session) return <Navigate to="/dashboard" replace />;

  const switchTo = (next: "signin" | "signup") => {
    setError(null);
    setNotice("");
    setUnconfirmed("");
    setSentTo("");
    setParams(next === "signup" ? { mode: "signup" } : {}, { replace: true });
  };

  const resend = async (email: string) => {
    if (!supabase || busy) return;
    setBusy(true);
    setError(null);
    try {
      const result = await supabase.auth.resend({
        type: "signup",
        email,
        options: { emailRedirectTo: `${window.location.origin}/login` },
      });
      if (result.error) throw result.error;
      setNotice(`We sent a new confirmation link to ${email}.`);
    } catch (err) {
      setError(friendly(err));
    } finally {
      setBusy(false);
    }
  };

  const view: Mode = sentTo ? "sent" : mode;

  return (
    <div className="login-page">
      <section className="login-story">
        <div className="brand">
          <Layers3 />
          <span>
            SprintBridge<span className="brand-dot">.</span>
          </span>
        </div>
        <div>
          <p className="eyebrow">From potential to possibility</p>
          <h1>
            Your skills.
            <br />
            Your people.
            <br />
            <em>Your next chapter.</em>
          </h1>
          <p>A clearer path from what you know to where you want to go.</p>
          <div className="story-steps">
            <span>
              <Check size={16} /> Build your skill profile
            </span>
            <span>
              <Check size={16} /> Discover your next opportunity
            </span>
            <span>
              <Check size={16} /> Grow with a mentor
            </span>
          </div>
        </div>
        <span className="story-footer">
          Make your next move count <ArrowUpRight size={22} />
        </span>
      </section>
      <main className="login-form">
        <div className="login-box">
          {view !== "sent" && (
            <nav className="tabs auth-tabs" aria-label="Account">
              <Link
                to="/login"
                replace
                aria-current={view === "signin" ? "page" : undefined}
                onClick={() => switchTo("signin")}
              >
                Sign in
              </Link>
              <Link
                to="/login?mode=signup"
                replace
                aria-current={view === "signup" ? "page" : undefined}
                onClick={() => switchTo("signup")}
              >
                Create account
              </Link>
            </nav>
          )}

          {view === "signin" && (
            <>
              <p className="eyebrow">Welcome to SprintBridge</p>
              <h2>Good to see you.</h2>
              <p className="muted">Sign in to pick up where you left off.</p>
            </>
          )}
          {view === "signup" && (
            <>
              <p className="eyebrow">Join SprintBridge</p>
              <h2>Create your account.</h2>
              <p className="muted">
                For students and job seekers. Companies, universities and mentors are onboarded by our team.
              </p>
            </>
          )}
          {view === "sent" && (
            <div className="sent-state" role="status">
              <span className="upload-icon">
                <MailCheck size={26} />
              </span>
              <h2>Check your inbox.</h2>
              <p className="muted">
                We sent a confirmation link to <strong>{sentTo}</strong>. Open it to activate your account, then
                sign in.
              </p>
            </div>
          )}

          {!configured && (
            <div className="notice">
              Sign-in is not configured yet. Your project administrator needs to connect authentication and the API.
            </div>
          )}
          <ErrorMessage error={error} />
          {notice && (
            <p className="notice success" role="status">
              {notice}
            </p>
          )}
          {unconfirmed && (
            <div className="notice">
              <div>
                Your email isn’t confirmed yet.{" "}
                <button className="link-button" disabled={busy} onClick={() => resend(unconfirmed)}>
                  Resend the confirmation link
                </button>
              </div>
            </div>
          )}

          {view === "signin" && (
            <form
              onSubmit={async (e) => {
                e.preventDefault();
                if (!supabase || busy) return;
                setBusy(true);
                setError(null);
                setNotice("");
                setUnconfirmed("");
                const data = new FormData(e.currentTarget);
                const email = String(data.get("email")).trim();
                try {
                  const result = await supabase.auth.signInWithPassword({
                    email,
                    password: String(data.get("password")),
                  });
                  if (result.error) {
                    if (result.error.code === "email_not_confirmed") setUnconfirmed(email);
                    else throw result.error;
                  }
                } catch (err) {
                  setError(friendly(err));
                } finally {
                  setBusy(false);
                }
              }}
            >
              <label>
                Email address
                <input
                  name="email"
                  type="email"
                  autoComplete="username"
                  spellCheck={false}
                  placeholder="you@university.edu"
                  required
                />
              </label>
              <label>
                Password
                <input
                  name="password"
                  type="password"
                  autoComplete="current-password"
                  placeholder="Enter your password"
                  required
                />
              </label>
              <button className="primary full" disabled={!configured || busy}>
                {busy ? "Signing in…" : "Sign in"}
                <ArrowRight size={18} />
              </button>
              <p className="small muted">
                New here?{" "}
                <button type="button" className="link-button" onClick={() => switchTo("signup")}>
                  Create an account
                </button>
              </p>
            </form>
          )}

          {view === "signup" && (
            <form
              onSubmit={async (e) => {
                e.preventDefault();
                if (!supabase || busy) return;
                const data = new FormData(e.currentTarget);
                const email = String(data.get("email")).trim();
                const password = String(data.get("password"));
                if (password !== String(data.get("confirm"))) {
                  setError(new Error("The two passwords don’t match."));
                  return;
                }
                setBusy(true);
                setError(null);
                try {
                  const result = await supabase.auth.signUp({
                    email,
                    password,
                    options: {
                      data: { name: String(data.get("name")).trim() },
                      emailRedirectTo: `${window.location.origin}/login`,
                    },
                  });
                  if (result.error) throw result.error;
                  // Supabase hides whether an address is taken: an existing account comes back with no identities.
                  if (result.data.user && result.data.user.identities?.length === 0)
                    throw Object.assign(new Error(), { code: "user_already_exists" });
                  // With email confirmation on, there is no session until the link is opened.
                  if (!result.data.session) setSentTo(email);
                } catch (err) {
                  setError(friendly(err));
                } finally {
                  setBusy(false);
                }
              }}
            >
              <label>
                Full name
                <input name="name" autoComplete="name" required maxLength={120} placeholder="Your name" />
              </label>
              <label>
                Email address
                <input
                  name="email"
                  type="email"
                  autoComplete="email"
                  spellCheck={false}
                  placeholder="you@university.edu"
                  required
                />
              </label>
              <label>
                Password <small>At least 8 characters</small>
                <input name="password" type="password" autoComplete="new-password" minLength={8} required />
              </label>
              <label>
                Confirm password
                <input name="confirm" type="password" autoComplete="new-password" minLength={8} required />
              </label>
              <button className="primary full" disabled={!configured || busy}>
                {busy ? "Creating your account…" : "Create account"}
                <ArrowRight size={18} />
              </button>
              <p className="small muted">
                Already have an account?{" "}
                <button type="button" className="link-button" onClick={() => switchTo("signin")}>
                  Sign in
                </button>
              </p>
            </form>
          )}

          {view === "sent" && (
            <div className="actions">
              <button className="secondary" disabled={busy} onClick={() => resend(sentTo)}>
                Resend link
              </button>
              <button className="primary" onClick={() => switchTo("signin")}>
                Go to sign in <ArrowRight size={16} />
              </button>
            </div>
          )}
        </div>
        <footer>One place to connect learning with opportunity.</footer>
      </main>
    </div>
  );
}
