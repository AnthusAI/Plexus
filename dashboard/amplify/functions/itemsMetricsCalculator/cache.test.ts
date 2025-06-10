import { InMemoryCache } from './cache';

describe('InMemoryCache', () => {
  let cache: InMemoryCache;
  
  beforeEach(() => {
    cache = new InMemoryCache(1000); // 1 second TTL for testing
  });

  afterEach(async () => {
    await cache.close();
  });

  describe('constructor', () => {
    it('should create cache with default TTL', () => {
      const defaultCache = new InMemoryCache();
      expect(defaultCache).toBeDefined();
      defaultCache.close();
    });

    it('should create cache with custom TTL', () => {
      expect(cache).toBeDefined();
    });
  });

  describe('get and set operations', () => {
    it('should return null for non-existent key', async () => {
      const result = await cache.get('non-existent-key');
      expect(result).toBeNull();
    });

    it('should store and retrieve a value', async () => {
      const key = 'test-key';
      const value = 42;
      
      await cache.set(key, value);
      const result = await cache.get(key);
      
      expect(result).toBe(value);
    });

    it('should handle multiple key-value pairs', async () => {
      const pairs: Array<[string, number]> = [
        ['key1', 100],
        ['key2', 200],
        ['key3', 300]
      ];
      
      // Store all pairs
      for (const [key, value] of pairs) {
        await cache.set(key, value);
      }
      
      // Retrieve and verify all pairs
      for (const [key, expectedValue] of pairs) {
        const result = await cache.get(key);
        expect(result).toBe(expectedValue);
      }
    });

    it('should update existing values', async () => {
      const key = 'update-test';
      const originalValue = 123;
      const updatedValue = 456;
      
      await cache.set(key, originalValue);
      let result = await cache.get(key);
      expect(result).toBe(originalValue);
      
      await cache.set(key, updatedValue);
      result = await cache.get(key);
      expect(result).toBe(updatedValue);
    });

    it('should handle zero values correctly', async () => {
      const key = 'zero-test';
      const value = 0;
      
      await cache.set(key, value);
      const result = await cache.get(key);
      
      expect(result).toBe(0);
      expect(result).not.toBeNull();
    });
  });

  describe('TTL functionality', () => {
    it('should expire entries after TTL', async () => {
      const key = 'ttl-test';
      const value = 789;
      
      await cache.set(key, value);
      
      // Should be available immediately
      let result = await cache.get(key);
      expect(result).toBe(value);
      
      // Wait for TTL to expire
      await new Promise(resolve => setTimeout(resolve, 1100));
      
      // Should be expired now
      result = await cache.get(key);
      expect(result).toBeNull();
    });

    it('should refresh timestamp on set', async () => {
      const key = 'refresh-test';
      const value1 = 100;
      const value2 = 200;
      
      await cache.set(key, value1);
      
      // Wait half the TTL
      await new Promise(resolve => setTimeout(resolve, 500));
      
      // Update the value (should refresh timestamp)
      await cache.set(key, value2);
      
      // Wait another half TTL (total time now exceeds original TTL)
      await new Promise(resolve => setTimeout(resolve, 600));
      
      // Should still be available due to timestamp refresh
      const result = await cache.get(key);
      expect(result).toBe(value2);
    });
  });

  describe('cache management', () => {
    it('should report correct size', () => {
      expect(cache.size()).toBe(0);
    });

    it('should update size when adding entries', async () => {
      await cache.set('key1', 100);
      expect(cache.size()).toBe(1);
      
      await cache.set('key2', 200);
      expect(cache.size()).toBe(2);
    });

    it('should clear all entries', async () => {
      await cache.set('key1', 100);
      await cache.set('key2', 200);
      expect(cache.size()).toBe(2);
      
      cache.clear();
      expect(cache.size()).toBe(0);
      
      const result = await cache.get('key1');
      expect(result).toBeNull();
    });
  });

  describe('cache key patterns', () => {
    it('should handle complex cache keys like the MetricsCalculator uses', async () => {
      const accountId = 'acc-123';
      const functionName = 'countItemsInTimeframe';
      const timestamp = '2023-12-01T10:15:00.000Z';
      const cacheKey = `${functionName}:${accountId}:${timestamp}`;
      const value = 789;
      
      await cache.set(cacheKey, value);
      const result = await cache.get(cacheKey);
      
      expect(result).toBe(value);
    });

    it('should handle special characters in keys', async () => {
      const specialKey = 'key:with:colons-and-dashes_and_underscores.and.dots';
      const value = 999;
      
      await cache.set(specialKey, value);
      const result = await cache.get(specialKey);
      
      expect(result).toBe(value);
    });
  });

  describe('realistic usage patterns', () => {
    it('should simulate MetricsCalculator cache usage pattern', async () => {
      const accountId = 'test-account-123';
      const baseTime = new Date('2023-12-01T10:00:00.000Z');
      
      // Simulate caching counts for 15-minute buckets over 2 hours
      const bucketSize = 15; // minutes
      const totalMinutes = 120; // 2 hours
      const bucketCount = totalMinutes / bucketSize;
      
      for (let i = 0; i < bucketCount; i++) {
        const bucketStart = new Date(baseTime.getTime() + i * bucketSize * 60 * 1000);
        
        // Create cache keys for both items and score results
        const itemsKey = `countItemsInTimeframe:${accountId}:${bucketStart.toISOString()}`;
        const scoreResultsKey = `countScoreResultsInTimeframe:${accountId}:${bucketStart.toISOString()}`;
        
        const itemsCount = Math.floor(Math.random() * 100);
        const scoreResultsCount = Math.floor(Math.random() * 50);
        
        await cache.set(itemsKey, itemsCount);
        await cache.set(scoreResultsKey, scoreResultsCount);
      }
      
      // Verify all cached values can be retrieved
      for (let i = 0; i < bucketCount; i++) {
        const bucketStart = new Date(baseTime.getTime() + i * bucketSize * 60 * 1000);
        
        const itemsKey = `countItemsInTimeframe:${accountId}:${bucketStart.toISOString()}`;
        const scoreResultsKey = `countScoreResultsInTimeframe:${accountId}:${bucketStart.toISOString()}`;
        
        const itemsResult = await cache.get(itemsKey);
        const scoreResultsResult = await cache.get(scoreResultsKey);
        
        expect(itemsResult).not.toBeNull();
        expect(scoreResultsResult).not.toBeNull();
        expect(typeof itemsResult).toBe('number');
        expect(typeof scoreResultsResult).toBe('number');
      }
    });

    it('should handle rapid sequential operations', async () => {
      const operations = [];
      
      // Create many concurrent set operations
      for (let i = 0; i < 50; i++) {
        operations.push(cache.set(`rapid-key-${i}`, i * 10));
      }
      
      await Promise.all(operations);
      
      // Verify all values were stored correctly
      for (let i = 0; i < 50; i++) {
        const result = await cache.get(`rapid-key-${i}`);
        expect(result).toBe(i * 10);
      }
    });
  });

  describe('cleanup functionality', () => {
    it('should clean up expired entries on close', async () => {
      const shortTtlCache = new InMemoryCache(100); // Very short TTL
      
      await shortTtlCache.set('key1', 100);
      await shortTtlCache.set('key2', 200);
      expect(shortTtlCache.size()).toBe(2);
      
      // Wait for entries to expire
      await new Promise(resolve => setTimeout(resolve, 150));
      
      // Close should clean up expired entries
      await shortTtlCache.close();
      
      // Verify entries are cleaned up (size should be 0)
      expect(shortTtlCache.size()).toBe(0);
    });
  });
}); 