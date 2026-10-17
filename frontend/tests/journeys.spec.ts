import { test, expect, type Page } from "@playwright/test";
const user = {
  id: "student-1",
  aud: "authenticated",
  role: "authenticated",
  email: "student@example.test",
  app_metadata: {},
  user_metadata: {},
  created_at: "2026-01-01T00:00:00Z",
};
const profile = {
  name: "Asha Rao",
  specialization: "Frontend development",
  education_summary: "B.Tech Computer Science, 2027",
  skills: ["react", "typescript"],
  portfolio_url: null,
  is_public: true,
};
const job = {
  id: "job-1",
  company_id: "company-1",
  company_name: "Acme Analytics",
  title: "Frontend Engineering Intern",
  description:
    "Build accessible experiences with a thoughtful engineering team.",
  type: "internship",
  visibility: "public",
  required_skills: ["react", "typescript", "docker"],
  compensation: { amount: "25000", currency: "INR", pay_period: "month" },
  deadline: "2099-12-31T00:00:00Z",
  status: "open",
  skill_coverage: {
    matched_count: 2,
    required_count: 3,
    matching_skills: ["react", "typescript"],
    missing_skills: ["docker"],
    coverage_percent: 67,
  },
};
const envelope = (items: unknown[], page = 1) => ({
  items,
  page,
  page_size: 10,
  total: items.length,
});
async function setup(page: Page, recruiter = false, campus = false) {
  let applied = false;
  let status = "applied";
  let savedProfile = { ...profile };
  let postedDrive: string | null = null;
  const errors: string[] = [];
  page.on("pageerror", (err) => errors.push(err.message));
  await page.addInitScript(
    ({ user }) => {
      localStorage.setItem(
        "sb-sprintbridge-test-auth-token",
        JSON.stringify({
          access_token: "test-token",
          refresh_token: "test-refresh",
          token_type: "bearer",
          expires_at: Math.floor(Date.now() / 1000) + 3600,
          user,
        }),
      );
    },
    { user },
  );
  await page.route("https://sprintbridge-test.supabase.co/**", (route) =>
    route.fulfill({ json: user }),
  );
  await page.route("http://127.0.0.1:8000/api/**", async (route) => {
    const req = route.request();
    const url = new URL(req.url());
    const path = url.pathname.replace("/api", "");
    if (req.method() === "OPTIONS")
      return route.fulfill({
        status: 204,
        headers: {
          "Access-Control-Allow-Origin": "*",
          "Access-Control-Allow-Headers": "*",
          "Access-Control-Allow-Methods": "*",
        },
      });
    const reply = (body: unknown, status = 200) =>
      route.fulfill({
        status,
        json: body,
        headers: { "Access-Control-Allow-Origin": "*" },
      });
    if (path === "/me") {
      if (req.method() === "PATCH")
        savedProfile = { ...savedProfile, ...req.postDataJSON() };
      return reply({
        user_id: user.id,
        email: user.email,
        profile: savedProfile,
        capabilities: recruiter ? ["student", "recruiter"] : ["student"],
        workspaces: recruiter
          ? [
              {
                organization_id: "company-1",
                name: "Acme Analytics",
                type: "company",
                role: "recruiter",
              },
              {
                organization_id: "company-2",
                name: "Second Company",
                type: "company",
                role: "recruiter",
              },
            ]
          : [],
      });
    }
    if (path === "/opportunities") return reply(envelope([job]));
    if (path === "/opportunities/job-1")
      return reply({ ...job, visibility: campus ? "campus" : "public" });
    if (path === "/university/drives")
      return reply(
        envelope(
          campus
            ? [
                {
                  id: "drive-1",
                  opportunity_id: "job-1",
                  university_name: "Sample University",
                  batch: 2027,
                },
              ]
            : [],
        ),
      );
    if (path === "/drives/drive-1/eligibility")
      return reply({
        drive_id: "drive-1",
        eligible: true,
        reasons: [],
        matching_skills: ["react"],
        missing_skills: [],
        rules_version: 1,
      });
    if (path === "/opportunities/job-1/applications") {
      applied = true;
      postedDrive = req.postDataJSON().drive_id;
      return reply({ id: "app-1" }, 201);
    }
    if (path === "/applications/app-1") {
      status = req.postDataJSON().status;
      return reply({ id: "app-1", status });
    }
    if (path === "/applications") {
      if (url.searchParams.get("workspace_id") === "company-2")
        return reply(envelope([]));
      return reply(
        envelope(
          applied || recruiter
            ? [
                {
                  id: "app-1",
                  opportunity_id: "job-1",
                  title: job.title,
                  status,
                  drive_id: postedDrive,
                  created_at: "2026-10-18T12:00:00Z",
                  profile_snapshot: savedProfile,
                },
              ]
            : [],
        ),
      );
    }
    if (path === "/me/skills")
      return reply({ resume_status: "none", items: [] });
    if (path === "/me/resume" || path === "/jds")
      return reply(
        {
          code: "SERVICE_UNAVAILABLE",
          detail: "Analysis is temporarily unavailable.",
          field_errors: {},
          request_id: "test-request",
        },
        503,
      );
    if (path === "/mentors" || path === "/mentor-requests")
      return reply(envelope([]));
    return reply(
      { code: "NOT_FOUND", detail: "Test route not configured" },
      404,
    );
  });
  return { errors, drive: () => postedDrive };
}

