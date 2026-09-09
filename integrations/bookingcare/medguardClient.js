/**
 * MedGuard AI Client for BookingCare (Node.js 18+)
 *
 * Implements:
 * - Principle P1: Thin adapter without heavy dependencies (uses global fetch).
 * - Principle P4: Fail-closed fallback and error handling.
 * - Multi-tenancy: Injects X-API-Key and X-Tenant-Id headers.
 * - Idempotency: Auto-generates UUIDv4 Idempotency-Key.
 * - Security: HMAC-SHA256 signature verification for prescription webhooks.
 */

const crypto = require("crypto");

class MedGuardClient {
  /**
   * @param {Object} options
   * @param {string} options.baseUrl - Base URL of MedGuard AI service (e.g. 'https://medguard.internal/v1')
   * @param {string} options.apiKey - Tenant API Key
   * @param {string} options.tenantId - Tenant Identifier (e.g. 'tenant-bookingcare')
   * @param {number} [options.timeoutMs=5000] - Request timeout in milliseconds
   * @param {string} [options.webhookSecret] - Shared HMAC secret for verifying webhooks
   */
  constructor(options) {
    if (!options.baseUrl || !options.apiKey || !options.tenantId) {
      throw new Error("MedGuardClient requires baseUrl, apiKey, and tenantId.");
    }
    this.baseUrl = options.baseUrl.replace(/\/+$/, "");
    this.apiKey = options.apiKey;
    this.tenantId = options.tenantId;
    this.timeoutMs = options.timeoutMs || 5000;
    this.webhookSecret = options.webhookSecret || "";
  }

  /**
   * Generate UUIDv4 for Idempotency-Key
   */
  _generateIdempotencyKey() {
    return crypto.randomUUID();
  }

  /**
   * Base request wrapper with timeout and error mapping
   */
  async _request(endpoint, method = "GET", body = null, extraHeaders = {}) {
    const url = `${this.baseUrl}${endpoint}`;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), this.timeoutMs);

    const headers = {
      "X-API-Key": this.apiKey,
      "X-Tenant-Id": this.tenantId,
      "Content-Type": "application/json",
      ...extraHeaders,
    };

    if (method === "POST" && !headers["Idempotency-Key"]) {
      headers["Idempotency-Key"] = this._generateIdempotencyKey();
    }

    try {
      const response = await fetch(url, {
        method,
        headers,
        body: body ? JSON.stringify(body) : null,
        signal: controller.signal,
      });

      const data = await response.json();

      if (!response.ok) {
        const error = new Error(data.message || `MedGuard API Error: ${response.status}`);
        error.status = response.status;
        error.code = data.error_code || "MEDGUARD_ERROR";
        error.details = data.details || {};
        error.requestId = data.request_id || response.headers.get("x-request-id");
        throw error;
      }

      return data;
    } catch (err) {
      if (err.name === "AbortError") {
        const timeoutErr = new Error(`MedGuard request to ${endpoint} timed out after ${this.timeoutMs}ms`);
        timeoutErr.code = "TIMEOUT";
        timeoutErr.status = 504;
        throw timeoutErr;
      }
      throw err;
    } finally {
      clearTimeout(timeout);
    }
  }

  /**
   * 1. Symptom Triage & ESI Classification
   * @param {Object} params
   * @param {string} params.symptomsText - Patient complaints in Vietnamese
   * @param {string} params.patientRef - Pseudonymous patient ID
   * @param {number} [params.age]
   * @param {string} [params.sex]
   * @param {Object} [params.vitals]
   * @param {string} [params.consentToken] - Proof of patient AI consent
   */
  async triage(params) {
    const headers = {};
    if (params.consentToken) {
      headers["X-Consent-Token"] = params.consentToken;
    }

    return this._request(
      "/triage",
      "POST",
      {
        patient_ref: params.patientRef,
        symptoms_text: params.symptomsText,
        age: params.age,
        sex: params.sex,
        vital_signs: params.vitals || null,
      },
      headers
    );
  }

  /**
   * 2. Medication Safety Check (Interactions + Allergies + Duplications)
   * @param {Object} params
   * @param {string} params.patientRef
   * @param {Array} params.currentMedications
   * @param {Array} params.proposedMedications
   * @param {Array} [params.allergies]
   * @param {Array} [params.conditions]
   */
  async checkMedicationSafety(params) {
    return this._request("/medication/safety-check", "POST", {
      patient_ref: params.patientRef,
      current_medications: params.currentMedications || [],
      proposed_medications: params.proposedMedications || [],
      allergies: params.allergies || [],
      conditions: params.conditions || [],
    });
  }

  /**
   * 3. Poll Prescription OCR Job Status
   * @param {string} jobId
   */
  async getJobStatus(jobId) {
    return this._request(`/jobs/${encodeURIComponent(jobId)}`, "GET");
  }

  /**
   * 4. Verify Webhook HMAC-SHA256 Signature
   * @param {string} rawBody - Exact raw HTTP request body string
   * @param {string} signature - Hex signature from X-MedGuard-Signature header
   * @param {number} timestamp - Unix timestamp from X-MedGuard-Timestamp header
   * @param {number} [toleranceSeconds=300] - Replay attack prevention window
   * @returns {boolean}
   */
  verifyWebhookSignature(rawBody, signature, timestamp, toleranceSeconds = 300) {
    if (!this.webhookSecret || !signature || !timestamp) {
      return false;
    }

    const now = Math.floor(Date.now() / 1000);
    if (Math.abs(now - timestamp) > toleranceSeconds) {
      return false; // Replay attack prevention
    }

    const payloadToSign = `${timestamp}.${rawBody}`;
    const expected = crypto
      .createHmac("sha256", this.webhookSecret)
      .update(payloadToSign)
      .digest("hex");

    return crypto.timingSafeEqual(Buffer.from(signature), Buffer.from(expected));
  }
}

module.exports = MedGuardClient;
