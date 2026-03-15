/**
 * Base page object — handles navigation, tab switching, and common actions.
 * On localhost the app auto-authenticates as local-dev.
 */
export class AppPage {
  constructor(page) {
    this.page = page;
  }

  /** Navigate to app and wait for it to load (auth auto-bypassed on localhost) */
  async goto() {
    await this.page.goto('/');
    // Wait for sidebar nav to render (contains tab buttons)
    await this.page.waitForSelector('nav button', { timeout: 15_000 });
  }

  /** Switch to a tab by clicking the sidebar nav button with exact label */
  async switchTab(tabName) {
    // Sidebar nav buttons contain icon + label text
    const tab = this.page.locator('nav button', { hasText: tabName });
    await tab.click();
    await this.page.waitForTimeout(300);
  }

  /** Take a named screenshot for visual comparison */
  async screenshot(name) {
    await this.page.screenshot({ path: `tests/reports/e2e/screenshots/${name}.png`, fullPage: true });
  }
}
