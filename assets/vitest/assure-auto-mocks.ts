import { vi } from 'vitest'

globalThis.fetch = vi.fn(async () => {
  throw new Error('Assure blocked outbound fetch')
}) as typeof fetch

globalThis.WebSocket = class {
  constructor() {
    throw new Error('Assure blocked outbound WebSocket')
  }
} as unknown as typeof WebSocket

vi.mock('node:http', () => ({
  request: () => {
    throw new Error('Assure blocked outbound HTTP')
  },
}))

vi.mock('node:https', () => ({
  request: () => {
    throw new Error('Assure blocked outbound HTTPS')
  },
}))
