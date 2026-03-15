/**
 * Settings tab page object — rubric, global notes, rosters, accommodations.
 */
export class SettingsPage {
  constructor(page) {
    this.page = page;
  }

  async navigateTo() {
    await this.page.locator('nav button', { hasText: 'Settings' }).click();
    await this.page.waitForTimeout(500);
  }

  // ── Global AI Notes ──

  async setGlobalNotes(text) {
    // Find the global notes textarea near its heading
    const section = this.page.locator('text=Global AI Notes').locator('..');
    const ta = section.locator('textarea').first();
    if (await ta.count() > 0) {
      await ta.fill(text);
    } else {
      // Fallback: find any textarea in settings
      const allTa = this.page.locator('textarea');
      for (let i = 0; i < await allTa.count(); i++) {
        const placeholder = await allTa.nth(i).getAttribute('placeholder');
        if (placeholder && placeholder.toLowerCase().includes('note')) {
          await allTa.nth(i).fill(text);
          break;
        }
      }
    }
    await this.page.waitForTimeout(600); // debounce
  }

  async saveGlobalSettings() {
    const saveBtn = this.page.locator('button', { hasText: /Save/i }).first();
    if (await saveBtn.count() > 0) {
      await saveBtn.click();
      await this.page.waitForTimeout(600);
    }
  }

  // ── Roster Upload ──

  async uploadRoster(filePath) {
    const fileInput = this.page.locator('input[type="file"][accept*=".csv"]');
    if (await fileInput.count() > 0) {
      await fileInput.setInputFiles(filePath);
      await this.page.waitForTimeout(1000);
    }
  }

  async getRosterCount() {
    const countText = this.page.locator('text=/\\d+ student/i');
    if (await countText.count() > 0) {
      const text = await countText.first().textContent();
      const match = text.match(/(\d+)/);
      return match ? parseInt(match[1]) : 0;
    }
    return 0;
  }
}
