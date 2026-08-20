#!/usr/bin/env node

const endpoint = process.env.QUICKSILVER_ENDPOINT || process.env.STARK_ENDPOINT || "http://127.0.0.1:4173";
const cases = [
  {
    name: "current fact",
    prompt: "Who is the current Prime Minister of Malaysia? Answer briefly and cite reliable web sources.",
  },
  {
    name: "factual correction",
    prompt: "Fact-check these claims: Langkawi is in Penang, and the Kapuas River is in Sarawak. Correct them and cite reliable web sources.",
  },
];

async function run(testCase) {
  const started = performance.now();
  const response = await fetch(`${endpoint}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      messages: [{ role: "user", content: testCase.prompt }],
      // Leave enough room for the answer and its source URLs. A 256-token cap
      // can truncate a correct answer before the citations are emitted.
      max_tokens: 512,
      temperature: 0,
      enable_thinking: false,
      web_search: true,
    }),
  });
  if (!response.ok) throw new Error(`${testCase.name}: HTTP ${response.status} ${await response.text()}`);

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let answer = "";
  let firstTokenAt = 0;
  let sources = [];
  let searchMs = 0;
  let usage = {};
  let sawDone = false;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";
    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      const data = line.slice(6).trim();
      if (data === "[DONE]") { sawDone = true; continue; }
      if (!data) continue;
      const chunk = JSON.parse(data);
      if (chunk.sources) {
        sources = chunk.sources;
        searchMs = chunk.search_ms || 0;
        continue;
      }
      if (chunk.usage) usage = chunk.usage;
      for (const choice of chunk.choices || []) {
        const text = choice.delta?.content || choice.delta?.reasoning || choice.delta?.reasoning_content || "";
        if (text && !firstTokenAt) firstTokenAt = performance.now();
        answer += text;
      }
    }
  }

  const finished = performance.now();
  const citedSources = sources.filter(source => {
    const numberedCitation = new RegExp(`\\[${source.id}\\](?:\\([^)]*\\))?`);
    return answer.includes(source.url) || numberedCitation.test(answer);
  });
  const completionTokens = usage.completion_tokens || 0;
  const generationMs = Math.max(1, finished - firstTokenAt);
  const result = {
    name: testCase.name,
    passed: Boolean(firstTokenAt && sawDone && sources.length && citedSources.length),
    sources: sources.length,
    cited_sources: citedSources.length,
    search_seconds: Number((searchMs / 1000).toFixed(3)),
    ttft_seconds: Number(((firstTokenAt - started) / 1000).toFixed(3)),
    total_seconds: Number(((finished - started) / 1000).toFixed(3)),
    completion_tokens: completionTokens,
    output_tokens_per_second: Number((completionTokens / (generationMs / 1000)).toFixed(2)),
    stream_completed: sawDone,
  };
  return { result, answer, sources };
}

let failures = 0;
for (const testCase of cases) {
  const output = await run(testCase);
  console.log(JSON.stringify(output, null, 2));
  if (!output.result.passed) failures += 1;
}
if (failures) process.exitCode = 1;
