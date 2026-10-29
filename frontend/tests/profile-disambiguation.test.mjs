import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import {
  isThirdPartyMessage,
  extractUserProfileProposal,
  calculateBmi
} from '../src/health/profileDisambiguation.js';

describe('Profile Disambiguation & Self vs Third-Party Extraction', () => {
  it('1. Correctly classifies relative/third-party messages as NOT user self-profile', () => {
    const tp1 = isThirdPartyMessage('Bố tôi năm nay 65 tuổi bị tăng huyết áp và đau khớp gối');
    assert.equal(tp1.isThirdParty, true);

    const prop1 = extractUserProfileProposal('Bố tôi năm nay 65 tuổi bị tăng huyết áp, số BHYT là DN4797912345678');
    assert.equal(prop1.isThirdParty, true);
    assert.equal(prop1.hasProposal, false);

    const prop2 = extractUserProfileProposal('Mẹ tôi có bảo hiểm y tế ở BV Bạch Mai, dị ứng aspirin');
    assert.equal(prop2.isThirdParty, true);
    assert.equal(prop2.hasProposal, false);

    const prop3 = extractUserProfileProposal('Con tôi 4 tuổi bị sốt cao 39 độ, dị ứng penicillin');
    assert.equal(prop3.isThirdParty, true);
    assert.equal(prop3.hasProposal, false);

    const prop4 = extractUserProfileProposal('Bác tôi bị đau ngực trái');
    assert.equal(prop4.isThirdParty, true);
    assert.equal(prop4.hasProposal, false);
  });

  it('2. Extracts full self-provided name, year of birth and age', () => {
    const res = extractUserProfileProposal('Tôi tên là Nguyễn Văn An, sinh năm 1990');
    assert.equal(res.isThirdParty, false);
    assert.equal(res.hasProposal, true);
    assert.equal(res.fields.display_name, 'Nguyễn Văn An');
    assert.equal(res.fields.age, 36);
    assert.equal(res.fields.dob, '1990-01-01');
  });

  it('3. Extracts BHYT card, primary care hospital, and coverage rate', () => {
    const res = extractUserProfileProposal('Số thẻ BHYT của tôi là DN 4 79 79 12345678, KCB ban đầu tại BV Chợ Rẫy, mức hưởng 80%');
    assert.equal(res.isThirdParty, false);
    assert.equal(res.hasProposal, true);
    assert.equal(res.fields.bhyt_number, 'DN4797912345678');
    assert.equal(res.fields.bhyt_hospital, 'BV Chợ Rẫy');
    assert.equal(res.fields.bhyt_rate, 80);
    assert.equal(res.fields.is_verified, true);
  });

  it('4. Extracts height, weight and accurately calculates Asian WHO BMI', () => {
    const res = extractUserProfileProposal('Cập nhật profile: tôi cao 1m75 nặng 68kg, nhóm máu O+');
    assert.equal(res.isThirdParty, false);
    assert.equal(res.hasProposal, true);
    assert.equal(res.fields.height_cm, 175);
    assert.equal(res.fields.weight_kg, 68);
    assert.equal(res.fields.bmi, 22.2);
    assert.equal(res.fields.blood_type, 'O+');
  });

  it('5. Extracts Commercial Life Insurance and BHXH/VssID code', () => {
    const res = extractUserProfileProposal('Tôi có bảo hiểm nhân thọ Prudential hạn mức 300 triệu, mã BHXH là 0790901234');
    assert.equal(res.isThirdParty, false);
    assert.equal(res.hasProposal, true);
    assert.equal(res.fields.life_insurance_provider, 'Prudential');
    assert.equal(res.fields.coverage_limit_vnd, 300000000);
    assert.equal(res.fields.bhxh_number, '0790901234');
  });

  it('6. Extracts Allergies and Chronic Conditions for self', () => {
    const res = extractUserProfileProposal('Tôi bị dị ứng Penicillin và Paracetamol, có bệnh nền tăng huyết áp');
    assert.equal(res.isThirdParty, false);
    assert.equal(res.hasProposal, true);
    assert.ok(res.fields.allergies.includes('Penicillin'));
    assert.ok(res.fields.allergies.includes('Paracetamol'));
    assert.ok(res.fields.conditions.some(c => c.toLowerCase().includes('tăng huyết áp')));
  });

  it('7. Tests BMI calculation utility boundaries', () => {
    const thin = calculateBmi(170, 50);
    assert.equal(thin.category.includes('Thiếu cân'), true);

    const normal = calculateBmi(175, 68);
    assert.equal(normal.category.includes('Chuẩn Châu Á'), true);

    const overweight = calculateBmi(165, 65);
    assert.equal(overweight.category.includes('Tiền béo phì'), true);

    const obese = calculateBmi(160, 75);
    assert.equal(obese.category.includes('Béo phì'), true);
  });
});
