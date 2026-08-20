import assert from "node:assert/strict";
import test from "node:test";
import { decodeTokensPerSecond, selectConcurrencyWinners } from "../public/concurrency-metrics.js";

const worker = (index, status, started, firstToken, finished, completionTokens) => ({
  index, status, started, firstToken, finished, usage: { completion_tokens: completionTokens },
});

test("selects the lowest successful TTFT and highest decode throughput independently", () => {
  const workers = [
    worker(0, "completed", 0, 900, 1900, 100),
    worker(1, "completed", 0, 500, 2500, 500),
    worker(2, "completed", 0, 700, 1200, 300),
    worker(3, "completed", 0, 800, 1800, 80),
  ];
  assert.deepEqual(selectConcurrencyWinners(workers), { ttftIndex: 1, tpsIndex: 2 });
  assert.equal(decodeTokensPerSecond(workers[2]), 600);
});

test("excludes failed and cancelled workers from best-metric comparison", () => {
  const workers = [
    worker(0, "completed", 0, 700, 1700, 100),
    worker(1, "failed", 0, 100, 200, 1000),
    worker(2, "cancelled", 0, 50, 100, 1000),
    worker(3, "completed", 0, 900, 1400, 200),
  ];
  assert.deepEqual(selectConcurrencyWinners(workers), { ttftIndex: 0, tpsIndex: 3 });
});

test("returns no winners when no worker completed", () => {
  assert.deepEqual(selectConcurrencyWinners([
    worker(0, "failed", 0, 0, 100, 0),
    worker(1, "cancelled", 0, 0, 100, 0),
  ]), { ttftIndex: null, tpsIndex: null });
});
