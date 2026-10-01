import {
  Activity,
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  CircleHelp,
  ListChecks,
  ShieldAlert,
  Stethoscope,
} from 'lucide-react';
import { selectPatientResponseSurface } from './responseAuthority.js';
import './GroundedAnswer.css';

const evidenceLabels = {
  direct_rule_match: 'Khớp quy tắc trực tiếp',
  bounded_result: 'Kết quả trong phạm vi dữ liệu',
  operation_confirmed: 'Thao tác đã được hệ thống xác nhận',
  partial_input: 'Chưa đủ dữ kiện',
};

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

const clinicalIntents = new Set(['triage', 'safety', 'monitoring', 'followup', 'pharmacy']);

function ClinicalSection({ title, icon: Icon, items, tone = 'neutral', ordered = false, className = '' }) {
  if (!items?.length) return null;
  const List = ordered ? 'ol' : 'ul';
  return (
    <section className={`clinical-section-card tone-${tone} ${className}`.trim()}>
      <div className="clinical-section-heading">
        <span className="clinical-section-icon"><Icon size={16} /></span>
        <h3>{title}</h3>
      </div>
      <List className={ordered ? 'clinical-steps-list' : 'clinical-bullet-list'}>
        {items.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}
      </List>
    </section>
  );
}

function statusConfig({ urgency, overallRisk, isClinical }) {
  if (!isClinical) {
    return {
      tone: 'workflow',
      label: 'Yêu cầu đã được xử lý',
      helper: 'Trạng thái và kết quả thao tác được trình bày bên dưới',
      icon: CheckCircle2,
    };
  }
  if (urgency === 'EMERGENCY') {
    return {
      tone: 'emergency',
      label: 'Cấp cứu ngay',
      helper: 'Ưu tiên hành động khẩn cấp trước khi tiếp tục trao đổi',
      icon: ShieldAlert,
    };
  }
  if (urgency === 'URGENT' || ['HIGH', 'MODERATE'].includes(overallRisk)) {
    return {
      tone: 'urgent',
      label: 'Cần đánh giá sớm',
      helper: 'Nên được nhân viên y tế đánh giá trong thời gian phù hợp',
      icon: AlertTriangle,
    };
  }
  return {
    tone: 'routine',
    label: 'Theo dõi / chăm sóc thông thường',
    helper: 'Chưa ghi nhận tiêu chí cấp cứu từ dữ kiện hiện có',
    icon: CheckCircle2,
  };
}

