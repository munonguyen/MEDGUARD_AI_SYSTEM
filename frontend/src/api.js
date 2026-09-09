export function createApiClient({ tenantId, apiKey, consentToken }) {
  async function request(path, options = {}) {
    const method = options.method || 'GET';
    const headers = {
      'X-Tenant-Id': tenantId,
      'X-API-Key': apiKey,
      'X-Request-Id': `ui-${crypto.randomUUID()}`,
      ...(options.headers || {}),
    };

    if (method !== 'GET') {
      headers['Idempotency-Key'] = options.idempotencyKey || crypto.randomUUID();
      headers['X-Consent-Token'] = consentToken;
    }
    if (options.body !== undefined) {
      headers['Content-Type'] = 'application/json';
    }

    const response = await fetch(path, {
      method,
      headers,
      body: options.formData || (options.body !== undefined ? JSON.stringify(options.body) : undefined),
    });
    const contentType = response.headers.get('content-type') || '';
    const data = contentType.includes('json') ? await response.json() : await response.text();
    if (!response.ok) {
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
