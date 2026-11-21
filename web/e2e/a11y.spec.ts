import AxeBuilder from '@axe-core/playwright'
import { expect, test as it } from '@playwright/test'
import { mockApi, real } from './mockApi.ts'

const PAGES = real
  ? ['/', '/planner', '/draft', '/live', '/meta', '/coach', '/coverage']
  : ['/', '/teams/fq/scouting', '/planner', '/draft', '/live', '/coach', '/coverage', '/nowhere']

for (const path of PAGES) {
  it(`no serious accessibility problems on ${path}`, async ({ page }) => {
    await mockApi(page)
    await page.goto(path)
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
    const result = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze()
    const serious = result.violations.filter((v) => v.impact === 'serious' || v.impact === 'critical')
    expect(serious.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(', ')}`)).toEqual([])
  })
}
