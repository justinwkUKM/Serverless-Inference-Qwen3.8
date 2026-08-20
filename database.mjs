import { mkdirSync } from "node:fs";
import { dirname } from "node:path";
import { DatabaseSync } from "node:sqlite";

export class ChatDatabase {
  constructor(path) {
    if (path !== ":memory:") mkdirSync(dirname(path), { recursive: true });
    this.db = new DatabaseSync(path);
    this.db.exec(`
      PRAGMA journal_mode = WAL;
      PRAGMA foreign_keys = ON;
      PRAGMA busy_timeout = 5000;
      CREATE TABLE IF NOT EXISTS chats (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL DEFAULT 'New chat',
        favorite INTEGER NOT NULL DEFAULT 0,
        created_at INTEGER NOT NULL,
        updated_at INTEGER NOT NULL
      );
      CREATE TABLE IF NOT EXISTS requests (
        id TEXT PRIMARY KEY,
        chat_id TEXT NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
        status TEXT NOT NULL CHECK(status IN ('streaming','completed','cancelled','failed')),
        model TEXT NOT NULL,
        request_kind TEXT NOT NULL DEFAULT 'chat',
        web_search INTEGER NOT NULL DEFAULT 0,
        thinking INTEGER NOT NULL DEFAULT 0,
        temperature REAL NOT NULL,
        max_tokens INTEGER NOT NULL,
        started_at INTEGER NOT NULL,
        finished_at INTEGER,
        ttft_ms INTEGER,
        total_ms INTEGER,
        search_ms INTEGER,
        prompt_tokens INTEGER,
        completion_tokens INTEGER,
        error TEXT,
        metadata_json TEXT NOT NULL DEFAULT '{}'
      );
      CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id TEXT NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
        request_id TEXT REFERENCES requests(id) ON DELETE SET NULL,
        role TEXT NOT NULL CHECK(role IN ('user','assistant','system')),
        content TEXT NOT NULL,
        created_at INTEGER NOT NULL,
        metadata_json TEXT NOT NULL DEFAULT '{}',
        attachments_json TEXT NOT NULL DEFAULT '[]'
      );
      CREATE INDEX IF NOT EXISTS idx_chats_updated ON chats(updated_at DESC);
      CREATE INDEX IF NOT EXISTS idx_messages_chat ON messages(chat_id, id);
      CREATE INDEX IF NOT EXISTS idx_requests_chat ON requests(chat_id, started_at);
    `);
    const messageColumns = this.db.prepare("PRAGMA table_info(messages)").all();
    if (!messageColumns.some(column => column.name === "attachments_json")) {
      this.db.exec("ALTER TABLE messages ADD COLUMN attachments_json TEXT NOT NULL DEFAULT '[]'");
    }
    const chatColumns = this.db.prepare("PRAGMA table_info(chats)").all();
    if (!chatColumns.some(column => column.name === "favorite")) {
      this.db.exec("ALTER TABLE chats ADD COLUMN favorite INTEGER NOT NULL DEFAULT 0");
    }
  }

  beginRequest({ chatId, requestId, prompt, attachments = [], model, kind, webSearch, thinking, temperature, maxTokens, startedAt, metadata = {} }) {
    const now = startedAt;
    this.db.exec("BEGIN IMMEDIATE");
    try {
      this.db.prepare("INSERT OR IGNORE INTO chats (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)")
        .run(chatId, prompt.slice(0, 80) || "New chat", now, now);
      this.db.prepare("UPDATE chats SET title = CASE WHEN title = 'New chat' THEN ? ELSE title END, updated_at = ? WHERE id = ?")
        .run(this.makeTitle(prompt), now, chatId);
      this.db.prepare(`INSERT INTO requests
        (id, chat_id, status, model, request_kind, web_search, thinking, temperature, max_tokens, started_at, metadata_json)
        VALUES (?, ?, 'streaming', ?, ?, ?, ?, ?, ?, ?, ?)`)
        .run(requestId, chatId, model, kind, Number(webSearch), Number(thinking), temperature, maxTokens, now, JSON.stringify(metadata));
      this.db.prepare("INSERT INTO messages (chat_id, request_id, role, content, created_at, attachments_json) VALUES (?, ?, 'user', ?, ?, ?)")
        .run(chatId, requestId, prompt, now, JSON.stringify(attachments));
      this.db.exec("COMMIT");
    } catch (error) {
      this.db.exec("ROLLBACK");
      throw error;
    }
  }

