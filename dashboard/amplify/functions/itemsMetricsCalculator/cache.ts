import * as sqlite3 from 'sqlite3';
import * as fs from 'fs';
import * as path from 'path';

/**
 * A SQLite-based cache for storing metric counts.
 * This mirrors the Python SQLiteCache implementation exactly.
 */
export class SQLiteCache {
  private db: sqlite3.Database;
  private dbPath: string;

  constructor(dbName: string = 'plexus-record-count-cache.db') {
    // Check if /tmp exists and is writable, common for Lambda environments
    if (fs.existsSync('/tmp') && this.canWrite('/tmp')) {
      this.dbPath = path.join('/tmp', dbName);
    } else {
      // Fallback to a local tmp directory for local development
      const localTmpDir = 'tmp';
      if (!fs.existsSync(localTmpDir)) {
        fs.mkdirSync(localTmpDir, { recursive: true });
      }
      this.dbPath = path.join(localTmpDir, dbName);
    }

    // Use an absolute path to avoid ambiguity
    const absDbPath = path.resolve(this.dbPath);
    console.log(`Initializing SQLite cache at ${absDbPath}`);
    
    this.db = new sqlite3.Database(absDbPath);
    this.createTable();
  }

  private canWrite(dirPath: string): boolean {
    try {
      fs.accessSync(dirPath, fs.constants.W_OK);
      return true;
    } catch {
      return false;
    }
  }

  private createTable(): void {
    const sql = `
      CREATE TABLE IF NOT EXISTS cache (
        key TEXT PRIMARY KEY,
        value INTEGER,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
      )
    `;
    
    this.db.run(sql, (err) => {
      if (err) {
        console.error('Error creating cache table:', err);
      }
    });
  }

  public async get(key: string): Promise<number | null> {
    return new Promise((resolve, reject) => {
      this.db.get(
        "SELECT value FROM cache WHERE key = ?",
        [key],
        (err, row: any) => {
          if (err) {
            console.error(`Cache GET error for key '${key}':`, err);
            reject(err);
            return;
          }
          
          if (row) {
            console.debug(`Cache GET - HIT: key='${key}', value=${row.value}`);
            resolve(row.value);
          } else {
            console.debug(`Cache GET - MISS: key='${key}'`);
            resolve(null);
          }
        }
      );
    });
  }

  public async set(key: string, value: number): Promise<void> {
    return new Promise((resolve, reject) => {
      this.db.run(
        "INSERT OR REPLACE INTO cache (key, value) VALUES (?, ?)",
        [key, value],
        function(err) {
          if (err) {
            console.error(`Cache SET error for key '${key}':`, err);
            reject(err);
            return;
          }
          
          console.debug(`Cache SET: key='${key}', value=${value}`);
          resolve();
        }
      );
    });
  }

  public async close(): Promise<void> {
    return new Promise((resolve) => {
      if (this.db) {
        this.db.close((err) => {
          if (err) {
            console.error('Error closing SQLite cache:', err);
          } else {
            console.log("SQLite cache connection closed.");
          }
          resolve();
        });
      } else {
        resolve();
      }
    });
  }
}

// Instantiate the cache once at the module level
export const cache = new SQLiteCache();

// Ensure graceful cleanup on process exit
process.on('exit', () => {
  cache.close();
});

process.on('SIGINT', () => {
  cache.close();
});

process.on('SIGTERM', () => {
  cache.close();
}); 