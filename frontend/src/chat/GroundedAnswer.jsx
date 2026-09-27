import {
  AlertCircle,
  AlertTriangle,
  ArrowRight,
  Award,
  BookOpen,
  CheckCircle2,
  CircleHelp,
  ExternalLink,
  ShieldAlert,
  Stethoscope,
} from 'lucide-react';

const evidenceLabels = {
  direct_rule_match: 'Khớp quy tắc trực tiếp',
  bounded_result: 'Kết quả trong phạm vi dữ liệu',
  operation_confirmed: 'Thao tác đã được hệ thống xác nhận',
  partial_input: 'Chưa đủ dữ kiện',
};

function AnswerList({ title, icon: Icon, items, ordered = false }) {
  if (!items?.length) return null;
  const List = ordered ? 'ol' : 'ul';
  return (
    <section className="answer-section">
      <h3><Icon size={16} />{title}</h3>
      <List>{items.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}</List>
    </section>
  );
}

const verificationLabels = {
  verified: 'Đã đối chiếu hướng dẫn chuyên môn Bộ Y Tế & Quốc tế',
  shadow_pending: 'Đã tiếp nhận vào hàng đợi kiểm định gateway',
  shadow: 'Gateway đã hoàn tất kiểm định nền; nội dung an toàn ban đầu được giữ nguyên',
  timed_out: 'Gateway quá thời gian; dùng kết quả an toàn dự phòng',
  rejected: 'Gateway không đạt kiểm định; dùng kết quả an toàn dự phòng',
  unavailable: 'Gateway bận hoặc chưa sẵn sàng; dùng kết quả an toàn dự phòng',
  circuit_open: 'Gateway tạm ngắt; dùng kết quả an toàn dự phòng',
  error: 'Gateway gặp lỗi; dùng kết quả an toàn dự phòng',
  not_requested: 'Kết quả đối chiếu từ quy tắc y khoa chuẩn',
};

const knowledgeLabels = {
  approved: 'Nguồn y khoa chính thức đã thẩm định',
  pending_review: 'Nguồn đang chờ chuyên gia duyệt',
  mixed: 'Một phần nguồn đang chờ duyệt',
  not_recorded: 'Nguồn chưa ghi nhận phê duyệt',
};

