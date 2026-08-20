import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { createServer } from "node:http";
import { after, before, test } from "node:test";

let upstream;
let app;
let baseUrl;
let lastChatRequest;
let lastSearchRequest;
let persistedChatId;
let upstreamCancelled;
let resolveUpstreamCancelled;

function listen(server) {
  return new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => resolve(server.address().port));
  });
}

function close(server) {
  return new Promise(resolve => server?.close(resolve));
}

async function waitForServer(url) {
  for (let attempt = 0; attempt < 150; attempt += 1) {
    try {
      const response = await fetch(url);
      if (response.ok) return;
    } catch {
      // The child process is still starting.
    }
    await new Promise(resolve => setTimeout(resolve, 50));
  }
  throw new Error("Quicksilver test server did not start");
}

before(async () => {
  upstream = createServer(async (req, res) => {
    if (req.url === "/search" && req.method === "POST") {
      const chunks = [];
      for await (const chunk of req) chunks.push(chunk);
      lastSearchRequest = JSON.parse(Buffer.concat(chunks).toString("utf8"));
      res.writeHead(200, { "Content-Type": "application/json" });
      return res.end(JSON.stringify({ results: [{
        title: "Cities and towns in Malaysia",
        url: "https://example.test/malaysia-cities",
        content: "Kuala Lumpur is Malaysia's national capital, while Putrajaya is its administrative centre.",
      }] }));
    }
    if (req.url === "/health") {
      assert.equal(req.headers.authorization, "Bearer test-inference-key");
      res.writeHead(200, { "Content-Type": "text/plain" });
      return res.end("ok");
    }
    if (req.url === "/v1/chat/completions" && req.method === "POST") {
      const chunks = [];
      for await (const chunk of req) chunks.push(chunk);
      lastChatRequest = {
        headers: req.headers,
        body: JSON.parse(Buffer.concat(chunks).toString("utf8")),
      };
      res.writeHead(200, { "Content-Type": "text/event-stream" });
      if (lastChatRequest.body.messages.at(-1)?.content === "cancel-stream") {
        res.write('data: {"choices":[{"delta":{"content":"Partial"}}]}\n\n');
        const timer = setInterval(() => res.write(': keepalive\n\n'), 25);
        res.once("close", () => {
          clearInterval(timer);
          resolveUpstreamCancelled?.();
        });
        return;
      }
      res.write('data: {"choices":[{"delta":{"content":"Hello"}}]}\n\n');
      res.write('data: {"usage":{"prompt_tokens":4,"completion_tokens":1},"choices":[]}\n\n');
      return res.end("data: [DONE]\n\n");
    }
    res.writeHead(404).end();
  });
  const upstreamPort = await listen(upstream);

  const portProbe = createServer();
  const appPort = await listen(portProbe);
  await close(portProbe);
  baseUrl = `http://127.0.0.1:${appPort}`;
  app = spawn(process.execPath, ["server.mjs"], {
    cwd: new URL("..", import.meta.url),
    env: {
      ...process.env,
      HOST: "127.0.0.1",
      PORT: String(appPort),
      VERDA_ENDPOINT: `http://127.0.0.1:${upstreamPort}`,
      VERDA_INFERENCE_KEY: "test-inference-key",
      TAVILY_API_KEY: "test-tavily-key",
      TAVILY_ENDPOINT: `http://127.0.0.1:${upstreamPort}/search`,
      QUICKSILVER_DB_PATH: ":memory:",
    },
    stdio: ["ignore", "pipe", "pipe"],
  });
  await waitForServer(`${baseUrl}/api/config`);
});

after(async () => {
  app?.kill("SIGTERM");
  await close(upstream);
});

test("public configuration reports capabilities without leaking secrets", async () => {
  const response = await fetch(`${baseUrl}/api/config`);
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-security-policy"), /default-src 'self'/);
  assert.equal(response.headers.get("x-content-type-options"), "nosniff");
  assert.equal(response.headers.get("x-frame-options"), "DENY");
  const config = await response.json();
  assert.deepEqual(config, {
    model: "qwen3.8-27b",
    scaleDownSeconds: 300,
    configured: true,
    webSearchConfigured: true,
  });
  assert.doesNotMatch(JSON.stringify(config), /test-inference-key|VERDA_ENDPOINT/);
});

test("new empty chats are created immediately and listed", async () => {
  const id = "sidebar-chat-1234";
  const createdResponse = await fetch(`${baseUrl}/api/chats`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id }),
  });
  assert.equal(createdResponse.status, 201);
  assert.equal((await createdResponse.json()).id, id);
  const { chats } = await fetch(`${baseUrl}/api/chats`).then(response => response.json());
  assert.ok(chats.some(chat => chat.id === id && chat.message_count === 0));
});

