import type { ApplicationStatus } from "./types";
export function nextStatuses(status: ApplicationStatus): ApplicationStatus[] {
  return status === "applied"
    ? ["shortlisted", "offered", "rejected"]
    : status === "shortlisted"
      ? ["offered", "rejected"]
      : [];
}
export function safeLink(value: string | null): string | null {
  try {
    const url = new URL(value || "");
    return ["http:", "https:"].includes(url.protocol) ? url.href : null;
  } catch {
    return null;
  }
}
export const skillList = (value: FormDataEntryValue | null) => [
  ...new Set(
    String(value || "")
      .split(",")
      .map((s) => s.trim().toLowerCase())
      .filter(Boolean),
  ),
];
