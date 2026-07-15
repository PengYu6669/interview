const SPEECH_ENERGY_THRESHOLD = 0.012;
const REQUIRED_SPEECH_FRAMES = 4;
const END_OF_ANSWER_SILENCE_MS = 3_200;

export class VoiceActivityDetector {
  private consecutiveSpeechFrames = 0;
  private lastSpeechAt: number | null = null;

  reset() {
    this.consecutiveSpeechFrames = 0;
    this.lastSpeechAt = null;
  }

  push(frame: ArrayBuffer, now = Date.now()) {
    const samples = new Int16Array(frame);
    if (!samples.length) return false;
    let squared = 0;
    for (const sample of samples) {
      const normalized = sample / 32_768;
      squared += normalized * normalized;
    }
    const energy = Math.sqrt(squared / samples.length);
    if (energy >= SPEECH_ENERGY_THRESHOLD) {
      this.consecutiveSpeechFrames += 1;
      if (this.consecutiveSpeechFrames >= REQUIRED_SPEECH_FRAMES) this.lastSpeechAt = now;
    } else {
      this.consecutiveSpeechFrames = Math.max(0, this.consecutiveSpeechFrames - 1);
    }
    return this.lastSpeechAt !== null && now - this.lastSpeechAt >= END_OF_ANSWER_SILENCE_MS;
  }
}
