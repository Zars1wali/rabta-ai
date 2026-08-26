import { drizzle } from 'drizzle-orm/postgres-js';
import postgres from 'postgres';
import * as schema from './schema.js';

export type Database = ReturnType<typeof createDbClient>['db'];

export function createDbClient(connectionString: string, options?: postgres.Options<Record<string, never>>) {
  const sql = postgres(connectionString, {
    max: options?.max ?? 10,
    idle_timeout: options?.idle_timeout ?? 20,
    connect_timeout: options?.connect_timeout ?? 10,
    ...options
  });

  const db = drizzle(sql, { schema });

  return {
    db,
    sql,
    async close() {
      await sql.end();
    }
  };
}