  createChat(id, title = "New chat") {
    const now = Date.now();
    this.db.prepare("INSERT OR IGNORE INTO chats (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)")
      .run(id, String(title).trim().slice(0, 80) || "New chat", now, now);
    return this.db.prepare("SELECT id, title, created_at, updated_at FROM chats WHERE id = ?").get(id);
  }

  makeTitle(prompt) {
    const compact = String(prompt).replace(/\s+/g, " ").trim();
    if (!compact) return "Image conversation";
    let title = compact.slice(0, 60);
    if (compact.length > 60 && title.lastIndexOf(" ") > 35) title = title.slice(0, title.lastIndexOf(" "));
    title = title.replace(/[.,;:!?\s]+$/, "");
    return compact.length > 60 ? `${title}…` : title;
  }

  updateChat(id, { title, favorite }) {
    const chat = this.db.prepare("SELECT * FROM chats WHERE id = ?").get(id);
    if (!chat) return null;
    const nextTitle = title === undefined ? chat.title : String(title).replace(/\s+/g, " ").trim().slice(0, 80);
    if (!nextTitle) throw new Error("Title cannot be empty");
    const nextFavorite = favorite === undefined ? chat.favorite : Number(Boolean(favorite));
    this.db.prepare("UPDATE chats SET title = ?, favorite = ?, updated_at = ? WHERE id = ?")
      .run(nextTitle, nextFavorite, Date.now(), id);
    return this.db.prepare("SELECT id, title, favorite, created_at, updated_at FROM chats WHERE id = ?").get(id);
  }

  deleteChat(id) { return this.db.prepare("DELETE FROM chats WHERE id = ?").run(id).changes > 0; }

  finishRequest({ requestId, chatId, status, content = "", finishedAt, ttftMs = null, totalMs, searchMs = null, promptTokens = null, completionTokens = null, error = null, metadata = {} }) {
    this.db.exec("BEGIN IMMEDIATE");
    try {
      this.db.prepare(`UPDATE requests SET status = ?, finished_at = ?, ttft_ms = ?, total_ms = ?, search_ms = ?,
        prompt_tokens = ?, completion_tokens = ?, error = ?, metadata_json = ? WHERE id = ?`)
        .run(status, finishedAt, ttftMs, totalMs, searchMs, promptTokens, completionTokens, error, JSON.stringify(metadata), requestId);
      if (content) this.db.prepare("INSERT INTO messages (chat_id, request_id, role, content, created_at, metadata_json) VALUES (?, ?, 'assistant', ?, ?, ?)")
        .run(chatId, requestId, content, finishedAt, JSON.stringify({ partial: status !== "completed" }));
      this.db.prepare("UPDATE chats SET updated_at = ? WHERE id = ?").run(finishedAt, chatId);
      this.db.exec("COMMIT");
    } catch (dbError) {
      this.db.exec("ROLLBACK");
      throw dbError;
    }
  }

  listChats(limit = 50) {
    return this.db.prepare(`SELECT c.id, c.title, c.created_at, c.updated_at,
      COUNT(DISTINCT m.id) AS message_count, COUNT(DISTINCT r.id) AS request_count
      FROM chats c LEFT JOIN messages m ON m.chat_id = c.id LEFT JOIN requests r ON r.chat_id = c.id
      GROUP BY c.id ORDER BY c.favorite DESC, c.updated_at DESC LIMIT ?`).all(limit);
  }

  getChat(id) {
    const chat = this.db.prepare("SELECT * FROM chats WHERE id = ?").get(id);
    if (!chat) return null;
    return {
      ...chat,
      messages: this.db.prepare("SELECT id, request_id, role, content, created_at, metadata_json, attachments_json FROM messages WHERE chat_id = ? ORDER BY id").all(id),
      requests: this.db.prepare("SELECT * FROM requests WHERE chat_id = ? ORDER BY started_at").all(id),
    };
  }

  close() { this.db.close(); }
}
