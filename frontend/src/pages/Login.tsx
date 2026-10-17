import { useState } from "react";
import { Navigate } from "react-router-dom";
import { ArrowUpRight, ArrowRight, Layers3, Check } from "lucide-react";
import { useAuth } from "../auth";
import { configured, supabase } from "../lib/supabase";
import { ErrorMessage } from "../components/ui";

export default function Login() {
  const { session } = useAuth();
  const [error, setError] = useState<unknown>();
  const [busy, setBusy] = useState(false);
  if (session) return <Navigate to="/dashboard" replace />;
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
          <p className="eyebrow">FROM POTENTIAL TO POSSIBILITY</p>
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
          MAKE YOUR NEXT MOVE COUNT <ArrowUpRight size={22} />
        </span>
      </section>
      <main className="login-form">
        <div className="login-box">
          <p className="eyebrow">WELCOME TO SPRINTBRIDGE</p>
          <h2>Good to see you.</h2>
          <p className="muted">Sign in to pick up where you left off.</p>
          {!configured && (
            <div className="notice">
              Sign-in is not configured yet. Your project administrator needs to
              connect authentication and the API.
            </div>
          )}
          <ErrorMessage error={error} />
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              if (!supabase || busy) return;
              setBusy(true);
              setError(null);
              const data = new FormData(e.currentTarget);
              try {
                const result = await supabase.auth.signInWithPassword({
                  email: String(data.get("email")),
                  password: String(data.get("password")),
                });
                if (result.error) throw result.error;
              } catch (err) {
                setError(err);
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
          </form>
          <p className="small muted login-help">
            Using a demo account? Use the credentials shared by your team.
            Access is determined by your account permissions.
          </p>
        </div>
        <footer>One place to connect learning with opportunity.</footer>
      </main>
    </div>
  );
}
