import sqlite3 from 'sqlite3';
import * as path from 'path';
import * as fs from 'fs';

const DB_NAME = 'plexus-record-count-cache.db';
const LAMBDA_TMP_DIR = '/tmp';

/**
 * A simple SQLite-based cache for storing metric counts.
 * It stores the database in /tmp if available (for Lambda), otherwise in a local tmp/ directory.
 */
export class SQLiteCache {
  private db: sqlite3.Database | null = null;
  private dbPath: string;

  constructor() {
    let dbDir = LAMBDA_TMP_DIR;
    // Check if /tmp exists and is writable, common for Lambda environments
    try {
      fs.accessSync(LAMBDA_TMP_DIR, fs.constants.W_OK);
    } catch (e) {
      // Fallback to a local tmp directory for local development
      dbDir = 'tmp';
      if (!fs.existsSync(dbDir)) {
        fs.mkdirSync(dbDir);
      }
    }
    this.dbPath = path.join(dbDir, DB_NAME);
    console.log(`Initializing SQLite cache at ${this.dbPath}`);
  }

  private async connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      if (this.db) {
        resolve();
        return;
      }
      this.db = new sqlite3.Database(this.dbPath, (err: Error | null) => {
        if (err) {
          console.error('Error opening SQLite database:', err);
          reject(err);
        } else {
          resolve();
        }
      });
    });
  }

  public async createTable(): Promise<void> {
    await this.connect();
    const query = `
      CREATE TABLE IF NOT EXISTS cache (
        key TEXT PRIMARY KEY,
        value INTEGER,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
      )
    `;
    return new Promise((resolve, reject) => {
      this.db!.run(query, (err: Error | null) => {
        if (err) reject(err);
        else resolve();
      });
    });
  }

  public async get(key: string): Promise<number | null> {
    await this.connect();
    const query = 'SELECT value FROM cache WHERE key = ?';
    return new Promise((resolve, reject) => {
      this.db!.get(query, [key], (err: Error | null, row: { value: number }) => {
        if (err) {
          reject(err);
        } else {
          if (row) {
            console.debug(`Cache GET - HIT: key='${key}', value=${row.value}`);
            resolve(row.value);
          } else {
            console.debug(`Cache GET - MISS: key='${key}'`);
            resolve(null);
          }
        }
      });
    });
  }

  public async set(key: string, value: number): Promise<void> {
    await this.connect();
    const query = 'INSERT OR REPLACE INTO cache (key, value) VALUES (?, ?)';
    return new Promise((resolve, reject) => {
      this.db!.run(query, [key, value], (err: Error | null) => {
        if (err) reject(err);
        else {
          console.debug(`Cache SET: key='${key}', value=${value}`);
          resolve();
        }
      });
    });
  }

  public async close(): Promise<void> {
    return new Promise((resolve, reject) => {
      if (this.db) {
        this.db.close((err: Error | null) => {
          if (err) reject(err);
          else {
            this.db = null;
            console.log('SQLite cache connection closed.');
            resolve();
          }
        });
      } else {
        resolve();
      }
    });
  }
}

// Instantiate the cache once at the module level
export const cache = new SQLiteCache();
// Ensure the table is created
cache.createTable(); 