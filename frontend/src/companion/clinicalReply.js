// Render the existing safety-checked response contract, never invent a reply.
export function clinicalReply(data) {
  if (typeof data?.spoken_reply === 'string' && data.spoken_reply.trim()) return data.spoken_reply.trim();
  const answer = data?.answer;
  const narrative = answer?.narrative?.map(b => b.text).filter(Boolean) || [];
  const base = data?.verification_status === 'verified' && narrative.length
    ? narrative.join('\n\n') : data?.reply || answer?.summary || answer?.clinical_advice || '';
  const parts = base ? [base] : [];
  for (const text of [
    ...(answer?.next_steps || []), ...(answer?.safety_notes || []),
    ...(answer?.display_questions || answer?.questions || []),
  ]) {
    if (typeof text === 'string' && text.trim() && !parts.some(p => p.includes(text.trim()))) parts.push(text.trim());
  }
  return parts.join('\n\n') || 'Chưa nhận được nội dung tư vấn. Bạn vui lòng thử lại.';
}

export function verificationNotice(data) {
  const status = data?.verification_status;
  if (status === 'verified') return 'Câu trả lời đã qua kiểm tra của hệ thống.';
  if (status === 'shadow_pending') return 'Đang kiểm tra câu trả lời AI. Nội dung hiện tại dựa trên quy tắc.';
  if (['unavailable', 'timed_out', 'error', 'rejected', 'circuit_open'].includes(status)) {
    return 'AI chưa trả lời được; đang dùng quy tắc. Kiểm tra kết nối AI trong Cài đặt.';
  }
  return 'Nội dung dựa trên quy tắc hỗ trợ y tế của hệ thống.';
}

function delay(ms, signal) {
  return new Promise((resolve, reject) => {
    const abort = () => {clearTimeout(timer); reject(new DOMException('Cancelled', 'AbortError'));};
    const timer = setTimeout(() => {signal.removeEventListener('abort', abort); resolve();}, ms);
    if (signal.aborted) abort(); else signal.addEventListener('abort', abort, {once:true});
  });
}

export async function awaitReviewedReply(data, fetchHistory, {signal, maxWaitMs=30000, intervalMs=2000}) {
  if (data.verification_status !== 'shadow_pending' || !data.request_id) return null;
  const deadline = Date.now() + maxWaitMs;
  let failures = 0;
  while (Date.now() < deadline) {
    await delay(Math.min(intervalMs, deadline - Date.now()), signal);
    if (Date.now() >= deadline) break;
    try {
      const history = await fetchHistory();
      const message = history.messages?.find(m => m.role === 'assistant' && m.request_id === data.request_id);
      if (message && message.verification_status !== 'shadow_pending') return {...message, reply:message.content};
      failures = 0;
    } catch (error) {
      if (signal.aborted || error?.name === 'AbortError') throw error;
      if (++failures >= 2) return null;
    }
  }
  return null;
}
