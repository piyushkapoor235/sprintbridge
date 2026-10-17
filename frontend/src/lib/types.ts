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
}
export interface MentorRequest {
  id: string;
  mentor_name: string;
  requester_name: string;
  note: string;
  status: "pending" | "accepted" | "declined";
  created_at: string;
}
