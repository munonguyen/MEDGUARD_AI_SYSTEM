// Only enqueue a final, safety-checked answer. Never speak an unverified draft.
export function splitSpeech(text, maxChars = 360) {
  const clean = text.trim();
  if (!clean) return [];
  const sentences = typeof Intl.Segmenter === 'function'
    ? [...new Intl.Segmenter('vi', { granularity: 'sentence' }).segment(clean)].map(s => s.segment.trim())
    : clean.split(/(?<=[.!?])\s+(?=[\p{Lu}\d])/u);
  const chunks = [];
  for (const sentence of sentences) {
    let remaining = sentence;
    while (remaining.length > maxChars) {
      const boundary = remaining.lastIndexOf(' ', maxChars);
      const cut = boundary > 0 ? boundary : maxChars;
      chunks.push(remaining.slice(0, cut));
      remaining = remaining.slice(cut).trimStart();
    }
    if (remaining) chunks.push(remaining);
  }
  // Keep the first sentence separate; group later short sentences to avoid
  // unnecessary provider calls. The text, including warnings, is never dropped.
  const grouped = [];
  for (const chunk of chunks) {
    const last = grouped.length - 1;
    if (last > 0 && grouped[last].length + chunk.length + 1 <= maxChars) grouped[last] += ' ' + chunk;
    else grouped.push(chunk);
  }
  return grouped;
}

export async function runSpeechQueue(chunks, { synthesize, play, signal }) {
  const active = () => { if (signal.aborted) throw new DOMException('Cancelled', 'AbortError'); };
  // Turn rejection into a value immediately: a prefetched request can fail
  // while the previous audio is playing without an unhandled rejection.
  const prepare = text => Promise.resolve().then(() => { active(); return synthesize(text); })
    .then(blob => ({ blob }), error => ({ error }));
  active();
  let pending = chunks.length ? prepare(chunks[0]) : null;
  for (let index = 0; index < chunks.length; index++) {
    const next = index + 1 < chunks.length ? prepare(chunks[index + 1]) : null;
    const result = await pending;
    active();
    if (result.error) throw result.error;
    await play(result.blob, chunks[index], index);
    active();
    pending = next;
  }
}
