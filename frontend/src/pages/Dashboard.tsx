import { Link } from "react-router-dom";
import {
  ArrowRight,
  ArrowUpRight,
  BriefcaseBusiness,
  FileCheck2,
  Sparkles,
} from "lucide-react";
import { useAuth } from "../auth";
import { useQuery } from "../lib/useQuery";
import type { Page, Opportunity, Application } from "../lib/types";
import { Heading, Badge, ErrorMessage, Loading, Empty } from "../components/ui";
import { OpportunityRow } from "./Opportunities";
export default function Dashboard() {
  const { me } = useAuth();
  const jobs = useQuery<Page<Opportunity>>("/opportunities?page_size=3");
  const applications = useQuery<Page<Application>>(
    "/applications?scope=student&page_size=1",
  );
  return (
    <>
      <Heading
        eyebrow="LET’S MOVE YOU FORWARD"
        title={`Hello, ${me!.profile.name.split(" ")[0]}.`}
      >
        A little clarity. A little momentum. Your next step starts here.
      </Heading>
      <section className="welcome-panel">
        <div>
          <Badge tone="light">YOUR CAREER, IN MOTION</Badge>
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
        <div className="bridge-art" aria-hidden="true">
          <div className="orbit orbit-one" />
          <div className="orbit orbit-two" />
          <div className="art-tile tile-one">
            <Sparkles />
            <span>Your skills</span>
          </div>
          <div className="art-tile tile-two">
            <BriefcaseBusiness />
            <span>New possibilities</span>
          </div>
          <div className="bridge-line" />
          <span className="art-dot" />
        </div>
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
          <span className="eyebrow">MAKE YOUR NEXT MOVE</span>
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
          <span className="eyebrow">BETTER, TOGETHER</span>
          <p>Find a mentor for the skill you want to build next.</p>
          <Link className="text-link" to="/mentors">
            Meet your mentors <ArrowUpRight size={17} />
          </Link>
        </aside>
      </div>
    </>
  );
}
