import test from 'node:test';
import assert from 'node:assert/strict';

import {
  detectConversationalNavigation,
  extractMedicationProposal,
  extractAppointmentProposal,
  extractNavigationAction,
  NAV_COMMANDS,
} from '../src/chat/chatActionInteractions.js';

test('1. Conversational Navigation Command Detection', () => {
  const t1 = detectConversationalNavigation('Mở trang sức khỏe và cơ thể 3D');
  assert.equal(t1?.isNavCommand, true);
  assert.equal(t1?.targetView, NAV_COMMANDS.HEALTH);

  const t2 = detectConversationalNavigation('Xem chi tiêu y tế và tiết kiệm care');
  assert.equal(t2?.isNavCommand, true);
  assert.equal(t2?.targetView, NAV_COMMANDS.SPENDING);

  const t3 = detectConversationalNavigation('Mở lịch khám bệnh của tôi');
  assert.equal(t3?.isNavCommand, true);
  assert.equal(t3?.targetView, NAV_COMMANDS.SCHEDULE);

  const t4 = detectConversationalNavigation('Mở lịch uống thuốc cá nhân');
  assert.equal(t4?.isNavCommand, true);
  assert.equal(t4?.targetView, NAV_COMMANDS.MEDICATION);

  const t5 = detectConversationalNavigation('Tôi muốn gặp bác sĩ 3D live');
  assert.equal(t5?.isNavCommand, true);
  assert.equal(t5?.targetView, NAV_COMMANDS.COMPANION);

  const t6 = detectConversationalNavigation('Mở bản đồ chỉ đường real-time');
  assert.equal(t6?.isNavCommand, true);
  assert.equal(t6?.targetView, NAV_COMMANDS.NAVIGATION);

  const t7 = detectConversationalNavigation('Chỉnh sửa hồ sơ cá nhân và BHYT');
  assert.equal(t7?.isNavCommand, true);
  assert.equal(t7?.targetView, NAV_COMMANDS.PROFILE);

  const t8 = detectConversationalNavigation('Thời tiết hôm nay thế nào');
  assert.equal(t8, null);
});

test('2. Medication Proposal Extraction from Chat', () => {
  const p1 = extractMedicationProposal('Lên lịch cho tôi uống Nexium 40mg sáng 1 viên sau ăn lúc 8h');
  assert.equal(p1?.hasProposal, true);
  assert.match(p1.medication.name, /Nexium/i);
  assert.equal(p1.medication.dosage, '1 viên');
  assert.equal(p1.medication.timing, '08:00');
  assert.equal(p1.medication.slot, 'morning');
  assert.match(p1.medication.instruction, /sau bữa ăn/i);

  const p2 = extractMedicationProposal('Nhắc tôi uống Panadol 500mg lúc 8h sáng và 20h tối');
  assert.equal(p2?.hasProposal, true);
  assert.match(p2.medication.name, /Panadol/i);
  assert.equal(p2.medication.strength, '500mg');
  assert.ok(p2.medication.times.length >= 2);
  assert.ok(p2.medication.times.includes('08:00'));
  assert.ok(p2.medication.times.includes('20:00'));

  const p3 = extractMedicationProposal('Hôm nay tôi thấy mệt mỏi trong người');
  assert.equal(p3, null);
});

test('3. Doctor Appointment Booking Proposal Extraction from Chat', () => {
  const context = { display_name: 'Nguyễn Văn An', phone: '0912345678', bhyt_number: 'DN4797912345678', bhyt_rate: 80 };
  const a1 = extractAppointmentProposal('Tôi muốn đặt lịch khám tim mạch sáng mai lúc 9h với BS Cường', context);
  assert.equal(a1?.hasProposal, true);
  assert.equal(a1.appointment.department, 'Nội Tim mạch');
  assert.match(a1.appointment.doctor, /Cường/i);
  assert.match(a1.appointment.timeSlot, /09:00/);
  assert.equal(a1.appointment.patientName, 'Nguyễn Văn An');
  assert.equal(a1.appointment.bhytCovered, true);
  assert.equal(a1.appointment.bhytRate, 80);

  const a2 = extractAppointmentProposal('Hẹn khám tiêu hóa dạ dày tại Bệnh viện Chợ Rẫy', context);
  assert.equal(a2?.hasProposal, true);
  assert.match(a2.appointment.department, /Tiêu hóa/i);
  assert.match(a2.appointment.hospital, /Chợ Rẫy/i);

  const a3 = extractAppointmentProposal('Xin chào MedGuard');
  assert.equal(a3, null);
});

test('4. Navigation Action & Medical POI Extraction from Chat', () => {
  const n1 = extractNavigationAction('Chỉ đường đến Bệnh viện Chợ Rẫy');
  assert.equal(n1?.hasAction, true);
  assert.match(n1.navigation.poiName, /Chợ Rẫy/i);
  assert.equal(n1.navigation.category, 'hospital');

  const n2 = extractNavigationAction('Tìm nhà thuốc GPP gần nhất để mua thuốc');
  assert.equal(n2?.hasAction, true);
  assert.match(n2.navigation.poiName, /Long Châu|GPP/i);
  assert.equal(n2.navigation.category, 'pharmacy');

  const n3 = extractNavigationAction('Gọi cấp cứu 115 khẩn cấp');
  assert.equal(n3?.hasAction, true);
  assert.equal(n3.navigation.category, 'emergency');

  const n4 = extractNavigationAction('Hôm nay ăn gì cho khỏe');
  assert.equal(n4, null);
});
