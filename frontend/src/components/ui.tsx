import type { ReactNode } from "react";
import { ArrowLeft, ArrowRight, AlertCircle, Inbox } from "lucide-react";
import type { Page } from "../lib/types";
import { ApiError } from "../lib/http";

export function Heading({
  eyebrow,
  title,
  children,
  action,
}: {
  eyebrow?: string;
  title: string;
  children?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <header className="page-heading">
      <div>
        <p className="eyebrow">{eyebrow || "Your next chapter"}</p>
        <h1>{title}</h1>
        {children && <p className="muted">{children}</p>}
      </div>
      {action}
    </header>
  );
}
export function ErrorMessage({ error }: { error: unknown }) {
  if (!error) return null;
  return (
    <div className="notice error" role="alert">
      <AlertCircle size={19} />
      <div>
        {error instanceof Error
          ? error.message
          : "Something went wrong. Please try again."}
        {error instanceof ApiError && (
          <>
            <ul>
              {Object.entries(error.fields).map(([key, value]) => (
                <li key={key}>
                  {key.replaceAll("_", " ")}: {value}
                </li>
              ))}
            </ul>
            {error.requestId && <small>Reference: {error.requestId}</small>}
          </>
        )}
      </div>
    </div>
  );
}
export function Empty({
  title = "Nothing here yet",
  children,
}: {
  title?: string;
  children?: ReactNode;
}) {
  return (
    <div className="empty">
      <Inbox size={30} />
      <h2>{title}</h2>
      <p className="muted">{children}</p>
    </div>
  );
}
export function Loading() {
  return (
    <div className="loading" role="status">
      <span />
      Loading your workspace…
    </div>
  );
}
export function Badge({
  children,
  tone = "",
}: {
  children: ReactNode;
  tone?: string;
}) {
  // Sentence case: capitalize only the first letter of plain-text badges ("offered" -> "Offered").
  const content =
    typeof children === "string" && children
      ? children[0].toUpperCase() + children.slice(1).replaceAll("_", " ")
      : children;
  return <span className={`badge ${tone}`}>{content}</span>;
}
export function Tags({ items }: { items: string[] }) {
  return (
    <div className="tags">
      {items.map((item) => (
        <span key={item} className="tag">
          {item}
        </span>
      ))}
    </div>
  );
}
export function Pagination({
  data,
  onPage,
}: {
  data: Page<unknown>;
  onPage: (p: number) => void;
}) {
  const more =
    data.total === null
      ? data.items.length === data.page_size
      : data.page * data.page_size < data.total;
  return (
    <div className="pagination">
      <span>
        Page {data.page}
        {data.total !== null ? ` · ${data.total} results` : ""}
      </span>
      <div className="flex gap-2">
        <button
          className="secondary"
          disabled={data.page <= 1}
          onClick={() => onPage(data.page - 1)}
          aria-label="Previous page"
        >
          <ArrowLeft size={16} />
        </button>
        <button
          className="secondary"
          disabled={!more}
          onClick={() => onPage(data.page + 1)}
          aria-label="Next page"
        >
          <ArrowRight size={16} />
        </button>
      </div>
    </div>
  );
}
export function date(value: string) {
  return new Intl.DateTimeFormat("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(new Date(value));
}
export function inr(value: number) {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(value);
}
/** A clearly labelled simulated payment step: no real money ever moves. */
export function TestPaymentNote({ amount, what }: { amount: number; what: string }) {
  return (
    <p className="notice test-pay" role="note">
      <strong>Test mode</strong>
      <span>
        {what} costs {inr(amount)}. Confirming records a simulated payment — no card is charged.
      </span>
    </p>
  );
}
