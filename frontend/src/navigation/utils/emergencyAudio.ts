/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 * MedGuard AI - Emergency Siren & Auditory Alert Synthesizer (Web Audio API)
 * Generates real ambulance two-tone hi-lo emergency siren without external audio files.
 */

class EmergencySirenSynthesizer {
  private audioCtx: AudioContext | null = null;
  private oscillator: OscillatorNode | null = null;
  private gainNode: GainNode | null = null;
  private intervalId: NodeJS.Timeout | null = null;
  private isHigh = false;
  private isPlaying = false;

  public start() {
    if (this.isPlaying) return;

    try {
      const AudioContextClass = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      if (!AudioContextClass) return;

      this.audioCtx = new AudioContextClass();
      if (this.audioCtx.state === 'suspended') {
        this.audioCtx.resume();
      }

      this.oscillator = this.audioCtx.createOscillator();
      this.gainNode = this.audioCtx.createGain();

      this.oscillator.type = 'sawtooth';
      this.oscillator.frequency.setValueAtTime(650, this.audioCtx.currentTime);

      // Low volume to be pleasant in-app
      this.gainNode.gain.setValueAtTime(0.08, this.audioCtx.currentTime);

      this.oscillator.connect(this.gainNode);
      this.gainNode.connect(this.audioCtx.destination);
      this.oscillator.start();

      this.isPlaying = true;

      // Two-tone ambulance siren: 650Hz <-> 900Hz alternating every 480ms
      this.intervalId = setInterval(() => {
        if (!this.oscillator || !this.audioCtx) return;
        this.isHigh = !this.isHigh;
        const targetFreq = this.isHigh ? 920 : 650;
        this.oscillator.frequency.setTargetAtTime(targetFreq, this.audioCtx.currentTime, 0.08);
      }, 480);
    } catch (e) {
      console.warn('Audio siren start failed:', e);
    }
  }

  public stop() {
    if (!this.isPlaying) return;

    try {
      if (this.intervalId) {
        clearInterval(this.intervalId);
        this.intervalId = null;
      }
      if (this.oscillator) {
        this.oscillator.stop();
        this.oscillator.disconnect();
        this.oscillator = null;
      }
      if (this.gainNode) {
        this.gainNode.disconnect();
        this.gainNode = null;
      }
      if (this.audioCtx) {
        this.audioCtx.close();
        this.audioCtx = null;
      }
    } catch (e) {
      console.warn('Audio siren stop failed:', e);
    } finally {
      this.isPlaying = false;
    }
  }

  public getStatus(): boolean {
    return this.isPlaying;
  }
}

export const emergencySiren = new EmergencySirenSynthesizer();
