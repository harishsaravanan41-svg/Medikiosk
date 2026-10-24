/**
 * PCMProcessor - AudioWorklet for converting browser audio stream to 16kHz 16-bit Mono PCM
 */
class PCMProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.bufferSize = 2048;
    this.buffer = new Float32Array(this.bufferSize);
    this.bufferIndex = 0;
  }

  process(inputs, outputs, parameters) {
    const input = inputs[0];
    if (!input || input.length === 0) return true;

    // Use mono channel 0
    const inputChannel = input[0];

    for (let i = 0; i < inputChannel.length; i++) {
      this.buffer[this.bufferIndex++] = inputChannel[i];

      if (this.bufferIndex >= this.bufferSize) {
        // Convert Float32 buffer to 16-bit Int16 PCM array
        const pcmData = new Int16Array(this.bufferSize);
        for (let j = 0; j < this.bufferSize; j++) {
          const s = Math.max(-1, Math.min(1, this.buffer[j]));
          pcmData[j] = s < 0 ? s * 0x8000 : s * 0x7FFF;
        }

        // Post raw PCM buffer to main thread
        this.port.postMessage(pcmData.buffer, [pcmData.buffer]);
        this.buffer = new Float32Array(this.bufferSize);
        this.bufferIndex = 0;
      }
    }

    return true;
  }
}

registerProcessor('pcm-processor', PCMProcessor);
