import { Link, useSearchParams } from "react-router-dom";
import { ArrowUpRight, Search, Building2 } from "lucide-react";
import type { Page, Opportunity } from "../lib/types";
import { useQuery } from "../lib/useQuery";
import {
  Heading,
  Badge,
  Tags,
  ErrorMessage,
  Loading,
  Empty,
  Pagination,
  date,
} from "../components/ui";
export function OpportunityRow({ item }: { item: Opportunity }) {
  return (
    <article className="opportunity-row">
      <div className="company-mark">
        <Building2 size={23} />
      </div>
      <div className="opportunity-info">
        <div className="flex flex-wrap gap-2 items-center">
          <span className="small muted">{item.company_name}</span>
          <Badge tone={item.visibility === "campus" ? "blue" : ""}>
            {item.visibility === "campus" ? "Campus" : "Public"}
          </Badge>
        </div>
        <h3>
          <Link to={`/opportunities/${item.id}`}>{item.title}</Link>
        </h3>
        <div className="job-meta">
          <span>{item.type === "internship" ? "Internship" : "Job"}</span>
          <span>
            {item.compensation
              ? `${item.compensation.currency} ${Number(item.compensation.amount).toLocaleString("en-IN")} / ${item.compensation.pay_period.replace("_", " ")}`
              : "Compensation not specified"}
          </span>
          <span>Closes {date(item.deadline)}</span>
        </div>
        <Tags items={item.required_skills} />
      </div>
      <Link
        className="row-arrow"
        to={`/opportunities/${item.id}`}
        aria-label={`View ${item.title}`}
      >
        <ArrowUpRight size={20} />
      </Link>
    </article>
  );
}
export default function Opportunities() {
  const [params, setParams] = useSearchParams();
  const query = new URLSearchParams({
    page: params.get("page") || "1",
    page_size: "10",
    sort: "newest",
  });
  for (const key of ["q", "type", "visibility"])
    if (params.get(key)) query.set(key, params.get(key)!);
  const result = useQuery<Page<Opportunity>>(`/opportunities?${query}`);
  function filter(key: string, value: string) {
    const next = new URLSearchParams(params);
    value ? next.set(key, value) : next.delete(key);
    next.delete("page");
    setParams(next);
  }
  return (
    <>
      <Heading eyebrow="FIND YOUR NEXT STEP" title="Opportunities">
        Find a place to put your skills to work.
      </Heading>
      <form
        className="filters"
        onSubmit={(e) => {
          e.preventDefault();
          filter("q", String(new FormData(e.currentTarget).get("q") || ""));
        }}
      >
        <div className="search-input">
          <Search size={19} />
          <input
            name="q"
            aria-label="Search opportunities"
            placeholder="Search by job title…"
            defaultValue={params.get("q") || ""}
          />
        </div>
        <select
          aria-label="Opportunity type"
          value={params.get("type") || ""}
          onChange={(e) => filter("type", e.target.value)}
        >
          <option value="">All types</option>
          <option value="internship">Internships</option>
          <option value="job">Jobs</option>
        </select>
        <select
          aria-label="Visibility"
          value={params.get("visibility") || ""}
          onChange={(e) => filter("visibility", e.target.value)}
        >
          <option value="">All opportunities</option>
          <option value="public">Public</option>
          <option value="campus">Campus</option>
        </select>
        <button className="primary">Search</button>
      </form>
      <div className="section-heading">
        <p className="muted">
          {result.data?.total != null
            ? `${result.data.total} opportunities`
            : "Explore available listings"}
        </p>
        <span className="small muted">Newest first</span>
      </div>
      <ErrorMessage error={result.error} />
      {result.error && (
        <button className="secondary" onClick={result.reload}>
          Try again
        </button>
      )}
      {result.loading && <Loading />}
      <div className="listing-list">
        {result.data?.items.map((item) => (
          <OpportunityRow item={item} key={item.id} />
        ))}
        {result.data?.items.length === 0 && (
          <Empty title="No opportunities match yet">
            Try a different title or broaden your filters.
          </Empty>
        )}
      </div>
      {result.data && (
        <Pagination
          data={result.data}
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
