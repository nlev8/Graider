/**
 * Analytics tab page object — charts, filters, student details.
 */
export class AnalyticsPage {
  constructor(page) {
    this.page = page;
  }

  async navigateTo() {
    await this.page.locator('nav button', { hasText: 'Analytics' }).click();
    await this.page.waitForTimeout(500);
  }

  /** Verify the main analytics sections render without overflow */
  async verifyChartsRender() {
    const charts = this.page.locator('[data-tutorial="analytics-charts"]');
    await charts.waitFor({ timeout: 5000 });

    const overflow = await this.page.evaluate(() => {
      const el = document.querySelector('[data-tutorial="analytics-charts"]');
      if (!el) return { overflows: false };
      return {
        scrollWidth: el.scrollWidth,
        clientWidth: el.clientWidth,
        overflows: el.scrollWidth > el.clientWidth + 5,
      };
    });
    return overflow;
  }

  /** Check stats cards render */
  async getStatsCards() {
    const stats = this.page.locator('[data-tutorial="analytics-stats"]');
    if (await stats.count() === 0) return [];
    const cards = stats.locator('.glass-card, [style*="glass"]');
    const count = await cards.count();
    const result = [];
    for (let i = 0; i < count; i++) {
      result.push(await cards.nth(i).textContent());
    }
    return result;
  }

  /** Click on a student in the student panel */
  async selectStudent(studentName) {
    const panel = this.page.locator('text=' + studentName);
    if (await panel.count() > 0) {
      await panel.first().click();
      await this.page.waitForTimeout(300);
    }
  }

  /** Check if scatter chart rendered (SVG elements present) */
  async hasScatterChart() {
    const scatter = this.page.locator('[data-tutorial="analytics-scatter"] svg');
    return (await scatter.count()) > 0;
  }

  /** Get page dimensions to verify no horizontal scroll */
  async checkNoHorizontalScroll() {
    return this.page.evaluate(() => ({
      bodyScrollWidth: document.body.scrollWidth,
      windowWidth: window.innerWidth,
      hasHorizontalScroll: document.body.scrollWidth > window.innerWidth + 5,
    }));
  }
}
