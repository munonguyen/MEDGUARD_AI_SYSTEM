import {
  AlertTriangle,
  Check,
  ChevronDown,
  CircleAlert,
  Clock3,
  Code2,
  LoaderCircle,
  Plus,
  Send,
  ShieldCheck,
  Trash2,
} from 'lucide-react';

export function Field({ label, children, className = '' }) {
  return (
    <label className={`field ${className}`}>
      <span>{label}</span>
      {children}
    </label>
  );
}

export function TextInput(props) {
  return <input className="control" {...props} />;
}

export function SelectInput({ children, ...props }) {
  return (
    <span className="select-wrap">
      <select className="control" {...props}>{children}</select>
      <ChevronDown size={15} aria-hidden="true" />
    </span>
  );
}

export function TextArea(props) {
  const { className = '', ...rest } = props;
  return <textarea className={`control textarea ${className}`} {...rest} />;
}

export function SubmitButton({ busy, children = 'Phân tích', disabled = false }) {
  return (
    <button className="primary-button" type="submit" disabled={busy || disabled}>
      {busy ? <LoaderCircle className="spin" size={17} /> : <Send size={17} />}
      <span>{busy ? 'Đang xử lý' : children}</span>
    </button>
  );
}

export function FormSection({ title, action, children }) {
  return (
    <section className="form-section">
      <div className="section-heading">
        <h3>{title}</h3>
        {action}
      </div>
      {children}
    </section>
  );
}

export function AddButton({ onClick, label = 'Thêm dòng' }) {
  return (
    <button className="text-button" type="button" onClick={onClick}>
      <Plus size={15} /> {label}
    </button>
  );
}

export function RemoveButton({ onClick, label = 'Xóa dòng' }) {
  return (
    <button className="icon-button danger-hover" type="button" onClick={onClick} title={label} aria-label={label}>
      <Trash2 size={16} />
    </button>
  );
}

function toneFor(value = '') {
  const normalized = String(value).toUpperCase();
  if (['EMERGENCY', 'HIGH', 'FAILED', 'FAIL', 'OPEN', 'REJECTED_BY_PHARMACIST'].includes(normalized)) return 'danger';
  if (['URGENT', 'MODERATE', 'DEGRADED', 'LIMITED', 'PENDING_REVIEW'].includes(normalized)) return 'warning';
  if (['LOW', 'ROUTINE', 'PASS', 'READY', 'COMPLETED', 'CLOSED', 'CONFIRMED_BY_PHARMACIST', 'AVAILABLE', 'OK'].includes(normalized)) return 'success';
  return 'neutral';
}

export function StatusBadge({ value }) {
  return <span className={`status-badge ${toneFor(value)}`}>{String(value || 'N/A').replaceAll('_', ' ')}</span>;
}

function JsonBlock({ data }) {
  return (
    <details className="json-block">
      <summary><Code2 size={15} /> JSON response</summary>
      <pre>{JSON.stringify(data, null, 2)}</pre>
    </details>
  );
}

function TraceFooter({ trace, requestId }) {
  if (!trace && !requestId) return null;
  return (
    <div className="trace-footer">
      <span><Clock3 size={13} /> {trace?.latency_ms ?? '—'} ms</span>
      <span>{trace?.rule_version || 'API response'}</span>
      <code>{requestId || trace?.request_id}</code>
    </div>
  );
}

function ResultList({ title, items, renderItem }) {
  if (!items?.length) return null;
  return (
    <section className="result-section">
      <h4>{title}</h4>
      <div className="result-list">{items.map((item, index) => renderItem(item, index))}</div>
    </section>
  );
}

