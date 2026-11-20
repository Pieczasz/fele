import { configure } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'

// findBy*/waitFor default to 1 s, which flakes on a loaded machine or under coverage instrumentation
configure({ asyncUtilTimeout: 5000 })
