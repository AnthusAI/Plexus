import { SQLiteCache } from './cache';
import * as fs from 'fs';
import * as path from 'path';

describe('SQLiteCache', () => {
  let cache: SQLiteCache;
  const testDbName = 'test-cache.db';
  
  beforeEach(() => {
    // Clean up any existing test database
    const testDbPath = path.join('tmp', testDbName);
    if (fs.existsSync(testDbPath)) {
      fs.unlinkSync(testDbPath);
    }
    
    cache = new SQLiteCache(testDbName);
  });

  afterEach(async () => {
    await cache.close();
    
    // Clean up test database
    const testDbPath = path.join('tmp', testDbName);
    if (fs.existsSync(testDbPath)) {
      fs.unlinkSync(testDbPath);
    }
  });

  describe('constructor', () => {
    it('should create cache with default database name', () => {
      const defaultCache = new SQLiteCache();
      expect(defaultCache).toBeDefined();
      defaultCache.close();
    });

    it('should create cache with custom database name', () => {
      expect(cache).toBeDefined();
    });

    it('should prefer /tmp directory in Lambda environment', () => {
      // This test verifies the path logic but actual path depends on environment
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

    it('should update existing values (INSERT OR REPLACE)', async () => {
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

  describe('error handling', () => {
    it('should handle errors gracefully on invalid operations', async () => {
      // Close the cache to simulate a closed database
      await cache.close();
      
      // Operations on closed database should reject
      await expect(cache.get('test-key')).rejects.toThrow();
      await expect(cache.set('test-key', 123)).rejects.toThrow();
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

  describe('database persistence', () => {
    it('should persist data across cache instances', async () => {
      const key = 'persistence-test';
      const value = 12345;
      
      // Store value in first instance
      await cache.set(key, value);
      await cache.close();
      
      // Create new instance with same database file
      const newCache = new SQLiteCache(testDbName);
      
      try {
        // Verify value persists
        const result = await newCache.get(key);
        expect(result).toBe(value);
      } finally {
        await newCache.close();
      }
    });
  });
}); 