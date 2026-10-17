export interface Page<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number | null;
}
export interface Profile {
  name: string;
  specialization: string | null;
  education_summary: string | null;
  skills: string[];
  portfolio_url: string | null;
  is_public: boolean;
}
export interface Workspace {
  organization_id: string;
  name: string;
  type: "company" | "university";
  role: "admin" | "recruiter";
}
export interface Me {
  user_id: string;
  email: string | null;
  profile: Profile;
  capabilities: string[];
  workspaces: Workspace[];
}
export interface Opportunity {
  id: string;
  company_id: string;
  company_name: string;
  title: string;
  description: string;
  type: "job" | "internship";
  visibility: "public" | "campus";
  required_skills: string[];
  compensation: {
    amount: string | number;
    currency: string;
    pay_period: string;
  } | null;
  deadline: string;
  status: "open" | "closed";
  red_flags?: string[];
  moderation_status?: string;
  skill_coverage: {
    matched_count: number;
    required_count: number;
    matching_skills: string[];
    missing_skills: string[];
    coverage_percent: number | null;
  } | null;
}
export type ApplicationStatus =
  "applied" | "shortlisted" | "offered" | "rejected";
export interface Application {
  id: string;
  opportunity_id: string;
  title: string;
  status: ApplicationStatus;
  created_at: string;
  drive_id: string | null;
  profile_snapshot: Profile | null;
}
export interface Drive {
  id: string;
  university_id: string;
  university_name: string;
  opportunity_id: string;
  opportunity_title: string;
  deadline: string;
  batch: number;
  min_cgpa: string | null;
  allowed_branches?: string[];
  required_skills?: string[];
  rules_version?: number;
}
export interface RosterRow {
  id: string;
  student_id: string;
  name: string;
  email: string;
  branch: string;
  batch: number;
  cgpa: string | null;
  linked: boolean;
  label: string;
}
export interface RosterPreview {
  total_rows: number;
  valid_rows: Omit<RosterRow, "id" | "linked" | "label">[];
  errors: { row: number; field: string | null; message: string }[];
}
export interface RosterCommit {
  inserted: number;
  updated: number;
  unchanged: number;
}
export interface UniversityReport {
  applications: number;
  shortlisted: number;
  offered: number;
  students_with_offers: number;
}
export interface Eligibility {
  drive_id: string;
  eligible: boolean;
  reasons: { code: string; message: string }[];
  matching_skills: string[];
  missing_skills: string[];
  rules_version: number;
}
export interface UserSkill {
  skill: string;
  label: string;
  level: number | null;
  evidence_score: number | null;
  verified_until?: string | null;
  evidence: {
    id: string;
    source: string;
    context_type: string;
    quote: string | null;
    points: number;
  }[];
}
export interface Skills {
  resume_status: string;
  items: UserSkill[];
}
export interface Fit {
  fit_percent: number | null;
  required_met: number;
  required_total: number;
  items: {
    skill: string;
    kind: string;
    min_level: number;
    user_level: number | null;
    bucket: string;
    jd_quote: string | null;
    label: string | null;
  }[];
}
export interface Mentor {
  id: string;
  user_id: string;
  name: string;
  niche: string;
  experience_summary: string;
  skills: string[];
  match_reason: string | null;
  mentor_verified?: boolean;
  expertise?: { skill: string; level: number }[];
  session_price_inr?: number | null;
}
export interface MentorRequest {
  id: string;
  mentor_name: string;
  requester_name: string;
  note: string;
  status: "pending" | "accepted" | "declined";
  session_status?: "pending" | "completed" | "disputed";
  price_inr?: number | null;
  payment_status?: string | null;
  created_at: string;
}
export interface Venture {
  id: string;
  founder_id: string;
  founder_name: string;
  title: string;
  teaser: string;
  problem: string | null;
  industry: string;
  stage: string;
  needed_skills: string[];
  compensation_type: string;
  accepted_collaborators: number;
  is_founder: boolean;
  my_request_status: string | null;
  created_at: string;
}
export interface CollaborationRequest {
  id: string;
  venture_id: string;
  venture_title: string;
  requester_name: string;
  note: string;
  status: "pending" | "accepted" | "declined";
  created_at: string;
}
export interface Plan {
  code: string;
  audience: string;
  name: string;
  price_inr: number;
  period: string;
  limits: Record<string, number>;
  features: string[];
}
export interface Billing {
  seeker_audience: string;
  plans: Record<string, string>;
  organizations: { organization_id: string; name: string; role: string; audience: string; plan: string }[];
  usage: Record<string, { used: number; limit: number | null }>;
  payments: { id: string; purpose: string; amount_inr: number; status: string; created_at: string }[];
  payouts: {
    id: string;
    source: string;
    gross_inr: number;
    commission_inr: number;
    net_inr: number;
    status: string;
    release_after: string;
  }[];
}
export interface Verification {
  id: string;
  skill: string;
  level_requested: number;
  status: string;
  created_at: string;
  session_started_at: string | null;
  decided_at: string | null;
  result_level: number | null;
  notes: string | null;
  expires_at: string | null;
  fee_inr: number | null;
  retry_after: string | null;
  verifier: { name: string; niche: string } | null;
}
export interface VerifierQueue {
  expertise: { skill: string; level: number }[];
  quality_score: number | null;
  assignments: {
    id: string;
    skill: string;
    level_requested: number;
    status: string;
    candidate_name: string;
    created_at: string;
    session_started_at: string | null;
    result_level: number | null;
  }[];
  audits: { id: string; skill: string; level_requested: number; candidate_name: string; decided_at: string | null }[];
}
export interface OperatorQueue {
  reports: {
    target_type: string;
    target_id: string;
    title: string;
    moderation_status: string | null;
    red_flags: string[] | null;
    open_reports: number;
    reasons: string[];
    details: string[] | null;
  }[];
  flagged: { id: string; title: string; company: string; red_flags: string[]; moderation_status: string }[];
  payouts: { id: string; source: string; net_inr: number; status: string; release_after: string; mentor: string }[];
  audit: { id: number; action: string; target_type: string; created_at: string; actor: string; details: Record<string, unknown> }[];
}
