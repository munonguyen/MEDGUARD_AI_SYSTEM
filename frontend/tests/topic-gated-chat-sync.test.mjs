import { describe, it } from 'node:test';
import assert from 'node:assert/strict';

import {
  calculateWilsonScore,
  detectSpamReviewNLP,
  calculateEigenTrust,
  classifyTopic,
  extractVndAmount,
  processUnifiedTopicGatedChat,
  getDefaultHealthProfile,
  getDefaultFinancialAssessment,
  TOPIC_MODES,
  TOPIC_LABELS,
} from '../src/chat/topicGatedSync.js';

describe('Suite 1: HEALTH_OVERVIEW_ONLY Gated Topic Sync', () => {
  it('1. Classifies Ibuprofen ADR query as HEALTH_OVERVIEW_ONLY', () => {
    const text = 'Sau khi uống thuốc giảm đau Ibuprofen lúc đói tôi bị đau rát dạ dày dữ dội';
    const mode = classifyTopic(text);
    assert.equal(mode, TOPIC_MODES.HEALTH_OVERVIEW_ONLY);
  });

  it('2. Mutates stomach organ health score from 95 to 38 and sets critical status', () => {
    const text = 'Sau khi uống thuốc giảm đau Ibuprofen lúc đói tôi bị đau rát dạ dày dữ dội';
    const result = processUnifiedTopicGatedChat(text);
    assert.ok(result.healthMutation, 'healthMutation must be populated');
    const stomach = result.healthMutation.organs.stomach;
    assert.equal(stomach.health_score, 38);
    assert.equal(stomach.vas_pain_score, 7);
    assert.equal(stomach.status, 'critical');
    assert.match(stomach.clinical_notes, /Ibuprofen/);
  });

  it('3. Updates overall health score from 81 to 66 and activates clinical ADR alert', () => {
    const text = 'Sau khi uống thuốc giảm đau Ibuprofen lúc đói tôi bị đau rát dạ dày dữ dội';
    const result = processUnifiedTopicGatedChat(text);
    assert.equal(result.healthMutation.overall_health_score, 66);
    assert.equal(result.healthMutation.vitals.heart_rate_bpm, 96);
    assert.equal(result.healthMutation.vitals.vas_pain_score, 7);

    const adr = result.healthMutation.adr_alert;
    assert.ok(adr, 'adr_alert must be present');
    assert.equal(adr.active, true);
    assert.equal(adr.level, 'danger');
    assert.match(adr.culprit_drug, /Ibuprofen/);
    assert.equal(adr.action_directive, 'DỪNG NGAY IBUPROFEN');
    assert.equal(adr.transfer_emergency_suggested, true);
  });

  it('4. Guarantees 100% isolation of expense data (expenseMutation is null)', () => {
    const text = 'Sau khi uống thuốc giảm đau Ibuprofen lúc đói tôi bị đau rát dạ dày dữ dội';
    const result = processUnifiedTopicGatedChat(text);
    assert.equal(result.expenseMutation, null, 'expenseMutation must be strictly null');
    assert.equal(result.label, TOPIC_LABELS[TOPIC_MODES.HEALTH_OVERVIEW_ONLY]);
  });
});

