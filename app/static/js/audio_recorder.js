/**
 * AudioRecorder - Browser Microphone capture with Web Audio API stream
 * Extracts audio chunks and feeds frequency analyser for real-time visualization and VAD.
 */

class AudioRecorder {
  constructor() {
    this.mediaRecorder = null;
    this.audioChunks = [];
    this.stream = null;
    this.audioContext = null;
    this.analyser = null;
    this.sourceNode = null;
    this.workletNode = null;
    this.isRecording = false;
    this.detectedMimeType = 'audio/webm';
    this.onPCMData = null; // Callback for raw PCM streaming
  }

  static checkMicrophoneSupport() {
    const isSecure = window.isSecureContext || window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
    const hasGetUserMedia = !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia);
    
    console.log('[AudioRecorder] Secure context:', isSecure);
    console.log('[AudioRecorder] getUserMedia supported:', hasGetUserMedia);

    return {
      isSecure,
      hasGetUserMedia,
      supported: isSecure && hasGetUserMedia
    };
  }

  async initialize() {
    if (this.stream && this.stream.active) return true;

    const support = AudioRecorder.checkMicrophoneSupport();
    if (!support.isSecure) {
      const err = new Error('Microphone access requires HTTPS or localhost. If accessing on mobile via LAN IP, please use a secure HTTPS tunnel.');
      err.name = 'InsecureContextError';
      throw err;
    }

    if (!support.hasGetUserMedia) {
      const err = new Error('Microphone is not supported by this browser.');
      err.name = 'NotSupportedError';
      throw err;
    }

    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: 16000,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        }
      });

      this.audioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
      this.analyser = this.audioContext.createAnalyser();
      this.analyser.fftSize = 256;
      this.analyser.smoothingTimeConstant = 0.8;

      this.sourceNode = this.audioContext.createMediaStreamSource(this.stream);

      // 80Hz High-pass Biquad Filter to eliminate low-frequency rumble, fan noise, and table vibrations
      this.highPassFilter = this.audioContext.createBiquadFilter();
      this.highPassFilter.type = 'highpass';
      this.highPassFilter.frequency.value = 80;
      this.highPassFilter.Q.value = 0.7;

      this.sourceNode.connect(this.highPassFilter);
      this.highPassFilter.connect(this.analyser);

      // Attempt to load AudioWorklet for raw PCM streaming if supported
      try {
        if (this.audioContext.audioWorklet) {
          await this.audioContext.audioWorklet.addModule('/static/js/pcm-processor.js');
          this.workletNode = new AudioWorkletNode(this.audioContext, 'pcm-processor');
          this.workletNode.port.onmessage = (event) => {
            if (this.isRecording && this.onPCMData) {
              this.onPCMData(event.data);
            }
          };
          this.highPassFilter.connect(this.workletNode);
        }
      } catch (workletErr) {
        console.warn('[AudioRecorder] AudioWorklet not loaded, using MediaRecorder fallback:', workletErr);
      }

      return true;
    } catch (err) {
      console.error('[AudioRecorder] Mic access error:', err);
      throw err;
    }
  }

  async start(onPCMCallback = null) {
    this.onPCMData = onPCMCallback;
    await this.initialize();

    if (this.audioContext && this.audioContext.state === 'suspended') {
      await this.audioContext.resume();
    }

    this.audioChunks = [];
    
    // Determine supported MIME type for fallback container recording
    let mimeType = 'audio/webm';
    if (typeof MediaRecorder !== 'undefined') {
      if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) {
        mimeType = 'audio/webm;codecs=opus';
      } else if (MediaRecorder.isTypeSupported('audio/webm')) {
        mimeType = 'audio/webm';
      } else if (MediaRecorder.isTypeSupported('audio/mp4')) {
        mimeType = 'audio/mp4';
      } else if (MediaRecorder.isTypeSupported('audio/ogg')) {
        mimeType = 'audio/ogg';
      } else if (MediaRecorder.isTypeSupported('audio/wav')) {
        mimeType = 'audio/wav';
      }
    }
    this.detectedMimeType = mimeType;

    try {
      this.mediaRecorder = new MediaRecorder(this.stream, { mimeType });
    } catch (e) {
      this.mediaRecorder = new MediaRecorder(this.stream);
      this.detectedMimeType = this.mediaRecorder.mimeType || 'audio/webm';
    }

    this.mediaRecorder.ondataavailable = (event) => {
      if (event.data && event.data.size > 0) {
        this.audioChunks.push(event.data);
      }
    };

    this.mediaRecorder.start(100);
    this.isRecording = true;
  }

  stop() {
    return new Promise((resolve) => {
      if (!this.mediaRecorder || this.mediaRecorder.state === 'inactive') {
        this.isRecording = false;
        resolve(null);
        return;
      }

      this.mediaRecorder.onstop = () => {
        const mimeType = this.detectedMimeType || this.mediaRecorder.mimeType || 'audio/webm';
        const audioBlob = new Blob(this.audioChunks, { type: mimeType });
        this.isRecording = false;
        resolve(audioBlob);
      };

      this.mediaRecorder.stop();
    });
  }

  getAnalyser() {
    return this.analyser;
  }

  getEnergyLevel() {
    if (!this.analyser) return 0;
    const dataArray = new Uint8Array(this.analyser.frequencyBinCount);
    this.analyser.getByteFrequencyData(dataArray);
    let sum = 0;
    for (let i = 0; i < dataArray.length; i++) {
      sum += dataArray[i];
    }
    return sum / dataArray.length;
  }
}

window.AudioRecorder = AudioRecorder;