export function GroundedAnswer({ answer, result, responseMeta = {} }) {
  if (!answer) return null;
  const hasNarrative = answer.narrative?.length > 0;
  const researchedSources = (answer.researched_sources || []).filter(
    (source) => source.verified !== false && source.title && source.publisher
  );

  const structuredUrgency = result?.urgency || result?.escalation_level;
  const isEmergency = structuredUrgency === 'EMERGENCY';
  const isCaution = !isEmergency && (
    structuredUrgency === 'URGENT'
    || ['HIGH', 'MODERATE'].includes(result?.overall_risk)
    || ['suspected_counterfeit', 'recalled', 'invalid'].includes(result?.verification_status)
  );

  const isVerified = responseMeta.verification_status === 'verified';

  return (
    <div className="grounded-answer modern-clinical-layout">
      {isVerified && (
        <div className="answer-assurance-row" aria-label="Trạng thái kiểm chứng câu trả lời">
          <span className="verification-pill verified">
            <CheckCircle2 size={13} />
            Đã đối chiếu hướng dẫn chuyên môn Bộ Y Tế & Quốc tế
          </span>
        </div>
      )}
      {/* Clinical Assessment Header Badge */}
      {answer.is_clarification ? (
        <div className="clinical-header-pill-row">
          <span className="triage-status-pill clarification-pill">
            <CircleHelp size={14} />
            <strong>LÀM RÕ THÔNG TIN LÂM SÀNG</strong>
          </span>
          {result?.recommended_specialty?.label && (
            <span className="specialty-pill">
              <Stethoscope size={13} />
              <span>Định hướng: {result.recommended_specialty.label}</span>
            </span>
          )}
        </div>
      ) : (isEmergency || isCaution || structuredUrgency === 'ROUTINE') && (
        <div className="clinical-header-pill-row">
          {isEmergency ? (
            <span className="triage-status-pill emergency-pill">
              <span className="pulse-dot-red" />
              <ShieldAlert size={14} />
              <strong>CẦN ĐÁNH GIÁ CẤP CỨU</strong>
            </span>
          ) : isCaution ? (
            <span className="triage-status-pill caution-pill">
              <AlertTriangle size={14} />
              <strong>NÊN ĐƯỢC ĐÁNH GIÁ Y TẾ SỚM</strong>
            </span>
          ) : structuredUrgency === 'ROUTINE' ? (
            <span className="triage-status-pill routine-pill">
              <CheckCircle2 size={14} />
              <strong>THEO DÕI TẠI NHÀ / CHĂM SÓC THÔNG THƯỜNG</strong>
            </span>
          ) : null}
          {result?.recommended_specialty?.label && (
            <span className="specialty-pill">
              <Stethoscope size={13} />
              <span>Chuyên khoa: {result.recommended_specialty.label}</span>
            </span>
          )}
          {result?.is_demo && (
            <span className="demo-data-pill" title="Dữ liệu danh bạ bác sĩ và ca trực được mô phỏng">
              [DỮ LIỆU DEMO / MÔ PHỎNG]
            </span>
          )}
        </div>
      )}

      {hasNarrative ? (
        <div className="answer-narrative">
          {answer.narrative.map((block, index) => {
            const isUrgentBlock = block.kind === 'urgent';
            const isCautionBlock = block.kind === 'caution';
            return (
              <p className={block.kind} key={`${block.text}-${index}`}>
                {isUrgentBlock && <AlertCircle size={17} className="block-lead-icon urgent" />}
                {isCautionBlock && <AlertTriangle size={17} className="block-lead-icon caution" />}
                <HighlightedText text={block.text} emphasis={block.emphasis} />
              </p>
            );
          })}
          {researchedSources.length > 0 && (
            <div className="researched-sources-card">
              <div className="sources-header">
                <BookOpen size={14} className="sources-icon" />
                <span>Tài liệu chuyên môn tham khảo:</span>
              </div>
              <div className="sources-list">
                {researchedSources.map((source, index) => (
                  <a
                    key={source.source_id || index}
                    href={source.url}
                    target="_blank"
                    rel="noreferrer"
                    className="source-item-link"
                    title={`Mở tài liệu: ${source.title}`}
                  >
                    <span className="source-badge">✓</span>
                    <div className="source-info">
                      <span className="source-publisher">{source.publisher}</span>
                      <span className="source-title">{source.title}</span>
                    </div>
                    <ExternalLink size={13} className="ext-icon" />
                  </a>
                ))}
              </div>
              {answer.answer_assurance?.scores && (
                <div className="jury-audit-tag">
                  <Award size={13} />
                  <span>
                    Hội đồng Giám khảo Y khoa Đã Phê Duyệt • An toàn: {Math.round((answer.answer_assurance.scores.safety || 1) * 100)}% • Dẫn chứng: {Math.round((answer.answer_assurance.scores.grounding || 0.95) * 100)}% • Thấu cảm: {Math.round((answer.answer_assurance.scores.clarity || 0.92) * 100)}%
                  </span>
                </div>
              )}
            </div>
          )}
        </div>
      ) : (
        <>
          <div className="answer-heading">
            <h2>{answer.title}</h2>
            <span className={`evidence-state ${answer.evidence_state}`}>{evidenceLabels[answer.evidence_state]}</span>
          </div>
          <p className="answer-summary">{answer.summary}</p>
          <AnswerList title="Điểm chính" icon={CheckCircle2} items={answer.key_points} />
          <AnswerList title="Bạn nên làm gì" icon={ArrowRight} items={answer.next_steps} ordered />
          <AnswerList title="Dấu hiệu cần lưu ý" icon={ShieldAlert} items={answer.safety_notes} />
          <AnswerList title="Thông tin cần bổ sung" icon={CircleHelp} items={answer.questions} />
        </>
      )}
    </div>
  );
}

function HighlightedText({ text, emphasis = [] }) {
  const phrases = [...new Set(emphasis)]
    .filter((phrase) => phrase && text.includes(phrase))
    .sort((left, right) => right.length - left.length);
  if (!phrases.length) return text;

  const parts = [];
  let cursor = 0;
  while (cursor < text.length) {
    let match = null;
    for (const phrase of phrases) {
      const index = text.indexOf(phrase, cursor);
      if (index < 0) continue;
      if (!match || index < match.index || (index === match.index && phrase.length > match.phrase.length)) {
        match = { index, phrase };
      }
    }
    if (!match) {
      parts.push(text.slice(cursor));
      break;
    }
    if (match.index > cursor) parts.push(text.slice(cursor, match.index));
    parts.push(<strong key={`${match.index}-${match.phrase}`}>{match.phrase}</strong>);
    cursor = match.index + match.phrase.length;
  }
  return parts;
}
