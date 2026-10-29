// Provider times are seconds relative to THIS audio segment, never wall time.
// Missing/invalid timings keep the existing media-clock estimate available.
const finite = n => typeof n === 'number' && Number.isFinite(n);
export function normalizeSpeechTiming(value) {
  if (!value || typeof value !== 'object') return null;
  const clean = list => Array.isArray(list) ? list.slice(0, 4000).filter(c =>
    finite(c?.start) && finite(c?.end) && c.start >= 0 && c.end > c.start
  ).map(c => ({start:c.start,end:c.end,text:String(c.text||''),viseme:String(c.viseme||'')}))
    .sort((a,b)=>a.start-b.start) : [];
  const phrases=clean(value.phrases),visemes=clean(value.visemes);
  return phrases.length || visemes.length ? {phrases,visemes} : null;
}
export function activeSpeechCue(cues,time) {
  if (!finite(time) || time < 0) return null;
  // Later cues win overlaps; never hold the final mouth across silence.
  let cue=null;
  for(const c of cues||[]) { if(c.start>time)break; if(time<c.end)cue=c; }
  return cue;
}
export function readSpeechTiming(headers) {
  try { return normalizeSpeechTiming(JSON.parse(headers.get('X-MedGuard-Speech-Timing')||'null')); }
  catch { return null; }
}
