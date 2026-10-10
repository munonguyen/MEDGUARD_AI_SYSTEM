import {
  Activity,
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  CircleHelp,
  ClipboardList,
  ExternalLink,
  ListChecks,
  Send,
  ShieldAlert,
  Sparkles,
  Stethoscope,
} from 'lucide-react';
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

/**
 * Generate contextual user follow-up questions to ask the AI assistant.
 * (Questions from user -> assistant, NOT system asking user).
 */
function getContextualFollowups(answer, intent, tone) {
  if (tone === 'emergency') {
    return [
      'Những việc cần làm ngay trong lúc chờ cấp cứu 115 là gì?',
      'Người nhà cần chuẩn bị giấy tờ hoặc thuốc men gì mang theo khi cấp cứu?',
    ];
  }

  const combined = `${answer?.title || ''} ${answer?.summary || ''} ${(answer?.key_points || []).join(' ')} ${(answer?.safety_notes || []).join(' ')}`.toLowerCase();

  if (['warfarin', 'aspirin', 'chống đông', 'tương tác', 'xuất huyết', 'nsaid', 'chảy máu'].some((k) => combined.includes(k))) {
    return [
      'Có loại thuốc giảm đau nào thay thế an toàn khi đang dùng warfarin không?',
      'Dấu hiệu xuất huyết nguy hiểm nào cần đi bệnh viện cấp cứu ngay?',
      'Nếu tôi đã lỡ uống một liều aspirin thì cần theo dõi và xử trí như thế nào?',
    ];
  }

  if (['răng', 'nướu', 'lợi', 'ê buốt', 'tủy', 'dental', 'nha sĩ'].some((k) => combined.includes(k))) {
    return [
      'Có cách nào giảm ê buốt và đau răng nhanh tại nhà an toàn không?',
      'Thuốc giảm đau nào an toàn và phù hợp cho đau răng không cần kê đơn?',
      'Khi nào đau răng là dấu hiệu tủy răng bị tổn thương cần đi nha sĩ ngay?',
    ];
  }

  if (['mắt', 'kết mạc', 'đỏ mắt', 'cộm', 'nhãn cầu', 'chảy nước mắt'].some((k) => combined.includes(k))) {
    return [
      'Cách dùng nước muối sinh lý vệ sinh mắt đúng cách hàng ngày?',
      'Dấu hiệu viêm mắt nào cảnh báo nguy hiểm cần khám bác sĩ ngay?',
      'Đau mắt đỏ có lây không và cần làm gì để phòng ngừa cho người xung quanh?',
    ];
  }

  if (['ngứa', 'mẩn', 'ban đỏ', 'mề đay', 'dị ứng', 'da liễu'].some((k) => combined.includes(k))) {
    return [
      'Có loại thuốc bôi hoặc thuốc uống dị ứng nào an toàn không?',
      'Dấu hiệu dị ứng nặng nào cần đến bệnh viện cấp cứu ngay?',
      'Cần kiêng ăn uống hoặc tránh tiếp xúc với những gì để đỡ ngứa?',
    ];
  }

  if (['khó thở', 'đau ngực', 'tức ngực', 'hô hấp', 'thở dốc'].some((k) => combined.includes(k))) {
    return [
      'Dấu hiệu nào cho thấy cần gọi cấp cứu 115 ngay lập tức?',
      'Tư thế nghỉ ngơi nào giúp dễ thở hơn trong lúc chờ nhân viên y tế?',
      'Khi nào cơn khó thở cần can thiệp y tế khẩn cấp?',
    ];
  }

  if (['dạ dày', 'loét', 'đau bụng', 'tiêu hóa', 'hp', 'trào ngược'].some((k) => combined.includes(k))) {
    return [
      'Nên ăn uống và kiêng gì khi đang bị đau dạ dày cấp?',
      'Dấu hiệu xuất huyết tiêu hóa cần nhập viện kiểm tra là gì?',
      'Thuốc giảm đau nào không làm tổn hại niêm mạc dạ dày?',
    ];
  }

  if (clinicalIntents.has(intent)) {
    return [
      'Khi nào tôi cần đi khám bác sĩ trực tiếp thay vì tự theo dõi tại nhà?',
      'Cần theo dõi thêm những triệu chứng bất thường nào tại nhà?',
      'Chế độ ăn uống và sinh hoạt nào phù hợp nhất với tình trạng này?',
    ];
  }

  return [];
}

