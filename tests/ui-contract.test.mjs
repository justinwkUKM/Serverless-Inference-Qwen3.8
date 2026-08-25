import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const root = new URL("..", import.meta.url);

test("inference demo exposes endpoint controls, accessible feedback, and safe context defaults", async () => {
  const html = await readFile(new URL("public/index.html", root), "utf8");
  assert.match(html, /id="endpointMenu"/);
  assert.match(html, /id="healthButton"/);
  assert.match(html, /id="warmButton"/);
  assert.match(html, /id="coldButton"/);
  assert.match(html, /id="toastRegion" aria-live="polite"/);
  assert.match(html, /id="statusAnnouncements" aria-live="polite"/);
  assert.match(html, /id="maxTokens"[^>]+value="4096"/);
  assert.match(html, /id="contextBudget"/);
  assert.match(html, /id="notificationSound"/);
});

test("concurrency demo exposes shared actions, mobile navigation, and comparable metrics", async () => {
  const [html, app, css] = await Promise.all([
    readFile(new URL("public/index.html", root), "utf8"),
    readFile(new URL("public/app.js", root), "utf8"),
    readFile(new URL("public/styles.css", root), "utf8"),
  ]);
  assert.match(html, /class="concurrency-composer"[\s\S]+id="concurrencyRun"/);
  assert.match(html, /id="workerPrevious"/);
  assert.match(html, /id="workerNext"/);
  assert.match(app, /Gateway wait/);
  assert.match(app, /First-token wait/);
  assert.match(app, /selectConcurrencyWinners/);
  assert.match(css, /\.worker-metrics \.best-metric/);
  assert.match(css, /\.worker-mobile-nav/);
});

test("completion notifications are opt-in to hidden-tab behavior and user configurable", async () => {
  const [html, app] = await Promise.all([
    readFile(new URL("public/index.html", root), "utf8"),
    readFile(new URL("public/app.js", root), "utf8"),
  ]);
  assert.match(html, /id="notificationSound"[^>]+checked/);
  assert.match(app, /document\.hidden/);
  assert.match(app, /function playCompletionSound/);
  assert.match(app, /localStorage\.setItem\("notificationSound"/);
  assert.match(app, /status==="ready"&&wasActive/);
});