describe('Suite 2: EXPENSE_MANAGEMENT_ONLY Gated Topic Sync', () => {
  it('5. Classifies Nexium pharmacy purchase as EXPENSE_MANAGEMENT_ONLY', () => {
    const text = 'Vừa mua thuốc dạ dày Nexium tại nhà thuốc hết 480.000đ';
    const mode = classifyTopic(text);
    assert.equal(mode, TOPIC_MODES.EXPENSE_MANAGEMENT_ONLY);
  });

  it('6. Adds transaction of 480.000đ and recalculates actual spend and BHYT', () => {
    const text = 'Vừa mua thuốc dạ dày Nexium tại nhà thuốc hết 480.000đ';
    const initialExpense = getDefaultFinancialAssessment();
    const result = processUnifiedTopicGatedChat(text, { financialAssessment: initialExpense });

    assert.ok(result.expenseMutation, 'expenseMutation must be populated');
    assert.equal(result.expenseMutation.total_actual_spend_vnd, 2450000 + 480000);
    assert.equal(result.expenseMutation.recent_transactions[0].amount_vnd, 480000);
    assert.equal(result.expenseMutation.bhyt_paid_vnd, Math.round((2450000 + 480000) * 0.35));
  });

  it('7. Updates monthly budget target to 12.000.000đ when user sets budget', () => {
    const text = 'Đặt ngân sách y tế tháng này 12 triệu';
    const result = processUnifiedTopicGatedChat(text);
    assert.equal(result.topicMode, TOPIC_MODES.EXPENSE_MANAGEMENT_ONLY);
    assert.ok(result.expenseMutation, 'expenseMutation must be populated');
    assert.equal(result.expenseMutation.monthly_budget_target_vnd, 12000000);
  });

  it('8. Guarantees 100% isolation of organ health scores (healthMutation is null)', () => {
    const text = 'Vừa mua thuốc dạ dày Nexium tại nhà thuốc hết 480.000đ';
    const result = processUnifiedTopicGatedChat(text);
    assert.equal(result.healthMutation, null, 'healthMutation must be strictly null');
    assert.equal(result.label, TOPIC_LABELS[TOPIC_MODES.EXPENSE_MANAGEMENT_ONLY]);
  });
});

describe('Suite 3: DUAL_HEALTH_AND_EXPENSE Gated Topic Sync', () => {
  it('9. Classifies combined clinical symptom and pharmacy cost as DUAL_HEALTH_AND_EXPENSE', () => {
    const text = 'Hôm nay tôi vẫn còn đau rát thượng vị dạ dày nên đi khám và mua thuốc hết 650.000đ';
    const mode = classifyTopic(text);
    assert.equal(mode, TOPIC_MODES.DUAL_HEALTH_AND_EXPENSE);
  });

  it('10. Mutates stomach organ health score to 45 and overall score to 70', () => {
    const text = 'Hôm nay tôi vẫn còn đau rát thượng vị dạ dày nên đi khám và mua thuốc hết 650.000đ';
    const result = processUnifiedTopicGatedChat(text);
    assert.ok(result.healthMutation, 'healthMutation must be populated');
    assert.equal(result.healthMutation.overall_health_score, 70);
    assert.equal(result.healthMutation.organs.stomach.health_score, 45);
    assert.equal(result.healthMutation.organs.stomach.vas_pain_score, 6);
  });

  it('11. Simultaneously mutates expense ledger with 650.000đ transaction', () => {
    const text = 'Hôm nay tôi vẫn còn đau rát thượng vị dạ dày nên đi khám và mua thuốc hết 650.000đ';
    const result = processUnifiedTopicGatedChat(text);
    assert.ok(result.expenseMutation, 'expenseMutation must be populated');
    assert.equal(result.expenseMutation.total_actual_spend_vnd, 2450000 + 650000);
    assert.equal(result.expenseMutation.recent_transactions[0].amount_vnd, 650000);
  });

  it('12. Provides dual sync explanation and audit label', () => {
    const text = 'Hôm nay tôi vẫn còn đau rát thượng vị dạ dày nên đi khám và mua thuốc hết 650.000đ';
    const result = processUnifiedTopicGatedChat(text);
    assert.match(result.label, /ĐỒNG BỘ KÉP/);
    assert.ok(result.healthMutation !== null && result.expenseMutation !== null);
  });
});

