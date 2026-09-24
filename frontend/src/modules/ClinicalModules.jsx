import { useState } from 'react';
import { AddButton, Field, FormSection, RemoveButton, SelectInput, SubmitButton, TextArea, TextInput } from '../components';

const splitList = (value) => value.split(',').map((item) => item.trim()).filter(Boolean);
const nowIso = (offsetHours = 0) => {
  const date = new Date(Date.now() + offsetHours * 3600000);
  date.setSeconds(0, 0);
  return date.toISOString().slice(0, 16);
};

export function TriageModule({ execute, busy }) {
  const [form, setForm] = useState({
    patient_ref: 'BN-TRIAGE-001', symptoms_text: 'Đau ngực lan cánh tay trái và khó thở', age: 58,
    sex: 'male', conditions: 'tăng huyết áp', medications: 'Amlodipine', systolic: 165,
    diastolic: 96, heart_rate: 102, temperature_c: 37.1, spo2: 94,
  });
  const set = (key) => (event) => setForm({ ...form, [key]: event.target.value });
  const submit = (event) => {
    event.preventDefault();
    execute('/v1/triage', {
      method: 'POST',
      body: {
        patient_ref: form.patient_ref,
        symptoms_text: form.symptoms_text,
        age: Number(form.age) || null,
        sex: form.sex,
        known_conditions: splitList(form.conditions),
        current_medications: splitList(form.medications).map((name) => ({ name })),
        vital_signs: {
          systolic: Number(form.systolic) || null, diastolic: Number(form.diastolic) || null,
          heart_rate: Number(form.heart_rate) || null, temperature_c: Number(form.temperature_c) || null,
          spo2: Number(form.spo2) || null,
        },
        locale: 'vi-VN',
      },
    }, `Phân luồng ${form.patient_ref}`);
  };
  return (
    <form onSubmit={submit} className="task-form">
      <FormSection title="Thông tin tiếp nhận">
        <div className="form-grid two">
          <Field label="Mã bệnh nhân"><TextInput required value={form.patient_ref} onChange={set('patient_ref')} /></Field>
          <Field label="Tuổi"><TextInput type="number" min="0" max="130" value={form.age} onChange={set('age')} /></Field>
        </div>
        <Field label="Giới tính"><SelectInput value={form.sex} onChange={set('sex')}><option value="male">Nam</option><option value="female">Nữ</option><option value="other">Khác</option></SelectInput></Field>
        <Field label="Triệu chứng"><TextArea rows="5" required value={form.symptoms_text} onChange={set('symptoms_text')} /></Field>
        <Field label="Bệnh nền"><TextInput value={form.conditions} onChange={set('conditions')} /></Field>
        <Field label="Thuốc đang dùng"><TextInput value={form.medications} onChange={set('medications')} /></Field>
      </FormSection>
      <FormSection title="Dấu hiệu sinh tồn">
        <div className="vital-grid">
          <Field label="Tâm thu"><TextInput type="number" value={form.systolic} onChange={set('systolic')} /></Field>
          <Field label="Tâm trương"><TextInput type="number" value={form.diastolic} onChange={set('diastolic')} /></Field>
          <Field label="Nhịp tim"><TextInput type="number" value={form.heart_rate} onChange={set('heart_rate')} /></Field>
          <Field label="Nhiệt độ"><TextInput type="number" step="0.1" value={form.temperature_c} onChange={set('temperature_c')} /></Field>
          <Field label="SpO2"><TextInput type="number" value={form.spo2} onChange={set('spo2')} /></Field>
        </div>
      </FormSection>
      <SubmitButton busy={busy}>Phân luồng</SubmitButton>
    </form>
  );
}

const blankMedication = () => ({ name: '', active_ingredient: '', dose_mg: '' });

