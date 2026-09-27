import {
  AlertCircle,
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  CircleHelp,
  ShieldAlert,
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
  verified: 'Đã kiểm chứng qua gateway',
  shadow_pending: 'Đã tiếp nhận vào hàng đợi kiểm định gateway',
  shadow: 'Gateway đã hoàn tất kiểm định nền; nội dung an toàn ban đầu được giữ nguyên',
  timed_out: 'Gateway quá thời gian; dùng kết quả an toàn dự phòng',
  rejected: 'Gateway không đạt kiểm định; dùng kết quả an toàn dự phòng',
  unavailable: 'Gateway bận hoặc chưa sẵn sàng; dùng kết quả an toàn dự phòng',
  circuit_open: 'Gateway tạm ngắt; dùng kết quả an toàn dự phòng',
  error: 'Gateway gặp lỗi; dùng kết quả an toàn dự phòng',
  not_requested: 'Gateway chưa được yêu cầu; kết quả từ quy tắc y khoa',
};

const knowledgeLabels = {
  approved: 'Nguồn nội bộ đã duyệt',
  pending_review: 'Nguồn đang chờ chuyên gia duyệt',
  mixed: 'Một phần nguồn đang chờ duyệt',
  not_recorded: 'Nguồn chưa ghi nhận phê duyệt',
};

const legacyQuestionPrefixes = [
  'Bạn cho mình biết thêm:',
  'Thông tin cần báo nhân viên y tế nếu có thể:',
];

function isLegacyQuestionNarrative(block) {
  return legacyQuestionPrefixes.some((prefix) => block?.text?.startsWith(prefix));
}

export function GroundedAnswer({ answer, result, responseMeta = {} }) {
  if (!answer) return null;
  const hasNarrative = answer.narrative?.length > 0;
  const researchedSources = answer.researched_sources || [];
  const sourcesById = new Map(researchedSources.map((source, index) => [source.source_id, { ...source, index: index + 1 }]));

  const structuredUrgency = result?.urgency || result?.escalation_level;
  const showTechnicalMeta = responseMeta.showTechnicalMeta === true;
  const isEmergency = structuredUrgency === 'EMERGENCY';
  const isCaution = !isEmergency && (
    structuredUrgency === 'URGENT'
    || ['HIGH', 'MODERATE'].includes(result?.overall_risk)
    || ['suspected_counterfeit', 'recalled', 'invalid'].includes(result?.verification_status)
  );
  const displayQuestions = answer.display_questions?.length
    ? answer.display_questions
    : (answer.questions || []).slice(0, 2);
  const narrativeBlocks = hasNarrative
    ? answer.narrative.filter((block) => !isLegacyQuestionNarrative(block))
    : [];

  return (
    <div className="grounded-answer modern-clinical-layout">
      {showTechnicalMeta && (
        <div className="answer-assurance-row" aria-label="Trạng thái kiểm chứng câu trả lời">
          <span className={`verification-pill ${responseMeta.verification_status || 'not_requested'}`}>
            {responseMeta.verification_status === 'verified'
              ? <CheckCircle2 size={13} />
              : <CircleHelp size={13} />}
            {verificationLabels[responseMeta.verification_status] || verificationLabels.not_requested}
          </span>
          {responseMeta.knowledge_approval && (
            <span className={`knowledge-pill ${responseMeta.knowledge_approval}`}>
              {knowledgeLabels[responseMeta.knowledge_approval]}
            </span>
          )}
        </div>
      )}
      {(isEmergency || isCaution) && <div className="clinical-header-pill-row">
        {isEmergency ? (
          <span className="triage-status-pill emergency-pill">
            <span className="pulse-dot-red" />
            <ShieldAlert size={14} />
            <strong>CẦN ĐÁNH GIÁ CẤP CỨU</strong>
          </span>
        ) : (
          <span className="triage-status-pill caution-pill">
            <AlertTriangle size={14} />
            <strong>CẦN ĐƯỢC ĐÁNH GIÁ SỚM</strong>
          </span>
        )}
      </div>}

      {hasNarrative ? (
        <>
          <div className="answer-narrative">
            {narrativeBlocks.map((block, index) => {
              const isUrgentBlock = block.kind === 'urgent';
              const isCautionBlock = block.kind === 'caution';
              return (
                <p className={block.kind} key={`${block.text}-${index}`}>
                  {isUrgentBlock && <AlertCircle size={17} className="block-lead-icon urgent" />}
                  {isCautionBlock && <AlertTriangle size={17} className="block-lead-icon caution" />}
                  <HighlightedText text={block.text} emphasis={block.emphasis} />
                  {block.source_ids?.length > 0 && (
                    <span className="inline-citations">
                      {[...new Set(block.source_ids)].map((sourceId) => {
                        const source = sourcesById.get(sourceId);
                        return source ? (
                          <a
                            key={sourceId}
                            href={source.url}
                            target="_blank"
                            rel="noreferrer"
                            title={`${source.publisher}: ${source.title}`}
                            aria-label={`Mở nguồn ${source.index}: ${source.title}`}
                          >
                            {source.index}
                          </a>
                        ) : null;
                      })}
                    </span>
                  )}
                </p>
              );
            })}
          </div>
          <AnswerList
            title="Câu hỏi quan trọng tiếp theo"
            icon={CircleHelp}
            items={displayQuestions}
          />
        </>
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
          <AnswerList title="Câu hỏi quan trọng tiếp theo" icon={CircleHelp} items={displayQuestions} />
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