describe('Suite 4: UNRELATED_NO_STATE_MUTATION Topic Preservation', () => {
  it('13. Classifies weather or casual banter as UNRELATED_NO_STATE_MUTATION', () => {
    const text = 'Hôm nay thời tiết ngoài trời thế nào nhỉ?';
    const mode = classifyTopic(text);
    assert.equal(mode, TOPIC_MODES.UNRELATED_NO_STATE_MUTATION);
  });

  it('14. Labels conversation as HỘI THOẠI CHUNG • KHÔNG CẬP NHẬT DỮ LIỆU', () => {
    const text = 'Hôm nay thời tiết ngoài trời thế nào nhỉ?';
    const result = processUnifiedTopicGatedChat(text);
    assert.equal(result.label, 'HỘI THOẠI CHUNG • KHÔNG CẬP NHẬT DỮ LIỆU');
  });

  it('15. Strictly preserves 100% health metrics without mutation', () => {
    const text = 'Hôm nay thời tiết ngoài trời thế nào nhỉ?';
    const result = processUnifiedTopicGatedChat(text);
    assert.equal(result.healthMutation, null, 'healthMutation must remain strictly null');
  });

  it('16. Strictly preserves 100% expense ledger metrics without mutation', () => {
    const text = 'Hôm nay thời tiết ngoài trời thế nào nhỉ?';
    const result = processUnifiedTopicGatedChat(text);
    assert.equal(result.expenseMutation, null, 'expenseMutation must remain strictly null');
  });
});

describe('Suite 5: Wilson Score 95% Confidence Interval Algorithm', () => {
  it('17. Returns lower bound 95% CI around ~0.88 for 95 positive out of 100 ratings', () => {
    const score = calculateWilsonScore(95, 100);
    assert.ok(score >= 0.88 && score <= 0.98, `Wilson score ${score} should be in [0.88, 0.98]`);
  });

  it('18. Correctly handles 0 total ratings without division by zero', () => {
    const score = calculateWilsonScore(0, 0);
    assert.equal(score, 0);
  });

  it('19. Returns 0 when all ratings are negative (0 positive, 50 total)', () => {
    const score = calculateWilsonScore(0, 50);
    assert.equal(score, 0);
  });

  it('20. Properly ranks a high-sample pharmacy (90/100) higher than a single-sample pharmacy (1/1)', () => {
    const scoreHigh = calculateWilsonScore(90, 100);
    const scoreLow = calculateWilsonScore(1, 1);
    assert.ok(scoreHigh > scoreLow, `High-sample score (${scoreHigh}) should exceed low-sample score (${scoreLow})`);
  });
});

describe('Suite 6: SpamReviewDetector NLP & EigenTrust Reputation', () => {
  it('21. Detects excessive exclamation, spam trigger words, and new unverified account', () => {
    const spamText = 'GIẢM GIÁ SỐC MUA NGAY SIÊU RẺ CAM KẾT KHỎI BỆNH 100% inbox zalo ngay!!!';
    const res = detectSpamReviewNLP(spamText, {
      accountAgeDays: 2,
      totalReviewsCount: 1,
      isVerifiedBuyer: false,
    });
    assert.equal(res.isSpam, true);
    assert.ok(res.spamConfidence >= 0.6, `Spam confidence ${res.spamConfidence} should be >= 0.6`);
    assert.ok(res.flaggedReasons.length >= 2, 'Should flag multiple spam indicators');
  });

  it('22. Validates authentic medical review with clinical context and verified user', () => {
    const genuineText = 'Dược sĩ tư vấn rất tận tâm, giải thích rõ cách uống Nexium trước ăn 30 phút và tác dụng phụ.';
    const res = detectSpamReviewNLP(genuineText, {
      accountAgeDays: 180,
      totalReviewsCount: 15,
      isVerifiedBuyer: true,
    });
    assert.equal(res.isSpam, false);
    assert.ok(res.authenticityScore >= 0.75, `Authenticity ${res.authenticityScore} should be >= 0.75`);
  });

  it('23. Calculates EigenTrust reputation convergence vector for 3 peers', () => {
    const matrix = [
      [0, 0.7, 0.3],
      [0.5, 0, 0.5],
      [0.4, 0.6, 0],
    ];
    const trust = calculateEigenTrust(matrix);
    assert.equal(trust.length, 3);
    const sum = trust.reduce((acc, v) => acc + v, 0);
    assert.ok(Math.abs(sum - 1.0) < 0.01, `EigenTrust vector sum ${sum} should be ~1.0`);
    assert.ok(trust.every((t) => t > 0), 'All trust scores should be positive');
  });

  it('24. EigenTrust correctly assigns highest global reputation to the most endorsed peer', () => {
    const matrix = [
      [0, 0.8, 0.2],
      [0.2, 0, 0.8],
      [0.1, 0.9, 0],
    ];
    const trust = calculateEigenTrust(matrix);
    // Peer 1 receives 0.8 from Peer 0 and 0.9 from Peer 2
    assert.ok(trust[1] > trust[0], `Peer 1 (${trust[1]}) should have higher trust than Peer 0 (${trust[0]})`);
    assert.ok(trust[1] > trust[2], `Peer 1 (${trust[1]}) should have higher trust than Peer 2 (${trust[2]})`);
  });
});

