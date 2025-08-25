// Municipal Voice Assistant - Fixed Speech Recognition State Management

class MunicipalVoiceAssistant {
    constructor() {
        this.sessionId = null;
        this.messageHistory = [];
        this.isRecording = false;
        this.isProcessing = false;
        this.isSpeaking = false;
        this.isVoiceMode = false;
        this.isInitialized = false;
        
        // Add recognition state tracking
        this.recognitionState = 'idle'; // 'idle', 'starting', 'listening', 'stopping'
        this.recognitionStarting = false;
        
        this.settings = {
            autoSpeak: true,
            voiceSpeed: 0.9,
            voicePitch: 1.0,
            voiceVolume: 1.0,
            speechLang: 'en-IN'
        };
        
        this.recognition = null;
        this.recognitionSupported = false;
        this.microphonePermission = false;
        this.recognitionTimeout = null;
        
        this.speechSynthesis = window.speechSynthesis;
        this.voices = [];
        this.selectedVoice = null;
        this.currentUtterance = null;
        
        this.apiBase = 'http://localhost:8000';
        this.elements = {};
        
        this.init();
    }

    async init() {
        try {
            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', () => this.init());
                return;
            }
            
            this.cacheElements();
            this.loadSettings();
            
            await this.initializeVoices();
            await this.checkMicrophonePermission();
            this.initSpeechRecognition();
            this.initEventListeners();
            
            this.updateStatus('Ready', 'online');
            this.updateAuthStatus('Authenticated');
            this.updateSessionInfo('New Session');
            this.updateTTSToggleUI();
            
            this.isInitialized = true;
            
        } catch (error) {
            console.error('Failed to initialize:', error);
            this.updateStatus('Error', 'offline');
            this.showError('Failed to initialize the application. Please refresh the page.');
        }
    }

    cacheElements() {
        const elementIds = [
            'chatMessages', 'typingIndicator', 'messageInput', 'sendBtn',
            'voiceInputBtn', 'bigVoiceBtn', 'voiceOnlySection', 'voiceStatus',
            'textModeBtn', 'voiceModeBtn', 'inputContainer',
            'connectionStatus', 'statusText', 'authStatus', 'sessionInfo',
            'settingsModal', 'permissionBanner', 'charCounter',
            'ttsToggleBtn', 'voiceSpeed', 'voicePitch', 'voiceVolume',
            'autoSpeakToggle', 'speechLang'
        ];
        
        this.elements = {};
        elementIds.forEach(id => {
            this.elements[id] = document.getElementById(id);
        });
    }

    // ==================== VOICE SYNTHESIS ====================
    
    async initializeVoices() {
        return new Promise((resolve) => {
            const loadVoices = () => {
                this.voices = this.speechSynthesis.getVoices();
                
                if (this.voices.length > 0) {
                    this.selectedVoice = this.findBestIndianVoice();
                    resolve();
                } else {
                    setTimeout(loadVoices, 100);
                }
            };
            
            if (this.voices.length === 0) {
                this.speechSynthesis.onvoiceschanged = loadVoices;
            }
            loadVoices();
        });
    }

    findBestIndianVoice() {
        this.voicePreferences = [
            'Microsoft Heera - English (India)',
            'Google हिन्दी',
            'Google English India',
            'Microsoft Ravi - English (India)',
            'en-IN',
            'hi-IN'
        ];
        
        for (const preference of this.voicePreferences) {
            const voice = this.voices.find(v => v.name === preference || v.lang === preference);
            if (voice) return voice;
        }
        
        let voice = this.voices.find(v => 
            v.lang.startsWith('en-IN') || 
            v.lang.startsWith('hi-IN') ||
            v.name.toLowerCase().includes('india')
        );
        
        return voice || this.voices.find(v => v.lang.startsWith('en-')) || this.voices[0];
    }

    speak(text, priority = false) {
        if (!this.settings.autoSpeak && !priority) return;
        if (!text || text.trim().length === 0) return;
        
        this.stopSpeaking();
        
        try {
            const cleanText = this.cleanTextForSpeech(text);
            this.currentUtterance = new SpeechSynthesisUtterance(cleanText);
            
            if (this.selectedVoice) {
                this.currentUtterance.voice = this.selectedVoice;
            }
            
            this.currentUtterance.rate = this.settings.voiceSpeed;
            this.currentUtterance.pitch = this.settings.voicePitch;
            this.currentUtterance.volume = this.settings.voiceVolume;
            
            this.currentUtterance.onstart = () => {
                this.isSpeaking = true;
                this.updateStatus('Speaking...', 'speaking');
            };
            
            this.currentUtterance.onend = () => {
                this.isSpeaking = false;
                this.currentUtterance = null;
                this.updateStatus('Ready', 'online');
            };
            
            this.currentUtterance.onerror = () => {
                this.isSpeaking = false;
                this.currentUtterance = null;
                this.updateStatus('Ready', 'online');
            };
            
            this.speechSynthesis.speak(this.currentUtterance);
            
        } catch (error) {
            console.error('Failed to speak:', error);
            this.updateStatus('Ready', 'online');
        }
    }

    cleanTextForSpeech(text) {
        return text
            .replace(/[🎤🔊✅❌🚧]/g, '')
            .replace(/https?:\/\/[^\s]+/g, 'link')
            .replace(/\*\*(.*?)\*\*/g, '$1')
            .replace(/\*(.*?)\*/g, '$1')
            .replace(/`(.*?)`/g, '$1')
            .replace(/\n+/g, '. ')
            .replace(/\s+/g, ' ')
            .trim();
    }

    stopSpeaking() {
        if (this.isSpeaking && this.speechSynthesis.speaking) {
            this.speechSynthesis.cancel();
            this.isSpeaking = false;
            this.currentUtterance = null;
            this.updateStatus('Ready', 'online');
        }
    }

    toggleAutoSpeak() {
        this.settings.autoSpeak = !this.settings.autoSpeak;
        this.updateTTSToggleUI();
        this.saveSettings();
        
        const message = this.settings.autoSpeak ? 'Auto-speak enabled' : 'Auto-speak disabled';
        this.addSystemMessage(message, 'info');
    }

    updateTTSToggleUI() {
        if (this.elements.ttsToggleBtn) {
            const icon = this.elements.ttsToggleBtn.querySelector('i');
            if (this.settings.autoSpeak) {
                this.elements.ttsToggleBtn.classList.remove('muted');
                if (icon) icon.className = 'fas fa-volume-up';
            } else {
                this.elements.ttsToggleBtn.classList.add('muted');
                if (icon) icon.className = 'fas fa-volume-mute';
            }
        }
    }

    // ==================== SPEECH RECOGNITION - FIXED STATE MANAGEMENT ====================
    
    async checkMicrophonePermission() {
        try {
            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                this.showPermissionBanner();
                return false;
            }
            
            if ('permissions' in navigator) {
                const result = await navigator.permissions.query({ name: 'microphone' });
                this.handlePermissionState(result.state);
                result.onchange = () => this.handlePermissionState(result.state);
                return result.state === 'granted';
            } else {
                try {
                    const stream = await navigator.mediaDevices.getUserMedia({ 
                        audio: {
                            echoCancellation: true,
                            noiseSuppression: true,
                            autoGainControl: true
                        }
                    });
                    stream.getTracks().forEach(track => track.stop());
                    this.handlePermissionState('granted');
                    return true;
                } catch (error) {
                    this.handlePermissionState('denied');
                    return false;
                }
            }
        } catch (error) {
            console.error('Error checking microphone permission:', error);
            this.showPermissionBanner();
            return false;
        }
    }

    handlePermissionState(state) {
        this.microphonePermission = state === 'granted';
        
        if (this.microphonePermission) {
            this.hidePermissionBanner();
        } else {
            this.showPermissionBanner();
        }
    }

    async requestMicrophonePermission() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ 
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true
                }
            });
            
            stream.getTracks().forEach(track => track.stop());
            
            this.microphonePermission = true;
            this.hidePermissionBanner();
            this.addSystemMessage('Microphone access granted! Voice features are now available.', 'success');
            
            this.initSpeechRecognition();
            
        } catch (error) {
            console.error('Microphone permission denied:', error);
            this.microphonePermission = false;
            
            let errorMessage = 'Microphone access denied. ';
            if (error.name === 'NotAllowedError') {
                errorMessage += 'Please allow microphone access in your browser settings.';
            } else if (error.name === 'NotFoundError') {
                errorMessage += 'No microphone found. Please connect a microphone.';
            } else {
                errorMessage += 'Please check your microphone and browser settings.';
            }
            
            this.addSystemMessage(errorMessage, 'error');
            this.showPermissionBanner();
        }
    }

    initSpeechRecognition() {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        
        if (!SpeechRecognition) {
            this.recognitionSupported = false;
            this.addSystemMessage('Voice recognition not supported. Please use Chrome, Edge, or Safari.', 'error');
            
            if (this.elements.voiceInputBtn) this.elements.voiceInputBtn.style.display = 'none';
            if (this.elements.bigVoiceBtn) this.elements.bigVoiceBtn.style.display = 'none';
            if (this.elements.voiceModeBtn) this.elements.voiceModeBtn.style.display = 'none';
            
            return;
        }
        
        this.recognitionSupported = true;
        
        try {
            this.recognition = new SpeechRecognition();
            
            this.recognition.continuous = false;
            this.recognition.interimResults = true;
            this.recognition.lang = this.settings.speechLang;
            this.recognition.maxAlternatives = 1;
            
            this.recognition.onstart = () => {
                console.log('Speech recognition started');
                this.recognitionState = 'listening';
                this.isRecording = true;
                this.recognitionStarting = false;
                this.updateStatus('Listening...', 'listening');
                this.updateVoiceButtons('recording');
                
                if (this.isVoiceMode) {
                    this.updateVoiceStatus('Listening... Speak clearly!');
                }
                
                // Clear any previous timeout
                if (this.recognitionTimeout) {
                    clearTimeout(this.recognitionTimeout);
                }
                
                // Set timeout to prevent hanging
                this.recognitionTimeout = setTimeout(() => {
                    if (this.recognitionState === 'listening') {
                        console.log('Recognition timeout - stopping');
                        this.forceStopRecognition();
                        this.addSystemMessage('Listening timeout. Please try again.', 'error');
                    }
                }, 10000);
            };

            this.recognition.onresult = (event) => {
                // Clear timeout since we got a result
                if (this.recognitionTimeout) {
                    clearTimeout(this.recognitionTimeout);
                    this.recognitionTimeout = null;
                }
                
                let finalTranscript = '';
                let interimTranscript = '';
                
                for (let i = event.resultIndex; i < event.results.length; i++) {
                    const result = event.results[i];
                    const transcript = result[0].transcript;
                    
                    if (result.isFinal) {
                        finalTranscript += transcript;
                    } else {
                        interimTranscript += transcript;
                    }
                }
                
                // Show interim results in text mode
                if (interimTranscript && !this.isVoiceMode && this.elements.messageInput) {
                    this.elements.messageInput.value = finalTranscript + interimTranscript;
                    this.updateCharCounter();
                }
                
                // Process final result - just pass it through if we got something
                if (finalTranscript && finalTranscript.trim().length > 0) {
                    this.processSpeechResult(finalTranscript.trim());
                }
            };

            this.recognition.onerror = (event) => {
                console.error('Speech recognition error:', event.error);
                
                // Clear timeout
                if (this.recognitionTimeout) {
                    clearTimeout(this.recognitionTimeout);
                    this.recognitionTimeout = null;
                }
                
                let errorMessage = 'Voice recognition error: ';
                
                switch (event.error) {
                    case 'no-speech':
                        errorMessage += 'No speech detected. Please try again.';
                        break;
                    case 'audio-capture':
                        errorMessage += 'Microphone not accessible.';
                        break;
                    case 'not-allowed':
                        errorMessage += 'Microphone access denied.';
                        this.microphonePermission = false;
                        this.showPermissionBanner();
                        break;
                    case 'network':
                        errorMessage += 'Network error. Please check your connection.';
                        break;
                    case 'aborted':
                        console.log('Recognition aborted - this is normal when stopping');
                        this.resetRecognitionState();
                        return;
                    default:
                        errorMessage += event.error + '. Please try again.';
                }
                
                this.addSystemMessage(errorMessage, 'error');
                this.resetRecognitionState();
            };

            this.recognition.onend = () => {
                console.log('Speech recognition ended');
                
                // Clear timeout
                if (this.recognitionTimeout) {
                    clearTimeout(this.recognitionTimeout);
                    this.recognitionTimeout = null;
                }
                
                this.resetRecognitionState();
            };
            
        } catch (error) {
            console.error('Failed to initialize speech recognition:', error);
            this.recognitionSupported = false;
            this.addSystemMessage('Failed to initialize voice recognition.', 'error');
        }
    }

    resetRecognitionState() {
        this.recognitionState = 'idle';
        this.isRecording = false;
        this.recognitionStarting = false;
        this.updateStatus('Ready', 'online');
        this.updateVoiceButtons('idle');
        
        if (this.isVoiceMode) {
            this.updateVoiceStatus('Ready to listen - Click microphone to speak');
        }
    }

    forceStopRecognition() {
        if (this.recognitionTimeout) {
            clearTimeout(this.recognitionTimeout);
            this.recognitionTimeout = null;
        }
        
        if (this.recognition && this.recognitionState !== 'idle') {
            try {
                this.recognitionState = 'stopping';
                this.recognition.abort();
            } catch (error) {
                console.warn('Error force stopping recognition:', error);
            }
        }
        
        this.resetRecognitionState();
    }

    processSpeechResult(transcript) {
        if (!transcript || transcript.length === 0) {
            this.addSystemMessage('No speech detected. Please try again.', 'error');
            return;
        }
        
        if (!this.isVoiceMode && this.elements.messageInput) {
            this.elements.messageInput.value = transcript;
            this.updateCharCounter();
        }
        
        this.sendMessage(transcript);
    }

    toggleVoiceRecording() {
        console.log(`Toggle voice recording - Current state: ${this.recognitionState}, isRecording: ${this.isRecording}`);
        
        if (this.recognitionState === 'listening' || this.isRecording) {
            this.stopVoiceRecording();
        } else if (this.recognitionState === 'idle' && !this.recognitionStarting) {
            this.startVoiceRecording();
        } else {
            console.log('Recognition busy, ignoring toggle request');
        }
    }

    startVoiceRecording() {
        console.log(`Start voice recording - State: ${this.recognitionState}, Starting: ${this.recognitionStarting}`);
        
        if (!this.microphonePermission) {
            this.requestMicrophonePermission();
            return;
        }
        
        if (!this.recognitionSupported || !this.recognition) {
            this.addSystemMessage('Voice recognition is not available.', 'error');
            return;
        }
        
        // Prevent multiple start attempts
        if (this.recognitionState !== 'idle' || this.recognitionStarting || this.isProcessing) {
            console.log('Cannot start - recognition busy or processing');
            return;
        }
        
        this.stopSpeaking();
        
        try {
            // Set flag to prevent multiple starts
            this.recognitionStarting = true;
            this.recognitionState = 'starting';
            
            if (this.recognition.lang !== this.settings.speechLang) {
                this.recognition.lang = this.settings.speechLang;
            }
            
            console.log('Attempting to start recognition...');
            this.recognition.start();
            
        } catch (error) {
            console.error('Failed to start voice recording:', error);
            
            // Reset flags on error
            this.recognitionStarting = false;
            this.recognitionState = 'idle';
            
            let errorMessage = 'Failed to start voice recording. ';
            if (error.name === 'InvalidStateError') {
                errorMessage += 'Please wait a moment and try again.';
                // Force reset the recognition
                setTimeout(() => {
                    this.forceStopRecognition();
                }, 500);
            } else {
                errorMessage += 'Please try again.';
            }
            
            this.addSystemMessage(errorMessage, 'error');
        }
    }

    stopVoiceRecording() {
        console.log(`Stop voice recording - State: ${this.recognitionState}`);
        
        if (this.recognitionTimeout) {
            clearTimeout(this.recognitionTimeout);
            this.recognitionTimeout = null;
        }
        
        if (this.recognition && this.recognitionState !== 'idle') {
            try {
                this.recognitionState = 'stopping';
                this.recognition.stop();
                console.log('Recognition stop called');
            } catch (error) {
                console.warn('Error stopping recognition:', error);
                this.forceStopRecognition();
            }
        } else {
            this.resetRecognitionState();
        }
    }

    // ==================== EVENT LISTENERS ====================
    
    initEventListeners() {
        if (this.elements.messageInput) {
            this.elements.messageInput.addEventListener('input', (e) => {
                this.autoResizeTextarea(e.target);
                this.updateCharCounter();
                this.updateSendButton();
            });
            
            this.elements.messageInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    this.sendMessage();
                }
            });
        }
        
        if (this.elements.voiceInputBtn) {
            this.elements.voiceInputBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.toggleVoiceRecording();
            });
        }
        
        if (this.elements.bigVoiceBtn) {
            this.elements.bigVoiceBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.toggleVoiceRecording();
            });
        }
        
        if (this.elements.textModeBtn) {
            this.elements.textModeBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.switchToTextMode();
            });
        }
        
        if (this.elements.voiceModeBtn) {
            this.elements.voiceModeBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.switchToVoiceMode();
            });
        }
        
        if (this.elements.sendBtn) {
            this.elements.sendBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.sendMessage();
            });
        }
        
        if (this.elements.ttsToggleBtn) {
            this.elements.ttsToggleBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.toggleAutoSpeak();
            });
        }
        
        // Settings controls
        const settingControls = [
            { id: 'voiceSpeed', prop: 'voiceSpeed' },
            { id: 'voicePitch', prop: 'voicePitch' },
            { id: 'voiceVolume', prop: 'voiceVolume' },
            { id: 'autoSpeakToggle', prop: 'autoSpeak' },
            { id: 'speechLang', prop: 'speechLang' }
        ];
        
        settingControls.forEach(({ id, prop }) => {
            const element = document.getElementById(id);
            if (element) {
                const eventType = element.type === 'checkbox' ? 'change' : 'input';
                element.addEventListener(eventType, (e) => {
                    const value = element.type === 'checkbox' ? e.target.checked : 
                                  element.type === 'range' ? parseFloat(e.target.value) : 
                                  e.target.value;
                    this.settings[prop] = value;
                    
                    if (prop === 'speechLang' && this.recognition) {
                        this.recognition.lang = value;
                    }
                    
                    if (prop === 'autoSpeak') {
                        this.updateTTSToggleUI();
                    }
                    
                    this.saveSettings();
                });
            }
        });
    }

    // ==================== UI METHODS ====================
    
    updateStatus(text, status = 'online') {
        if (this.elements.statusText) {
            this.elements.statusText.textContent = text;
        }
        
        if (this.elements.connectionStatus) {
            this.elements.connectionStatus.className = `status-dot ${status}`;
        }
    }

    updateAuthStatus(status) {
        if (this.elements.authStatus) {
            this.elements.authStatus.textContent = status;
        }
    }

    updateSessionInfo(info) {
        if (this.elements.sessionInfo) {
            this.elements.sessionInfo.textContent = info;
        }
    }

    updateVoiceStatus(status) {
        if (this.elements.voiceStatus) {
            this.elements.voiceStatus.textContent = status;
        }
    }

    updateVoiceButtons(state) {
        const buttons = [this.elements.voiceInputBtn, this.elements.bigVoiceBtn];
        
        buttons.forEach(btn => {
            if (!btn) return;
            
            const icon = btn.querySelector('i');
            if (!icon) return;
            
            btn.classList.remove('recording', 'idle');
            
            if (state === 'recording') {
                btn.classList.add('recording');
                icon.className = 'fas fa-stop';
                btn.title = 'Stop recording';
            } else {
                btn.classList.add('idle');
                icon.className = 'fas fa-microphone';
                btn.title = 'Start voice input';
            }
        });
    }

    updateCharCounter() {
        if (this.elements.charCounter && this.elements.messageInput) {
            const count = this.elements.messageInput.value.length;
            this.elements.charCounter.textContent = `${count}/1000`;
            
            if (count > 800) {
                this.elements.charCounter.style.color = '#f44336';
            } else if (count > 600) {
                this.elements.charCounter.style.color = '#ff9800';
            } else {
                this.elements.charCounter.style.color = '#666';
            }
        }
    }

    updateSendButton() {
        if (this.elements.sendBtn && this.elements.messageInput) {
            const hasText = this.elements.messageInput.value.trim().length > 0;
            this.elements.sendBtn.disabled = !hasText || this.isProcessing;
        }
    }

    autoResizeTextarea(textarea) {
        textarea.style.height = 'auto';
        const newHeight = Math.min(textarea.scrollHeight, 120);
        textarea.style.height = newHeight + 'px';
    }

    showPermissionBanner() {
        if (this.elements.permissionBanner) {
            this.elements.permissionBanner.style.display = 'flex';
        }
    }

    hidePermissionBanner() {
        if (this.elements.permissionBanner) {
            this.elements.permissionBanner.style.display = 'none';
        }
    }

    // ==================== MODE SWITCHING ====================
    
    switchToTextMode() {
        this.stopVoiceRecording();
        
        this.isVoiceMode = false;
        
        if (this.elements.textModeBtn) this.elements.textModeBtn.classList.add('active');
        if (this.elements.voiceModeBtn) this.elements.voiceModeBtn.classList.remove('active');
        
        if (this.elements.inputContainer) this.elements.inputContainer.style.display = 'flex';
        if (this.elements.voiceOnlySection) this.elements.voiceOnlySection.style.display = 'none';
    }

    switchToVoiceMode() {
        if (!this.microphonePermission) {
            this.requestMicrophonePermission();
            return;
        }
        
        if (!this.recognitionSupported) {
            this.addSystemMessage('Voice recognition not supported in this browser.', 'error');
            return;
        }
        
        this.isVoiceMode = true;
        
        if (this.elements.voiceModeBtn) this.elements.voiceModeBtn.classList.add('active');
        if (this.elements.textModeBtn) this.elements.textModeBtn.classList.remove('active');
        
        if (this.elements.voiceOnlySection) this.elements.voiceOnlySection.style.display = 'block';
        if (this.elements.inputContainer) this.elements.inputContainer.style.display = 'none';
        
        this.updateVoiceStatus('Voice mode active - Click microphone to speak');
    }

    // ==================== MESSAGING ====================
    
    async sendMessage(messageText = null) {
        const text = messageText || (this.elements.messageInput ? this.elements.messageInput.value.trim() : '');
        
        if (!text || this.isProcessing) return;
        
        if (this.elements.messageInput && !messageText) {
            this.elements.messageInput.value = '';
            this.autoResizeTextarea(this.elements.messageInput);
            this.updateCharCounter();
            this.updateSendButton();
        }
        
        this.addMessage('user', text);
        this.showTypingIndicator();
        this.isProcessing = true;
        
        try {
            const response = await this.sendToAPI(text);
            
            if (response.success) {
                if (response.session_id) {
                    this.sessionId = response.session_id;
                    this.updateSessionInfo(`Session: ${this.sessionId.substring(0, 8)}...`);
                }
                
                this.addMessage('bot', response.response);
                this.speak(response.response);
                
                if (response.session_info && response.session_info.authenticated) {
                    this.updateAuthStatus('Authenticated');
                }
                
            } else {
                this.addMessage('bot', `Error: ${response.error || 'Unknown error occurred'}`, 'error');
            }
            
        } catch (error) {
            console.error('Failed to send message:', error);
            this.addMessage('bot', 'Sorry, I encountered an error. Please try again.', 'error');
        } finally {
            this.hideTypingIndicator();
            this.isProcessing = false;
            this.updateSendButton();
            
            // Auto-start listening in voice mode after response
            if (this.isVoiceMode && this.recognitionState === 'idle' && !this.isSpeaking) {
                setTimeout(() => {
                    if (this.isVoiceMode && this.recognitionState === 'idle' && !this.isSpeaking) {
                        this.startVoiceRecording();
                    }
                }, 2000);
            }
        }
    }

    async sendToAPI(message) {
        const response = await fetch(`${this.apiBase}/chat/text`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                message: message,
                session_id: this.sessionId,
                language: 'en'
            })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        return await response.json();
    }

    addMessage(sender, text, type = 'normal') {
        if (!this.elements.chatMessages) return;
        
        const welcomeSection = this.elements.chatMessages.querySelector('.welcome-section');
        if (welcomeSection) {
            welcomeSection.remove();
        }
        
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}`;
        
        const avatar = document.createElement('div');
        avatar.className = 'message-avatar';
        
        if (sender === 'user') {
            avatar.innerHTML = '<i class="fas fa-user"></i>';
        } else if (sender === 'bot') {
            avatar.innerHTML = '<i class="fas fa-robot"></i>';
        } else {
            avatar.innerHTML = '<i class="fas fa-info-circle"></i>';
        }
        
        const content = document.createElement('div');
        content.className = 'message-content';
        
        if (type === 'error') {
            content.classList.add('error');
        } else if (type === 'success') {
            content.classList.add('success');
        }
        
        const textDiv = document.createElement('div');
        textDiv.innerHTML = this.formatMessageText(text);
        
        const timeDiv = document.createElement('div');
        timeDiv.className = 'message-time';
        timeDiv.textContent = new Date().toLocaleTimeString();
        
        content.appendChild(textDiv);
        content.appendChild(timeDiv);
        
        messageDiv.appendChild(avatar);
        messageDiv.appendChild(content);
        
        this.elements.chatMessages.appendChild(messageDiv);
        this.scrollToBottom();
        
        this.messageHistory.push({
            sender,
            text,
            type,
            timestamp: new Date()
        });
    }

    addSystemMessage(text, type = 'info') {
        this.addMessage('system', text, type);
    }

    formatMessageText(text) {
        text = text.replace(/(https?:\/\/[^\s]+)/g, '<a href="$1" target="_blank" rel="noopener">$1</a>');
        text = text.replace(/\n/g, '<br>');
        text = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        text = text.replace(/\*(.*?)\*/g, '<em>$1</em>');
        return text;
    }

    showTypingIndicator() {
        if (this.elements.typingIndicator) {
            this.elements.typingIndicator.style.display = 'flex';
            this.scrollToBottom();
        }
    }

    hideTypingIndicator() {
        if (this.elements.typingIndicator) {
            this.elements.typingIndicator.style.display = 'none';
        }
    }

    scrollToBottom() {
        if (this.elements.chatMessages) {
            this.elements.chatMessages.scrollTop = this.elements.chatMessages.scrollHeight;
        }
    }

    // ==================== QUICK MESSAGES ====================
    
    sendQuickMessage(message) {
        this.sendMessage(message);
    }

    // ==================== SESSION MANAGEMENT ====================
    
    async clearSession() {
        if (this.messageHistory.length > 0) {
            const confirmed = confirm('Start a new conversation? This will clear your current chat history.');
            if (!confirmed) return;
        }
        
        this.stopSpeaking();
        this.forceStopRecognition();
        
        this.sessionId = null;
        this.messageHistory = [];
        
        if (this.elements.chatMessages) {
            this.elements.chatMessages.innerHTML = `
                <div class="welcome-section">
                    <div class="welcome-avatar">
                        <i class="fas fa-robot"></i>
                    </div>
                    <h2>Welcome to Municipal Voice Assistant!</h2>
                    <p>I can help you with complaints, OTP verification, profile management, and municipal information through voice or text.</p>
                    
                    <div class="feature-grid">
                        <div class="feature-card" onclick="app.sendQuickMessage('What services do you offer?')">
                            <i class="fas fa-info-circle"></i>
                            <h3>Available Services</h3>
                            <p>Learn about all municipal services</p>
                        </div>
                        <div class="feature-card" onclick="app.sendQuickMessage('Show me complaint categories')">
                            <i class="fas fa-list-alt"></i>
                            <h3>Complaint Categories</h3>
                            <p>View all complaint types</p>
                        </div>
                        <div class="feature-card" onclick="app.sendQuickMessage('I want to register a complaint')">
                            <i class="fas fa-exclamation-triangle"></i>
                            <h3>Register Complaint</h3>
                            <p>Report municipal issues</p>
                        </div>
                        <div class="feature-card" onclick="app.sendQuickMessage('Help me login with my mobile number')">
                            <i class="fas fa-mobile-alt"></i>
                            <h3>Login with OTP</h3>
                            <p>Authenticate with mobile</p>
                        </div>
                    </div>
                </div>
            `;
        }
        
        this.updateSessionInfo('New Session');
        this.updateAuthStatus('Not Authenticated');
    }

    // ==================== SETTINGS ====================
    
    showSettings() {
        if (this.elements.settingsModal) {
            this.elements.settingsModal.style.display = 'flex';
            this.loadSettingsToUI();
        }
    }

    closeSettings() {
        if (this.elements.settingsModal) {
            this.elements.settingsModal.style.display = 'none';
        }
    }

    loadSettingsToUI() {
        const settingElements = [
            { id: 'voiceSpeed', value: this.settings.voiceSpeed },
            { id: 'voicePitch', value: this.settings.voicePitch },
            { id: 'voiceVolume', value: this.settings.voiceVolume },
            { id: 'autoSpeakToggle', checked: this.settings.autoSpeak },
            { id: 'speechLang', value: this.settings.speechLang }
        ];
        
        settingElements.forEach(({ id, value, checked }) => {
            const element = document.getElementById(id);
            if (element) {
                if (element.type === 'checkbox') {
                    element.checked = checked;
                } else {
                    element.value = value;
                }
            }
        });
    }

    saveSettings() {
        try {
            // Since we can't use localStorage in artifacts, we'll just keep settings in memory
            console.log('Settings updated:', this.settings);
        } catch (error) {
            console.error('Failed to save settings:', error);
        }
    }

    loadSettings() {
        // Since we can't use localStorage in artifacts, settings will use defaults
        console.log('Using default settings');
    }

    resetSettings() {
        this.settings = {
            autoSpeak: true,
            voiceSpeed: 0.9,
            voicePitch: 1.0,
            voiceVolume: 1.0,
            speechLang: 'en-IN'
        };
        
        this.loadSettingsToUI();
        this.updateTTSToggleUI();
        this.saveSettings();
    }

    // ==================== ERROR HANDLING ====================
    
    showError(message, duration = 5000) {
        console.error('Error:', message);
        
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-toast';
        errorDiv.innerHTML = `
            <i class="fas fa-exclamation-triangle"></i>
            <span>${message}</span>
            <button onclick="this.parentElement.remove()">
                <i class="fas fa-times"></i>
            </button>
        `;
        
        document.body.appendChild(errorDiv);
        
        setTimeout(() => {
            if (errorDiv.parentElement) {
                errorDiv.remove();
            }
        }, duration);
    }

    // ==================== CLEANUP ====================
    
    destroy() {
        this.stopSpeaking();
        this.forceStopRecognition();
        
        this.saveSettings();
    }
}

// ==================== INITIALIZATION ====================

let app;

document.addEventListener('DOMContentLoaded', () => {
    app = new MunicipalVoiceAssistant();
});

document.addEventListener('visibilitychange', () => {
    if (app && document.hidden && app.recognitionState === 'listening') {
        app.forceStopRecognition();
    }
});

window.addEventListener('beforeunload', () => {
    if (app) {
        app.destroy();
    }
});

window.addEventListener('error', (event) => {
    console.error('Global error:', event.error);
    if (app && app.showError) {
        app.showError('An unexpected error occurred. Please refresh if the problem persists.');
    }
});

window.addEventListener('unhandledrejection', (event) => {
    console.error('Unhandled promise rejection:', event.reason);
    event.preventDefault();
    if (app && app.showError) {
        app.showError('A network error occurred. Please check your connection.');
    }
});