function MedicationRows({ title, rows, setRows, minimum = 0 }) {
  const update = (index, key, value) => setRows(rows.map((row, rowIndex) => rowIndex === index ? { ...row, [key]: value } : row));
  return (
    <FormSection title={title} action={<AddButton label="Thêm thuốc" onClick={() => setRows([...rows, blankMedication()])} />}>
      <div className="repeat-list">
        {rows.map((row, index) => (
          <div className="repeat-row medication-row" key={index}>
            <TextInput aria-label="Tên thuốc" placeholder="Tên thuốc" required value={row.name} onChange={(e) => update(index, 'name', e.target.value)} />
            <TextInput aria-label="Hoạt chất" placeholder="Hoạt chất" value={row.active_ingredient} onChange={(e) => update(index, 'active_ingredient', e.target.value)} />
            <TextInput aria-label="Liều mg" placeholder="mg" type="number" min="0" value={row.dose_mg} onChange={(e) => update(index, 'dose_mg', e.target.value)} />
            <RemoveButton onClick={() => rows.length > minimum && setRows(rows.filter((_, rowIndex) => rowIndex !== index))} />
          </div>
        ))}
      </div>
    </FormSection>
  );
}

export function SafetyModule({ execute, busy }) {
  const [patientRef, setPatientRef] = useState('BN-SAFETY-001');
  const [conditions, setConditions] = useState('loét dạ dày');
  const [allergies, setAllergies] = useState([{ substance: 'Penicillin', reaction: 'mề đay', severity: 'HIGH' }]);
  const [current, setCurrent] = useState([{ name: 'Warfarin', active_ingredient: 'warfarin', dose_mg: 5 }]);
  const [proposed, setProposed] = useState([{ name: 'Aspirin', active_ingredient: 'aspirin', dose_mg: 81 }]);
  const updateAllergy = (index, key, value) => setAllergies(allergies.map((row, i) => i === index ? { ...row, [key]: value } : row));
  const cleanMeds = (rows) => rows.filter((row) => row.name).map((row) => ({ ...row, dose_mg: Number(row.dose_mg) || null }));
  const submit = (event) => {
    event.preventDefault();
    execute('/v1/medication/safety-check', { method: 'POST', body: {
      patient_ref: patientRef, conditions: splitList(conditions), allergies,
      current_medications: cleanMeds(current), proposed_medications: cleanMeds(proposed),
    } }, `Kiểm tra thuốc ${patientRef}`);
  };
  return (
    <form onSubmit={submit} className="task-form">
      <FormSection title="Hồ sơ an toàn">
        <Field label="Mã bệnh nhân"><TextInput required value={patientRef} onChange={(e) => setPatientRef(e.target.value)} /></Field>
        <Field label="Bệnh lý liên quan"><TextInput value={conditions} onChange={(e) => setConditions(e.target.value)} /></Field>
      </FormSection>
      <FormSection title="Dị ứng" action={<AddButton label="Thêm dị ứng" onClick={() => setAllergies([...allergies, { substance: '', reaction: '', severity: 'MODERATE' }])} />}>
        <div className="repeat-list">
          {allergies.map((row, index) => <div className="repeat-row allergy-row" key={index}>
            <TextInput required placeholder="Dị nguyên" value={row.substance} onChange={(e) => updateAllergy(index, 'substance', e.target.value)} />
            <TextInput placeholder="Phản ứng" value={row.reaction} onChange={(e) => updateAllergy(index, 'reaction', e.target.value)} />
            <SelectInput value={row.severity} onChange={(e) => updateAllergy(index, 'severity', e.target.value)}><option>LOW</option><option>MODERATE</option><option>HIGH</option></SelectInput>
            <RemoveButton onClick={() => setAllergies(allergies.filter((_, i) => i !== index))} />
          </div>)}
        </div>
      </FormSection>
      <MedicationRows title="Thuốc đang dùng" rows={current} setRows={setCurrent} />
      <MedicationRows title="Thuốc đề xuất" rows={proposed} setRows={setProposed} minimum={1} />
      <SubmitButton busy={busy}>Kiểm tra an toàn</SubmitButton>
    </form>
  );
}

const metricUnits = { pain_score: '/10', temperature_c: 'C', systolic: 'mmHg', diastolic: 'mmHg', heart_rate: 'bpm', spo2: '%', glucose_mg_dl: 'mg/dl' };

