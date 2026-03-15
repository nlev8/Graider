/**
 * Planner tab page object — lesson plans, assessments, standards.
 */
export class PlannerPage {
  constructor(page) {
    this.page = page;
  }

  async navigateTo() {
    await this.page.locator('nav button', { hasText: 'Planner' }).click();
    await this.page.waitForTimeout(500);
  }

  /** Fill in the lesson plan title */
  async setTitle(title) {
    const titleInput = this.page.locator('input[placeholder*="Causes"]');
    if (await titleInput.count() > 0) {
      await titleInput.first().fill(title);
    }
  }

  /** Check that standards loaded */
  async hasStandards() {
    const standards = this.page.locator('text=/Select Standards|standards available/i');
    return (await standards.count()) > 0;
  }

  /** Check generate button exists */
  async hasGenerateButton() {
    const btn = this.page.locator('button', { hasText: /Create|Generate|Brainstorm/i });
    return (await btn.count()) > 0;
  }
}
