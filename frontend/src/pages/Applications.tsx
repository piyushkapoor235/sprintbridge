import { Link, useSearchParams } from "react-router-dom";
import { useQuery } from "../lib/useQuery";
import type { Application, Page } from "../lib/types";
import {
  Heading,
  Badge,
  Loading,
  ErrorMessage,
  Empty,
  Pagination,
  date,
} from "../components/ui";
export default function Applications() {
  const [params, setParams] = useSearchParams();
  const page = params.get("page") || "1";
  const result = useQuery<Page<Application>>(
    `/applications?scope=student&page=${page}&page_size=10`,
  );
  return (
    <>
      <Heading eyebrow="Every step counts" title="My applications">
        One place to follow your next chapter.
      </Heading>
      <div className="status-legend">
        <span>Applied</span>
        <span>→</span>
        <span>Shortlisted</span>
        <span>→</span>
        <span>Offered</span>
        <small className="muted">
          Recruiters may also decline an application.
        </small>
      </div>
      <ErrorMessage error={result.error} />
      <button className="secondary" onClick={result.reload}>
        Refresh status
      </button>
      {result.loading && <Loading />}
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Opportunity</th>
              <th>Applied</th>
              <th>Route</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {result.data?.items.map((item) => (
              <tr key={item.id}>
                <td>
                  <Link to={`/opportunities/${item.opportunity_id}`}>
                    {item.title}
                  </Link>
                </td>
                <td>{date(item.created_at)}</td>
                <td>{item.drive_id ? "Campus drive" : "Public"}</td>
                <td>
                  <Badge
                    tone={
                      item.status === "offered"
                        ? "green"
                        : item.status === "shortlisted"
                          ? "blue"
                          : ""
                    }
                  >
                    {item.status}
                  </Badge>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {result.data?.items.length === 0 && (
        <Empty title="Your journey starts with an application">
          <Link to="/opportunities">Explore opportunities</Link> and find your
          next step.
        </Empty>
      )}
      {result.data && (
        <Pagination
          data={result.data}
          onPage={(page) => setParams({ page: String(page) })}
        />
      )}
    </>
  );
}