test("chats can be renamed, favorited, and deleted", async () => {
  const id = "managed-chat-1234";
  await fetch(`${baseUrl}/api/chats`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ id }),
  });
  const updatedResponse = await fetch(`${baseUrl}/api/chats/${id}`, {
    method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title: "Important research", favorite: true }),
  });
  assert.equal(updatedResponse.status, 200);
  const updated = await updatedResponse.json();
  assert.equal(updated.title, "Important research");
  assert.equal(updated.favorite, 1);
  const { chats } = await fetch(`${baseUrl}/api/chats`).then(response => response.json());
  assert.equal(chats[0].id, id);
  assert.equal((await fetch(`${baseUrl}/api/chats/${id}`, { method: "DELETE" })).status, 200);
  assert.equal((await fetch(`${baseUrl}/api/chats/${id}`)).status, 404);
});

test("the first prompt automatically titles an empty chat", async () => {
  const id = "auto-title-chat-1234";
  await fetch(`${baseUrl}/api/chats`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ id }),
  });
  const response = await fetch(`${baseUrl}/api/chat`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chat_id: id, messages: [{ role: "user", content: "Plan a resilient multilingual inference service with observability and sensible safeguards" }] }),
  });
  await response.text();
  const chat = await fetch(`${baseUrl}/api/chats/${id}`).then(result => result.json());
  assert.equal(chat.title, "Plan a resilient multilingual inference service with…");
});

test("health request is authenticated and proxied", async () => {
  const response = await fetch(`${baseUrl}/api/status`);
  assert.equal(response.status, 200);
  const status = await response.json();
  assert.equal(status.healthy, true);
  assert.equal(status.status, 200);
});

test("chat keeps bounded conversational history, clamps settings, and streams SSE", async () => {
  const response = await fetch(`${baseUrl}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      messages: [
        { role: "user", content: "discard me" },
        { role: "assistant", content: "previous answer" },
        { role: "user", content: "current question" },
      ],
      temperature: 99,
      max_tokens: 99999,
    }),
  });
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type"), /text\/event-stream/);
  const stream = await response.text();
  assert.match(stream, /Hello/);
  assert.match(stream, /server_metrics/);
  persistedChatId = JSON.parse(stream.split("\n").find(line => line.includes('"chat_id"')).slice(6)).chat_id;
  assert.match(lastChatRequest.body.messages[0].content, /conversational assistant/i);
  assert.deepEqual(lastChatRequest.body.messages.slice(1), [
    { role: "user", content: "discard me" },
    { role: "assistant", content: "previous answer" },
    { role: "user", content: "current question" },
  ]);
  assert.equal(lastChatRequest.body.temperature, 2);
  assert.equal(lastChatRequest.body.max_tokens, 20480);
  assert.equal(lastChatRequest.body.stream, true);
  assert.equal(lastChatRequest.headers.authorization, "Bearer test-inference-key");
  assert.equal(lastChatRequest.headers["accept-encoding"], "identity");
});

test("conversation context is bounded to the latest twelve user/assistant messages", async () => {
  const messages = Array.from({ length: 14 }, (_, index) => ({
    role: index % 2 ? "assistant" : "user",
    content: `message-${index}`,
  }));
  const response = await fetch(`${baseUrl}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ messages }),
  });
  assert.equal(response.status, 200);
  await response.text();
  assert.equal(lastChatRequest.body.messages.length, 13);
  assert.equal(lastChatRequest.body.messages[1].content, "message-2");
  assert.equal(lastChatRequest.body.messages.at(-1).content, "message-13");
});

test("oversized history is truncated while preserving the newest user message", async () => {
  const messages = [
    { role: "user", content: "old ".repeat(80000) },
    { role: "assistant", content: "older ".repeat(80000) },
    { role: "user", content: "another old ".repeat(50000) },
    { role: "assistant", content: "another older answer" },
    { role: "user", content: "current question" },
  ];
  const response = await fetch(`${baseUrl}/api/chat`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ messages, max_tokens: 20480 }) });
  assert.equal(response.status, 200);
  const body = await response.text();
  assert.equal(lastChatRequest.body.messages.at(-1).content, "current question");
  assert.equal(lastChatRequest.body.messages.some(message => typeof message.content === "string" && message.content.startsWith("old old")), false);
  assert.match(body, /"omitted_messages":[1-9]/);
});

test("disabled history sends no prior context and writes nothing to SQLite", async () => {
  const chatId = "temporary-private-chat";
  const response = await fetch(`${baseUrl}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      chat_id: chatId,
      history_enabled: false,
      messages: [
        { role: "user", content: "private earlier message" },
        { role: "assistant", content: "private earlier answer" },
        { role: "user", content: "private current message" },
      ],
    }),
  });
  assert.equal(response.status, 200);
  await response.text();
  assert.equal(lastChatRequest.body.messages.length, 2);
  assert.equal(lastChatRequest.body.messages[1].content, "private current message");
  assert.equal((await fetch(`${baseUrl}/api/chats/${chatId}`)).status, 404);
});

test("multilingual text and image content blocks reach the model and SQLite", async () => {
  const chatId = "multilingual-image-chat";
  const imageUrl = "data:image/png;base64,iVBORw0KGgo=";
  const response = await fetch(`${baseUrl}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      chat_id: chatId,
      messages: [{ role: "user", content: [
        { type: "text", text: "你好 · مرحبا · नमस्ते · こんにちは" },
        { type: "image_url", image_url: { url: imageUrl } },
      ] }],
    }),
  });
  assert.equal(response.status, 200);
  await response.text();
  assert.deepEqual(lastChatRequest.body.messages.at(-1).content[0], { type: "text", text: "你好 · مرحبا · नमस्ते · こんにちは" });
  assert.equal(lastChatRequest.body.messages.at(-1).content[1].image_url.url, imageUrl);
  const detail = await fetch(`${baseUrl}/api/chats/${chatId}`).then(result => result.json());
  assert.equal(detail.messages[0].content, "你好 · مرحبا · नमस्ते · こんにちは");
  assert.deepEqual(JSON.parse(detail.messages[0].attachments_json), [imageUrl]);
});

