import { useRef, useState } from 'react';
import { FileImage, RefreshCw, ScanLine, ThumbsDown, ThumbsUp, Upload } from 'lucide-react';
import { Field, FormSection, StatusBadge, SubmitButton, TextInput } from '../components';

export function OcrModule({ execute, busy }) {
  const [patientRef, setPatientRef] = useState('BN-OCR-001');
  const [catalogRef, setCatalogRef] = useState('catalog-demo');
  const [file, setFile] = useState(null);
  const [job, setJob] = useState(null);
  const inputRef = useRef(null);

  const upload = async (event) => {
    event.preventDefault();
    if (!file) return;
    const data = new FormData();
    data.append('image', file);
    data.append('patient_ref', patientRef);
    if (catalogRef) data.append('catalog_ref', catalogRef);
    const response = await execute('/v1/prescription/extract', { method: 'POST', formData: data }, `OCR ${patientRef}`);
    if (response) setJob(response);
  };

  const jobAction = async (action, options = {}) => {
    if (!job?.job_id) return;
    const method = action === 'status' ? 'GET' : 'POST';
    const suffix = action === 'status' ? '' : action === 'review' ? `/review?approved=${options.approved}` : '/process';
    const response = await execute(`/v1/jobs/${job.job_id}${suffix}`, { method }, `${action} ${job.job_id}`);
    if (response) setJob(response);
  };

  return (
    <form onSubmit={upload} className="task-form">
      <FormSection title="Nguồn đơn thuốc">
        <Field label="Mã bệnh nhân"><TextInput required value={patientRef} onChange={(e) => setPatientRef(e.target.value)} /></Field>
        <Field label="Danh mục đối soát"><TextInput value={catalogRef} onChange={(e) => setCatalogRef(e.target.value)} /></Field>
        <button className={`upload-zone ${file ? 'has-file' : ''}`} type="button" onClick={() => inputRef.current?.click()}>
          {file ? <FileImage size={28} /> : <Upload size={28} />}
          <span>{file ? file.name : 'Chọn ảnh đơn thuốc'}</span>
          {file && <small>{(file.size / 1024).toFixed(1)} KB · {file.type}</small>}
        </button>
        <input ref={inputRef} className="visually-hidden" type="file" accept="image/png,image/jpeg,image/webp" onChange={(e) => setFile(e.target.files?.[0] || null)} />
      </FormSection>
      <SubmitButton busy={busy} disabled={!file}>Tạo OCR job</SubmitButton>

      {job?.job_id && <section className="job-console">
        <div className="job-console-head"><div><span>Job ID</span><code>{job.job_id}</code></div><StatusBadge value={job.status || job.review_status} /></div>
        <div className="job-actions">
          <button type="button" className="secondary-button" disabled={busy} onClick={() => jobAction('status')}><RefreshCw size={16} /> Làm mới</button>
          {(job.status === 'queued' || job.status === 'processing') && <button type="button" className="secondary-button" disabled={busy} onClick={() => jobAction('process')}><ScanLine size={16} /> Xử lý</button>}
          {job.status === 'completed' && <>
            <button type="button" className="secondary-button success-action" disabled={busy} onClick={() => jobAction('review', { approved: true })}><ThumbsUp size={16} /> Xác nhận</button>
            <button type="button" className="secondary-button danger-action" disabled={busy} onClick={() => jobAction('review', { approved: false })}><ThumbsDown size={16} /> Từ chối</button>
          </>}
        </div>
      </section>}
    </form>
  );
}
