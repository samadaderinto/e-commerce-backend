import { expect, test, type Page } from "@playwright/test";

async function mockWorkspace(
  page: Page,
  admin = false,
  enrolled = true,
): Promise<void> {
  await page.route("**/api/**", async (route) => {
    const path: string = new URL(route.request().url()).pathname.replace(
      /\/$/,
      "",
    );
    let json: unknown = {};
    if (path === "/api/me") {
      json = {
        id: 7,
        first_name: "Referral",
        last_name: "Member",
        email: "affiliate@test.com",
        is_staff: admin,
      };
    } else if (path === "/api/affiliates/register") {
      expect(route.request().postDataJSON()).toEqual({ name: "New affiliate" });
      enrolled = true;
      json = { id: 1 };
    } else if (path === "/api/affiliates/workspace") {
      const status: string | null = new URL(
        route.request().url(),
      ).searchParams.get("status");
      json = {
        enrolled,
        name: "Referral Member",
        referral_code: "INVITE123",
        invite_url: "http://127.0.0.1:3000/register?ref=INVITE123",
        reward_amount: "25.00",
        max_rewards: 4,
        rewarded_count: 4,
        credit_earned: "100.00",
        count: status === "pending" ? 0 : 1,
        results:
          status === "pending"
            ? []
            : [
                {
                  id: 1,
                  status: "rewarded",
                  reward_amount: "25.00",
                  created: "2026-10-11T08:00:00Z",
                },
              ],
      };
    } else if (path === "/api/admin/affiliates") {
      json = {
        count: 1,
        results: [
          {
            id: 1,
            user: 42,
            name: "Affiliate Member",
            email: "member@test.com",
            marketer_id: "INVITE123",
            is_active: true,
            referral_count: 5,
            rewarded_count: 4,
            credit_earned: "100.00",
            created: "2026-10-11T08:00:00Z",
          },
        ],
      };
    } else if (path === "/api/stores") json = { count: 0, results: [] };
    else if (path.includes("notifications"))
      json = { unread: 0, total: 0, results: [] };
    else if (path === "/api/cart") json = { items: [], total: "0.00" };
    else if (path === "/api/wishlist") json = [];
    await route.fulfill({ json });
  });
}

test("referral workspace shows capped store credit and filters across themes", async ({
  page,
}, testInfo) => {
  await mockWorkspace(page);
  await page.goto("/account/affiliates");
  await expect(
    page.getByRole("heading", { name: "Affiliates & referrals" }),
  ).toBeVisible();
  await expect(page.getByText("4 / 4", { exact: true })).toBeVisible();
  await expect(page.getByText("$100.00", { exact: true })).toBeVisible();
  await expect(page.getByLabel("Share this link")).toHaveValue(
    /register\?ref=INVITE123/,
  );
  await page.getByLabel("referrals: Reward status").selectOption("pending");
  await expect(page.getByText(/No results match these filters/)).toBeVisible();
  await page.getByRole("button", { name: "Reset filters" }).click();
  await expect(
    page.getByRole("cell", { name: "#1", exact: true }),
  ).toBeVisible();
  for (const theme of ["light", "dark"]) {
    await page.evaluate(
      (value) => (document.documentElement.dataset.theme = value),
      theme,
    );
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth + 2,
      ),
    ).toBe(true);
    await page.screenshot({
      path: testInfo.outputPath(`referrals-${theme}.png`),
      fullPage: true,
    });
  }
});

test("unenrolled customer can join the existing referral program", async ({
  page,
}) => {
  await mockWorkspace(page, false, false);
  await page.goto("/account/affiliates");
  await page.getByLabel("Affiliate display name").fill("New affiliate");
  await page.getByRole("button", { name: "Join referral program" }).click();
  await expect(
    page.getByRole("heading", { name: "Your invite link" }),
  ).toBeVisible();
});

test("backoffice sees referral totals and existing account management", async ({
  page,
}, testInfo) => {
  await mockWorkspace(page, true);
  await page.goto("/admin/affiliates");
  await expect(
    page.getByRole("heading", { name: "Affiliate referrals", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Affiliate Member" }),
  ).toHaveAttribute("href", "/admin/users/42");
  await expect(
    page.getByRole("cell", { name: "5 / 4", exact: true }),
  ).toBeVisible();
  for (const theme of ["light", "dark"]) {
    await page.evaluate(
      (value) => (document.documentElement.dataset.theme = value),
      theme,
    );
    await page.screenshot({
      path: testInfo.outputPath(`affiliate-admin-${theme}.png`),
      fullPage: true,
    });
  }
});

test("invite registration displays the referral code", async ({ page }) => {
  await mockWorkspace(page);
  await page.goto("/register?ref=INVITE123");
  await expect(page.getByLabel("Referral code (optional)")).toHaveValue(
    "INVITE123",
  );
});
