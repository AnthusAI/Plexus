import { getFromCache, setInCache, cleanupCache } from './cache';

describe('In-Memory Cache', () => {
  beforeEach(() => {
    // Clear the cache before each test
    cleanupCache();
  });

  it('should store and retrieve a value', () => {
    setInCache('testKey', 123);
    const value = getFromCache<number>('testKey');
    expect(value).toBe(123);
  });

  it('should return undefined for a non-existent key', () => {
    const value = getFromCache('nonExistentKey');
    expect(value).toBeUndefined();
  });

  it('should overwrite an existing value', () => {
    setInCache('testKey', 123);
    setInCache('testKey', 456);
    const value = getFromCache<number>('testKey');
    expect(value).toBe(456);
  });

  it('should handle different data types', () => {
    const obj = { a: 1, b: 'test' };
    setInCache('objectKey', obj);
    const retrievedObj = getFromCache<{ a: number, b: string }>('objectKey');
    expect(retrievedObj).toEqual(obj);

    setInCache('stringKey', 'hello');
    const retrievedString = getFromCache<string>('stringKey');
    expect(retrievedString).toBe('hello');
  });

  it('should clear the cache', () => {
    setInCache('testKey', 123);
    cleanupCache();
    const value = getFromCache('testKey');
    expect(value).toBeUndefined();
  });
}); 