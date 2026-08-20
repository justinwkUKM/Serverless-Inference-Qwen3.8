import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { createServer } from "node:http";
import { after, before, test } from "node:test";

let upstream;
let app;
let baseUrl;
let lastChatRequest;

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
  for (let attempt = 0; attempt < 50; attempt += 1) {
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
      TAVILY_API_KEY: "PASTE_TEST_PLACEHOLDER",
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
  const config = await response.json();
  assert.deepEqual(config, {
    model: "qwen3.8-27b",
    scaleDownSeconds: 300,
    configured: true,
    webSearchConfigured: false,
  });
  assert.doesNotMatch(JSON.stringify(config), /test-inference-key|VERDA_ENDPOINT/);
});

test("health request is authenticated and proxied", async () => {
  const response = await fetch(`${baseUrl}/api/status`);
  assert.equal(response.status, 200);
  const status = await response.json();
  assert.equal(status.healthy, true);
  assert.equal(status.status, 200);
});

test("chat keeps two messages, clamps settings, and streams SSE", async () => {
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
  assert.match(await response.text(), /Hello/);
  assert.deepEqual(lastChatRequest.body.messages, [
    { role: "assistant", content: "previous answer" },
    { role: "user", content: "current question" },
  ]);
  assert.equal(lastChatRequest.body.temperature, 2);
  assert.equal(lastChatRequest.body.max_tokens, 4096);
  assert.equal(lastChatRequest.body.stream, true);
  assert.equal(lastChatRequest.headers.authorization, "Bearer test-inference-key");
  assert.equal(lastChatRequest.headers["accept-encoding"], "identity");
});
