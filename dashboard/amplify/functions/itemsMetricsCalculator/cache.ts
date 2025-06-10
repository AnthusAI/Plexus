/**
 * A simple in-memory cache for storing metric counts within a Lambda execution.
 * Since Lambda functions are stateless, this cache only persists for the duration
 * of a single invocation, but it can help avoid redundant queries within that timeframe.
 */
export class InMemoryCache {
  private cache: Map<string, { value: number; timestamp: number }> = new Map();
  private readonly TTL_MS = 5 * 60 * 1000; // 5 minutes TTL

  constructor() {
    console.log('Initializing in-memory cache for Lambda execution');
  }

  public async createTable(): Promise<void> {
    // No-op for in-memory cache
    return Promise.resolve();
  }

  public async get(key: string): Promise<number | null> {
    const cached = this.cache.get(key);
    
    if (!cached) {
      console.debug(`Cache GET - MISS: key='${key}'`);
      return null;
    }

    // Check if the cached value has expired
    const now = Date.now();
    if (now - cached.timestamp > this.TTL_MS) {
      this.cache.delete(key);
      console.debug(`Cache GET - EXPIRED: key='${key}'`);
      return null;
    }

    console.debug(`Cache GET - HIT: key='${key}', value=${cached.value}`);
    return cached.value;
  }

  public async set(key: string, value: number): Promise<void> {
    const now = Date.now();
    this.cache.set(key, { value, timestamp: now });
    console.debug(`Cache SET: key='${key}', value=${value}`);
    return Promise.resolve();
  }

  public async close(): Promise<void> {
    this.cache.clear();
    console.log('In-memory cache cleared');
    return Promise.resolve();
  }

  /**
   * Clean up expired entries from the cache
   */
  public cleanup(): void {
    const now = Date.now();
    let cleaned = 0;
    
    for (const [key, cached] of this.cache.entries()) {
      if (now - cached.timestamp > this.TTL_MS) {
        this.cache.delete(key);
        cleaned++;
      }
    }
    
    if (cleaned > 0) {
      console.debug(`Cache cleanup: removed ${cleaned} expired entries`);
    }
  }
}

// Instantiate the cache once at the module level
export const cache = new InMemoryCache();
// Ensure the table is "created" (no-op for in-memory)
cache.createTable(); 