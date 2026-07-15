export class PcmRecorder {
  private context: AudioContext | null = null;
  private stream: MediaStream | null = null;
  private source: MediaStreamAudioSourceNode | null = null;
  private processor: AudioWorkletNode | null = null;

  async start(onFrame: (frame: ArrayBuffer) => void, sourceStream?: MediaStream | null) {
    const sourceTrack = sourceStream?.getAudioTracks()[0];
    this.stream = sourceTrack
      ? new MediaStream([sourceTrack.clone()])
      : await navigator.mediaDevices.getUserMedia({
          audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
          video: false,
        });
    this.context = new AudioContext({ latencyHint: "interactive" });
    await this.context.audioWorklet.addModule("/audio/pcm16-worklet.js");
    this.source = this.context.createMediaStreamSource(this.stream);
    this.processor = new AudioWorkletNode(this.context, "pcm16-worklet");
    const mute = this.context.createGain();
    mute.gain.value = 0;
    this.processor.port.onmessage = (event: MessageEvent<ArrayBuffer>) => onFrame(event.data);
    this.source.connect(this.processor);
    this.processor.connect(mute).connect(this.context.destination);
  }

  async stop() {
    this.processor?.disconnect();
    this.source?.disconnect();
    this.stream?.getTracks().forEach((track) => track.stop());
    if (this.context && this.context.state !== "closed") await this.context.close();
    this.processor = null;
    this.source = null;
    this.stream = null;
    this.context = null;
  }
}
