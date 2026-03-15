/**
 * Builder (Grading Setup) tab page object — assignment config, document import.
 */
export class BuilderPage {
  constructor(page) {
    this.page = page;
  }

  async navigateTo() {
    await this.page.locator('button', { hasText: /Grading Setup|Builder/i }).last().click();
    await this.page.waitForTimeout(500);
  }

  /** Upload a document for parsing */
  async uploadDocument(filePath) {
    const fileInput = this.page.locator('input[type="file"]').first();
    await fileInput.setInputFiles(filePath);
    // Wait for parse to complete
    await this.page.waitForTimeout(3000);
  }

  /** Check that parsed document sections appeared */
  async hasParsedSections() {
    const sections = this.page.locator('[data-tutorial="builder-card"]');
    return (await sections.count()) > 0;
  }

  /** Save the current assignment config */
  async saveAssignment(name) {
    const saveBtn = this.page.locator('button', { hasText: /Save/i }).first();
    if (await saveBtn.count() > 0) {
      // If there's a name input, fill it
      const nameInput = this.page.locator('input[placeholder*="name"], input[placeholder*="itle"]');
      if (name && await nameInput.count() > 0) {
        await nameInput.first().fill(name);
      }
      await saveBtn.click();
      await this.page.waitForTimeout(600);
    }
  }

  /** Load a saved assignment from the list */
  async loadAssignment(name) {
    const item = this.page.locator(`text=${name}`);
    if (await item.count() > 0) {
      await item.first().click();
      await this.page.waitForTimeout(600);
    }
  }

  /** Get list of saved assignments */
  async getSavedAssignments() {
    const listBtn = this.page.locator('button', { hasText: /Load|Saved/i });
    if (await listBtn.count() > 0) {
      await listBtn.first().click();
      await this.page.waitForTimeout(500);
    }
    // Collect assignment names from the list
    const items = this.page.locator('[role="listbox"] [role="option"], .assignment-list-item');
    const names = [];
    for (let i = 0; i < await items.count(); i++) {
      names.push(await items.nth(i).textContent());
    }
    return names;
  }
}
