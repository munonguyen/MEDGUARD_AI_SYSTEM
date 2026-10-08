import { Euler } from 'three';

const REST = {
  spine: [0, 0, 0], chest: [0, 0, 0], neck: [0, 0, 0], head: [0, 0, 0],
  leftShoulder: [0, 0, 0], rightShoulder: [0, 0, 0],
  leftUpperArm: [.08, .04, 1.30], rightUpperArm: [.08, -.04, -1.30],
  leftLowerArm: [-.12, 0, .28], rightLowerArm: [-.12, 0, -.28],
  leftHand: [0, .04, .04], rightHand: [0, -.04, -.04],
};
const smoothPulse = (t, start, duration) => {
  const x = (t - start) / duration;
  return x > 0 && x < 1 ? Math.sin(Math.PI * x) ** 2 : 0;
};

// C2 envelope: preparation, a readable hold, then a slower release.
const ease = x => { x = Math.max(0, Math.min(1,x)); return x*x*x*(x*(x*6-15)+10); };
const phraseEnvelope = (t, delay, duration) => {
  const x = (t-delay)/duration;
  return x <= 0 || x >= 1 ? 0 : ease(x/.27) * (1-ease((x-.58)/.42));
};
// Critically damped joints retain velocity across interruptions. Small integration
// steps and explicit speed/acceleration limits also handle low rendering rates.
function spring(state, target, omega, dt, maxSpeed) {
  const count=Math.max(1,Math.ceil(dt*120)), h=dt/count;
  const maxAcceleration=maxSpeed*5;
  for(let i=0;i<count;i++) {
    const acceleration=Math.max(-maxAcceleration,Math.min(maxAcceleration,
      omega*omega*(target-state.position)-2*omega*state.velocity));
    const velocity=Math.max(-maxSpeed,Math.min(maxSpeed,state.velocity+acceleration*h));
    state.position+=(state.velocity+velocity)*.5*h;
    state.velocity=velocity;
  }
}