export function ClinicalResult({ data, embedded = false }) {
  if (!data) return null;
  const headline = data.urgency || data.overall_risk || data.escalation_level || data.verification_status || data.status || data.review_status || data.resourceType;
  const summary = data.summary || data.advice || data.disclaimer;
  const medicationSchedules = data.schedules || data.medication_schedules;
  const body = (
      <div className={`message-body ${embedded ? 'embedded-result' : ''}`}>
        <div className="result-heading">
          <div>
            <span className="message-author">MedGuard AI</span>
            <h3>{data.recommended_specialty?.label || data.job_id || data.envelope?.event_id || 'Kết quả nghiệp vụ'}</h3>
          </div>
          {headline && <StatusBadge value={headline} />}
        </div>

        {data.esi_level && <div className="metric-strip"><strong>ESI {data.esi_level}</strong><span>{data.emergency_flag ? 'Có dấu hiệu cấp cứu' : 'Không có cờ cấp cứu'}</span></div>}
        {data.estimated_seconds && <div className="metric-strip"><strong>Đã tiếp nhận</strong><span>Dự kiến xử lý trong {data.estimated_seconds} giây</span></div>}
        {summary && <p className="result-summary">{summary}</p>}
        {data.error_code && <div className="inline-error"><strong>Không thể xử lý:</strong> {data.error_code.replaceAll('_', ' ')}</div>}

        <ResultList title="Cảnh báo" items={data.warnings || data.alerts || data.red_flags} renderItem={(item, index) => (
          <div className="alert-row" key={index}>
            <AlertTriangle size={17} />
            <div><strong>{item.severity || item.type || `Cảnh báo ${index + 1}`}</strong><p>{item.detail || item}</p></div>
          </div>
        )} />

        <ResultList title="Cần bổ sung thông tin" items={data.clarifying_questions} renderItem={(item, index) => (
          <div className="list-row" key={index}><div><strong>{item}</strong></div></div>
        )} />

        <ResultList title="Hoạt chất chưa xác định" items={data.unknown_ingredients} renderItem={(item, index) => (
          <div className="alert-row" key={index}><CircleAlert size={17} /><div><strong>{item}</strong><p>Cần dược sĩ xác minh trước khi quyết định.</p></div></div>
        )} />

        <ResultList title="Xu hướng chỉ số" items={data.metrics} renderItem={(item, index) => (
          <div className="list-row" key={`${item.metric}-${index}`}>
            <div><strong>{String(item.metric).replaceAll('_', ' ')}</strong><p>{item.delta == null ? 'Chưa đủ dữ liệu so sánh' : `Thay đổi ${item.delta > 0 ? '+' : ''}${item.delta}`}</p></div>
            <StatusBadge value={item.direction} />
          </div>
        )} />

        <ResultList title="Khuyến nghị theo dõi" items={data.suggestions} renderItem={(item) => (
          <div className="list-row" key={item.code}>
            <div><strong>{item.title}</strong><p>{item.instructions?.join(' · ')}</p></div>
            <span>{item.scheduled_for || `${item.due_in_days} ngày`}</span>
          </div>
        )} />

        <ResultList title="Phương án cấp phát" items={data.options} renderItem={(item) => (
          <div className="list-row" key={item.provider_code}>
            <div><strong>{item.provider_name}</strong><p>{item.rationale?.join(' · ')}</p></div>
            <StatusBadge value={item.availability} />
          </div>
        )} />

        <ResultList title="Thứ tự tiếp nhận" items={data.items} renderItem={(item) => (
          <div className="queue-row" key={`${item.patient_ref}-${item.rank}`}>
            <span className="rank">{item.rank}</span><strong>{item.patient_ref}</strong>
            <StatusBadge value={item.priority_band} /><span className="score">{item.priority_score}</span>
          </div>
        )} />

        {data.envelope && (
          <div className="envelope-view">
            <div><span>Kênh</span><strong>{data.envelope.channel}</strong></div>
            <div><span>Đích</span><strong>{data.envelope.target_ref || '—'}</strong></div>
            <div><span>Ký số</span><strong>{data.envelope.signed ? 'Đã ký' : 'Chưa ký'}</strong></div>
          </div>
        )}

        {data.resourceType === 'Bundle' && (
          <div className="metric-strip"><strong>{data.total} tài nguyên</strong><span>FHIR R4 Bundle · {data.type}</span></div>
        )}

        {data.verification_status && (
          <>
            <div className="metric-strip"><strong>{String(data.verification_status).replaceAll('_', ' ')}</strong><span>{data.product?.name || data.decoded?.product || 'Mã chưa xác định'}</span></div>
            <ResultList title="Đối chiếu registry" items={data.reasons} renderItem={(item, index) => (
              <div className="list-row" key={index}><div><strong>{item}</strong></div></div>
            )} />
          </>
        )}

        {medicationSchedules && (
          <ResultList title="Lịch uống thuốc" items={medicationSchedules} renderItem={(item) => (
            <div className="list-row" key={item.schedule_id}>
              <div><strong>{item.medication_name}</strong><p>{item.patient_ref} · {item.recurrence === 'daily' ? 'Mỗi ngày' : 'Một lần'}</p></div>
              <span>{new Date(item.scheduled_at).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })}</span>
            </div>
          )} />
        )}

        {data.result?.extracted_medications && (
          <ResultList title="Thuốc trích xuất" items={data.result.extracted_medications} renderItem={(item, index) => (
            <div className="list-row" key={index}>
              <div><strong>{item.extracted_entity?.medicine_name || item.raw_text}</strong><p>{item.extracted_entity?.strength || 'Chưa xác định hàm lượng'}</p></div>
              <span>{Math.round((item.confidence || 0) * 100)}%</span>
            </div>
          )} />
        )}

        <TraceFooter trace={data.trace} requestId={data.request_id} />
        <JsonBlock data={data} />
      </div>
  );
  if (embedded) return body;
  return (
    <article className="assistant-message">
      <div className="message-avatar"><ShieldCheck size={18} /></div>
      {body}
    </article>
  );
}

export function ErrorResult({ error }) {
  return (
    <article className="assistant-message error-message">
      <div className="message-avatar"><CircleAlert size={18} /></div>
      <div className="message-body">
        <div className="result-heading"><div><span className="message-author">MedGuard API</span><h3>{error.code || 'request_failed'}</h3></div><StatusBadge value={`HTTP ${error.status || 500}`} /></div>
        <p className="result-summary">{error.message}</p>
        {error.requestId && <code className="request-code">{error.requestId}</code>}
      </div>
    </article>
  );
}

export function EmptyResult({ icon: Icon, title }) {
  return (
    <div className="empty-result">
      <div className="empty-mark"><Icon size={26} /></div>
      <h2>{title}</h2>
    </div>
  );
}

export function CheckRow({ check }) {
  const Icon = check.status === 'pass' ? Check : check.status === 'fail' ? CircleAlert : AlertTriangle;
  return (
    <div className="check-row">
      <Icon size={17} />
      <div><strong>{check.name.replaceAll('_', ' ')}</strong><p>{check.detail}</p></div>
      <StatusBadge value={check.status} />
    </div>
  );
}
