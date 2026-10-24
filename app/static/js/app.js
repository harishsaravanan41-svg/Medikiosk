/**
 * MediKiosk AI - Complete Application Controller
 * Handles View Routing, i18n Localization, Patient ABHA Authentication,
 * Conversational Voice/Text Kiosk, and Doctor Clinical Workstation.
 */

class MediKioskApp {
  constructor() {
    this.currentView = 'viewLanding';
    this.currentLanguage = localStorage.getItem('medikiosk_language') || 'en';
    this.locales = {};
    this.currentUser = null; // { user_type: 'patient'|'doctor', ... }
    this.currentPatient = null;
    this.activeEncounter = null;
    this.currentDocTab = 'tabCurrentProblem';

    // Chat & Audio properties
    this.recorder = new AudioRecorder();
    this.audioPlayer = new Audio();
    this.ttsQueue = [];
    this.isTtsPlaying = false;
    this.currentTtsSentenceBuffer = '';
    this.energyCheckInterval = null;
    this.sessionId = localStorage.getItem('medikiosk_session_id') || null;
    this.chatHistory = [];

    // Initialize
    this.cacheDomElements();
    this.initEvents();
    this.initLocalization();
    this.initSocket();
    this.checkSessionAndRoute();
  }

  cacheDomElements() {
    // Views
    this.views = {
      landing: document.getElementById('viewLanding'),
      language: document.getElementById('viewLanguageSelection'),
      role: document.getElementById('viewRoleSelection'),
      patientLogin: document.getElementById('viewPatientLogin'),
      doctorLogin: document.getElementById('viewDoctorLogin'),
      patientPortal: document.getElementById('viewPatientPortal'),
      doctorPortal: document.getElementById('viewDoctorPortal')
    };

    // Global Navigation & Auth elements
    this.globalLangSelect = document.getElementById('globalLangSelect');
    this.btnNavPatient = document.getElementById('btnNavPatient');
    this.btnNavDoctor = document.getElementById('btnNavDoctor');
    this.userAuthPill = document.getElementById('userAuthPill');
    this.authRoleBadge = document.getElementById('authRoleBadge');
    this.authUserName = document.getElementById('authUserName');
    this.btnNavLogout = document.getElementById('btnNavLogout');
    this.brandHomeLink = document.getElementById('brandHomeLink');

    // Landing Page elements
    this.btnLandingGetStarted = document.getElementById('btnLandingGetStarted');
    this.btnLandingDoctorPortal = document.getElementById('btnLandingDoctorPortal');

    // Language Selector Screen elements
    this.langGridContainer = document.getElementById('langGridContainer');
    this.btnConfirmLangSelection = document.getElementById('btnConfirmLangSelection');

    // Role Selector Screen elements
    this.cardRolePatient = document.getElementById('cardRolePatient');
    this.cardRoleDoctor = document.getElementById('cardRoleDoctor');

    // Patient Login elements
    this.formPatientLogin = document.getElementById('formPatientLogin');
    this.inputAbhaId = document.getElementById('inputAbhaId');
    this.patientLoginError = document.getElementById('patientLoginError');
    this.btnQuickGuestPatient = document.getElementById('btnQuickGuestPatient');

    // Doctor Login elements
    this.formDoctorLogin = document.getElementById('formDoctorLogin');
    this.inputDoctorEmail = document.getElementById('inputDoctorEmail');
    this.inputDoctorPassword = document.getElementById('inputDoctorPassword');
    this.doctorLoginError = document.getElementById('doctorLoginError');

    // Patient Portal elements
    this.portalPatientName = document.getElementById('portalPatientName');
    this.portalPatientAbha = document.getElementById('portalPatientAbha');
    this.patientChatMessages = document.getElementById('patientChatMessages');
    this.patientTextInput = document.getElementById('patientTextInput');
    this.btnSendPatientText = document.getElementById('btnSendPatientText');
    this.btnVoiceRecord = document.getElementById('btnVoiceRecord');
    this.voiceStatePill = document.getElementById('voiceStatePill');
    this.voiceStateDot = document.getElementById('voiceStateDot');
    this.voiceStateLabel = document.getElementById('voiceStateLabel');
    this.btnPatientUploadDoc = document.getElementById('btnPatientUploadDoc');
    this.btnPatientEndSession = document.getElementById('btnPatientEndSession');
    this.triageUrgencyBadge = document.getElementById('triageUrgencyBadge');
    this.triageChiefComplaint = document.getElementById('triageChiefComplaint');
    this.triageDepartment = document.getElementById('triageDepartment');
    this.triageSymptomsList = document.getElementById('triageSymptomsList');

    // Doctor Portal elements
    this.docNameDisplay = document.getElementById('docNameDisplay');
    this.docSpecDisplay = document.getElementById('docSpecDisplay');
    this.formDocPatientSearch = document.getElementById('formDocPatientSearch');
    this.inputDocSearchAbha = document.getElementById('inputDocSearchAbha');
    this.btnDocLogout = document.getElementById('btnDocLogout');

    // Doctor Subviews
    this.docSubviewDashboard = document.getElementById('docSubviewDashboard');
    this.docSubviewVerification = document.getElementById('docSubviewVerification');
    this.docSubviewWorkstation = document.getElementById('docSubviewWorkstation');

    // Verification screen
    this.verifyPatientName = document.getElementById('verifyPatientName');
    this.verifyPatientAbha = document.getElementById('verifyPatientAbha');
    this.verifyPatientAgeGender = document.getElementById('verifyPatientAgeGender');
    this.verifyPatientPhone = document.getElementById('verifyPatientPhone');
    this.verifyPatientConditions = document.getElementById('verifyPatientConditions');
    this.btnVerifyReject = document.getElementById('btnVerifyReject');
    this.btnVerifyAccept = document.getElementById('btnVerifyAccept');

    // Workstation elements
    this.wsPatientName = document.getElementById('wsPatientName');
    this.wsPatientMeta = document.getElementById('wsPatientMeta');
    this.wsEncounterDate = document.getElementById('wsEncounterDate');
    this.aiChiefComplaintText = document.getElementById('aiChiefComplaintText');
    this.aiHpiList = document.getElementById('aiHpiList');
    this.aiPastMedText = document.getElementById('aiPastMedText');
    this.aiMedicationsText = document.getElementById('aiMedicationsText');
    this.aiAllergiesText = document.getElementById('aiAllergiesText');
    this.aiFamilyText = document.getElementById('aiFamilyText');
    this.aiPersonalText = document.getElementById('aiPersonalText');
    this.btnEditAiHistory = document.getElementById('btnEditAiHistory');
    this.btnVerifyAiHistory = document.getElementById('btnVerifyAiHistory');
    this.formDoctorConsultation = document.getElementById('formDoctorConsultation');
    this.docClinicalFindings = document.getElementById('docClinicalFindings');
    this.docAssessment = document.getElementById('docAssessment');
    this.docDiagnosis = document.getElementById('docDiagnosis');
    this.docPrescription = document.getElementById('docPrescription');
    this.docFollowUp = document.getElementById('docFollowUp');
    this.docNotes = document.getElementById('docNotes');
    this.btnSaveConsultation = document.getElementById('btnSaveConsultation');

    // Tab bodies
    this.previousConsultationsList = document.getElementById('previousConsultationsList');
    this.uploadedDocumentsGrid = document.getElementById('uploadedDocumentsGrid');
    this.patientTimelineFeed = document.getElementById('patientTimelineFeed');

    // Modals
    this.modalConsultationSaved = document.getElementById('modalConsultationSaved');
    this.savedModalDate = document.getElementById('savedModalDate');
    this.savedModalPatient = document.getElementById('savedModalPatient');
    this.savedModalEncId = document.getElementById('savedModalEncId');
    this.btnModalViewHistory = document.getElementById('btnModalViewHistory');
    this.btnModalReturnDashboard = document.getElementById('btnModalReturnDashboard');

    this.modalDocViewer = document.getElementById('modalDocViewer');
    this.docViewerTitle = document.getElementById('docViewerTitle');
    this.docViewerMeta = document.getElementById('docViewerMeta');
    this.docSheetContent = document.getElementById('docSheetContent');
    this.ocrExtDiagnosis = document.getElementById('ocrExtDiagnosis');
    this.ocrExtMedications = document.getElementById('ocrExtMedications');
    this.ocrExtLabTable = document.getElementById('ocrExtLabTable');
    this.ocrExtRawText = document.getElementById('ocrExtRawText');
    this.btnCloseDocViewer = document.getElementById('btnCloseDocViewer');

    this.modalEditAiHistory = document.getElementById('modalEditAiHistory');
    this.formEditHistory = document.getElementById('formEditHistory');
    this.editChiefComplaint = document.getElementById('editChiefComplaint');
    this.editPastMedical = document.getElementById('editPastMedical');
    this.editMedications = document.getElementById('editMedications');
    this.editAllergies = document.getElementById('editAllergies');
    this.editFamily = document.getElementById('editFamily');
    this.editDoctorNotes = document.getElementById('editDoctorNotes');
    this.btnCloseEditHistory = document.getElementById('btnCloseEditHistory');
    this.btnCancelEditHistory = document.getElementById('btnCancelEditHistory');

    this.modalPatientUpload = document.getElementById('modalPatientUpload');
    this.formPatientUploadDoc = document.getElementById('formPatientUploadDoc');
    this.inputDocTitle = document.getElementById('inputDocTitle');
    this.selectDocType = document.getElementById('selectDocType');
    this.inputFileDoc = document.getElementById('inputFileDoc');
    this.btnCloseUploadModal = document.getElementById('btnCloseUploadModal');
    this.btnCancelUploadDoc = document.getElementById('btnCancelUploadDoc');
  }

