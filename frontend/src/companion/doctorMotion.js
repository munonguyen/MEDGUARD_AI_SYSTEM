import { Euler, Quaternion } from 'three';

const REST = {
  spine: [0, 0, 0], chest: [0, 0, 0], neck: [0, 0, 0], head: [0, 0, 0],
  leftUpperArm: [.08, .04, 1.30], rightUpperArm: [.08, -.04, -1.30],
  leftLowerArm: [-.12, 0, .12], rightLowerArm: [-.12, 0, -.12],
  leftHand: [0, .04, .04], rightHand: [0, -.04, -.04],
};
const smoothPulse = (t, start, duration) => {
  const x = (t - start) / duration;
  return x > 0 && x < 1 ? Math.sin(Math.PI * x) ** 2 : 0;
};

// Time-based quaternion damping makes transitions identical at 30/60/120 fps.
export class DoctorMotion {
  constructor(vrm, persona) {
    this.vrm = vrm; this.persona = persona; this.pose = 'pose_idle';
    this.tone = 'empathetic'; this.expression = 'neutral';
    this.time = 0; this.speechTime = 0; this.speechWeight = 0;
    this.bones = Object.fromEntries(Object.keys(REST).map(name => [name, vrm.humanoid?.getNormalizedBoneNode(name)]));
    this.target = new Quaternion(); this.euler = new Euler();
    this.values = {};
    this.blinkAt = 2.5 + Math.random() * 2; this.blinkStarted = -10;
    this.gesturePlan = ['explain', 'invite', 'reassure', 'explain'];
    for (const [name, xyz] of Object.entries(REST)) this.bones[name]?.quaternion.setFromEuler(this.euler.set(...xyz));
  }
  setPose(pose) { this.pose = pose; this.poseStarted = this.time; }
  setExpression(expression) { this.expression = expression; }
  startUtterance(text = '') {
    this.speechTime = 0;
    const content = text.toLocaleLowerCase('vi');
    const greeting = /xin chào|chào bạn/.test(content);
    const cautious = /cấp cứu|khẩn cấp|gọi 115/.test(content);
    this.gesturePlan = [greeting ? 'greeting' : cautious ? 'caution' : 'explain',
      content.includes('?') ? 'invite' : 'reassure', 'explain', 'present', 'enumerate', 'invite'];
  }
  update(dt, { speaking, look, audioLevel = 0, hasAudio = false, reducedMotion = false }) {
    dt = Math.min(Math.max(dt, 0), .15); this.time += dt;
    if (speaking) this.speechTime += dt;
    const replyAge = this.time - (this.poseStarted ?? this.time);
    const responding = this.pose === 'pose_acknowledge' && replyAge < 3.8;
    const alpha = 1 - Math.exp(-dt * 7);
    this.speechWeight += ((speaking || responding ? 1 : 0) - this.speechWeight) * alpha;
    const targets = Object.fromEntries(Object.entries(REST).map(([k, v]) => [k, [...v]]));
    const listen = this.pose === 'pose_listening';
    const think = this.pose === 'pose_thinking';
    const cautious = this.tone === 'cautious';
    const time = this.time;
    if (!reducedMotion) {
      targets.spine[0] = Math.sin(time * 1.35) * .004;
      targets.chest[0] = Math.sin(time * 1.35 - .2) * .003;
      targets.head = [-look.y * .09 + (listen ? -.025 : think ? .02 : 0), look.x * .22, listen ? .025 : 0];
      targets.neck = [-look.y * .035, look.x * .055, 0];
      targets.chest[1] = look.x * .022;
      // Smoothly alternate a phrase gesture with a quiet rest, involving the
      // shoulder, forearm, wrist, torso and head rather than moving one joint.
      const gestureTime = speaking ? this.speechTime : responding ? replyAge : 0;
      const cycle = Math.floor(gestureTime / 4.8);
      const phase = gestureTime % 4.8;
      const index = Math.floor(gestureTime / 4.8) % this.gesturePlan.length;
      const kind = this.gesturePlan[index];
      this.activeGesture = speaking || responding ? kind : 'idle';
      const gesture = smoothPulse(phase, 0, 4.3) * this.speechWeight * (cautious ? .65 : 1);
      const left = cycle % 2 === 1;
      const arm = left ? 'left' : 'right';
      const sign = left ? -1 : 1;
      targets[arm + 'UpperArm'][0] += gesture * .24;
      targets[arm + 'UpperArm'][2] += sign * gesture * .24;
      targets[arm + 'LowerArm'][0] -= gesture * .10;
      const elbow = smoothPulse(phase, .12, 4.15) * this.speechWeight * (cautious ? .65 : 1);
      const wrist = smoothPulse(phase, .28, 3.95) * this.speechWeight;
      targets[arm + 'LowerArm'][2] += sign * elbow * (kind === 'invite' ? 1.0 : .82);
      targets[arm + 'Hand'][1] -= sign * wrist * .20;
      targets[arm + 'Hand'][2] -= sign * gesture * .10;
      targets.chest[1] += sign * gesture * .025;
      targets.spine[2] += sign * gesture * .009;
      targets.head[2] -= sign * gesture * .014;
      if (kind === 'reassure') {
        targets.head[0] -= gesture * .028;
        targets.chest[0] -= gesture * .014;
      }
      if (kind === 'present') {
        const other = left ? 'right' : 'left';
        targets[other + 'UpperArm'][2] -= sign * gesture * .15;
        targets[other + 'LowerArm'][2] -= sign * elbow * .65;
        targets[other + 'Hand'][1] += sign * wrist * .16;
      }
      if (kind === 'enumerate') {
        targets[arm + 'LowerArm'][0] -= gesture * .18;
        targets[arm + 'Hand'][0] += Math.sin(phase * 4) * wrist * .035;
      }
      targets.neck[0] += smoothPulse(phase, 1.6, 1.5) * .012 * this.speechWeight;
      targets.spine[1] += Math.sin(time * .53) * .012;
      targets.chest[2] += Math.sin(time * .53 - .3) * .006;
      if (kind === 'caution') targets[arm + 'Hand'][0] += gesture * .15;
      if (kind === 'greeting') {
        targets.rightUpperArm[2] += gesture * .85;
        targets.rightLowerArm[2] += gesture * .75;
        targets.rightHand[2] += Math.sin(this.speechTime * 7) * gesture * .12;
      }
      targets.head[0] += smoothPulse(phase, 1.8, 1.1) * .028 * this.speechWeight;
      targets.head[1] += Math.sin(time * .42) * .008;
      if (think) targets.head[1] += .045;
      if (this.pose === 'pose_wave') {
        const age = time - (this.poseStarted ?? time);
        const wave = smoothPulse(age, 0, 2.4);
        targets.rightUpperArm[2] += wave * 1.0;
        targets.rightLowerArm[2] += wave * 1.5;
        targets.rightHand[2] += Math.sin(age * 7) * wave * .12;
      }
    }
    for (const [name, xyz] of Object.entries(targets)) {
      this.target.setFromEuler(this.euler.set(...xyz));
      this.bones[name]?.quaternion.slerp(this.target, alpha);
    }
    if (time >= this.blinkAt) { this.blinkStarted = time; this.blinkAt = time + 3 + Math.random() * 3; }
    const blinkAge = time - this.blinkStarted;
    const blink = blinkAge < .08 ? blinkAge / .08 : blinkAge < .22 ? 1 - (blinkAge - .08) / .14 : 0;
    this.setValue('blink', Math.max(0, blink), 1);
    const accent = speaking ? .025 * (1 + Math.sin(this.speechTime * 1.7)) : 0;
    const happy = cautious ? 0 : accent + (this.tone === 'encouraging' ? .20 : this.tone === 'empathetic' ? .12 : .035);
    this.setValue('happy', this.expression === 'surprised' ? 0 : happy, alpha);
    this.setValue('relaxed', think ? .10 : .035 + (listen ? .04 : 0), alpha);
    this.setValue('sad', cautious || this.activeGesture === 'reassure' ? .035 : 0, alpha);
    for (const [name, value] of Object.entries({lookRight:look.x, lookLeft:-look.x, lookUp:look.y, lookDown:-look.y})) this.setValue(name, Math.max(0, value) * .12, alpha);
    this.setValue('surprised', this.expression === 'surprised' ? .10 : 0, alpha);
    // RMS gates mouth movement during actual audio pauses; no invented phoneme alignment.
    const fallback = Math.max(0, Math.sin(this.speechTime * 14) * .10 + Math.sin(this.speechTime * 23) * .06);
    const opening = speaking ? (hasAudio ? Math.min(.55, Math.max(0, audioLevel - .012) * 3.8) : fallback) : 0;
    this.setValue('aa', opening * .75, 1 - Math.exp(-dt * 24));
    this.setValue('oh', opening * .16, alpha);
    this.setValue('ih', opening * .09, alpha);
    this.setValue('ee', 0, alpha);
    this.vrm.update(dt);
  }
  setValue(name, target, alpha) {
    this.values[name] = (this.values[name] ?? 0) + (target - (this.values[name] ?? 0)) * alpha;
    this.vrm.expressionManager?.setValue(name, this.values[name]);
  }
}
