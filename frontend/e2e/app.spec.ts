import { expect, test, type Page } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await mockApi(page);
});

test("nav, training start, leak cards, and study plan render", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("button", { name: "AI Coach" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Leak Finder" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Study Plan" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Settings" })).toBeVisible();

  await page.getByRole("button", { name: "Start" }).click();
  await expect(page.getByText("Training started.")).toBeVisible();

  await page.getByRole("button", { name: "Leak Finder" }).click();
  await expect(page.getByRole("button", { name: /Passive preflop gap/ })).toBeVisible();
  await page.getByRole("button", { name: /Passive preflop gap/ }).click();
  await expect(page.getByText("Hand 101")).toBeVisible();

  await page.getByRole("button", { name: "Study Plan" }).click();
  await expect(page.getByText("Focus areas")).toBeVisible();
  await expect(page.getByText("Write effective stack in bb.")).toBeVisible();
});

test("settings hides full path and mobile has no horizontal overflow", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Settings" }).click();
  await expect(page.getByText("mock.hmdb")).toBeVisible();
  await expect(page.getByText("C:\\Users")).toHaveCount(0);

  const overflow = await page.evaluate(() => document.body.scrollWidth > window.innerWidth + 1);
  expect(overflow).toBe(false);
});

async function mockApi(page: Page) {
  await page.route("**/api/health", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: {
        ai_configured: true,
        ai_enabled: true,
        ai_model: "mock",
        app: "poker-ai-coach",
        hero_name: "hero",
        status: "ok",
        version: "0.1.0",
      },
    });
  });
  await page.route("**/api/database/status", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: {
        configured: true,
        connected: true,
        database_name: "mock.hmdb",
        table_counts: { handhistories: 100 },
        tables: ["handhistories", "players"],
        expected_tables: ["handhistories", "players"],
        missing_tables: [],
        warnings: [],
        error: null,
      },
    });
  });
  await page.route("**/api/training-runs", async (route) => {
    if (route.request().method() === "POST") {
      await route.fulfill({
        contentType: "application/json",
        json: {
          created: true,
          error: null,
          warnings: [],
          training_run: trainingRunDetail,
        },
      });
      return;
    }
    await route.fulfill({
      contentType: "application/json",
      json: { training_runs: [trainingRunSummary] },
    });
  });
  await page.route("**/api/coach/deep-analysis", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: deepJob,
    });
  });
}

const trainingRunSummary = {
  id: 1,
  created_at: "2026-05-24T12:00:00Z",
  database_name: "mock.hmdb",
  hero_name: "hero",
  model: "mock",
  total_hands: 1000,
  max_hand_id: 101,
  latest_valid_month: "202605",
  initial_summary: "Training created for 202605.",
  leak_count: 1,
  study_item_count: 1,
};

const trainingRunDetail = {
  ...trainingRunSummary,
  valid_hand_count: 900,
  invalid_1970_count: 100,
  warnings: [],
  deep_leak_result: null,
  study_plan_result: null,
  leaks: [],
  study_items: [],
};

const deepJob = {
  job_id: "job-1",
  status: "completed",
  mode: "leak_finder_deep",
  training_run_id: null,
  content: "## Main takeaway\nReview passive preflop entries and concrete hands.",
  warnings: [],
  error: null,
  steps: [{ name: "find_stat_leaks", arguments: {}, summary: "Found leaks." }],
  leaks: [
    {
      id: null,
      training_run_id: null,
      leak_key: "passive_preflop_gap",
      title: "Passive preflop gap",
      severity: "high",
      status: "open",
      evidence: "VPIP/PFR gap is 6.0%.",
      coach_read: "Review flats and missed iso raises.",
      sample_size: 1000,
      related_hand_ids: [101],
      confidence: "high",
    },
  ],
  hand_analyses: [
    {
      hand_id: 101,
      tournament_number: "777",
      hand_date: "2026-05-20",
      hero_position: "BTN",
      hero_stack_bb: 24,
      hero_cards_seen: true,
      hero_actions: ["call", "all-in call"],
      pot_size: 12000,
      coach_questions: ["Was call better than raise or fold?"],
      hand_text_excerpt: "Dealt to hero [As Ks] | hero calls | hero calls all-in",
    },
  ],
  study_items: [
    {
      id: null,
      training_run_id: null,
      title: "Passive preflop gap",
      drill: "Review passive preflop hands.",
      checklist: ["Write effective stack in bb.", "Mark position and preflop line."],
      linked_leak_keys: ["passive_preflop_gap"],
      linked_hand_ids: [101],
      status: "new",
    },
  ],
};