export function GroundedAnswer({ answer, result, responseMeta = {} }) {
  if (!answer) return null;

  const researchedSources = answer.researched_sources || [];
  const sourcesById = new Map(
    researchedSources.map((source, index) => [source.source_id, { ...source, index: index + 1 }]),
  );
  const responseSurface = selectPatientResponseSurface({
    answer,
    verificationStatus: responseMeta.verification_status,
  });
  const narrativeBlocks = responseSurface.narrativeBlocks;
  const hasNarrative = narrativeBlocks.length > 0;

  const structuredUrgency = result?.urgency || result?.escalation_level;
  const showTechnicalMeta = responseMeta.showTechnicalMeta === true;
  const isClinical = clinicalIntents.has(responseMeta.intent);
  const status = statusConfig({
    urgency: structuredUrgency,
    overallRisk: result?.overall_risk,
    isClinical,
  });
  const StatusIcon = status.icon;

  if (responseSurface.canonicalVerifiedResponse) {
    return (
      <div className="grounded-answer modern-clinical-layout canonical-patient-response">
        {showTechnicalMeta && (
          <div className="answer-assurance-row" aria-label="Trạng thái kiểm chứng câu trả lời">
            <span className="verification-pill verified">
              <CheckCircle2 size={13} />
              {verificationLabels.verified}
            </span>
            {responseMeta.knowledge_approval && (
              <span className={`knowledge-pill ${responseMeta.knowledge_approval}`}>
                {knowledgeLabels[responseMeta.knowledge_approval]}
              </span>
            )}
          </div>
        )}

        {isClinical && (
          <div className={`clinical-status-row canonical-safety-overlay status-${status.tone}`}>
            <span className={`clinical-status-badge ${status.tone}`}>
              <StatusIcon size={15} />
              <strong>{status.label}</strong>
            </span>
          </div>
        )}

        <div className="answer-narrative clinical-narrative-fallback canonical-narrative">
          {narrativeBlocks.map((block, index) => (
            <NarrativeBlock
              key={`${block.text}-${index}`}
              block={block}
              sourcesById={sourcesById}
            />
          ))}
        </div>
      </div>
    );
  }

  const displayQuestions = Array.isArray(answer.display_questions)
    ? answer.display_questions
    : (answer.questions || []).slice(0, 2);
  const hypotheses = (answer.clinical_hypotheses || [])
    .filter((item) => !String(item).toLowerCase().startsWith('lưu ý:'))
    .slice(0, 4);
  const keyPoints = (answer.key_points || []).slice(0, 5);
  const nextSteps = (answer.next_steps || []);
  const safetyNotes = (answer.safety_notes || []);
  const limitations = (answer.limitations || []).slice(0, 2);
  const hasStructuredContent = Boolean(
    keyPoints.length
    || hypotheses.length
    || nextSteps.length
    || safetyNotes.length
    || displayQuestions.length,
  );

  return (
    <div className="grounded-answer modern-clinical-layout deterministic-fallback-response">
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

      <section className={`clinical-summary-card status-${status.tone}`}>
        <div className="clinical-status-row">
          <span className={`clinical-status-badge ${status.tone}`}>
            <StatusIcon size={15} />
            <strong>{status.label}</strong>
          </span>
          {answer.evidence_state && (
            <span className={`clinical-evidence-chip ${answer.evidence_state}`}>
              {evidenceLabels[answer.evidence_state] || answer.evidence_state}
            </span>
          )}
        </div>

        <div className="clinical-summary-copy">
          <span className="clinical-kicker">{isClinical ? 'Đánh giá ban đầu' : 'Kết quả xử lý'}</span>
          {answer.title && <h2>{answer.title}</h2>}
          {answer.summary && <p>{answer.summary}</p>}
          <small>{status.helper}</small>
        </div>
      </section>

      {hasStructuredContent ? (
        <div className="clinical-report-body">
          <ClinicalSection
            title={isClinical ? 'Dữ kiện chính' : 'Thông tin chính'}
            icon={Activity}
            items={keyPoints}
            tone="neutral"
          />
          <ClinicalSection
            title="Khả năng cần cân nhắc"
            icon={Stethoscope}
            items={hypotheses}
            tone="clinical"
          />
          <ClinicalSection
            title={isClinical ? 'Bạn nên làm gì lúc này' : 'Bước tiếp theo'}
            icon={ListChecks}
            items={nextSteps}
            tone="action"
            ordered
            className="clinical-section-wide"
          />
          <ClinicalSection
            title={status.tone === 'emergency' ? 'Hành động và dấu hiệu khẩn cấp' : 'Khi nào cần đi khám / cấp cứu'}
            icon={ShieldAlert}
            items={safetyNotes}
            tone={status.tone === 'emergency' ? 'danger' : 'warning'}
            className="clinical-section-wide"
          />
          <ClinicalSection
            title={isClinical ? 'Thông tin cần biết thêm' : 'Thông tin cần bổ sung'}
            icon={CircleHelp}
            items={displayQuestions}
            tone="question"
            className="clinical-section-wide"
          />
        </div>
      ) : hasNarrative ? (
        <div className="answer-narrative clinical-narrative-fallback">
          {narrativeBlocks.map((block, index) => (
            <NarrativeBlock
              key={`${block.text}-${index}`}
              block={block}
              sourcesById={sourcesById}
            />
          ))}
        </div>
      ) : null}

      {limitations.length > 0 && (
        <div className="clinical-limitations">
          <AlertCircle size={15} />
          <div>
            <strong>{isClinical ? 'Giới hạn đánh giá từ xa' : 'Giới hạn xử lý'}</strong>
            {limitations.map((item, index) => <p key={`${item}-${index}`}>{item}</p>)}
          </div>
        </div>
      )}
    </div>
  );
}

function NarrativeBlock({ block, sourcesById }) {
  const isUrgentBlock = block.kind === 'urgent';
  const isCautionBlock = block.kind === 'caution';
  return (
    <p className={block.kind}>
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