export function MonitoringModule({ execute, busy }) {
  const [patientRef, setPatientRef] = useState('BN-MONITOR-001');
  const [metrics, setMetrics] = useState([
    { metric: 'spo2', value: 97, unit: '%', recorded_at: nowIso(-2) },
    { metric: 'spo2', value: 94, unit: '%', recorded_at: nowIso(-1) },
    { metric: 'spo2', value: 91, unit: '%', recorded_at: nowIso(0) },
  ]);
  const update = (index, key, value) => setMetrics(metrics.map((row, i) => {
    if (i !== index) return row;
    if (key === 'metric') return { ...row, metric: value, unit: metricUnits[value] };
    return { ...row, [key]: value };
  }));
  const submit = (event) => {
    event.preventDefault();
    execute('/v1/monitoring/ingest', { method: 'POST', body: {
      patient_ref: patientRef,
      metrics: metrics.map((row) => ({ ...row, value: Number(row.value), recorded_at: new Date(row.recorded_at).toISOString() })),
    } }, `Theo dõi ${patientRef}`);
  };
  return (
    <form onSubmit={submit} className="task-form">
      <FormSection title="Kế hoạch theo dõi">
        <Field label="Mã bệnh nhân"><TextInput required value={patientRef} onChange={(e) => setPatientRef(e.target.value)} /></Field>
      </FormSection>
      <FormSection title="Chuỗi chỉ số" action={<AddButton onClick={() => setMetrics([...metrics, { metric: 'heart_rate', value: 80, unit: 'bpm', recorded_at: nowIso() }])} />}>
        <div className="repeat-list">
          {metrics.map((row, index) => <div className="repeat-row metric-row" key={index}>
            <SelectInput value={row.metric} onChange={(e) => update(index, 'metric', e.target.value)}>{Object.keys(metricUnits).map((metric) => <option key={metric}>{metric}</option>)}</SelectInput>
            <TextInput required type="number" step="0.1" value={row.value} onChange={(e) => update(index, 'value', e.target.value)} />
            <TextInput required value={row.unit} onChange={(e) => update(index, 'unit', e.target.value)} />
            <TextInput required type="datetime-local" value={row.recorded_at} onChange={(e) => update(index, 'recorded_at', e.target.value)} />
            <RemoveButton onClick={() => metrics.length > 1 && setMetrics(metrics.filter((_, i) => i !== index))} />
          </div>)}
        </div>
      </FormSection>
      <SubmitButton busy={busy}>Phân tích xu hướng</SubmitButton>
    </form>
  );
}

export function FollowUpModule({ execute, busy }) {
  const [form, setForm] = useState({ patient_ref: 'BN-FOLLOWUP-001', diagnosis_text: 'viêm phổi', discharge_date: new Date().toISOString().slice(0, 10), medications: '', conditions: '' });
  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });
  const submit = (e) => { e.preventDefault(); execute('/v1/followup/plan', { method: 'POST', body: {
    patient_ref: form.patient_ref, diagnosis_text: form.diagnosis_text, discharge_date: form.discharge_date || null,
    current_medications: splitList(form.medications), conditions: splitList(form.conditions),
  } }, `Lập lịch ${form.patient_ref}`); };
  return <form onSubmit={submit} className="task-form">
    <FormSection title="Thông tin xuất viện">
      <Field label="Mã bệnh nhân"><TextInput required value={form.patient_ref} onChange={set('patient_ref')} /></Field>
      <Field label="Chẩn đoán"><TextArea rows="4" required value={form.diagnosis_text} onChange={set('diagnosis_text')} /></Field>
      <Field label="Ngày xuất viện"><TextInput type="date" value={form.discharge_date} onChange={set('discharge_date')} /></Field>
      <Field label="Thuốc hiện tại"><TextInput value={form.medications} onChange={set('medications')} /></Field>
      <Field label="Bệnh nền"><TextInput value={form.conditions} onChange={set('conditions')} /></Field>
    </FormSection>
    <SubmitButton busy={busy}>Tạo kế hoạch</SubmitButton>
  </form>;
}

