export function createApiClient({ tenantId, apiKey, consentToken, csrfToken } = {}) {
  async function request(path, options = {}) {
    const method = options.method || 'GET';
    const headers = {
      ...(apiKey ? { 'X-Tenant-Id': tenantId, 'X-API-Key': apiKey } : {}),
      'X-Request-Id': `ui-${crypto.randomUUID()}`,
      ...(options.headers || {}),
    };

    if (method !== 'GET') {
      headers['Idempotency-Key'] = options.idempotencyKey || crypto.randomUUID();
      if (consentToken) headers['X-Consent-Token'] = consentToken;
      if (csrfToken) headers['X-CSRF-Token'] = csrfToken;
    }
    if (options.body !== undefined) {
      headers['Content-Type'] = 'application/json';
    }

    const controller = options.timeoutMs ? new AbortController() : null;
    const timeoutId = controller
      ? window.setTimeout(() => controller.abort(), options.timeoutMs)
      : null;
    let response;
    try {
      response = await fetch(path, {
        method,
        credentials: 'same-origin',
        headers,
        body: options.formData || (options.body !== undefined ? JSON.stringify(options.body) : undefined),
        signal: options.signal || controller?.signal,
      });
    } catch (error) {
      if (error?.name === 'AbortError') {
        const timeoutError = new Error('MedGuard chưa thể trả lời trong 10 giây. Vui lòng thử lại.');
        timeoutError.code = 'response_timeout';
        throw timeoutError;
      }
      throw error;
    } finally {
      if (timeoutId !== null) window.clearTimeout(timeoutId);
    }
    const contentType = response.headers.get('content-type') || '';
    const data = [204, 205].includes(response.status) ? null : contentType.includes('json') ? await response.json() : await response.text();
    if (!response.ok) {
      if (response.status === 401 && path !== '/v1/auth/login' && path !== '/v1/auth/me') window.dispatchEvent(new Event('medguard:session-expired'));
      const error = new Error(data?.message || data?.error_code || `HTTP ${response.status}`);
      error.status = response.status;
      error.code = data?.error_code || 'request_failed';
      error.requestId = data?.request_id || response.headers.get('X-Request-Id');
      error.details = data?.details;
      throw error;
    }
    return data;
  }

  return { request };
}
