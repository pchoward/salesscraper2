// A small D1-compatible wrapper over node:sqlite, for tests and the local mock
// server. It covers the subset the Worker uses: prepare().bind().first(),
// .all(), .run(), and DB.batch(). Never used in a deployed Worker.

import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { DatabaseSync } from "node:sqlite";

class Statement {
  constructor(db, sql, params = []) {
    this.db = db;
    this.sql = sql;
    this.params = params;
  }

  bind(...params) {
    return new Statement(this.db, this.sql, params.map((value) => (value === undefined ? null : value)));
  }

  async first(column) {
    const row = this.db.prepare(this.sql).get(...this.params);
    if (!row) return null;
    const plain = { ...row };
    return column ? plain[column] : plain;
  }

  async all() {
    const rows = this.db.prepare(this.sql).all(...this.params).map((row) => ({ ...row }));
    return { results: rows, success: true, meta: {} };
  }

  async run() {
    const info = this.db.prepare(this.sql).run(...this.params);
    return { success: true, meta: { changes: Number(info.changes), last_row_id: Number(info.lastInsertRowid) } };
  }
}

export class D1Sqlite {
  constructor(path = ":memory:") {
    this.db = new DatabaseSync(path);
    this.db.exec("PRAGMA foreign_keys = ON;");
  }

  prepare(sql) {
    return new Statement(this.db, sql);
  }

  async batch(statements) {
    const results = [];
    this.db.exec("BEGIN");
    try {
      for (const statement of statements) results.push(await statement.run());
      this.db.exec("COMMIT");
    } catch (error) {
      this.db.exec("ROLLBACK");
      throw error;
    }
    return results;
  }

  async exec(sql) {
    this.db.exec(sql);
    return { count: 1 };
  }

  applyMigrations(directory) {
    for (const file of readdirSync(directory).filter((name) => name.endsWith(".sql")).sort()) {
      this.db.exec(readFileSync(join(directory, file), "utf8"));
    }
    return this;
  }
}
