import { expect, test as it } from 'vitest'
import { matchesChampion, normalize, resolveChampion } from './champions.ts'

const NAMES = ["Kai'Sa", "K'Sante", 'Miss Fortune', 'Twisted Fate', 'Jarvan IV', 'Dr. Mundo', 'Azir', 'Aatrox', 'Ahri']

it('ignores case and punctuation', () => {
  expect(normalize("Kai'Sa")).toBe('kaisa')
  expect(resolveChampion('kaisa', NAMES)).toBe("Kai'Sa")
  expect(resolveChampion('ksante', NAMES)).toBe("K'Sante")
  expect(resolveChampion('dr mundo', NAMES)).toBe('Dr. Mundo')
})

it('knows common nicknames', () => {
  expect(resolveChampion('MF', NAMES)).toBe('Miss Fortune')
  expect(resolveChampion('tf', NAMES)).toBe('Twisted Fate')
  expect(resolveChampion('j4', NAMES)).toBe('Jarvan IV')
  expect(matchesChampion('Miss Fortune', 'mf')).toBe(true)
})

it('takes a unique prefix, refuses an ambiguous one', () => {
  expect(resolveChampion('azi', NAMES)).toBe('Azir')
  expect(resolveChampion('a', NAMES)).toBeNull() // Azir, Aatrox, Ahri
  expect(resolveChampion('nobody', NAMES)).toBeNull()
  expect(resolveChampion('', NAMES)).toBeNull()
})