function ClinicalSection({
  title,
  icon: Icon,
  items,
  tone = 'neutral',
  ordered = false,
  className = '',
}) {
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

/**
 * Clinical Clarifying Information from Doctor/System to User.
 * Printed purely as text/bullets within the clinical document ("in trên văn bản").
 */
function ClinicalClarifyingNotes({ questions }) {
  if (!questions?.length) return null;
  return (
    <div className="clinical-clarifying-notes" role="note" aria-label="Thông tin lâm sàng cần làm rõ">
      <div className="clarifying-notes-header">
        <ClipboardList size={15} className="clarifying-notes-icon" />
        <span>Thông tin cần biết thêm</span>
      </div>
      <ul className="clarifying-notes-list">
        {questions.map((q, idx) => (
          <li key={`clarify-q-${idx}`}>{q}</li>
        ))}
      </ul>
    </div>
  );
}

/**
 * Interactive Follow-up Question Chips for the User to ask the AI Assistant.
 * (Clickable prompt chips: User -> Assistant).
 */
function InteractiveFollowupPrompts({ questions, onSelectQuestion }) {
  if (!questions?.length) return null;
  return (
    <section className="interactive-followup-section" aria-label="Gợi ý câu hỏi tiếp theo dành cho bạn">
      <div className="interactive-followup-header">
        <Sparkles size={14} className="followup-header-icon" />
        <span>Gợi ý câu hỏi bạn có thể hỏi tiếp (Nhấn để gửi nhanh):</span>
      </div>
      <div className="interactive-followup-chips" role="group">
        {questions.map((q, idx) => (
          <button
            key={`followup-chip-${idx}`}
            type="button"
            className="interactive-followup-chip"
            onClick={() => onSelectQuestion?.(q)}
            title={`Nhấn để gửi câu hỏi: "${q}"`}
          >
            <span className="followup-chip-sparkle">💬</span>
            <span className="followup-chip-text">{q}</span>
            <Send size={12} className="followup-chip-icon" />
          </button>
        ))}
      </div>
    </section>
  );
}

/**
 * Authoritative Ministry of Health Guideline References Footnote.
 */
function ResearchedSourcesFootnote({ sources }) {
  if (!sources?.length) return null;
  return (
    <section className="answer-sources-footnote" aria-label="Tài liệu tham khảo chuyên môn">
      <div className="sources-footnote-header">
        <span className="sources-footnote-title">Tài liệu tham khảo chuyên môn & văn bản quy chuẩn (Bộ Y tế):</span>
      </div>
      <ol className="sources-footnote-list">
        {sources.map((src, idx) => (
          <li key={`src-${src.source_id || idx}`}>
            <a
              href={src.url}
              target="_blank"
              rel="noreferrer"
              className="source-footnote-link"
              title={`${src.publisher}: ${src.title}`}
            >
              <span className="source-footnote-index">[{idx + 1}]</span>
              <strong className="source-footnote-name">{src.title}</strong>
              {src.publisher ? <span className="source-footnote-publisher"> — {src.publisher}</span> : null}
              <ExternalLink size={11} className="source-footnote-external" />
            </a>
          </li>
        ))}
      </ol>
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

export function GroundedAnswer({ answer, result, responseMeta = {}, onSelectQuestion }) {
  if (!answer) return null;

  const hasNarrative = answer.narrative?.length > 0;
  const verifiedAgentPrimary = responseMeta.verification_status === 'verified'
    && responseMeta.answer_origin === 'gateway_verified' && hasNarrative;
  const agentUnavailable = clinicalIntents.has(responseMeta.intent)
    && ['unavailable', 'timed_out', 'rejected', 'error', 'circuit_open'].includes(responseMeta.verification_status);

  // Clinical action/safety sections are never collapsed by brevity preferences.
  const isBrief = answer.presentation === 'brief' && !clinicalIntents.has(responseMeta.intent)
    && !(answer.safety_notes?.length) && !(answer.next_steps?.length)
    && !(answer.questions?.length) && !(answer.key_points?.length) && !(answer.clinical_hypotheses?.length)
    && !answer.requires_human_review
    && !['URGENT', 'EMERGENCY', 'CRITICAL'].includes(result?.urgency || result?.escalation_level);
  const isFocused = answer.presentation === 'focused';
  const researchedSources = answer.researched_sources || [];
  const sourcesById = new Map(
    researchedSources.map((source, index) => [source.source_id, { ...source, index: index + 1 }]),
  );

  const structuredUrgency = result?.urgency || result?.escalation_level;
  const showTechnicalMeta = responseMeta.showTechnicalMeta === true;
  const isClinical = clinicalIntents.has(responseMeta.intent);
  const status = statusConfig({
    urgency: structuredUrgency,
    overallRisk: result?.overall_risk,
    isClinical,
  });
  const StatusIcon = status.icon;

  // System clarifying questions (printed in document/narrative only)
  const systemClarifyingQuestions = [
    ...new Set([
      ...(Array.isArray(answer.display_questions) ? answer.display_questions : []),
      ...(Array.isArray(answer.questions) ? answer.questions : []),
    ]),
  ].slice(0, 3);

  // User follow-up questions (clickable chips for user to ask assistant)
  const userFollowupQuestions = [
    ...new Set([
      ...(Array.isArray(answer.suggested_followups) ? answer.suggested_followups : []),
      ...(!verifiedAgentPrimary ? getContextualFollowups(answer, responseMeta.intent, status.tone) : []),
    ]),
  ].slice(0, 3);

  const hypotheses = (answer.clinical_hypotheses || [])
    .filter((item) => !String(item).toLowerCase().startsWith('lưu ý:'))
    .slice(0, 4);
  const keyPoints = isClinical ? (answer.key_points || []) : (answer.key_points || []).slice(0, 5);
  const focusedRoutine = isFocused && responseMeta.intent === 'triage' && result?.urgency === 'ROUTINE';
  const nextSteps = focusedRoutine && Array.isArray(answer.display_next_steps)
    ? answer.display_next_steps : (answer.next_steps || []);
  const safetyNotes = answer.safety_notes || [];
  const limitations = (answer.limitations || []).slice(0, 2);

  // Narrative blocks: preserve all clinical context, system clarifying questions are printed in document
  const narrativeBlocks = hasNarrative ? answer.narrative : [];
  const hasNarrativeClarifying = narrativeBlocks.some((b) =>
    b.text?.startsWith('Bạn cho mình biết thêm:') || b.text?.startsWith('Thông tin cần báo nhân viên y tế')
  );

  const hasStructuredContent = Boolean(
    keyPoints.length
    || hypotheses.length
    || nextSteps.length
    || safetyNotes.length
    || systemClarifyingQuestions.length,
  );

  return (
    <div className="grounded-answer modern-clinical-layout">
      {(showTechnicalMeta || isClinical) && (
        <div className="answer-assurance-row" aria-label="Trạng thái kiểm chứng câu trả lời">
          <span className={`verification-pill ${responseMeta.verification_status || 'not_requested'}`}>
            {responseMeta.verification_status === 'verified'
              ? <CheckCircle2 size={13} />
              : <CircleHelp size={13} />}
            {verificationLabels[responseMeta.verification_status] || verificationLabels.not_requested}
          </span>
          {showTechnicalMeta && responseMeta.knowledge_approval && (
            <span className={`knowledge-pill ${responseMeta.knowledge_approval}`}>
              {knowledgeLabels[responseMeta.knowledge_approval]}
            </span>
          )}
        </div>
      )}

      <section className={`clinical-summary-card status-${status.tone}`}>
        {!isBrief && <div className="clinical-status-row">
          <span className={`clinical-status-badge ${status.tone}`}>
            <StatusIcon size={15} />
            <strong>{status.label}</strong>
          </span>
          {answer.evidence_state && (
            <span className={`clinical-evidence-chip ${answer.evidence_state}`}>
              {evidenceLabels[answer.evidence_state] || answer.evidence_state}
            </span>
          )}
        </div>}

        <div className="clinical-summary-copy">
          {!isBrief && <span className="clinical-kicker">{isClinical ? 'Đánh giá ban đầu' : 'Kết quả xử lý'}</span>}
          <h2>{answer.title}</h2>
          {agentUnavailable && <p role="status" className="agent-unavailable-notice">Chưa hoàn tất thẩm định câu trả lời. Nội dung bên dưới là hướng dẫn dự phòng, không phải tư vấn đã được thẩm định.</p>}
          {!verifiedAgentPrimary && <p>{focusedRoutine && answer.display_summary ? answer.display_summary : answer.summary}</p>}
          {!isBrief && <small>{status.helper}</small>}
        </div>
      </section>

      {verifiedAgentPrimary ? (
        <>
          <div className="answer-narrative clinical-agent-primary" data-answer-authority="verified-agent">
            {narrativeBlocks.map((block, index) => (
              <NarrativeBlock key={`primary-${index}`} block={block} sourcesById={sourcesById} />
            ))}
          </div>

          {safetyNotes.length > 0 && (
            <ClinicalSection
              title={status.tone === 'emergency' ? 'Hành động và dấu hiệu khẩn cấp' : 'Khi nào cần đi khám / cấp cứu'}
              icon={ShieldAlert}
              items={safetyNotes}
              tone={status.tone === 'emergency' ? 'danger' : 'warning'}
              className="clinical-section-wide"
            />
          )}

          {!hasNarrativeClarifying && systemClarifyingQuestions.length > 0 && (
            <ClinicalClarifyingNotes questions={systemClarifyingQuestions} />
          )}

          <ResearchedSourcesFootnote sources={researchedSources} />

          <InteractiveFollowupPrompts
            questions={userFollowupQuestions}
            onSelectQuestion={onSelectQuestion}
          />
        </>
      ) : !isBrief && hasStructuredContent ? (
        <div className="clinical-report-body">
          <ClinicalSection
            title={isClinical ? 'Dữ kiện chính' : 'Thông tin chính'}
            icon={Activity}
            items={isFocused && responseMeta.intent === 'triage' && status.tone === 'routine' ? [] : keyPoints}
            tone="neutral"
          />

          <ClinicalSection
            title="Khả năng cần cân nhắc"
            icon={Stethoscope}
            items={isFocused ? [] : hypotheses}
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

          {hasNarrativeClarifying && (
            <div className="clinical-clarifying-direct-wrap">
              {narrativeBlocks
                .filter((b) => b.text?.startsWith('Bạn cho mình biết thêm:') || b.text?.startsWith('Thông tin cần báo nhân viên y tế'))
                .map((block, i) => (
                  <NarrativeBlock key={`clarifying-direct-${i}`} block={block} sourcesById={sourcesById} />
                ))}
            </div>
          )}

          {!hasNarrativeClarifying && systemClarifyingQuestions.length > 0 && (
            <ClinicalClarifyingNotes questions={systemClarifyingQuestions} />
          )}

          <ResearchedSourcesFootnote sources={researchedSources} />

          <InteractiveFollowupPrompts
            questions={userFollowupQuestions}
            onSelectQuestion={onSelectQuestion}
          />
        </div>
      ) : !isBrief && hasNarrative ? (
        <>
          <div className="answer-narrative clinical-narrative-fallback">
            {narrativeBlocks.map((block, index) => (
              <NarrativeBlock
                key={`${block.text}-${index}`}
                block={block}
                sourcesById={sourcesById}
              />
            ))}
          </div>

          {!hasNarrativeClarifying && systemClarifyingQuestions.length > 0 && (
            <ClinicalClarifyingNotes questions={systemClarifyingQuestions} />
          )}

          <ResearchedSourcesFootnote sources={researchedSources} />

          <InteractiveFollowupPrompts
            questions={userFollowupQuestions}
            onSelectQuestion={onSelectQuestion}
          />
        </>
      ) : null}

      {!isBrief && limitations.length > 0 && (
        <div className="clinical-limitations">
          <AlertCircle size={15} />
          <div>
            <strong>{isClinical ? 'Giới hạn đánh giá từ xa' : 'Giới hạn xử lý'}</strong>
            {limitations.map((item, index) => <p key={`${item}-${index}`}>{item}</p>)}
          </div>
        </div>
      )}

      {(isBrief || isFocused || (hasNarrative && narrativeBlocks.length > 0)) && (
        <details className="clinical-detail-panel">
          <summary>
            <span><Stethoscope size={15} /> {isClinical ? 'Giải thích chi tiết' : 'Chi tiết xử lý'}</span>
            <ChevronDown size={14} className="panel-chevron" />
          </summary>
          <div className="clinical-detail-content">
            {narrativeBlocks.filter((b) => !hasNarrativeClarifying || (!b.text?.startsWith('Bạn cho mình biết thêm:') && !b.text?.startsWith('Thông tin cần báo nhân viên y tế'))).length > 0 ? (
              narrativeBlocks
                .filter((b) => !hasNarrativeClarifying || (!b.text?.startsWith('Bạn cho mình biết thêm:') && !b.text?.startsWith('Thông tin cần báo nhân viên y tế')))
                .map((block, index) => (
                  <NarrativeBlock
                    key={`detail-${index}`}
                    block={block}
                    sourcesById={sourcesById}
                  />
                ))
            ) : (
              <p>{answer.summary}</p>
            )}
          </div>
        </details>
      )}
    </div>
  );
}

function NarrativeBlock({ block, sourcesById }) {
  const isUrgentBlock = block.kind === 'urgent';
  const isCautionBlock = block.kind === 'caution';
  const isClarifyingBlock = block.text?.startsWith('Bạn cho mình biết thêm:') || block.text?.startsWith('Thông tin cần báo nhân viên y tế nếu có thể:');

  if (isClarifyingBlock) {
    const cleanPrompt = block.text.replace(/^(Bạn cho mình biết thêm:|Thông tin cần báo nhân viên y tế nếu có thể:)\s*/, '');
    return (
      <div className="narrative-clarifying-block">
        <div className="clarifying-block-header">
          <ClipboardList size={14} className="clarifying-block-icon" />
          <span>Thông tin cần biết thêm</span>
        </div>
        <p className="clarifying-block-text">
          <HighlightedText text={cleanPrompt} emphasis={block.emphasis} />
        </p>
      </div>
    );
  }

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
