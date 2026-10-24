const API = {
  socket: null,
  socketConnected: false,

  initSocket() {
    if (typeof io !== 'undefined' && !this.socket) {
      try {
        this.socket = io(window.location.origin, {
          transports: ['websocket', 'polling'],
          reconnection: true,
          reconnectionAttempts: 5,
          reconnectionDelay: 1000
        });

        this.socket.on('connect', () => {
          this.socketConnected = true;
          console.log('[API] WebSocket connected');
        });

        this.socket.on('disconnect', () => {
          this.socketConnected = false;
          console.log('[API] WebSocket disconnected');
        });
      } catch (e) {
        console.warn('[API] Could not initialize Socket.IO:', e);
      }
    }
  },

  async checkLLMHealth() {
    try {
      const res = await fetch('/api/health/llm');
      const data = await res.json();
      return data;
    } catch (e) {
      return { status: 'offline', error: String(e) };
    }
  },

  sendTextMessageWebSocket(text, sessionId, patientId = 'P-1001', language = 'auto', onToken, onComplete, onError) {
    if (!this.socket || !this.socketConnected) {
      // Fallback to SSE if WebSocket not ready
      return this.sendTextMessageStream(text, sessionId, patientId, language, onToken, onComplete, onError);
    }

    let fullText = '';
    let activeSessionId = sessionId;

    let timeoutTimer = setTimeout(() => {
      this.socket.off('response_chunk', onChunk);
      this.socket.off('response_complete', onFinish);
      this.socket.off('error', onErr);
      if (onError) {
        onError(new Error('AI response is taking longer than expected. Please check your connection or try again.'));
      }
    }, 35000);

    const onChunk = (data) => {
      if (timeoutTimer) {
        clearTimeout(timeoutTimer);
        timeoutTimer = setTimeout(() => {
          this.socket.off('response_chunk', onChunk);
          this.socket.off('response_complete', onFinish);
          this.socket.off('error', onErr);
          if (onComplete) onComplete({ session_id: activeSessionId, full_text: fullText });
        }, 12000);
      }
      if (data && data.token) {
        fullText += data.token;
        if (onToken) onToken(data.token, fullText);
      }
      if (data && data.session_id) activeSessionId = data.session_id;
    };

    const onFinish = (data) => {
      if (timeoutTimer) clearTimeout(timeoutTimer);
      this.socket.off('response_chunk', onChunk);
      this.socket.off('response_complete', onFinish);
      this.socket.off('error', onErr);

      if (onComplete) {
        onComplete({
          session_id: (data && data.session_id) || activeSessionId,
          full_text: (data && data.full_text) || fullText,
          message_id: data && data.message_id
        });
      }
    };

    const onErr = (data) => {
      if (timeoutTimer) clearTimeout(timeoutTimer);
      this.socket.off('response_chunk', onChunk);
      this.socket.off('response_complete', onFinish);
      this.socket.off('error', onErr);

      if (onError) onError(new Error(data.message || 'WebSocket generation error'));
    };

    // Clean up any lingering listeners first to prevent duplication
    this.socket.off('response_chunk');
    this.socket.off('response_complete');
    this.socket.off('error');
    this.socket.off('message_duplicate');

    this.socket.on('response_chunk', onChunk);
    this.socket.on('response_complete', onFinish);
    this.socket.on('error', onErr);

    this.socket.emit('chat_message', {
      message: text,
      session_id: sessionId,
      patient_id: patientId,
      language: language
    });
  },

  startVoiceStream() {
    if (this.socket && this.socketConnected) {
      this.socket.emit('voice_start');
    }
  },

  sendVoiceChunk(pcmBuffer) {
    if (this.socket && this.socketConnected && pcmBuffer) {
      this.socket.emit('voice_chunk', pcmBuffer);
    }
  },

  endVoiceStream(sessionId, patientId = 'P-1001', language = 'auto', onTranscript, onToken, onComplete, onError) {
    if (!this.socket || !this.socketConnected) {
      if (onError) onError(new Error('WebSocket not connected'));
      return;
    }

    let fullText = '';
    let activeSessionId = sessionId;

    const onTrans = (data) => {
      this.socket.off('voice_transcript', onTrans);
      if (onTranscript) onTranscript(data);
    };

    const onChunk = (data) => {
      if (data && data.token) {
        fullText += data.token;
        if (onToken) onToken(data.token, fullText);
      }
      if (data && data.session_id) activeSessionId = data.session_id;
    };

    const onFinish = (data) => {
      this.socket.off('response_chunk', onChunk);
      this.socket.off('response_complete', onFinish);
      this.socket.off('error', onErr);

      if (onComplete) {
        onComplete({
          session_id: (data && data.session_id) || activeSessionId,
          full_text: (data && data.full_text) || fullText,
          message_id: data && data.message_id
        });
      }
    };

    const onErr = (data) => {
      this.socket.off('voice_transcript', onTrans);
      this.socket.off('response_chunk', onChunk);
      this.socket.off('response_complete', onFinish);
      this.socket.off('error', onErr);

      if (onError) onError(new Error(data.message || 'Voice streaming error'));
    };

    // Clean up any lingering listeners first to prevent duplication
    this.socket.off('voice_transcript');
    this.socket.off('voice_processing');
    this.socket.off('response_chunk');
    this.socket.off('response_complete');
    this.socket.off('voice_error');
    this.socket.off('error');

    this.socket.on('voice_transcript', onTrans);
    this.socket.on('response_chunk', onChunk);
    this.socket.on('response_complete', onFinish);
    this.socket.on('error', onErr);

    this.socket.emit('voice_end', {
      session_id: sessionId,
      patient_id: patientId,
      language: language
    });
  },

  async sendTextMessageStream(text, sessionId, patientId = 'P-GUEST', language = 'en', onToken, onComplete, onError) {
    try {
      const res = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        signal: AbortSignal.timeout ? AbortSignal.timeout(18000) : undefined,
        body: JSON.stringify({
          message: text,
          session_id: sessionId,
          patient_id: patientId,
          language: language
        })
      });

      if (!res.ok) {
        throw new Error(`HTTP error ${res.status}`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';
      let activeSessionId = sessionId;
      let fullText = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop();

        for (const line of lines) {
          const trimmed = line.trim();
          if (trimmed.startsWith('data: ')) {
            const jsonStr = trimmed.slice(6);
            try {
              const data = JSON.parse(jsonStr);
              if (data.token) {
                fullText += data.token;
                if (onToken) onToken(data.token, fullText);
              }
              if (data.session_id) {
                activeSessionId = data.session_id;
              }
              if (data.done) {
                if (onComplete) onComplete({
                  session_id: activeSessionId,
                  full_text: data.full_text || fullText,
                  message_id: data.message_id
                });
                return;
              }
            } catch (e) {
              // skip parse errors
            }
          }
        }
      }

      if (onComplete) onComplete({ session_id: activeSessionId, full_text: fullText });
    } catch (err) {
      if (onError) onError(err);
      else console.error('Streaming error:', err);
    }
  },

  async synthesizeAudio(text, language = 'en') {
    try {
      const res = await fetch('/api/chat/synthesize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, language })
      });
      return await res.json();
    } catch (e) {
      console.warn('Synthesize audio error:', e);
      return { audio_url: null };
    }
  },

  async sendTextMessage(text, sessionId, patientId = 'P-GUEST', language = 'en') {
    const res = await fetch('/api/chat/text', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: text,
        session_id: sessionId,
        patient_id: patientId,
        language: language
      })
    });
    return await res.json();
  },

  async transcribeVoiceAudio(audioBlob, sessionId, patientId = 'P-GUEST') {
    const formData = new FormData();
    const type = audioBlob.type || 'audio/webm';
    let filename = 'voice_input.webm';
    if (type.includes('mp4')) filename = 'voice_input.mp4';
    else if (type.includes('ogg')) filename = 'voice_input.ogg';
    else if (type.includes('wav')) filename = 'voice_input.wav';

    formData.append('audio', audioBlob, filename);
    if (sessionId) formData.append('session_id', sessionId);
    formData.append('patient_id', patientId);

    const res = await fetch('/api/chat/transcribe', {
      method: 'POST',
      body: formData
    });
    return await res.json();
  },

  async sendVoiceAudio(audioBlob, sessionId, patientId = 'P-GUEST', language = 'en') {
    const formData = new FormData();
    const type = audioBlob.type || 'audio/webm';
    let filename = 'voice_input.webm';
    if (type.includes('mp4')) filename = 'voice_input.mp4';
    else if (type.includes('ogg')) filename = 'voice_input.ogg';
    else if (type.includes('wav')) filename = 'voice_input.wav';

    formData.append('audio', audioBlob, filename);
    if (sessionId) formData.append('session_id', sessionId);
    formData.append('patient_id', patientId);
    formData.append('language', language);

    const res = await fetch('/api/chat/voice', {
      method: 'POST',
      body: formData
    });
    return await res.json();
  },

  async startNewSession(patientId = 'P-1001') {
    const res = await fetch('/api/session/new', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ patient_id: patientId })
    });
    return await res.json();
  },

  async loadLocale(langCode = 'en') {
    try {
      const res = await fetch(`/static/locales/${langCode}.json`);
      if (res.ok) {
        return await res.json();
      }
    } catch (e) {
      console.warn(`[API] Failed to load locale ${langCode}, falling back to en:`, e);
    }
    // Fallback to English
    try {
      const fallback = await fetch('/static/locales/en.json');
      return await fallback.json();
    } catch (e) {
      return {};
    }
  },

  async patientLogin(abhaId) {
    const res = await fetch('/api/auth/patient/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ abha_id: abhaId })
    });
    return await res.json();
  },

  async doctorLogin(email, password) {
    const res = await fetch('/api/auth/doctor/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });
    return await res.json();
  },

  async logout() {
    const res = await fetch('/api/auth/logout', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    });
    return await res.json();
  },

  async checkAuthStatus() {
    try {
      const res = await fetch('/api/auth/me');
      return await res.json();
    } catch (e) {
      return { authenticated: false };
    }
  },

  async getDoctorDashboardStats() {
    const res = await fetch('/api/doctor/dashboard-stats');
    return await res.json();
  },

  async searchPatientByAbha(abhaId) {
    const res = await fetch(`/api/doctor/patient/by-abha/${encodeURIComponent(abhaId.trim())}`);
    return await res.json();
  },

  async getPatientHistory(patientId) {
    const res = await fetch(`/api/doctor/patient/${encodeURIComponent(patientId)}/history`);
    return await res.json();
  },

  async getPatientConsultations(patientId) {
    const res = await fetch(`/api/doctor/patient/${encodeURIComponent(patientId)}/consultations`);
    return await res.json();
  },

  async getPatientDocuments(patientId) {
    const res = await fetch(`/api/doctor/patient/${encodeURIComponent(patientId)}/documents`);
    return await res.json();
  },

  async getPatientTimeline(patientId) {
    const res = await fetch(`/api/doctor/patient/${encodeURIComponent(patientId)}/timeline`);
    return await res.json();
  },

  async getDocumentExtraction(documentId) {
    const res = await fetch(`/api/doctor/document/${encodeURIComponent(documentId)}/extraction`);
    return await res.json();
  },

  async updateEncounterHistory(encounterId, historyData) {
    const res = await fetch(`/api/doctor/encounter/${encodeURIComponent(encounterId)}/history`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(historyData)
    });
    return await res.json();
  },

  async verifyEncounterHistory(encounterId, doctorNotes = '') {
    const res = await fetch(`/api/doctor/encounter/${encodeURIComponent(encounterId)}/verify`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ doctor_notes: doctorNotes })
    });
    return await res.json();
  },

  async saveDoctorConsultation(encounterId, consultationData) {
    const res = await fetch(`/api/doctor/encounter/${encodeURIComponent(encounterId)}/consultation`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(consultationData)
    });
    return await res.json();
  },

  async uploadPatientDocument(patientId, formData) {
    const res = await fetch(`/api/patient/${encodeURIComponent(patientId)}/upload-doc`, {
      method: 'POST',
      body: formData
    });
    return await res.json();
  },

  async createNewPatient(name = 'New Patient') {
    const res = await fetch('/api/patient/new', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name })
    });
    return await res.json();
  },

  async getPatientMemory(patientId) {
    if (!patientId) return null;
    try {
      const res = await fetch(`/api/patient/${encodeURIComponent(patientId)}/memory`);
      if (res.ok) {
        return await res.json();
      }
    } catch (e) {
      console.warn('Error fetching patient memory:', e);
    }
    return null;
  },

  async getSession(sessionId) {
    if (!sessionId) return null;
    try {
      const res = await fetch(`/api/session/${encodeURIComponent(sessionId)}`);
      if (res.ok) {
        return await res.json();
      }
    } catch (e) {
      console.warn('Error fetching session:', e);
    }
    return null;
  },

  async completeSession(sessionId) {
    const res = await fetch('/api/session/complete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId })
    });
    return await res.json();
  },

  async getTriageHistory() {
    const res = await fetch('/api/triage/history');
    return await res.json();
  },

  async getConfig() {
    const res = await fetch('/api/config');
    return await res.json();
  },

  async updateConfig(configData) {
    const res = await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(configData)
    });
    return await res.json();
  }
};

window.API = API;