import {
  evaluateHolisticHealthInput,
  computeEpisodicHealthAnalytics,
  computePersonalizedHealthSolutions,
} from '../src/health/holisticHealthEngine.js';

describe('Suite 7: Holistic Symptom & Feeling Sync, Episodic Batches & 4-Pillar Solutions', () => {
  it('25. Automatically updates head, sleep, stress and energy when user reports stress, insomnia and eye strain', () => {
    const baseProfile = {
      overall_health_score: 96,
      vitals: { heart_rate_bpm: 72, temperature_celsius: 36.7, overall_pain_level: 0 },
      organs: [
        { id: 'head', vietnamese_name: 'Đầu & Thần kinh', status: 'normal', health_score: 98, pain_level: 0, symptoms: [] },
        { id: 'stomach', vietnamese_name: 'Dạ dày & Tiêu hoá', status: 'normal', health_score: 96, pain_level: 0, symptoms: [] },
      ],
    };
    const updated = evaluateHolisticHealthInput(
      baseProfile,
      'Hôm nay tôi đau đầu âm ỉ, căng thẳng stress, mất ngủ cả đêm và mỏi mắt nhìn mờ'
    );
    const head = updated.organs.find((o) => o.id === 'head');
    assert.ok(head.health_score < 90, 'Head health score should decrease');
    assert.ok(head.symptoms.length >= 2, 'Head symptoms should be recorded');
    assert.ok(updated.wellbeing.sleep_quality_score < 70, 'Sleep quality should reflect insomnia');
    assert.match(updated.wellbeing.stress_level_label, /Cao/);
  });

  it('26. Computes 3 clinical batches (Đợt 1, Đợt 2, Đợt 3) across HOUR, DAY, WEEK, MONTH timeframes', () => {
    for (const tf of ['HOUR', 'DAY', 'WEEK', 'MONTH']) {
      const analytics = computeEpisodicHealthAnalytics({ overall_health_score: 82 }, tf);
      assert.equal(analytics.batches.length, 3);
      assert.equal(analytics.series.length, 6);
      assert.equal(analytics.batches[0].code, 'ĐỢT 1');
      assert.equal(analytics.batches[1].code, 'ĐỢT 2');
      assert.match(analytics.batches[2].code, /ĐỢT 3/);
    }
  });

  it('27. Generates 4-pillar personalized health solutions tailored to active organ status', () => {
    const solutions = computePersonalizedHealthSolutions({
      overall_health_score: 68,
      safe_guardrail_alert: { title: 'ADR' },
      vitals: { temperature_celsius: 38.6, vas_pain_score: 6 },
      organs: [{ id: 'stomach', vietnamese_name: 'Dạ dày & Tiêu hoá', status: 'adverse_reaction', health_score: 42 }],
    });
    assert.equal(solutions.length, 4);
    assert.equal(solutions[0].priorityLevel, 'high');
    assert.ok(solutions[0].actionSteps.length >= 2);
  });
});
