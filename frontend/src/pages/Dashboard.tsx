import { Link } from "react-router-dom";
import {
  ArrowRight,
  ArrowUpRight,
  BriefcaseBusiness,
  Check,
  FileCheck2,
  Sparkles,
  UserRound,
  UsersRound,
} from "lucide-react";
import { useAuth } from "../auth";
import { useQuery } from "../lib/useQuery";
import type { Page, Opportunity, Application } from "../lib/types";
import { Heading, Badge, ErrorMessage, Loading, Empty } from "../components/ui";
import { OpportunityRow } from "./Opportunities";
import { ROLE_LABEL } from "./Join";
import type { RoleKind } from "../lib/types";

const CAPABILITY: Record<RoleKind, string> = {
  recruiter: "recruiter",
  university_admin: "university_admin",
  mentor: "mentor",
};

export default function Dashboard() {
  const { me, session } = useAuth();
  const joiningAs = session?.user.user_metadata?.joining_as as string | undefined;
  const partner = joiningAs && joiningAs in CAPABILITY ? (joiningAs as RoleKind) : null;
  const needsRole = partner && !me!.capabilities.includes(CAPABILITY[partner] as never);
  const jobs = useQuery<Page<Opportunity>>("/opportunities?page_size=3");
  const applications = useQuery<Page<Application>>(
    "/applications?scope=student&page_size=1",
  );
  return (
    <>
      <Heading
        eyebrow="Let’s move you forward"
        title={`Hello, ${me!.profile.name.split(" ")[0]}.`}
      >
        A little clarity. A little momentum. Your next step starts here.
      </Heading>
      {needsRole && (
        <p className="notice" role="status">
          You signed up as a {ROLE_LABEL[partner].toLowerCase()}.{" "}
          <Link to={`/join?as=${partner}`}>Finish your {ROLE_LABEL[partner].toLowerCase()} application</Link> so an
          operator can verify you and open your workspace. Until then you can explore as a job seeker.
        </p>
      )}
      {joiningAs === "founder" && (
        <p className="notice" role="status">
          Ready to build a team? <Link to="/ventures">Post your venture</Link>: collaborators see only your public
          teaser until they accept your NDA and you accept them.
        </p>
      )}
      <section className="welcome-panel">
        <div>
          <Badge tone="light">Your career, in motion</Badge>
          <h2>
            Turn what you know
            <br />
            into what comes next.
          </h2>
          <p>
            Discover opportunities, understand your skill gaps,
            <br className="desktop-only" /> and connect with people who can
            help.
          </p>
          <Link className="primary" to="/opportunities">
            Explore opportunities <ArrowRight size={18} />
          </Link>
        </div>
        <nav className="path-card" aria-label="Your path">
          <h3>Your path</h3>
          <Link
            className={`path-step ${me!.profile.skills.length ? "done" : ""}`}
            to="/profile"
          >
            <span className="path-icon">
              {me!.profile.skills.length ? <Check size={16} /> : <UserRound size={16} />}
            </span>
            Add your skills
            <span>{me!.profile.skills.length} added</span>
          </Link>
          <Link className="path-step" to="/skills">
            <span className="path-icon">
              <Sparkles size={16} />
            </span>
            Back them with evidence
            <span>Resume</span>
          </Link>
          <Link
            className={`path-step ${applications.data?.total ? "done" : ""}`}
            to="/opportunities"
          >
            <span className="path-icon">
              {applications.data?.total ? <Check size={16} /> : <BriefcaseBusiness size={16} />}
            </span>
            Apply where you fit
            <span>{applications.data?.total ?? "—"} sent</span>
          </Link>
          <Link className="path-step" to="/mentors">
            <span className="path-icon">
              <UsersRound size={16} />
            </span>
            Close a gap with a mentor
            <span>Mentors</span>
          </Link>
        </nav>
      </section>
      <div className="stats-row">
        <Link to="/profile" className="stat">
          <span className="stat-icon">
            <Sparkles size={21} />
          </span>
          <div>
            <span className="stat-value">{me!.profile.skills.length}</span>
            <span className="muted">Self-declared skills</span>
          </div>
          <ArrowUpRight size={18} />
        </Link>
        <Link to="/applications" className="stat">
          <span className="stat-icon">
            <FileCheck2 size={21} />
          </span>
          <div>
            <span className="stat-value">
              {applications.data?.total ?? "—"}
            </span>
            <span className="muted">Applications submitted</span>
          </div>
          <ArrowUpRight size={18} />
        </Link>
        <Link to="/skills" className="stat">
          <span className="stat-icon">
            <BriefcaseBusiness size={21} />
          </span>
          <div>
            <strong>Show your experience</strong>
            <span className="muted">Add evidence to your skills</span>
          </div>
          <ArrowUpRight size={18} />
        </Link>
      </div>
      <ErrorMessage error={applications.error} />
      <div className="dashboard-bottom">
        <section>
          <div className="section-heading">
            <div>
              <h2>Fresh opportunities</h2>
              <p className="muted">The latest openings you can explore.</p>
            </div>
            <Link className="text-link" to="/opportunities">
              View all <ArrowRight size={16} />
            </Link>
          </div>
          <ErrorMessage error={jobs.error} />
          {jobs.loading && <Loading />}
          <div className="listing-list">
            {jobs.data?.items.map((item) => (
              <OpportunityRow key={item.id} item={item} />
            ))}
            {jobs.data?.items.length === 0 && (
              <Empty title="Your next opportunity is on its way">
                Check back as recruiters add new listings.
              </Empty>
            )}
          </div>
        </section>
        <aside className="next-step">
          <span className="eyebrow">Make your next move</span>
          <h2>
            A stronger profile.
            <br />A clearer direction.
          </h2>
          <p className="muted">
            Add your skills and portfolio so you can see where you match and
            where to grow.
          </p>
          <Link className="text-link" to="/profile">
            Update your profile <ArrowUpRight size={17} />
          </Link>
          <hr />
          <span className="eyebrow">Better, together</span>
          <p>Find a mentor for the skill you want to build next.</p>
          <Link className="text-link" to="/mentors">
            Meet your mentors <ArrowUpRight size={17} />
          </Link>
        </aside>
      </div>
    </>
  );
}
