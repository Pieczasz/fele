import { expect, test as it } from '@playwright/test'
import { mockApi } from './mockApi.ts'

// mock-only: the opponent and champions exist in the fake API (playwright.config.ts skips this file with E2E_REAL=1)
const FLYQUEST = /FlyQuest/u
const AHRI = /^(?:Ban |Pick )?Ahri(?::.*)?$/u // the grid tile, whatever its state

it.beforeEach(async ({ page }) => {
  await mockApi(page)
})

it('coach flow: opponent → scouting → plan a Bo5 → draft a full game → it counts in the series', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('link', { name: FLYQUEST }).click()
  await expect(page.getByRole('heading', { name: 'FlyQuest' })).toBeVisible()
  await expect(page.getByText('Azir is a game-1 priority')).toBeVisible()
  await expect(page).toHaveTitle('Scouting report · fele')

  await page.getByRole('button', { name: 'Plan a series vs this team' }).click()
  await expect(page.getByRole('heading', { name: 'Fearless series planner' })).toBeVisible()
  await page.getByRole('button', { name: 'Best of 5' }).click()
  await page.getByRole('link', { name: 'Draft it on the mock draft board' }).click()

  await expect(page.getByRole('heading', { name: 'Mock draft: game 1 vs FlyQuest' })).toBeVisible()
  // 20 actions: each time the keyboard takes option 1 (or their likely pick) once the advice for this slot is in
  await expect(page.getByText('option 1 for slot 1')).toBeVisible()
  for (let slot = 0; slot < 20; slot += 1) {
    await expect(page.locator('[aria-busy="false"]')).toHaveCount(1)
    const answered = page.waitForResponse(
      (r) => r.url().endsWith('/api/draft/recommend') && r.request().postDataJSON()?.actions?.length === slot + 1,
    )
    await page.keyboard.press('1')
    await answered
  }
  await page.getByRole('button', { name: 'Save to series as a win' }).click()
  await page.getByRole('link', { name: 'Series planner' }).click()
  await expect(page.getByText('Score 1–0 · next: game 2')).toBeVisible()
})

it('mock draft keeps its state across navigation', async ({ page }) => {
  await page.goto('/draft')
  await page.getByRole('combobox', { name: 'Who are we drafting against?' }).selectOption('fq')
  await page.getByRole('button', { name: 'Skip this ban' }).click()
  await page.getByRole('button', { name: AHRI }).click()
  await page.getByRole('link', { name: 'Meta' }).click()
  await page.getByRole('link', { name: 'Mock draft' }).click()
  await expect(page.getByRole('button', { name: AHRI })).toBeDisabled()
})

it('fele Live shows champ select with party names and options', async ({ page }) => {
  await page.goto('/live')
  await expect(page.getByRole('heading', { name: 'Pick options for you' })).toBeVisible()
  await expect(page.getByText('Ally', { exact: true })).toBeVisible()
  await expect(page.getByText('Friend', { exact: true })).toBeVisible()
  await expect(page.getByText('56% adj. win rate at mid in 120 high-elo games (16.22–16.23)')).toBeVisible()
})
