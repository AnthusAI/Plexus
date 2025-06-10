/**
 * An in-memory cache for storing metric counts.
 * Suitable for Lambda environments where persistence across invocations is not required.
 */
export class InMemoryCache {
  private cache: Map<string, { value: number; timestamp: number }> = new Map();
  private ttlMs: number;

  constructor(ttlMs: number = 5 * 60 * 1000) { // 5 minutes default TTL
    this.ttlMs = ttlMs;
  }

  public async get(key: string): Promise<number | null> {
    const entry = this.cache.get(key);
    
    if (!entry) {
      console.debug(`Cache GET - MISS: key='${key}'`);
      return null;
    }
    
    // Check if entry has expired
    const now = Date.now();
    if (now - entry.timestamp > this.ttlMs) {
      console.debug(`Cache GET - EXPIRED: key='${key}'`);
      this.cache.delete(key);
      return null;
    }
    
    console.debug(`Cache GET - HIT: key='${key}', value=${entry.value}`);
    return entry.value;
  }

  public async set(key: string, value: number): Promise<void> {
    const timestamp = Date.now();
    this.cache.set(key, { value, timestamp });
    console.debug(`Cache SET: key='${key}', value=${value}`);
  }

  public async close(): Promise<void> {
    // Clean up expired entries
    const now = Date.now();
    for (const [key, entry] of this.cache.entries()) {
      if (now - entry.timestamp > this.ttlMs) {
        this.cache.delete(key);
      }
    }
    console.log("In-memory cache cleaned up.");
  }

  public clear(): void {
    this.cache.clear();
    console.debug("Cache cleared");
  }

  public size(): number {
    return this.cache.size;
  }
}

// Instantiate the cache once at the module level
export const cache = new InMemoryCache();

// Ensure graceful cleanup on Lambda execution completion
export const cleanupCache = () => {
  cache.close();
}; 