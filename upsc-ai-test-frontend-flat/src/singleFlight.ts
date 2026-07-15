export function createSingleFlight() {
  let pending = false
  return async <T>(operation: () => Promise<T>) => {
    if (pending) return undefined
    pending = true
    try { return await operation() } finally { pending = false }
  }
}