export class DoctorMotion {
  constructor(vrm, persona) {
    this.vrm = vrm; this.persona = persona; this.pose = 'pose_idle';
    this.tone = 'empathetic'; this.expression = 'neutral';
    this.time = 0; this.speechTime = 0; this.speechWeight = 0;
    this.bones = Object.fromEntries(Object.keys(REST).map(name => [name, vrm.humanoid?.getNormalizedBoneNode(name)]));
    this.euler = new Euler();
    this.joints = Object.fromEntries(Object.entries(REST).map(([name,xyz])=>[name,xyz.map(position=>({position,velocity:0}))]));
    this.pauseAge = 10; this.audioAccent = 0;
    this.values = {};
    this.blinkAt = 2.5 + Math.random() * 2; this.blinkStarted = -10;
    this.gesturePlan = ['explain', 'invite', 'reassure', 'explain'];
    for (const [name, xyz] of Object.entries(REST)) this.bones[name]?.quaternion.setFromEuler(this.euler.set(...xyz));
  }
  setPose(pose) { if(this.pose !== pose) { this.pose = pose; this.poseStarted = this.time; } else if(pose === 'pose_wave') this.poseStarted = this.time; }
  setExpression(expression) { this.expression = expression; }
  startUtterance(text = '') {
    this.speechTime = 0;
    const content = text.toLocaleLowerCase('vi');
    const greeting = /xin chào|chào bạn/.test(content);
    const cautious = /cấp cứu|khẩn cấp|gọi 115/.test(content);
    const sentences = content.match(/[^.!?]+[.!?]*/gu) || [content];
    const classify = (sentence, index) => {
      if (index === 0 && greeting) return 'greeting';
      if (/cấp cứu|khẩn cấp|gọi 115|không tự|ngừng/.test(sentence)) return 'caution';
      if (/\?|cho biết|chia sẻ|bạn có/.test(sentence)) return 'invite';
      if (/lo lắng|khó chịu|lắng nghe|đồng hành|ghi nhận/.test(sentence)) return 'reassure';
      if (/đầu tiên|tiếp theo|bước|thứ nhất|thứ hai/.test(sentence)) return 'enumerate';
      return index % 3 === 2 ? 'present' : 'explain';
    };
    this.gesturePlan = sentences.slice(0,12).map(classify);
    if (!this.gesturePlan.length) this.gesturePlan = [cautious ? 'caution' : 'explain'];
    this.gesturePlan.push('explain','present','enumerate','invite');
    // Variation is stable for the utterance; it never jitters per frame.
    this.utteranceSeed = [...content].reduce((hash,c)=>(hash*31+c.codePointAt(0))>>>0,17);
    this.gestureDurations = this.gesturePlan.map((_,i)=>3.8+((this.utteranceSeed >>> (i%8))%17)*.1);

  }
  update(dt, { speaking, look, audioLevel = 0, hasAudio = false, reducedMotion = false }) {
    dt = Math.min(Math.max(dt, 0), .15); this.time += dt;
    if (speaking) this.speechTime += dt;
    const replyAge = this.time - (this.poseStarted ?? this.time);
    const responding = this.pose === 'pose_acknowledge' && replyAge < 3.8;
    const alpha = 1 - Math.exp(-dt * 7);
    this.pauseAge = speaking ? 0 : this.pauseAge + dt;
    this.audioAccent += (Math.min(1, audioLevel*5) - this.audioAccent) * (1-Math.exp(-dt*9));
    this.speechWeight += ((speaking || responding || this.pauseAge < .18 ? 1 : 0) - this.speechWeight) * alpha;
    const targets = Object.fromEntries(Object.entries(REST).map(([k, v]) => [k, [...v]]));
    const listen = this.pose === 'pose_listening';
    const think = this.pose === 'pose_thinking';
    const cautious = this.tone === 'cautious';
    const time = this.time;
    if (!reducedMotion) {
      targets.spine[0] = Math.sin(time * 1.35) * .004;
      targets.chest[0] = Math.sin(time * 1.35 - .2) * .006;
      // Quiet asymmetric posture shifts, breathing, and loose shoulders.
      const shift = Math.sin(time*.29)*.012 + Math.sin(time*.47+1.3)*.005;
      targets.spine[2] = shift;
      targets.chest[2] = -shift*.55;
      targets.leftShoulder[2] = Math.sin(time*1.35-.35)*.004;
      targets.rightShoulder[2] = -Math.sin(time*1.35+.1)*.004;
      targets.leftLowerArm[2] += .035 + Math.sin(time*.41)*.012;
      targets.rightLowerArm[2] -= .055 + Math.sin(time*.37+.8)*.012;
      if (listen) {
        const nod = smoothPulse((time-(this.poseStarted??time))%7.3,1.15,1.3);
        targets.spine[0] -= .012;
        targets.neck[0] += nod*.018;
        targets.head[0] += nod*.035;
      }
      if (think) {
        targets.leftLowerArm[2] += .25;
        targets.rightLowerArm[2] -= .12;
        targets.chest[1] -= .012;
      }
      targets.head = [targets.head[0] -look.y * .09 + (listen ? -.025 : think ? .02 : 0), look.x * .22, listen ? .025 : 0];
      targets.neck = [targets.neck[0] -look.y * .035, look.x * .055, 0];
      targets.chest[1] += look.x * .022;
      // Smoothly alternate a phrase gesture with a quiet rest, involving the
      // shoulder, forearm, wrist, torso and head rather than moving one joint.
      const gestureTime = responding ? replyAge : this.speechTime;
      const durations = this.gestureDurations || [4.4, 5.2, 4.8, 5.5, 4.6, 5.0];
      const total = durations.reduce((a,b) => a+b,0);
      let phase = gestureTime % total;
      let index = 0;
      while (phase >= durations[index]) { phase -= durations[index]; index++; }
      const duration = durations[index];
      let kind = this.gesturePlan[index % this.gesturePlan.length];
      if (kind === 'greeting' && gestureTime >= total) kind = 'explain';
      this.activeGesture = speaking || responding ? kind : 'idle';
      const weight = this.speechWeight * (cautious ? .65 : 1);
      const shoulder = phraseEnvelope(phase, .10, duration - .30) * weight;
      // The elbow anticipates the shoulder; wrist arrives later. Flexion is
      // held throughout the lift instead of extending a straight arm sideways.
      const elbow = phraseEnvelope(phase, 0, duration - .08) * weight;
      const wrist = phraseEnvelope(phase, .22, duration - .30) * weight;
      const left = kind !== 'greeting' && ((index + ((this.utteranceSeed || 0) >>> (index%8))) % 3 === 1);
      const arm = left ? 'left' : 'right';
      const sign = left ? -1 : 1;
      const open = kind === 'invite' || kind === 'present';
      const style = {
        explain: {lift:.15,bend:1.50,turn:.16,lean:0},
        invite: {lift:.20,bend:1.72,turn:.28,lean:-.012},
        reassure: {lift:.10,bend:1.82,turn:.09,lean:-.025},
        present: {lift:.23,bend:1.58,turn:.24,lean:.006},
        enumerate: {lift:.16,bend:1.68,turn:.12,lean:0},
        caution: {lift:.12,bend:1.65,turn:.08,lean:-.008},
      }[kind] || {lift:.14,bend:1.55,turn:.15,lean:0};
      // Small arcs keep a held hand alive without another whole-arm swing.
      const arc = Math.sin(phase*1.9 + index*.7)*wrist;
      targets.chest[0] += shoulder*style.lean;
      const accent = this.audioAccent * wrist;
      targets[arm+'Shoulder'][1] -= sign*shoulder*.025;
      targets[arm+'Shoulder'][2] += sign*shoulder*.018;
      targets[arm + 'UpperArm'][0] += shoulder * (open ? .18 : .12);
      targets[arm + 'UpperArm'][1] -= sign * shoulder * .12;
      targets[arm + 'UpperArm'][2] += sign * shoulder * style.lift;
      targets[arm + 'LowerArm'][0] -= elbow * .20;
      targets[arm + 'LowerArm'][2] += sign * elbow * style.bend;
      targets[arm + 'Hand'][0] += wrist * .09 + accent*.022 + arc*.026;
      targets[arm + 'LowerArm'][1] += sign*arc*.035;
      targets[arm + 'Hand'][1] -= sign * wrist * style.turn;
      targets[arm + 'Hand'][2] -= sign * wrist * .12;
      // Counterbalance the other arm and distribute rotation through the torso.
      const other = left ? 'right' : 'left';
      targets[other + 'LowerArm'][2] -= sign * shoulder * (kind === 'present' ? .7 : .08);
      targets[other + 'UpperArm'][0] += shoulder * .035;
      targets.chest[1] += sign * shoulder * .035;
      targets.spine[1] += sign * smoothPulse(phase, .12, duration - .3) * weight * .015;
      targets.spine[2] += sign * shoulder * .012;
      targets.head[2] -= sign * wrist * .02;
      targets.neck[0] += smoothPulse(phase, 1.4, 1.5) * weight * .014;
      targets.head[0] += smoothPulse(phase, 1.6, 1.4) * weight * .025;
      targets.spine[1] += Math.sin(time * .53) * .008;
      targets.chest[2] += Math.sin(time * .53 - .3) * .006;
      if (kind === 'reassure') {
        targets.chest[0] -= shoulder * .025;
        targets.head[0] -= shoulder * .025;
        targets[arm + 'UpperArm'][1] -= sign * shoulder * .10;
      }
      if (kind === 'enumerate') targets[arm + 'Hand'][0] += Math.sin(phase * 3.5) * wrist * .035;
      if (kind === 'caution') targets[arm + 'Hand'][0] += wrist * .09 + accent*.022 + arc*.026;
      targets[arm + 'LowerArm'][1] += sign*arc*.035;
      // Greeting is a bent-elbow wave close to the shoulder, not a lateral
      // straight-arm raise. Use the same authored pose for preview and speech.
      const waveAge = this.pose === 'pose_wave' ? time - (this.poseStarted ?? time) : phase;
      const wave = this.pose === 'pose_wave' ? phraseEnvelope(waveAge,0,3.4)
        : kind === 'greeting' ? shoulder : 0;
      if (wave > 0) {
        targets.rightUpperArm[0] = REST.rightUpperArm[0] + wave * .18;
        targets.rightUpperArm[1] = REST.rightUpperArm[1] - wave * .12;
        targets.rightUpperArm[2] = REST.rightUpperArm[2] + wave * .62;
        targets.rightLowerArm[0] = REST.rightLowerArm[0] - wave * .20;
        targets.rightLowerArm[2] = REST.rightLowerArm[2] + wave * 2.60;
        targets.rightHand[1] = REST.rightHand[1] - wave * .18;
        targets.rightHand[2] = REST.rightHand[2] + Math.sin(waveAge * 5.5) * phraseEnvelope(waveAge,.65,1.65) * .12;
        targets.chest[1] += wave * .025;
        targets.head[2] -= wave * .015;
      }
      targets.head[1] += Math.sin(time * .42) * .008;
      if (think) targets.head[1] += .045;

    }
    for (const [name, xyz] of Object.entries(targets)) {
      const response = name.endsWith('Hand') ? 15 : name.endsWith('LowerArm') ? 13 : name.endsWith('UpperArm') ? 11 : 12;
      const joint = this.joints[name];
      for(let axis=0;axis<3;axis++) spring(joint[axis],xyz[axis],response,dt,name.endsWith('Hand') ? 3 : name.includes('Arm') ? 2.4 : 1.2);
      this.bones[name]?.quaternion.setFromEuler(this.euler.set(...joint.map(v=>v.position)));
    }
    if (time >= this.blinkAt) { this.blinkStarted = time; this.blinkAt = time + 3 + Math.random() * 3; }
    const blinkAge = time - this.blinkStarted;
    const blink = blinkAge < .075 ? ease(blinkAge/.075) : blinkAge < .23 ? 1-ease((blinkAge-.075)/.155) : 0;
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
