import { useEffect, useState } from "react";
import {
  Link,
  NavLink,
  Navigate,
  Outlet,
  Route,
  Routes,
  useLocation,
} from "react-router-dom";
import {
  LayoutDashboard,
  BriefcaseBusiness,
  FileCheck2,
  UserRound,
  Sparkles,
  UsersRound,
  Layers3,
  LogOut,
  ArrowUpRight,
  Menu,
  X,
  Building2,
  FileSearch,
  GraduationCap,
  Rocket,
  CreditCard,
  ShieldCheck,
  ShieldAlert,
} from "lucide-react";
import { useAuth } from "./auth";
import { ErrorMessage, Loading } from "./components/ui";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Profile from "./pages/Profile";
import Opportunities from "./pages/Opportunities";
import OpportunityDetail from "./pages/OpportunityDetail";
import Applications from "./pages/Applications";
import Recruiter from "./pages/Recruiter";
import Skills from "./pages/Skills";
import JobFit from "./pages/JobFit";
import Mentors from "./pages/Mentors";
import University from "./pages/University";
import Ventures, { VentureDetail } from "./pages/Ventures";
import Billing from "./pages/Billing";
import Verify from "./pages/Verify";
import Operator from "./pages/Operator";

function Layout() {
  const {
    session,
    me,
    loading,
    error,
    workspace,
    setWorkspace,
    reload,
    signOut,
  } = useAuth();
  const [open, setOpen] = useState(false);
  const [logoutError, setLogoutError] = useState<unknown>();
  const location = useLocation();
  useEffect(() => {
    setOpen(false);
    document.querySelector<HTMLElement>("main")?.focus();
  }, [location.pathname]);
  if (loading && !me) return <Loading />;
  if (!session) return <Navigate to="/login" replace />;
  if (!me)
    return (
      <main className="connection-state">
        <h1>Let’s reconnect your workspace</h1>
        <ErrorMessage error={error} />
        <button className="primary" onClick={reload}>
          Try again
        </button>
        <button
          className="secondary"
          onClick={() => signOut().catch(setLogoutError)}
        >
          Sign out
        </button>
        <ErrorMessage error={logoutError} />
      </main>
    );
  const nav = [
    ["/dashboard", "Overview", LayoutDashboard],
    ["/opportunities", "Opportunities", BriefcaseBusiness],
    ["/applications", "My applications", FileCheck2],
    ["/profile", "My profile", UserRound],
    ["/skills", "Skill evidence", Sparkles],
    ["/job-fit", "Explore job fit", FileSearch],
    ["/mentors", "Mentorship", UsersRound],
    ["/ventures", "Ventures", Rocket],
    ["/billing", "Plans & billing", CreditCard],
  ] as const;
  return (
    <div className="app">
      <a className="skip-link" href="#content">
        Skip to content
      </a>
      <button
        className="mobile-toggle secondary"
        aria-label={open ? "Close navigation" : "Open navigation"}
        aria-expanded={open}
        onClick={() => setOpen(!open)}
      >
        {open ? <X /> : <Menu />}
      </button>
      <aside className={`sidebar ${open ? "is-open" : ""}`}>
        <Link className="brand" to="/dashboard">
          <Layers3 />
          <span>
            SprintBridge<span className="brand-dot">.</span>
          </span>
        </Link>
        <p className="nav-caption">Your workspace</p>
        <nav aria-label="Main navigation">
          {nav.map(([to, label, Icon]) => (
            <NavLink key={to} to={to}>
              <Icon size={19} />
              {label}
            </NavLink>
          ))}
          {me.capabilities.includes("recruiter") && (
            <NavLink to="/recruiter">
              <Building2 size={19} />
              Recruiter workspace
            </NavLink>
          )}
          {me.capabilities.includes("mentor") && (
            <NavLink to="/verify">
              <ShieldCheck size={19} />
              Verifier desk
            </NavLink>
          )}
          {me.capabilities.includes("operator") && (
            <NavLink to="/operator">
              <ShieldAlert size={19} />
              Operator console
            </NavLink>
          )}
          {me.capabilities.includes("university_admin") && (
            <NavLink to="/university">
              <GraduationCap size={19} />
              University workspace
            </NavLink>
          )}
        </nav>
        <div className="sidebar-note">
          <span className="small">A little progress, every day</span>
          <p>Your next opportunity starts with what you know.</p>
          <Link to="/profile">
            Build your profile <ArrowUpRight size={16} />
          </Link>
        </div>
        <div className="sidebar-user">
          <span className="avatar">
            {me.profile.name.slice(0, 1).toUpperCase()}
          </span>
          <div>
            <strong>{me.profile.name}</strong>
            <small>{me.email}</small>
          </div>
          <button
            className="icon-button"
            title="Sign out"
            aria-label="Sign out"
            onClick={() => signOut().catch(setLogoutError)}
          >
            <LogOut size={18} />
          </button>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <span className="breadcrumb">
            Your workspace <span>/</span>{" "}
            <strong>
              {nav.find(([path]) => location.pathname.startsWith(path))?.[1] ||
                ({ "/university": "University", "/verify": "Verifier desk", "/operator": "Operator console" } as Record<string, string>)[
                  location.pathname
                ] ||
                "Recruiting"}
            </strong>
          </span>
          <div className="flex items-center gap-3">
            {me.workspaces.length > 0 && (
              <select
                aria-label="Active organization"
                value={workspace}
                onChange={(e) => setWorkspace(e.target.value)}
              >
                {me.workspaces.map((w) => (
                  <option
                    key={`${w.organization_id}-${w.role}`}
                    value={w.organization_id}
                  >
                    {w.name}
                  </option>
                ))}
              </select>
            )}
            <span className="avatar small-avatar">
              {me.profile.name.slice(0, 1).toUpperCase()}
            </span>
          </div>
        </header>
        <main id="content" tabIndex={-1} key={`${me.user_id}:${workspace}`}>
          <ErrorMessage error={logoutError} />
          <Outlet />
        </main>
        <footer className="app-footer">
          SprintBridge <span>Built for your next chapter.</span>
        </footer>
      </div>
    </div>
  );
}
export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<Layout />}>
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<Dashboard />} />
        <Route path="profile" element={<Profile />} />
        <Route path="opportunities" element={<Opportunities />} />
        <Route path="opportunities/:id" element={<OpportunityDetail />} />
        <Route path="applications" element={<Applications />} />
        <Route path="recruiter" element={<Recruiter />} />
        <Route path="university" element={<University />} />
        <Route path="ventures" element={<Ventures />} />
        <Route path="ventures/:id" element={<VentureDetail />} />
        <Route path="billing" element={<Billing />} />
        <Route path="verify" element={<Verify />} />
        <Route path="operator" element={<Operator />} />
        <Route path="skills" element={<Skills />} />
        <Route path="job-fit" element={<JobFit />} />
        <Route path="mentors" element={<Mentors />} />
        <Route path="mentor-requests" element={<Mentors inbox />} />
        <Route
          path="*"
          element={
            <div className="empty">
              <h1>Page not found</h1>
              <Link to="/dashboard">Back to your overview</Link>
            </div>
          }
        />
      </Route>
    </Routes>
  );
}
