export function createCachedOptionalLoader<T>(load: (key: string) => Promise<T>, isMissing: (reason: unknown) => boolean) {
  const cache = new Map<string, Promise<T | null>>()
  return (key: string, force = false) => {
    if (force) cache.delete(key)
    if (!cache.has(key)) cache.set(key, load(key).catch(reason => {
      if (isMissing(reason)) return null
      cache.delete(key)
      throw reason
    }))
    return cache.get(key)!
  }
}