test("text documents are extracted, forwarded, and persisted", async () => {
  const chatId = "document-context-chat";
  const documentData = `data:text/plain;base64,${Buffer.from("Quicksilver launch code is MERCURY-42. The owner is Amina.").toString("base64")}`;
  const document = { name: "project notes.txt", mime_type: "text/plain", data: documentData };
  const response = await fetch(`${baseUrl}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      chat_id: chatId,
      messages: [{ role: "user", content: [
        { type: "text", text: "What is the launch code?" },
        { type: "document", document },
      ] }],
    }),
  });
  assert.equal(response.status, 200);
  await response.text();
  const forwarded = lastChatRequest.body.messages.at(-1).content;
  assert.equal(forwarded[0].text, "What is the launch code?");
  assert.match(forwarded[1].text, /<attached_document name="project notes.txt">/);
  assert.match(forwarded[1].text, /MERCURY-42/);
  const detail = await fetch(`${baseUrl}/api/chats/${chatId}`).then(result => result.json());
  assert.deepEqual(JSON.parse(detail.messages[0].attachments_json), [{ type: "document", document }]);
  assert.equal(JSON.parse(detail.requests[0].metadata_json).document_count, 1);
});

test("web search expands terse follow-ups with conversational context", async () => {
  const response = await fetch(`${baseUrl}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      web_search: true,
      messages: [
        { role: "user", content: "List important cities and towns in Malaysia." },
        { role: "assistant", content: "Here are major Malaysian cities organized by state." },
        { role: "user", content: "Write one accurate fact about each city." },
        { role: "assistant", content: "Some of those facts need correction." },
        { role: "user", content: "try again" },
      ],
    }),
  });
  assert.equal(response.status, 200);
  const stream = await response.text();
  assert.match(lastSearchRequest.query, /Current follow-up: try again/i);
  assert.match(lastSearchRequest.query, /Previous user request: Write one accurate fact/i);
  assert.match(lastSearchRequest.query, /Malaysia|Malaysian/i);
  assert.doesNotMatch(lastSearchRequest.query, /^try again$/i);
  assert.match(stream, /Cities and towns in Malaysia/);
  assert.match(lastChatRequest.body.messages[1].content, /exact form \[1\]\(URL\)/);
});

test("completed chats, messages, and inference metrics are persisted", async () => {
  const listResponse = await fetch(`${baseUrl}/api/chats`);
  assert.equal(listResponse.status, 200);
  const { chats } = await listResponse.json();
  const persistedChat = chats.find(chat => chat.id === persistedChatId);
  assert.ok(persistedChat);
  assert.equal(persistedChat.message_count, 2);

  const detailResponse = await fetch(`${baseUrl}/api/chats/${persistedChatId}`);
  assert.equal(detailResponse.status, 200);
  const detail = await detailResponse.json();
  assert.deepEqual(detail.messages.map(message => message.role), ["user", "assistant"]);
  assert.equal(detail.messages[1].content, "Hello");
  assert.equal(detail.requests[0].status, "completed");
  assert.equal(detail.requests[0].prompt_tokens, 4);
  assert.equal(detail.requests[0].completion_tokens, 1);
  assert.ok(detail.requests[0].total_ms >= 0);
});

test("client cancellation closes the upstream generation stream", async () => {
  upstreamCancelled = new Promise(resolve => { resolveUpstreamCancelled = resolve; });
  const controller = new AbortController();
  const response = await fetch(`${baseUrl}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    signal: controller.signal,
    body: JSON.stringify({ messages: [{ role: "user", content: "cancel-stream" }] }),
  });
  assert.equal(response.status, 200);
  controller.abort();
  await Promise.race([
    upstreamCancelled,
    new Promise((_, reject) => setTimeout(() => reject(new Error("Upstream stream was not cancelled")), 1000)),
  ]);
  let cancelled;
  for (let attempt = 0; attempt < 20; attempt += 1) {
    const { chats } = await fetch(`${baseUrl}/api/chats`).then(response => response.json());
    const cancelledChat = chats.find(chat => chat.title === "cancel-stream");
    if (cancelledChat) {
      const detail = await fetch(`${baseUrl}/api/chats/${cancelledChat.id}`).then(response => response.json());
      cancelled = detail.requests[0];
      if (cancelled?.status === "cancelled") break;
    }
    await new Promise(resolve => setTimeout(resolve, 10));
  }
  assert.equal(cancelled?.status, "cancelled");
  assert.ok(cancelled.total_ms >= 0);
});
