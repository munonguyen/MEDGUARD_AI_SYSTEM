// A prepared segment belongs to one approved turn/persona. Never substitute an
// unrelated prefix. A mismatching or expired ticket uses ordinary TTS instead.
export function preparedSpeechPlan(text, persona, prepared, split) {
  if (!prepared || prepared.persona !== persona || !/^[A-Za-z0-9_-]{32}$/.test(prepared.ticket || '') ||
      typeof prepared.text !== 'string' || !prepared.text || prepared.text.length > 180 ||
      !text.startsWith(prepared.text) ||
      (text.length > prepared.text.length && !/\s/.test(text[prepared.text.length]))) {
    return {chunks: split(text), ticket: null};
  }
  const rest = text.slice(prepared.text.length).trim();
  return {chunks: [prepared.text, ...split(rest)], ticket: prepared.ticket};
}

export function validateSpeechBlob(blob) {
  if (!(blob instanceof Blob) || blob.size === 0 || !/^audio\//i.test(blob.type)) {
    const error = new Error('No playable audio'); error.code = 'tts_empty_audio'; throw error;
  }
  return blob;
}

export function optionalAudioContext(create) {
  try { return create(); } catch { return null; }
}

export async function optionalLipSync(engine, context) {
  try { await engine?.prepareLipSync(context); } catch { /* audio stays available */ }
}
