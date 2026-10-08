import {readSpeechTiming} from './companion/speechTimeline.js';
let browserSession = null;
export function setBrowserSession(value) { browserSession = value; }
export function createApiClient({ tenantId, apiKey, consentToken }) {
  async function request(path, options = {}) {
    const method = options.method || 'GET';
    const headers = {
      'X-Tenant-Id': tenantId,
      'X-API-Key': apiKey,
      'X-Request-Id': `ui-${crypto.randomUUID()}`,
      ...(options.headers || {}),
    };
    if (browserSession) {
      delete headers['X-Tenant-Id']; delete headers['X-API-Key'];
      headers['X-CSRF-Token'] = browserSession.csrf;
    }

    if (method !== 'GET') {
      headers['Idempotency-Key'] = options.idempotencyKey || crypto.randomUUID();
      headers['X-Consent-Token'] = consentToken;
    }
    if (options.body !== undefined) {
      headers['Content-Type'] = 'application/json';
    }

    const controller = new AbortController();
    const cancel = () => controller.abort();
    if (options.signal?.aborted) cancel();
    else options.signal?.addEventListener('abort', cancel, { once: true });
    let timedOut = false;
    const timeoutId = options.timeoutMs
      ? window.setTimeout(() => { timedOut = true; controller.abort(); }, options.timeoutMs)
      : null;
    try {
      const response = await fetch(path, {
        method,
        credentials: 'same-origin',
        headers,
        body: options.formData || (options.body !== undefined ? JSON.stringify(options.body) : undefined),
        signal: controller.signal,
      });
      const contentType = response.headers.get('content-type') || '';
      const data = response.ok && options.responseType === 'blob'
        ? await response.blob()
        : contentType.includes('json') ? await response.json() : await response.text();
      if (!response.ok) {
        if (response.status === 401 && browserSession) window.dispatchEvent(new Event('medguard:session-expired'));
        const error = new Error(data?.message || data?.error_code || `HTTP ${response.status}`);
        error.status = response.status;
        error.code = data?.error_code || 'request_failed';
        error.requestId = data?.request_id || response.headers.get('X-Request-Id');
        error.details = data?.details;
        throw error;
      }
      if(options.responseType==='blob')data.motionTiming=readSpeechTiming(response.headers);
      return data;
    } catch (error) {
      if (timedOut && !options.signal?.aborted) {
        const timeoutError = new Error(`MedGuard chưa thể trả lời trong ${options.timeoutMs / 1000} giây. Vui lòng thử lại.`);
        timeoutError.code = 'response_timeout';
        throw timeoutError;
      }
      throw error;
    } finally {
      if (timeoutId !== null) window.clearTimeout(timeoutId);
      options.signal?.removeEventListener('abort', cancel);
    }

  }

  return { request };
}