  // --- Localization (i18n) Engine ---

  async initLocalization() {
    if (this.globalLangSelect) {
      this.globalLangSelect.value = this.currentLanguage;
    }
    await this.setLocale(this.currentLanguage);
  }

  async setLocale(langCode) {
    this.currentLanguage = langCode || 'en';
    localStorage.setItem('medikiosk_language', this.currentLanguage);

    if (this.globalLangSelect) {
      this.globalLangSelect.value = this.currentLanguage;
    }

    // Highlight active in Language selection screen
    document.querySelectorAll('.lang-tile-btn').forEach(b => {
      if (b.getAttribute('data-lang') === this.currentLanguage) {
        b.classList.add('active');
      } else {
        b.classList.remove('active');
      }
    });

    try {
      this.locales[this.currentLanguage] = await API.loadLocale(this.currentLanguage);
    } catch (e) {
      console.warn('Locale load error:', e);
    }

    this.applyTranslations();
  }

  t(key, fallback = '') {
    const dict = this.locales[this.currentLanguage] || this.locales['en'] || {};
    return dict[key] || fallback || key;
  }

  applyTranslations() {
    document.querySelectorAll('[data-i18n]').forEach(el => {
      const key = el.getAttribute('data-i18n');
      const translation = this.t(key);
      if (translation) {
        el.textContent = translation;
      }
    });

    document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
      const key = el.getAttribute('data-i18n-placeholder');
      const translation = this.t(key);
      if (translation) {
        el.setAttribute('placeholder', translation);
      }
    });
  }

  // --- View Router ---

  navigateTo(viewName) {
    Object.values(this.views).forEach(v => {
      if (v) v.classList.remove('active');
    });

    const targetView = this.views[viewName];
    if (targetView) {
      targetView.classList.add('active');
      this.currentView = viewName;
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    // Update global header buttons visibility
    this.updateGlobalNavState();
  }

  updateGlobalNavState() {
    if (this.currentUser) {
      if (this.userAuthPill) this.userAuthPill.style.display = 'flex';
      if (this.authRoleBadge) this.authRoleBadge.textContent = this.currentUser.user_type === 'doctor' ? 'Doctor' : 'Patient';
      if (this.authUserName) this.authUserName.textContent = this.currentUser.name || 'User';
      if (this.btnNavPatient) this.btnNavPatient.style.display = 'none';
      if (this.btnNavDoctor) this.btnNavDoctor.style.display = 'none';
    } else {
      if (this.userAuthPill) this.userAuthPill.style.display = 'none';
      if (this.btnNavPatient) this.btnNavPatient.style.display = 'inline-block';
      if (this.btnNavDoctor) this.btnNavDoctor.style.display = 'inline-block';
    }
  }

  async checkSessionAndRoute() {
    try {
      const auth = await API.checkAuthStatus();
      if (auth.authenticated && auth.user) {
        this.currentUser = { user_type: auth.user_type, ...auth.user };
        if (auth.user_type === 'patient') {
          this.currentPatient = auth.user;
          this.initPatientPortal(auth.user);
          this.navigateTo('patientPortal');
          return;
        } else if (auth.user_type === 'doctor') {
          this.initDoctorPortal(auth.user);
          this.navigateTo('doctorPortal');
          return;
        }
      }
    } catch (e) {
      console.warn('Auth check error:', e);
    }
    this.navigateTo('landing');
  }

  // --- Event Bindings ---

  initEvents() {
    // Brand home link
    this.brandHomeLink?.addEventListener('click', () => {
      if (!this.currentUser) {
        this.navigateTo('landing');
      } else if (this.currentUser.user_type === 'patient') {
        this.navigateTo('patientPortal');
      } else {
        this.navigateTo('doctorPortal');
      }
    });

    // Global Language Dropdown
    this.globalLangSelect?.addEventListener('change', (e) => {
      this.setLocale(e.target.value);
    });

    // Top Header Role Quick Links
    this.btnNavPatient?.addEventListener('click', () => {
      this.navigateTo('patientLogin');
    });
    this.btnNavDoctor?.addEventListener('click', () => {
      this.navigateTo('doctorLogin');
    });

    // Global Logout
    this.btnNavLogout?.addEventListener('click', () => this.handleLogout());
    this.btnDocLogout?.addEventListener('click', () => this.handleLogout());

    // Landing Page CTAs
    this.btnLandingGetStarted?.addEventListener('click', () => {
      this.navigateTo('language');
    });
    this.btnLandingDoctorPortal?.addEventListener('click', () => {
      this.navigateTo('doctorLogin');
    });

    // Language Selector Tiles
    document.querySelectorAll('.lang-tile-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const lang = btn.getAttribute('data-lang');
        if (lang) {
          this.setLocale(lang);
        }
      });
    });

    this.btnConfirmLangSelection?.addEventListener('click', () => {
      this.navigateTo('role');
    });

    // Role Selection Cards
    this.cardRolePatient?.addEventListener('click', () => {
      this.navigateTo('patientLogin');
    });
    this.cardRoleDoctor?.addEventListener('click', () => {
      this.navigateTo('doctorLogin');
    });

    // Demo Chips on Patient Login
    document.querySelectorAll('.demo-id-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        const abha = chip.getAttribute('data-abha');
        if (this.inputAbhaId && abha) {
          this.inputAbhaId.value = abha;
        }
      });
    });

    // Patient Login Form Submit
    this.formPatientLogin?.addEventListener('submit', async (e) => {
      e.preventDefault();
      const abha = this.inputAbhaId?.value.trim();
      if (!abha) return;

      if (this.patientLoginError) this.patientLoginError.style.display = 'none';

      try {
        const res = await API.patientLogin(abha);
        if (res.status === 'success' && res.patient) {
          this.currentUser = { user_type: 'patient', ...res.patient };
          this.currentPatient = res.patient;
          this.activeEncounter = res.active_encounter;
          this.initPatientPortal(res.patient);
          this.navigateTo('patientPortal');
        } else {
          this.showFormError(this.patientLoginError, res.message || 'Invalid ABHA ID');
        }
      } catch (err) {
        this.showFormError(this.patientLoginError, 'Server error during check-in.');
      }
    });

    // Quick Register Guest Patient
    this.btnQuickGuestPatient?.addEventListener('click', () => {
      if (this.inputAbhaId) this.inputAbhaId.value = 'DEMO-ABHA-001';
      this.formPatientLogin?.dispatchEvent(new Event('submit'));
    });

    // Demo Chips on Doctor Login
    document.querySelectorAll('.demo-doc-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        const email = chip.getAttribute('data-email');
        if (this.inputDoctorEmail && email) {
          this.inputDoctorEmail.value = email;
          if (this.inputDoctorPassword) this.inputDoctorPassword.value = 'DemoDoc#123';
        }
      });
    });

    // Doctor Login Form Submit
    this.formDoctorLogin?.addEventListener('submit', async (e) => {
      e.preventDefault();
      const email = this.inputDoctorEmail?.value.trim();
      const password = this.inputDoctorPassword?.value.trim();
      if (!email || !password) return;

      if (this.doctorLoginError) this.doctorLoginError.style.display = 'none';

      try {
        const res = await API.doctorLogin(email, password);
        if (res.status === 'success' && res.doctor) {
          this.currentUser = { user_type: 'doctor', ...res.doctor };
          this.initDoctorPortal(res.doctor);
          this.navigateTo('doctorPortal');
        } else {
          this.showFormError(this.doctorLoginError, res.message || 'Invalid credentials');
        }
      } catch (err) {
        this.showFormError(this.doctorLoginError, 'Server error during doctor sign-in.');
      }
    });

    // --- Patient Portal Voice & Chat Events ---
    this.btnSendPatientText?.addEventListener('click', () => this.handlePatientSendText());
    this.patientTextInput?.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        this.handlePatientSendText();
      }
    });

    this.btnVoiceRecord?.addEventListener('click', () => this.handleVoiceToggle());

    document.querySelectorAll('.chip-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const text = btn.getAttribute('data-text');
        if (text && this.patientTextInput) {
          this.patientTextInput.value = text;
          this.handlePatientSendText();
        }
      });
    });

    this.btnPatientUploadDoc?.addEventListener('click', () => {
      this.openModal(this.modalPatientUpload);
    });

    this.btnPatientEndSession?.addEventListener('click', () => {
      this.handleLogout();
    });

    // --- Doctor Portal Search & Verification Events ---
    this.formDocPatientSearch?.addEventListener('submit', async (e) => {
      e.preventDefault();
      const abha = this.inputDocSearchAbha?.value.trim();
      if (!abha) return;
      await this.handleDoctorSearchPatient(abha);
    });

    // Open Demo Patient from Dashboard Table
    document.querySelectorAll('.btn-open-demo').forEach(btn => {
      btn.addEventListener('click', async () => {
        const abha = btn.getAttribute('data-abha');
        if (abha) {
          await this.handleDoctorSearchPatient(abha);
        }
      });
    });

    this.btnVerifyReject?.addEventListener('click', () => {
      this.showDoctorSubview('dashboard');
    });

    this.btnVerifyAccept?.addEventListener('click', () => {
      this.openPatientWorkstation(this.searchedPatient, this.searchedEncounter);
    });

    // Workstation Tabs Navigation
    document.querySelectorAll('.ws-tab-btn').forEach(tabBtn => {
      tabBtn.addEventListener('click', () => {
        const tabId = tabBtn.getAttribute('data-tab');
        if (tabId) {
          this.switchDoctorWorkstationTab(tabId);
        }
      });
    });

    // Edit AI History Modal
    this.btnEditAiHistory?.addEventListener('click', () => {
      this.openEditAiHistoryModal();
    });

    this.btnCloseEditHistory?.addEventListener('click', () => this.closeModal(this.modalEditAiHistory));
    this.btnCancelEditHistory?.addEventListener('click', () => this.closeModal(this.modalEditAiHistory));

    this.formEditHistory?.addEventListener('submit', async (e) => {
      e.preventDefault();
      await this.handleSaveEditedAiHistory();
    });

    // Verify AI History
    this.btnVerifyAiHistory?.addEventListener('click', async () => {
      await this.handleVerifyAiHistory();
    });

    // Save Consultation Form Submit
    this.formDoctorConsultation?.addEventListener('submit', async (e) => {
      e.preventDefault();
      await this.handleSaveDoctorConsultation();
    });

    // Saved Consultation Modal Buttons
    this.btnModalViewHistory?.addEventListener('click', () => {
      this.closeModal(this.modalConsultationSaved);
      this.switchDoctorWorkstationTab('tabPreviousConsultations');
    });

    this.btnModalReturnDashboard?.addEventListener('click', () => {
      this.closeModal(this.modalConsultationSaved);
      this.showDoctorSubview('dashboard');
      this.refreshDoctorDashboard();
    });

    // Close Doc Viewer
    this.btnCloseDocViewer?.addEventListener('click', () => this.closeModal(this.modalDocViewer));

    // Patient Upload Form
    this.btnCloseUploadModal?.addEventListener('click', () => this.closeModal(this.modalPatientUpload));
    this.btnCancelUploadDoc?.addEventListener('click', () => this.closeModal(this.modalPatientUpload));
    this.formPatientUploadDoc?.addEventListener('submit', async (e) => {
      e.preventDefault();
      await this.handlePatientDocumentUpload();
    });
  }

  showFormError(elem, msg) {
    if (elem) {
      elem.textContent = msg;
      elem.style.display = 'block';
    }
  }

  openModal(modal) {
    if (modal) modal.classList.add('active');
  }

  closeModal(modal) {
    if (modal) modal.classList.remove('active');
  }

  async handleLogout() {
    this.stopAllAudioAndTtsQueue();
    try {
      await API.logout();
    } catch (e) {}
    this.currentUser = null;
    this.currentPatient = null;
    this.activeEncounter = null;
    localStorage.removeItem('medikiosk_session_id');
    this.sessionId = null;
    this.navigateTo('landing');
  }

  // --- Patient Portal Workflow ---

  initPatientPortal(patient) {
    if (this.portalPatientName) this.portalPatientName.textContent = patient.name;
    if (this.portalPatientAbha) this.portalPatientAbha.textContent = `ABHA ID: ${patient.abha_id}`;

    if (!this.sessionId) {
      this.sessionId = `session_${patient.patient_id}_${Date.now()}`;
      localStorage.setItem('medikiosk_session_id', this.sessionId);
    }

    if (patient.preferred_lang && patient.preferred_lang !== this.currentLanguage) {
      this.setLocale(patient.preferred_lang);
    }
  }

  async handlePatientSendText() {
    const text = this.patientTextInput?.value.trim();
    if (!text || this.isSendingMessage) return;

    this.isSendingMessage = true;
    if (this.btnSendPatientText) this.btnSendPatientText.disabled = true;
    if (this.patientTextInput) this.patientTextInput.disabled = true;

    const unlockUi = () => {
      this.isSendingMessage = false;
      if (this.btnSendPatientText) this.btnSendPatientText.disabled = false;
      if (this.patientTextInput) {
        this.patientTextInput.disabled = false;
        this.patientTextInput.focus();
      }
    };

    this.stopAllAudioAndTtsQueue();
    this.patientTextInput.value = '';

    this.appendMessage('patient', text, 'text');
    this.setUiState('SENDING');

    const streamBubble = this.createStreamingAiBubble();
    const detectedLang = this.detectLanguage(text, this.currentLanguage);

    API.sendTextMessageWebSocket(
      text,
      this.sessionId,
      this.currentPatient ? this.currentPatient.patient_id : 'P-1001',
      detectedLang,
      // onToken
      (token, fullText) => {
        streamBubble.update(fullText);
        this.queueTtsToken(token, detectedLang);
      },
      // onComplete
      (result) => {
        this.sessionId = result.session_id;
        localStorage.setItem('medikiosk_session_id', this.sessionId);
        streamBubble.finalize(result.full_text);
        this.flushTtsRemaining(detectedLang);

        const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        this.chatHistory.push({ sender: 'ai', text: result.full_text, modality: 'stream', timestamp: timeStr });
        unlockUi();
      },
      // onError
      (err) => {
        console.error('Chat error:', err);
        streamBubble.showError(err.message || 'AI is taking longer than expected. Please try again.');
        this.setUiState('IDLE');
        unlockUi();
      }
    );
  }

  async handleVoiceToggle() {
    if (this.isVoiceProcessing) return;

    this.stopAllAudioAndTtsQueue();

    if (this.energyCheckInterval) {
      clearInterval(this.energyCheckInterval);
      this.energyCheckInterval = null;
    }

    if (this.recorder.isRecording) {
      // Stop recording
      this.isVoiceProcessing = true;
      this.setUiState('TRANSCRIBING');
      const audioBlob = await this.recorder.stop();

      if (API.socket && API.socketConnected) {
        let streamBubble = null;
        let detectedLang = 'en';

        API.endVoiceStream(
          this.sessionId,
          this.currentPatient ? this.currentPatient.patient_id : 'P-1001',
          'auto',
          // onTranscript
          (transData) => {
            if (transData && transData.text) {
              const cleanText = transData.text.trim();
              detectedLang = transData.language || this.detectLanguage(cleanText, this.currentLanguage);
              this.appendMessage('patient', cleanText, 'voice');
              streamBubble = this.createStreamingAiBubble();
            } else {
              this.isVoiceProcessing = false;
              this.setUiState('IDLE');
              this.appendMessage('ai', "I couldn't hear any clear speech. Please try speaking a little closer to the microphone.", 'text');
            }
          },
          // onToken (streaming from voice_end -> process_ai_message)
          (token, fullText) => {
            if (streamBubble) {
              streamBubble.update(fullText);
            }
            this.queueTtsToken(token, detectedLang);
          },
          // onComplete
          (streamResult) => {
            this.isVoiceProcessing = false;
            if (streamResult && streamResult.session_id) {
              this.sessionId = streamResult.session_id;
              localStorage.setItem('medikiosk_session_id', this.sessionId);
            }
            if (streamBubble) {
              streamBubble.finalize(streamResult ? streamResult.full_text : '');
            }
            this.flushTtsRemaining(detectedLang);
            this.setUiState('IDLE');
          },
          // onError
          (err) => {
            this.isVoiceProcessing = false;
            console.error('Voice stream error:', err);
            if (streamBubble) {
              streamBubble.showError(err.message || 'AI is taking longer than expected. Please try again.');
            } else {
              this.appendMessage('ai', err.message || 'Voice processing failed. Please try again.', 'text');
            }
            this.setUiState('IDLE');
          }
        );
      } else {
        this.isVoiceProcessing = false;
      }
    } else {
      // Start recording
      try {
        API.startVoiceStream();
        await this.recorder.start((pcmBuffer) => {
          API.sendVoiceChunk(pcmBuffer);
        });

        this.setUiState('LISTENING');

        this.energyCheckInterval = setInterval(() => {
          if (!this.recorder.isRecording) {
            clearInterval(this.energyCheckInterval);
            return;
          }
          const energy = this.recorder.getEnergyLevel();
          if (energy > 18) {
            this.setUiState('LISTENING', '🔴 Listening... (Speaking detected)');
          } else {
            this.setUiState('LISTENING', '🔴 Listening...');
          }
        }, 200);

      } catch (err) {
        console.error('Mic error:', err);
        this.setUiState('ERROR', '⚠️ Microphone Access Denied');
      }
    }
  }

  sendVoiceTranscriptDirectly(text, language) {
    if (!text || !text.trim()) return;
    const cleanText = text.trim();
    const detectedLang = language || this.detectLanguage(cleanText, this.currentLanguage);

    this.appendMessage('patient', cleanText, 'voice');
    const streamBubble = this.createStreamingAiBubble();

    API.sendTextMessageWebSocket(
      cleanText,
      this.sessionId,
      this.currentPatient ? this.currentPatient.patient_id : 'P-1001',
      detectedLang,
      (token, fullText) => {
        streamBubble.update(fullText);
        this.queueTtsToken(token, detectedLang);
      },
      (streamResult) => {
        this.sessionId = streamResult.session_id;
        localStorage.setItem('medikiosk_session_id', this.sessionId);
        streamBubble.finalize(streamResult.full_text);
        this.flushTtsRemaining(detectedLang);
      },
      (err) => {
        console.error('Direct voice error:', err);
        streamBubble.showError(err.message || 'AI is taking longer than expected. Please try again.');
        this.setUiState('IDLE');
      }
    );
  }

  async handlePatientDocumentUpload() {
    const title = this.inputDocTitle?.value.trim();
    const docType = this.selectDocType?.value;
    const file = this.inputFileDoc?.files[0];

    if (!title || !file) {
      alert('Please enter a document title and select a file.');
      return;
    }

    const patientId = this.currentPatient ? this.currentPatient.patient_id : 'P-1001';
    const formData = new FormData();
    formData.append('title', title);
    formData.append('document_type', docType);
    formData.append('file', file);
    if (this.activeEncounter) {
      formData.append('encounter_id', this.activeEncounter.encounter_id);
    }

    try {
      const res = await API.uploadPatientDocument(patientId, formData);
      this.closeModal(this.modalPatientUpload);
      alert('Document uploaded and stored permanently under your medical record.');
      this.appendMessage('ai', `I have recorded your uploaded document "${title}" (${docType}) for the doctor.`, 'text');
    } catch (e) {
      alert('Failed to upload document.');
    }
  }

  // --- Doctor Portal Workflow ---

  initDoctorPortal(doctor) {
    if (this.docNameDisplay) this.docNameDisplay.textContent = doctor.name;
    if (this.docSpecDisplay) this.docSpecDisplay.textContent = `${doctor.specialization} • ${doctor.hospital}`;
    this.showDoctorSubview('dashboard');
    this.refreshDoctorDashboard();
  }

  showDoctorSubview(subviewName) {
    if (this.docSubviewDashboard) this.docSubviewDashboard.classList.remove('active');
    if (this.docSubviewVerification) this.docSubviewVerification.classList.remove('active');
    if (this.docSubviewWorkstation) this.docSubviewWorkstation.classList.remove('active');

    if (subviewName === 'dashboard' && this.docSubviewDashboard) {
      this.docSubviewDashboard.classList.add('active');
    } else if (subviewName === 'verification' && this.docSubviewVerification) {
      this.docSubviewVerification.classList.add('active');
    } else if (subviewName === 'workstation' && this.docSubviewWorkstation) {
      this.docSubviewWorkstation.classList.add('active');
    }
  }

  async refreshDoctorDashboard() {
    try {
      const stats = await API.getDoctorDashboardStats();
      if (stats.status === 'success' && stats.data) {
        document.getElementById('metricNewCases').textContent = stats.data.new_cases;
        document.getElementById('metricPriority').textContent = stats.data.priority;
        document.getElementById('metricCompleted').textContent = stats.data.completed;
      }
    } catch (e) {
      console.warn('Dashboard stats error:', e);
    }
  }

  async handleDoctorSearchPatient(abhaId) {
    try {
      const res = await API.searchPatientByAbha(abhaId);
      if (res.status === 'success' && res.patient) {
        this.searchedPatient = res.patient;
        this.searchedEncounter = res.active_encounter;

        // Populate Verification Screen
        if (this.verifyPatientName) this.verifyPatientName.textContent = res.patient.name;
        if (this.verifyPatientAbha) this.verifyPatientAbha.textContent = res.patient.abha_id;
        if (this.verifyPatientAgeGender) this.verifyPatientAgeGender.textContent = `${res.patient.age} / ${res.patient.gender}`;
        if (this.verifyPatientPhone) this.verifyPatientPhone.textContent = res.patient.phone || 'N/A';
        if (this.verifyPatientConditions) this.verifyPatientConditions.textContent = res.patient.known_conditions || 'None reported';

        this.showDoctorSubview('verification');
      } else {
        alert(res.message || 'Patient not found.');
      }
    } catch (e) {
      alert('Error searching patient.');
    }
  }

  openPatientWorkstation(patient, encounter) {
    this.currentWsPatient = patient;
    this.currentWsEncounter = encounter;

    if (this.wsPatientName) this.wsPatientName.textContent = patient.name;
    if (this.wsPatientMeta) this.wsPatientMeta.textContent = `${patient.age} Yrs • ${patient.gender} • ABHA: ${patient.abha_id} • Phone: ${patient.phone}`;
    if (this.wsEncounterDate) this.wsEncounterDate.textContent = `Active Visit: ${encounter ? encounter.date : new Date().toISOString().slice(0,10)}`;

    this.populateAiHistory(encounter);
    this.showDoctorSubview('workstation');
    this.switchDoctorWorkstationTab('tabCurrentProblem');
  }

  populateAiHistory(encounter) {
    if (!encounter) return;
    if (this.aiChiefComplaintText) this.aiChiefComplaintText.textContent = encounter.ai_chief_complaint || encounter.current_problem || 'Chest pain since yesterday';
    if (this.aiPastMedText) this.aiPastMedText.textContent = encounter.past_medical_history || 'Type 2 Diabetes Mellitus (5 years duration)';
    if (this.aiMedicationsText) this.aiMedicationsText.textContent = encounter.medications || 'Tab Metformin 500mg BD after meals';
    if (this.aiAllergiesText) this.aiAllergiesText.textContent = encounter.allergies || 'Penicillin (developed severe rash)';
    if (this.aiFamilyText) this.aiFamilyText.textContent = encounter.family_history || 'Father had acute MI at 52; Mother diabetic';
    if (this.aiPersonalText) this.aiPersonalText.textContent = encounter.personal_history || 'Non-smoker, sedentary office work';

    if (this.aiHpiList && encounter.ai_hpi) {
      this.aiHpiList.innerHTML = Object.entries(encounter.ai_hpi).map(([k, v]) => `<li><strong>${this.formatKey(k)}:</strong> ${Array.isArray(v) ? v.join(', ') : v}</li>`).join('');
    }
  }

  formatKey(str) {
    return str.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
  }

  switchDoctorWorkstationTab(tabId) {
    this.currentDocTab = tabId;
    document.querySelectorAll('.ws-tab-btn').forEach(b => {
      if (b.getAttribute('data-tab') === tabId) b.classList.add('active');
      else b.classList.remove('active');
    });

    document.querySelectorAll('.ws-tab-content').forEach(c => {
      if (c.id === tabId) c.classList.add('active');
      else c.classList.remove('active');
    });

    if (tabId === 'tabPreviousConsultations') {
      this.loadPreviousConsultations();
    } else if (tabId === 'tabUploadedDocs') {
      this.loadUploadedDocuments();
    } else if (tabId === 'tabTimeline') {
      this.loadPatientTimeline();
    }
  }

  async loadPreviousConsultations() {
    if (!this.currentWsPatient || !this.previousConsultationsList) return;
    this.previousConsultationsList.innerHTML = '<div class="loading-spinner">Loading past encounters...</div>';

    try {
      const res = await API.getPatientConsultations(this.currentWsPatient.patient_id);
      if (res.status === 'success' && res.consultations.length > 0) {
        this.previousConsultationsList.innerHTML = res.consultations.map(c => `
          <div class="encounter-history-card">
            <div class="enc-card-header">
              <div class="enc-title-col">
                <span class="enc-date">📅 ${c.date}</span>
                <h4 class="enc-problem">Chief Problem: ${c.current_problem || c.diagnosis || 'Clinical Visit'}</h4>
              </div>
              <span class="enc-doctor-badge">👨‍⚕️ ${c.doctor_name || 'Dr. Arun Kumar'}</span>
            </div>
            <div class="enc-card-body">
              <div class="enc-row"><strong>Assessment:</strong> <span>${c.assessment || 'Completed'}</span></div>
              <div class="enc-row"><strong>Diagnosis:</strong> <span class="badge-diag">${c.diagnosis || 'General Clinical Review'}</span></div>
              <div class="enc-row"><strong>Treatment / Prescription:</strong> <pre class="enc-rx">${c.prescription_treatment || 'None prescribed'}</pre></div>
              <div class="enc-row"><strong>Follow-up:</strong> <span>${c.follow_up || 'Routine SOS'}</span></div>
            </div>
          </div>
        `).join('');
      } else {
        this.previousConsultationsList.innerHTML = '<div class="empty-state">No previous consultations found for this patient.</div>';
      }
    } catch (e) {
      this.previousConsultationsList.innerHTML = '<div class="empty-state">Error loading past consultations.</div>';
    }
  }

  async loadUploadedDocuments() {
    if (!this.currentWsPatient || !this.uploadedDocumentsGrid) return;
    this.uploadedDocumentsGrid.innerHTML = '<div class="loading-spinner">Loading uploaded documents...</div>';

    try {
      const res = await API.getPatientDocuments(this.currentWsPatient.patient_id);
      if (res.status === 'success' && res.documents.length > 0) {
        this.uploadedDocumentsGrid.innerHTML = res.documents.map(d => `
          <div class="document-card">
            <div class="doc-type-icon">📄</div>
            <div class="doc-card-info">
              <h4 class="doc-title">${d.title}</h4>
              <span class="doc-meta">Uploaded: ${d.uploaded_at.slice(0, 10)} • ${d.document_type}</span>
            </div>
            <button type="button" class="btn-view-doc-ocr" data-doc-id="${d.document_id}">
              🔍 View Document &amp; OCR
            </button>
          </div>
        `).join('');

        this.uploadedDocumentsGrid.querySelectorAll('.btn-view-doc-ocr').forEach(btn => {
          btn.addEventListener('click', () => {
            const docId = btn.getAttribute('data-doc-id');
            if (docId) this.openDocumentOcrViewer(docId);
          });
        });
      } else {
        this.uploadedDocumentsGrid.innerHTML = '<div class="empty-state">No uploaded documents available for this patient.</div>';
      }
    } catch (e) {
      this.uploadedDocumentsGrid.innerHTML = '<div class="empty-state">Error loading documents.</div>';
    }
  }

  async openDocumentOcrViewer(documentId) {
    try {
      const res = await API.getDocumentExtraction(documentId);
      if (res.status === 'success' && res.document) {
        const d = res.document;
        if (this.docViewerTitle) this.docViewerTitle.textContent = d.title;
        if (this.docViewerMeta) this.docViewerMeta.textContent = `Uploaded ${d.uploaded_at.slice(0, 10)} • ${d.document_type}`;
        if (this.ocrExtDiagnosis) this.ocrExtDiagnosis.textContent = d.extraction_diagnosis || 'Not specified';
        if (this.ocrExtMedications) this.ocrExtMedications.textContent = d.extraction_medications || 'None extracted';
        if (this.ocrExtRawText) this.ocrExtRawText.textContent = d.extraction_raw_text || 'OCR text not available';

        if (this.ocrExtLabTable && d.extraction_lab_results) {
          this.ocrExtLabTable.innerHTML = Object.entries(d.extraction_lab_results).map(([k, v]) => `
            <div class="lab-row">
              <span class="lab-key">${k}</span>
              <span class="lab-val">${v}</span>
            </div>
          `).join('');
        }

        this.openModal(this.modalDocViewer);
      }
    } catch (e) {
      alert('Error fetching document extraction details.');
    }
  }

  async loadPatientTimeline() {
    if (!this.currentWsPatient || !this.patientTimelineFeed) return;
    this.patientTimelineFeed.innerHTML = '<div class="loading-spinner">Loading timeline feed...</div>';

    try {
      const res = await API.getPatientTimeline(this.currentWsPatient.patient_id);
      if (res.status === 'success' && res.timeline.length > 0) {
        this.patientTimelineFeed.innerHTML = res.timeline.map(item => `
          <div class="timeline-event-card ${item.type}">
            <div class="timeline-dot"></div>
            <div class="timeline-event-header">
              <span class="timeline-date">📅 ${item.date}</span>
              <h4 class="timeline-title">${item.title}</h4>
            </div>
            <div class="timeline-event-body">
              ${item.type === 'consultation' 
                ? `<p><strong>Diagnosis:</strong> ${item.diagnosis}</p><p><strong>Doctor:</strong> ${item.doctor_name}</p>` 
                : `<p><strong>Document Type:</strong> ${item.document_type}</p><p><strong>File:</strong> ${item.file_name}</p>`
              }
            </div>
          </div>
        `).join('');
      } else {
        this.patientTimelineFeed.innerHTML = '<div class="empty-state">No timeline events recorded.</div>';
      }
    } catch (e) {
      this.patientTimelineFeed.innerHTML = '<div class="empty-state">Error loading timeline.</div>';
    }
  }

  openEditAiHistoryModal() {
    if (this.editChiefComplaint) this.editChiefComplaint.value = this.aiChiefComplaintText?.textContent || '';
    if (this.editPastMedical) this.editPastMedical.value = this.aiPastMedText?.textContent || '';
    if (this.editMedications) this.editMedications.value = this.aiMedicationsText?.textContent || '';
    if (this.editAllergies) this.editAllergies.value = this.aiAllergiesText?.textContent || '';
    if (this.editFamily) this.editFamily.value = this.aiFamilyText?.textContent || '';
    this.openModal(this.modalEditAiHistory);
  }

  async handleSaveEditedAiHistory() {
    if (!this.currentWsEncounter) return;
    const updateData = {
      chief_complaint: this.editChiefComplaint?.value,
      past_medical_history: this.editPastMedical?.value,
      medications: this.editMedications?.value,
      allergies: this.editAllergies?.value,
      family_history: this.editFamily?.value,
      doctor_notes: this.editDoctorNotes?.value
    };

    try {
      const res = await API.updateEncounterHistory(this.currentWsEncounter.encounter_id, updateData);
      if (res.status === 'success' && res.encounter) {
        this.currentWsEncounter = res.encounter;
        this.populateAiHistory(res.encounter);
        this.closeModal(this.modalEditAiHistory);
        alert('AI Clinical History updated successfully.');
      }
    } catch (e) {
      alert('Error updating AI history.');
    }
  }

  async handleVerifyAiHistory() {
    if (!this.currentWsEncounter) return;
    try {
      const res = await API.verifyEncounterHistory(this.currentWsEncounter.encounter_id, 'Verified by doctor');
      if (res.status === 'success') {
        alert('AI History marked as Verified by Doctor.');
        if (this.btnVerifyAiHistory) {
          this.btnVerifyAiHistory.textContent = '✓ Verified';
          this.btnVerifyAiHistory.disabled = true;
        }
      }
    } catch (e) {
      alert('Error verifying history.');
    }
  }

  async handleSaveDoctorConsultation() {
    if (!this.currentWsEncounter) return;

    const consultData = {
      clinical_findings: this.docClinicalFindings?.value,
      assessment: this.docAssessment?.value,
      diagnosis: this.docDiagnosis?.value,
      prescription_treatment: this.docPrescription?.value,
      follow_up: this.docFollowUp?.value,
      notes: this.docNotes?.value
    };

    try {
      const res = await API.saveDoctorConsultation(this.currentWsEncounter.encounter_id, consultData);
      if (res.status === 'success' && res.data) {
        if (this.savedModalDate) this.savedModalDate.textContent = res.data.date;
        if (this.savedModalPatient) this.savedModalPatient.textContent = this.currentWsPatient ? this.currentWsPatient.name : 'Patient';
        if (this.savedModalEncId) this.savedModalEncId.textContent = res.data.encounter_id;

        this.openModal(this.modalConsultationSaved);
      }
    } catch (e) {
      alert('Error saving consultation.');
    }
  }

  // --- WebSocket, Audio & TTS Queue Management ---

  initSocket() {
    API.initSocket();
  }

  setUiState(state, customLabel = null) {
    if (this.voiceStateLabel) {
      if (customLabel) {
        this.voiceStateLabel.textContent = customLabel;
      } else if (state === 'LISTENING') {
        this.voiceStateLabel.textContent = '🔴 Listening... Speak naturally';
      } else if (state === 'TRANSCRIBING') {
        this.voiceStateLabel.textContent = '⏳ Transcribing speech...';
      } else if (state === 'SENDING') {
        this.voiceStateLabel.textContent = '⚡ Thinking...';
      } else if (state === 'AI_RESPONDING') {
        this.voiceStateLabel.textContent = '🔊 MediKiosk Speaking...';
      } else {
        this.voiceStateLabel.textContent = '🎤 Tap to speak';
      }
    }
  }

  stopAllAudioAndTtsQueue() {
    this.ttsQueue = [];
    this.isTtsPlaying = false;
    this.currentTtsSentenceBuffer = '';
    if (this.audioPlayer) {
      this.audioPlayer.pause();
      this.audioPlayer.currentTime = 0;
      this.audioPlayer.src = '';
    }
    this.setUiState('IDLE');
  }

  queueTtsToken(token, language) {
    if (!token) return;
    this.currentTtsSentenceBuffer += token;

    const sentenceDelimMatch = this.currentTtsSentenceBuffer.match(/([.!?\n।]+)\s*/);
    if (sentenceDelimMatch && sentenceDelimMatch.index !== undefined) {
      const splitIdx = sentenceDelimMatch.index + sentenceDelimMatch[0].length;
      const completeSentence = this.currentTtsSentenceBuffer.slice(0, splitIdx).trim();
      this.currentTtsSentenceBuffer = this.currentTtsSentenceBuffer.slice(splitIdx);

      if (completeSentence && completeSentence.length > 3) {
        this.synthesizeAndQueueSentence(completeSentence, language);
      }
    }
  }

  flushTtsRemaining(language) {
    const remaining = this.currentTtsSentenceBuffer.trim();
    this.currentTtsSentenceBuffer = '';
    if (remaining && remaining.length > 2) {
      this.synthesizeAndQueueSentence(remaining, language);
    }
  }

  async synthesizeAndQueueSentence(sentenceText, language) {
    const detectedLang = this.detectLanguage(sentenceText, language);
    try {
      const synthRes = await API.synthesizeAudio(sentenceText, detectedLang);
      if (synthRes && synthRes.status === 'success' && synthRes.audio_url) {
        this.ttsQueue.push({ url: synthRes.audio_url, text: sentenceText, lang: detectedLang });
        this.playNextTtsInQueue();
      }
    } catch (e) {
      console.warn('TTS Synthesis error:', e);
    }
  }

  playNextTtsInQueue() {
    if (this.isTtsPlaying || this.ttsQueue.length === 0) return;
    const item = this.ttsQueue.shift();
    if (!item) return;

    this.isTtsPlaying = true;
    this.setUiState('AI_RESPONDING');
    this.audioPlayer.src = item.url;
    this.audioPlayer.onended = () => {
      this.isTtsPlaying = false;
      if (this.ttsQueue.length > 0) {
        this.playNextTtsInQueue();
      } else {
        this.setUiState('IDLE');
      }
    };
    this.audioPlayer.onerror = () => {
      this.isTtsPlaying = false;
      this.playNextTtsInQueue();
    };
    this.audioPlayer.play().catch(() => {
      this.isTtsPlaying = false;
      this.playNextTtsInQueue();
    });
  }

  detectLanguage(text, fallback = 'en') {
    if (!text) return fallback;
    const tamil = (text.match(/[\u0B80-\u0BFF]/g) || []).length;
    const devanagari = (text.match(/[\u0900-\u097F]/g) || []).length;
    const telugu = (text.match(/[\u0C00-\u0C7F]/g) || []).length;
    const malayalam = (text.match(/[\u0D00-\u0D7F]/g) || []).length;
    const kannada = (text.match(/[\u0C80-\u0CFF]/g) || []).length;
    const bengali = (text.match(/[\u0980-\u09FF]/g) || []).length;
    const latin = (text.match(/[a-zA-Z]/g) || []).length;

    const counts = { ta: tamil, hi: devanagari, te: telugu, ml: malayalam, kn: kannada, bn: bengali, en: latin };
    const max = Object.entries(counts).reduce((a, b) => (b[1] > a[1] ? b : a), ['en', 0]);

    if (max[1] > 1) return max[0];

    const t_lower = text.toLowerCase ? text.toLowerCase() : text;
    if (['irukku', 'iruku', 'enakku', 'romba', 'vali'].some(w => t_lower.includes(w))) return 'ta';
    if (['hai', 'nahi', 'kya', 'dard', 'bukhar'].some(w => t_lower.includes(w))) return 'hi';
    if (['undi', 'ledu', 'naku', 'noppi'].some(w => t_lower.includes(w))) return 'te';
    return fallback;
  }

  appendMessage(sender, text, modality = 'text') {
    const isAi = sender === 'ai';
    const row = document.createElement('div');
    row.className = `chat-bubble-row ${isAi ? 'ai-row' : 'user-row'}`;

    const avatar = document.createElement('div');
    avatar.className = `avatar-bubble ${isAi ? 'ai-avatar' : 'user-avatar'}`;
    avatar.innerHTML = isAi
      ? '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="10" rx="2"/><circle cx="12" cy="5" r="2"/><path d="M12 7v4"/><line x1="8" y1="16" x2="8" y2="16"/><line x1="16" y1="16" x2="16" y2="16"/></svg>'
      : '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>';

    const wrapper = document.createElement('div');
    wrapper.className = 'message-bubble-wrapper';

    const bubble = document.createElement('div');
    bubble.className = `message-bubble ${isAi ? 'ai-bubble' : 'user-bubble'}`;

    const contentDiv = document.createElement('div');
    contentDiv.className = 'bubble-content formatted-message';
    contentDiv.innerHTML = this.formatMarkdown(text);
    bubble.appendChild(contentDiv);

    const timeElem = document.createElement('span');
    timeElem.className = 'bubble-timestamp';
    timeElem.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    bubble.appendChild(timeElem);

    wrapper.appendChild(bubble);
    row.appendChild(avatar);
    row.appendChild(wrapper);

    if (this.patientChatMessages) {
      this.patientChatMessages.appendChild(row);
      this.patientChatMessages.scrollTop = this.patientChatMessages.scrollHeight;
    }
  }

  createStreamingAiBubble() {
    const row = document.createElement('div');
    row.className = 'chat-bubble-row ai-row';

    const avatar = document.createElement('div');
    avatar.className = 'avatar-bubble ai-avatar';
    avatar.innerHTML = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="10" rx="2"/><circle cx="12" cy="5" r="2"/><path d="M12 7v4"/><line x1="8" y1="16" x2="8" y2="16"/><line x1="16" y1="16" x2="16" y2="16"/></svg>';

    const wrapper = document.createElement('div');
    wrapper.className = 'message-bubble-wrapper';

    const bubble = document.createElement('div');
    bubble.className = 'message-bubble ai-bubble';

    const contentDiv = document.createElement('div');
    contentDiv.className = 'bubble-content formatted-message';
    contentDiv.innerHTML = '<div class="typing-indicator"><span></span><span></span><span></span></div>';
    bubble.appendChild(contentDiv);

    const timeElem = document.createElement('span');
    timeElem.className = 'bubble-timestamp';
    timeElem.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    bubble.appendChild(timeElem);

    wrapper.appendChild(bubble);
    row.appendChild(avatar);
    row.appendChild(wrapper);

    if (this.patientChatMessages) {
      this.patientChatMessages.appendChild(row);
      this.patientChatMessages.scrollTop = this.patientChatMessages.scrollHeight;
    }

    return {
      element: row,
      update: (fullText) => {
        this.setUiState('AI_RESPONDING');
        contentDiv.innerHTML = this.formatMarkdown(fullText);
        if (this.patientChatMessages) this.patientChatMessages.scrollTop = this.patientChatMessages.scrollHeight;
      },
      finalize: (fullText) => {
        contentDiv.innerHTML = this.formatMarkdown(fullText);
        this.setUiState('IDLE');
      },
      showError: (err) => {
        contentDiv.innerHTML = `<p class="text-danger">${this.escapeHtml(err)}</p>`;
        this.setUiState('IDLE');
      }
    };
  }

  formatMarkdown(text) {
    if (!text) return '';

    // 1. Extract and preserve code blocks (fenced by ```)
    const codeBlocks = [];
    let processed = text.replace(/```([a-zA-Z0-9_\-#+]*)\n?([\s\S]*?)(?:```|$)/g, (match, lang, code) => {
      const id = codeBlocks.length;
      const cleanLang = (lang || 'code').trim().toLowerCase();
      const escapedCode = this.escapeHtml(code.replace(/\r\n/g, '\n').replace(/^\n+|\n+$/g, ''));
      codeBlocks.push(
        `<div class="code-block-container">` +
          `<div class="code-block-header">` +
            `<span class="code-lang-tag">${cleanLang}</span>` +
            `<button type="button" class="copy-code-btn" onclick="navigator.clipboard.writeText(this.closest('.code-block-container').querySelector('code').innerText);this.innerText='Copied!';setTimeout(()=>this.innerText='Copy',2000);">Copy</button>` +
          `</div>` +
          `<pre><code>${escapedCode}</code></pre>` +
        `</div>`
      );
      return `\n\n__CODE_BLOCK_${id}__\n\n`;
    });

    // 2. Escape HTML in regular markdown text
    processed = this.escapeHtml(processed);

    // 3. Inline code `code`
    processed = processed.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>');

    // 4. Bold **text**
    processed = processed.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

    // 5. Italic *text*
    processed = processed.replace(/\*([^*]+)\*/g, '<em>$1</em>');

    // 6. Handle double newlines as paragraphs and single newlines as <br>
    const paragraphs = processed.split(/\n\s*\n/);
    const htmlParas = paragraphs.map(para => {
      let p = para.trim();
      if (!p) return '';
      if (/^__CODE_BLOCK_\d+__$/.test(p)) {
        return p;
      }
      p = p.replace(/\n/g, '<br>');
      return `<p>${p}</p>`;
    }).filter(p => p.length > 0);

    let html = htmlParas.join('');

    // 7. Restore code blocks
    codeBlocks.forEach((blockHtml, idx) => {
      html = html.replace(new RegExp(`(<p>)?__CODE_BLOCK_${idx}__(</p>)?`, 'g'), blockHtml);
    });

    return html || `<p>${this.escapeHtml(text)}</p>`;
  }

  escapeHtml(str) {
    if (!str) return '';
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }
}

document.addEventListener('DOMContentLoaded', () => {
  window.app = new MediKioskApp();
});
