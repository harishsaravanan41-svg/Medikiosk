/**
 * WaveVisualizer - Real-time HTML5 Canvas Audio Waveform for MediKiosk
 * Handles Idle, Listening (Mic frequency), and AI Speaking (TTS playback) waves.
 */

class WaveVisualizer {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) return;
    this.ctx = this.canvas.getContext('2d');
    
    this.state = 'idle'; // 'idle' | 'listening' | 'speaking' | 'processing'
    this.analyser = null;
    this.dataArray = null;
    this.audioElement = null;
    this.audioContext = null;
    this.audioSource = null;

    this.phase = 0;
    this.animationId = null;

    this.resize();
    window.addEventListener('resize', () => this.resize());
    this.start();
  }

  resize() {
    if (!this.canvas) return;
    this.canvas.width = this.canvas.parentElement.clientWidth * window.devicePixelRatio;
    this.canvas.height = this.canvas.parentElement.clientHeight * window.devicePixelRatio;
    this.ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
  }

  setState(newState) {
    this.state = newState;
    const indicator = document.getElementById('waveModeIndicator');
    const label = document.getElementById('waveModeLabel');
    if (indicator && label) {
      indicator.className = `wave-mode-indicator ${newState}`;
      if (newState === 'listening') label.textContent = 'Listening to Patient Voice...';
      else if (newState === 'speaking') label.textContent = 'Qwen AI Speaking (TTS)...';
      else if (newState === 'processing') label.textContent = 'Processing Triage with Qwen 2.5...';
      else label.textContent = 'MediKiosk Ready (Voice / Text)';
    }
  }

  setMicAnalyser(analyser) {
    this.analyser = analyser;
    this.dataArray = new Uint8Array(analyser.frequencyBinCount);
  }

  attachAudioElement(audioEl) {
    this.audioElement = audioEl;
    try {
      if (!this.audioContext) {
        this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
      }
      if (!this.audioSource && this.audioElement) {
        this.audioSource = this.audioContext.createMediaElementSource(this.audioElement);
        const ttsAnalyser = this.audioContext.createAnalyser();
        ttsAnalyser.fftSize = 128;
        this.audioSource.connect(ttsAnalyser);
        ttsAnalyser.connect(this.audioContext.destination);
        this.ttsAnalyser = ttsAnalyser;
        this.ttsDataArray = new Uint8Array(ttsAnalyser.frequencyBinCount);
      }
    } catch (e) {
      console.warn('Audio element source attach warning:', e);
    }
  }

  start() {
    const render = () => {
      this.draw();
      this.animationId = requestAnimationFrame(render);
    };
    render();
  }

  draw() {
    if (!this.canvas) return;
    const width = this.canvas.width / window.devicePixelRatio;
    const height = this.canvas.height / window.devicePixelRatio;
    const centerY = height / 2;

    this.ctx.clearRect(0, 0, width, height);
    this.phase += 0.04;

    if (this.state === 'listening' && this.analyser) {
      this.analyser.getByteFrequencyData(this.dataArray);
      this.drawFrequencyBars(width, height, this.dataArray, '#06b6d4', '#0ea5e9');
    } else if (this.state === 'speaking') {
      let energy = 0.5;
      if (this.ttsAnalyser && this.ttsDataArray) {
        this.ttsAnalyser.getByteFrequencyData(this.ttsDataArray);
        const sum = this.ttsDataArray.reduce((a, b) => a + b, 0);
        energy = Math.max(0.2, (sum / this.ttsDataArray.length) / 128);
      }
      this.drawSineWaves(width, centerY, energy * 28, '#10b981', '#06b6d4');
    } else if (this.state === 'processing') {
      this.drawPulseWave(width, centerY, '#f59e0b');
    } else {
      // Idle ambient wave
      this.drawSineWaves(width, centerY, 8, '#0ea5e9', 'rgba(14, 165, 233, 0.4)');
    }
  }

  drawSineWaves(width, centerY, amplitude, primaryColor, secondaryColor) {
    const layers = [
      { amp: amplitude * 1.0, freq: 0.015, speed: 1.0, color: primaryColor, alpha: 0.8 },
      { amp: amplitude * 0.6, freq: 0.025, speed: 1.4, color: secondaryColor, alpha: 0.5 },
      { amp: amplitude * 0.3, freq: 0.035, speed: -0.8, color: '#38bdf8', alpha: 0.3 }
    ];

    layers.forEach(layer => {
      this.ctx.beginPath();
      this.ctx.lineWidth = 2.5;
      this.ctx.strokeStyle = layer.color;
      this.ctx.globalAlpha = layer.alpha;

      for (let x = 0; x < width; x += 2) {
        const y = centerY + Math.sin(x * layer.freq + this.phase * layer.speed) * layer.amp 
                          * Math.sin((x / width) * Math.PI); // Windowing at edges
        if (x === 0) this.ctx.moveTo(x, y);
        else this.ctx.lineTo(x, y);
      }
      this.ctx.stroke();
    });

    this.ctx.globalAlpha = 1.0;
  }

  drawFrequencyBars(width, height, dataArray, color1, color2) {
    const bars = 48;
    const barWidth = (width / bars) * 0.6;
    const gap = (width / bars) * 0.4;
    const step = Math.floor(dataArray.length / bars) || 1;

    for (let i = 0; i < bars; i++) {
      const val = (dataArray[i * step] || 0) / 255.0;
      const barHeight = Math.max(4, val * (height * 0.75));
      const x = i * (barWidth + gap) + gap;
      const y = (height - barHeight) / 2;

      const grad = this.ctx.createLinearGradient(x, y, x, y + barHeight);
      grad.addColorStop(0, color1);
      grad.addColorStop(1, color2);

      this.ctx.fillStyle = grad;
      this.ctx.beginPath();
      this.ctx.roundRect(x, y, barWidth, barHeight, 4);
      this.ctx.fill();
    }
  }

  drawPulseWave(width, centerY, color) {
    this.ctx.beginPath();
    this.ctx.lineWidth = 2;
    this.ctx.strokeStyle = color;
    this.ctx.shadowColor = color;
    this.ctx.shadowBlur = 10;

    for (let x = 0; x < width; x += 4) {
      const y = centerY + Math.sin(x * 0.04 + this.phase * 3) * 14 * Math.sin((x / width) * Math.PI);
      if (x === 0) this.ctx.moveTo(x, y);
      else this.ctx.lineTo(x, y);
    }
    this.ctx.stroke();
    this.ctx.shadowBlur = 0;
  }
}

window.WaveVisualizer = WaveVisualizer;
