import { useState } from 'react';
import { Field, FormSection, SelectInput, SubmitButton, TextArea, TextInput } from '../components';

const parseJson = (value, label, expectedType) => {
  let parsed;
  try {
    parsed = JSON.parse(value);
  } catch {
    throw new Error(`${label} không phải JSON hợp lệ.`);
  }
  const valid = expectedType === 'array' ? Array.isArray(parsed) : parsed && typeof parsed === 'object' && !Array.isArray(parsed);
  if (!valid) throw new Error(`${label} phải là ${expectedType === 'array' ? 'một mảng JSON' : 'một JSON object'}.`);
  return parsed;
};

export function IntegrationModule({ execute, busy }) {
  const [mode, setMode] = useState('fhir');
  const [patientRef, setPatientRef] = useState('BN-FHIR-001');
  const [medications, setMedications] = useState('[{"name":"Amoxicillin 500mg","active_ingredient":"amoxicillin","strength":"500mg"}]');
  const [observations, setObservations] = useState('[{"indicator":"heart_rate","value":78,"unit":"bpm"}]');
  const [eventName, setEventName] = useState('clinical.result.ready');
  const [channel, setChannel] = useState('webhook');
  const [target, setTarget] = useState('bookingcare-clinical-api');
  const [body, setBody] = useState('{"patient_ref":"BN-FHIR-001","status":"ready"}');
  const [validationError, setValidationError] = useState('');
  const submit = (event) => {
    event.preventDefault();
    setValidationError('');
    try {
      if (mode === 'fhir') {
        execute('/v1/fhir/export', { method: 'POST', body: {
          patient_ref: patientRef,
          medications: parseJson(medications, 'MedicationRequest', 'array'),
          observations: parseJson(observations, 'Observation', 'array'),
        } }, `FHIR ${patientRef}`);
      } else {
        execute('/v1/result-delivery/prepare', { method: 'POST', body: {
          event_name: eventName, channel, target_ref: target || null, body: parseJson(body, 'Payload', 'object'),
        } }, `Delivery ${eventName}`);
      }
    } catch (error) {
      setValidationError(error.message);
    }
  };
  return <form onSubmit={submit} className="task-form">
    <div className="segmented" role="tablist">
      <button type="button" className={mode === 'fhir' ? 'active' : ''} onClick={() => { setMode('fhir'); setValidationError(''); }}>FHIR R4</button>
      <button type="button" className={mode === 'delivery' ? 'active' : ''} onClick={() => { setMode('delivery'); setValidationError(''); }}>Result delivery</button>
    </div>
    {mode === 'fhir' ? <FormSection title="FHIR Bundle">
      <Field label="Mã bệnh nhân"><TextInput required value={patientRef} onChange={(e) => setPatientRef(e.target.value)} /></Field>
      <Field label="MedicationRequest"><TextArea className="mono-control" rows="6" value={medications} onChange={(e) => setMedications(e.target.value)} /></Field>
      <Field label="Observation"><TextArea className="mono-control" rows="5" value={observations} onChange={(e) => setObservations(e.target.value)} /></Field>
    </FormSection> : <FormSection title="Delivery envelope">
      <Field label="Tên sự kiện"><TextInput required value={eventName} onChange={(e) => setEventName(e.target.value)} /></Field>
      <Field label="Kênh"><SelectInput value={channel} onChange={(e) => setChannel(e.target.value)}><option value="webhook">Webhook</option><option value="sse">SSE</option><option value="notification">Notification</option></SelectInput></Field>
      <Field label="Đích nhận"><TextInput value={target} onChange={(e) => setTarget(e.target.value)} /></Field>
      <Field label="Payload"><TextArea className="mono-control" rows="7" value={body} onChange={(e) => setBody(e.target.value)} /></Field>
    </FormSection>}
    {validationError && <div className="inline-error" role="alert">{validationError}</div>}
    <SubmitButton busy={busy}>{mode === 'fhir' ? 'Xuất FHIR Bundle' : 'Tạo envelope'}</SubmitButton>
  </form>;
}
