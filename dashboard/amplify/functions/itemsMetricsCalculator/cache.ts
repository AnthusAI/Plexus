/**
 * An in-memory cache for storing metric counts.
 * Suitable for Lambda environments where persistence across invocations is not required.
 */
const cache = new Map<string, { value: any, timestamp: number }>();
const TTL = 5 * 60 * 1000; // 5 minutes

function cleanupExpiredEntries() {
    const now = Date.now();
    for (const [key, entry] of cache.entries()) {
        if (now - entry.timestamp > TTL) {
            cache.delete(key);
        }
    }
}

export function getFromCache<T>(key: string): T | undefined {
    cleanupExpiredEntries();
    const entry = cache.get(key);
    return entry ? entry.value as T : undefined;
}

export function setInCache<T>(key: string, value: T): void {
    const timestamp = Date.now();
    cache.set(key, { value, timestamp });
}

// Ensure graceful cleanup on Lambda execution completion
export const cleanupCache = () => {
  cache.clear();
}; 