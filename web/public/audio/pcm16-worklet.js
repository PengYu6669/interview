class Pcm16Worklet extends AudioWorkletProcessor {
  constructor() {
    super();
    this.samples = [];
    this.offset = 0;
    this.ratio = sampleRate / 16000;
    this.frameSamples = 640;
  }

  process(inputs) {
    const channel = inputs[0]?.[0];
    if (!channel) return true;
    for (let index = 0; index < channel.length; index += 1) this.samples.push(channel[index]);
    const required = Math.ceil(this.ratio * this.frameSamples) + 1;
    while (this.samples.length - this.offset >= required) {
      const pcm = new Int16Array(this.frameSamples);
      for (let index = 0; index < this.frameSamples; index += 1) {
        const sourcePosition = this.offset + index * this.ratio;
        const lower = Math.floor(sourcePosition);
        const fraction = sourcePosition - lower;
        const sample = this.samples[lower] * (1 - fraction) + this.samples[lower + 1] * fraction;
        const clamped = Math.max(-1, Math.min(1, sample));
        pcm[index] = clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff;
      }
      this.offset += this.ratio * this.frameSamples;
      this.port.postMessage(pcm.buffer, [pcm.buffer]);
    }
    if (this.offset > 4096) {
      const consumed = Math.floor(this.offset);
      this.samples = this.samples.slice(consumed);
      this.offset -= consumed;
    }
    return true;
  }
}

registerProcessor("pcm16-worklet", Pcm16Worklet);