export function PharmacyModule({ execute, busy }) {
  const [patientRef, setPatientRef] = useState('BN-PHARMACY-001');
  const [location, setLocation] = useState('Quận 1, TP.HCM');
  const [mode, setMode] = useState('pickup');
  const [urgency, setUrgency] = useState('ROUTINE');
  const [medications, setMedications] = useState([{ name: 'Amoxicillin 500mg', active_ingredient: 'amoxicillin', dose_mg: 500 }]);
  const submit = (e) => { e.preventDefault(); execute('/v1/pharmacy/fulfillment', { method: 'POST', body: {
    patient_ref: patientRef, location_hint: location, preferred_mode: mode, urgency,
    medications: medications.filter((m) => m.name).map((m) => ({ ...m, dose_mg: Number(m.dose_mg) || null, quantity: 1 })),
  } }, `Tìm nhà thuốc ${patientRef}`); };
  return <form onSubmit={submit} className="task-form">
    <FormSection title="Yêu cầu cấp phát">
      <Field label="Mã bệnh nhân"><TextInput required value={patientRef} onChange={(e) => setPatientRef(e.target.value)} /></Field>
      <Field label="Khu vực"><TextInput value={location} onChange={(e) => setLocation(e.target.value)} /></Field>
      <div className="form-grid two"><Field label="Hình thức"><SelectInput value={mode} onChange={(e) => setMode(e.target.value)}><option value="pickup">Nhận tại quầy</option><option value="delivery">Giao thuốc</option></SelectInput></Field><Field label="Mức ưu tiên"><SelectInput value={urgency} onChange={(e) => setUrgency(e.target.value)}><option>ROUTINE</option><option>URGENT</option><option>EMERGENCY</option></SelectInput></Field></div>
    </FormSection>
    <MedicationRows title="Danh sách thuốc" rows={medications} setRows={setMedications} minimum={1} />
    <SubmitButton busy={busy}>Tìm phương án</SubmitButton>
  </form>;
}

export function QueueModule({ execute, busy }) {
  const [items, setItems] = useState([
    { patient_ref: 'BN-001', urgency: 'ROUTINE', esi_level: 5, emergency_flag: false, wait_minutes: 35 },
    { patient_ref: 'BN-002', urgency: 'URGENT', esi_level: 3, emergency_flag: false, wait_minutes: 12 },
    { patient_ref: 'BN-003', urgency: 'EMERGENCY', esi_level: 1, emergency_flag: true, wait_minutes: 2 },
  ]);
  const update = (index, key, value) => setItems(items.map((row, i) => i === index ? { ...row, [key]: value } : row));
  const submit = (e) => { e.preventDefault(); execute('/v1/queue/prioritize', { method: 'POST', body: {
    items: items.map((item) => ({ ...item, esi_level: Number(item.esi_level), wait_minutes: Number(item.wait_minutes) })),
  } }, 'Xếp hàng tiếp nhận'); };
  return <form onSubmit={submit} className="task-form">
    <FormSection title="Danh sách chờ" action={<AddButton label="Thêm bệnh nhân" onClick={() => setItems([...items, { patient_ref: '', urgency: 'ROUTINE', esi_level: 5, emergency_flag: false, wait_minutes: 0 }])} />}>
      <div className="repeat-list">
        {items.map((row, index) => <div className="queue-editor" key={index}>
          <div className="queue-editor-top"><TextInput required placeholder="Mã bệnh nhân" value={row.patient_ref} onChange={(e) => update(index, 'patient_ref', e.target.value)} /><RemoveButton onClick={() => items.length > 1 && setItems(items.filter((_, i) => i !== index))} /></div>
          <div className="form-grid three"><Field label="Mức độ"><SelectInput value={row.urgency} onChange={(e) => update(index, 'urgency', e.target.value)}><option>ROUTINE</option><option>URGENT</option><option>EMERGENCY</option></SelectInput></Field><Field label="ESI"><TextInput type="number" min="1" max="5" value={row.esi_level} onChange={(e) => update(index, 'esi_level', e.target.value)} /></Field><Field label="Chờ (phút)"><TextInput type="number" min="0" value={row.wait_minutes} onChange={(e) => update(index, 'wait_minutes', e.target.value)} /></Field></div>
          <label className="check-control"><input type="checkbox" checked={row.emergency_flag} onChange={(e) => update(index, 'emergency_flag', e.target.checked)} /> Cờ cấp cứu</label>
        </div>)}
      </div>
    </FormSection>
    <SubmitButton busy={busy}>Xếp thứ tự</SubmitButton>
  </form>;
}