test("student edits profile, applies once, and sees a persisted tracker", async ({
  page,
}) => {
  const state = await setup(page);
  await page.goto("/profile");
  await page.getByLabel("Full name").fill("Asha Updated");
  await page.getByRole("button", { name: "Save profile" }).click();
  await expect(page.getByRole("status")).toContainText("saved");
  await page.reload();
  await expect(page.getByLabel("Full name")).toHaveValue("Asha Updated");
  await page.getByRole("link", { name: "Opportunities", exact: true }).click();
  await page.getByRole("link", { name: job.title, exact: true }).click();
  await expect(page.getByText("67%")).toBeVisible();
  await page
    .getByRole("button", { name: "Apply for this opportunity" })
    .click();
  await expect(page.getByRole("status")).toContainText("Application received");
  await page.reload();
  await expect(
    page.getByRole("button", { name: "Apply for this opportunity" }),
  ).toHaveCount(0);
  await page
    .getByRole("link", { name: "My applications", exact: true })
    .click();
  await expect(
    page.getByRole("cell", { name: "applied", exact: true }),
  ).toBeVisible();
  expect(state.errors).toEqual([]);
});
test("campus apply requires an authorized drive and sends it", async ({
  page,
}) => {
  const state = await setup(page, false, true);
  await page.goto("/opportunities/job-1");
  await expect(
    page.getByRole("button", { name: "Apply for this opportunity" }),
  ).toBeDisabled();
  await page.getByLabel("Application route").selectOption("drive-1");
  await expect(
    page.getByText("Eligible for this drive", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Apply for this opportunity" })
    .click();
  await expect(page.getByRole("status")).toContainText("Application received");
  expect(state.drive()).toBe("drive-1");
});
test("recruiter status changes persist and organization changes clear applicants", async ({
  page,
}) => {
  await setup(page, true);
  await page.goto("/recruiter");
  await page.getByRole("button", { name: "Applicants", exact: true }).click();
  await page.getByRole("button", { name: "Shortlist", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Shortlist", exact: true }),
  ).toHaveCount(0);
  await expect(page.getByText("shortlisted", { exact: true })).toBeVisible();
  await page.getByLabel("Active organization").selectOption("company-2");
  await page.getByRole("button", { name: "Applicants", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "No applications yet" }),
  ).toBeVisible();
  await expect(page.getByRole("heading", { name: "Asha Rao" })).toHaveCount(0);
});
test("skill-gap navigation uses a filter and shows an honest empty result", async ({
  page,
}) => {
  await setup(page);
  await page.goto("/opportunities/job-1");
  await page.getByRole("link", { name: "Find a mentor", exact: true }).click();
  await expect(page).toHaveURL(/skill=docker/);
  await expect(
    page.getByRole("heading", { name: "No matching mentors yet" }),
  ).toBeVisible();
});
test("analysis outage keeps manual profile editing available", async ({
  page,
}) => {
  await setup(page);
  await page.goto("/job-fit");
  await page
    .getByLabel("Job description", { exact: true })
    .fill("Build applications with React");
  await page.getByRole("button", { name: "Analyze my fit" }).click();
  await expect(page.getByRole("alert")).toContainText(
    "temporarily unavailable",
  );
  await page.getByRole("link", { name: "My profile", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Save profile" }),
  ).toBeEnabled();
});
test("overview has no overflow at mobile/tablet/desktop and no runtime errors", async ({
  page,
}) => {
  const state = await setup(page);
  await page.goto("/dashboard");
  await expect(
    page.getByRole("heading", { name: "Hello, Asha." }),
  ).toBeVisible();
  for (const width of [320, 768, 1024, 1440]) {
    await page.setViewportSize({ width, height: 960 });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
  }
  await page.screenshot({
    path: "test-results/overview-desktop.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({
    path: "test-results/overview-mobile.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Open navigation" }).click();
  await page.getByRole("link", { name: "My profile", exact: true }).click();
  await expect(page.getByLabel("Full name")).toBeVisible();
  expect(state.errors).toEqual([]);
});
test("signed-out user sees login and protected deep links do not reveal data", async ({
  page,
}) => {
  await page.goto("/recruiter");
  await expect(
    page.getByRole("button", { name: "Sign in", exact: true }),
  ).toBeVisible();
  await expect(page.getByLabel("Password")).toHaveAttribute("type", "password");
  await page.screenshot({ path: "test-results/login.png", fullPage: true });
});

test("ineligible campus drive cannot be overridden by skill coverage", async ({
  page,
}) => {
  await setup(page, false, true);
  await page.route("**/api/drives/drive-1/eligibility", (route) =>
    route.fulfill({
      json: {
        drive_id: "drive-1",
        eligible: false,
        reasons: [
          {
            code: "CGPA_BELOW_MINIMUM",
            message: "The minimum CGPA is not met.",
          },
        ],
        matching_skills: [],
        missing_skills: [],
        rules_version: 1,
      },
    }),
  );
  await page.goto("/opportunities/job-1?drive_id=drive-1");
  await expect(page.getByText("The minimum CGPA is not met.")).toBeVisible();
  await expect(page.getByText("67%")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Apply for this opportunity" }),
  ).toBeDisabled();
  await page.screenshot({
    path: "test-results/campus-detail.png",
    fullPage: true,
  });
});

test("uncertain application failure is not automatically replayed", async ({
  page,
}) => {
  await setup(page);
  let submissions = 0;
  await page.route("**/api/opportunities/job-1/applications", (route) => {
    submissions++;
    return route.abort("failed");
  });
  await page.goto("/opportunities/job-1");
  await page
    .getByRole("button", { name: "Apply for this opportunity" })
    .click();
  await expect(
    page.getByText("The outcome is uncertain.", { exact: false }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Apply for this opportunity" }),
  ).toBeDisabled();
  expect(submissions).toBe(1);
});

test("recruiter create form sends the company and API compensation contract", async ({
  page,
}) => {
  await setup(page, true);
  let payload: Record<string, unknown> | undefined;
  await page.route("**/api/opportunities", async (route) => {
    if (route.request().method() !== "POST") return route.fallback();
    payload = route.request().postDataJSON();
    return route.fulfill({ status: 201, json: job });
  });
  await page.goto("/recruiter");
  await page
    .getByRole("button", { name: "Create opportunity", exact: true })
    .click();
  await page
    .getByLabel("Title", { exact: true })
    .fill("Frontend Engineering Intern");
  await page.getByLabel("Application deadline").fill("2099-12-31T18:00");
  await page.getByLabel("Required skills").fill("React, TypeScript");
  await page.getByLabel("Compensation (optional)").fill("25000");
  await page
    .getByRole("button", { name: "Create opportunity", exact: true })
    .last()
    .click();
  await expect(page.getByRole("status").filter({ hasText: "Opportunity created" })).toBeVisible();
  expect(payload).toMatchObject({
    company_id: "company-1",
    compensation_amount: "25000",
    currency: "INR",
    pay_period: "month",
    required_skills: ["react", "typescript"],
  });
  expect(String(payload?.deadline)).toMatch(/Z$/);
});

test("login submits credentials through Supabase and logout clears private views", async ({
  page,
}) => {
  await setup(page);
  await page.addInitScript(() => localStorage.clear());
  await page.route(
    "https://sprintbridge-test.supabase.co/auth/v1/token**",
    async (route) => {
      expect(route.request().postDataJSON()).toMatchObject({
        email: "student@example.test",
        password: "test-password",
      });
      await route.fulfill({
        json: {
          access_token: "test-token",
          refresh_token: "test-refresh",
          token_type: "bearer",
          expires_in: 3600,
          user,
        },
      });
    },
  );
  await page.goto("/login");
  await page.getByLabel("Email address").fill("student@example.test");
  await page.getByLabel("Password", { exact: true }).fill("test-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Hello, Asha." }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Sign in", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("student@example.test", { exact: true }),
  ).toHaveCount(0);
});
