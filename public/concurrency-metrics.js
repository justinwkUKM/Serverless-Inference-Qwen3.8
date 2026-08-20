export function decodeTokensPerSecond(worker) {
  const completion = Number(worker.usage?.completion_tokens || 0);
  const decodeMs = worker.finished && worker.firstToken ? worker.finished - worker.firstToken : 0;
  return completion > 0 && decodeMs > 0 ? completion / (decodeMs / 1000) : 0;
}

export function selectConcurrencyWinners(workers) {
  const successful = workers.filter(worker => worker.status === "completed" && worker.firstToken > worker.started);
  if (!successful.length) return { ttftIndex: null, tpsIndex: null };
  const ttftWinner = successful.reduce((best, worker) =>
    worker.firstToken - worker.started < best.firstToken - best.started ? worker : best
  );
  const tpsWinner = successful.reduce((best, worker) =>
    decodeTokensPerSecond(worker) > decodeTokensPerSecond(best) ? worker : best
  );
  return { ttftIndex: ttftWinner.index, tpsIndex: tpsWinner.index };
}
