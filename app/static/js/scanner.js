// Shaheen Public High School Loi Shalman - Attendance Scanner Engine

function getLocalDateString(d = new Date()) {
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

class AttendanceApp {
  constructor() {
    this.html5QrCode = null;
    this.audioCtx = null;
    this.wakeLock = null;
    this.isScanning = false;
    this.lastScannedCode = null;
    this.lastScanTime = 0;
    this.currentCamera = localStorage.getItem('sphs_camera') || 'environment'; // 'user' or 'environment'
    this.isOnline = navigator.onLine;
    // Sound mode: 'voice' (Spoken greeting), 'beep' (Classic electronic chime), 'mute' (Silent)
    this.soundMode = localStorage.getItem('sphs_sound_mode') || 'voice';
    this.db = null;
    this.pendingSyncInProgress = false;
    this.scannerKey = localStorage.getItem('sphs_scanner_key') || '';
    this.isLocked = true;

    this.init();
  }

  async init() {
    this.updateClock();
    setInterval(() => this.updateClock(), 1000);

    await this.initDB();
    this.setupAudio();
    this.setupWakeLock();
    this.setupNetworkListeners();
    this.setupUIListeners();
    this.setupTapToFocus();
    await this.updatePendingCountUI();

    // Check server reset token & fetch latest count before doing anything
    await this.updateTodayStats();
    setInterval(() => this.updateTodayStats(), 15000);

    // Auto sync on boot
    if (this.isOnline) {
      this.syncPendingScans();
    }

    // Periodic sync every 20 seconds
    setInterval(() => {
      if (navigator.onLine && !this.pendingSyncInProgress) {
        this.syncPendingScans();
      }
    }, 20000);

    // Verify key before starting scanner
    await this.checkScannerAccess();
  }

  // --- IndexedDB for 100% Offline Resilience ---
  initDB() {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open('SPHS_Offline_Attendance', 1);
      request.onupgradeneeded = (e) => {
        const db = e.target.result;
        if (!db.objectStoreNames.contains('pending_scans')) {
          const store = db.createObjectStore('pending_scans', { keyPath: 'sync_id' });
          store.createIndex('timestamp', 'timestamp', { unique: false });
        }
      };
      request.onsuccess = (e) => {
        this.db = e.target.result;
        console.log('[DB] IndexedDB initialized');
        resolve();
      };
      request.onerror = (e) => {
        console.error('[DB] IndexedDB error:', e);
        resolve(); // Continue anyway
      };
    });
  }

  saveScanToDB(scanRecord) {
    return new Promise((resolve) => {
      if (!this.db) return resolve(false);
      try {
        const tx = this.db.transaction('pending_scans', 'readwrite');
        const store = tx.objectStore('pending_scans');
        store.put(scanRecord);
        tx.oncomplete = () => resolve(true);
        tx.onerror = () => resolve(false);
      } catch (err) {
        console.error('[DB] Save error:', err);
        resolve(false);
      }
    });
  }

  getAllPendingFromDB() {
    return new Promise((resolve) => {
      if (!this.db) return resolve([]);
      try {
        const tx = this.db.transaction('pending_scans', 'readonly');
        const store = tx.objectStore('pending_scans');
        const req = store.getAll();
        req.onsuccess = () => resolve(req.result || []);
        req.onerror = () => resolve([]);
      } catch (err) {
        resolve([]);
      }
    });
  }

  removeSyncedFromDB(syncIds) {
    return new Promise((resolve) => {
      if (!this.db || !syncIds.length) return resolve();
      try {
        const tx = this.db.transaction('pending_scans', 'readwrite');
        const store = tx.objectStore('pending_scans');
        syncIds.forEach(id => store.delete(id));
        tx.oncomplete = () => resolve();
        tx.onerror = () => resolve();
      } catch (err) {
        resolve();
      }
    });
  }

  clearAllPendingDB() {
    return new Promise((resolve) => {
      if (!this.db) return resolve();
      try {
        const tx = this.db.transaction('pending_scans', 'readwrite');
        const store = tx.objectStore('pending_scans');
        store.clear();
        tx.oncomplete = () => resolve();
        tx.onerror = () => resolve();
      } catch (err) {
        resolve();
      }
    });
  }

  async updatePendingCountUI() {
    const list = await this.getAllPendingFromDB();
    const count = list.length;
    const badge = document.getElementById('sync-status-badge');
    const syncBtn = document.getElementById('sync-btn');

    if (!badge) return;

    if (!navigator.onLine) {
      badge.className = 'status-badge offline';
      badge.innerHTML = `<span class="dot"></span> Offline (${count} pending)`;
      syncBtn.disabled = true;
    } else if (count > 0) {
      badge.className = 'status-badge pending';
      badge.innerHTML = `<span class="dot"></span> Online (${count} to sync)`;
      syncBtn.disabled = false;
    } else {
      badge.className = 'status-badge online';
      badge.innerHTML = `<span class="dot"></span> Online (All Synced)`;
      syncBtn.disabled = true;
    }

    const pendingCountElem = document.getElementById('pending-count-num');
    if (pendingCountElem) pendingCountElem.textContent = count;
  }

  // --- Web Audio Synthesizer (Zero asset dependencies) ---
  setupAudio() {
    if ('speechSynthesis' in window) {
      this.cachedVoices = window.speechSynthesis.getVoices();
      window.speechSynthesis.onvoiceschanged = () => {
        this.cachedVoices = window.speechSynthesis.getVoices();
      };
    }

    const initCtx = () => {
      if (!this.audioCtx) {
        const AudioContext = window.AudioContext || window.webkitAudioContext;
        this.audioCtx = new AudioContext();
      }
      if (this.audioCtx && this.audioCtx.state === 'suspended') {
        this.audioCtx.resume();
      }
    };
    document.addEventListener('click', initCtx, { once: true });
    document.addEventListener('touchstart', initCtx, { once: true });
  }

  playBeep(type = 'success') {
    if (this.soundMode === 'mute') return;
    try {
      if (!this.audioCtx) {
        const AudioContext = window.AudioContext || window.webkitAudioContext;
        this.audioCtx = new AudioContext();
      }
      if (this.audioCtx.state === 'suspended') {
        this.audioCtx.resume();
      }

      const now = this.audioCtx.currentTime;
      const osc = this.audioCtx.createOscillator();
      const gain = this.audioCtx.createGain();
      osc.connect(gain);
      gain.connect(this.audioCtx.destination);

      if (type === 'success') {
        // High cheerful double-beep (880Hz -> 1320Hz)
        osc.type = 'sine';
        osc.frequency.setValueAtTime(880, now);
        osc.frequency.setValueAtTime(1320, now + 0.08);
        gain.gain.setValueAtTime(0.3, now);
        gain.gain.exponentialRampToValueAtTime(0.01, now + 0.22);
        osc.start(now);
        osc.stop(now + 0.22);
      } else if (type === 'late') {
        // Amber chime
        osc.type = 'triangle';
        osc.frequency.setValueAtTime(659.25, now);
        osc.frequency.setValueAtTime(880, now + 0.12);
        gain.gain.setValueAtTime(0.3, now);
        gain.gain.exponentialRampToValueAtTime(0.01, now + 0.3);
        osc.start(now);
        osc.stop(now + 0.3);
      } else if (type === 'already_marked') {
        // Soft double blip
        osc.type = 'sine';
        osc.frequency.setValueAtTime(440, now);
        osc.frequency.setValueAtTime(440, now + 0.12);
        gain.gain.setValueAtTime(0.2, now);
        gain.gain.exponentialRampToValueAtTime(0.01, now + 0.25);
        osc.start(now);
        osc.stop(now + 0.25);
      } else {
        // Low error buzz
        osc.type = 'sawtooth';
        osc.frequency.setValueAtTime(220, now);
        gain.gain.setValueAtTime(0.3, now);
        gain.gain.exponentialRampToValueAtTime(0.01, now + 0.3);
        osc.start(now);
        osc.stop(now + 0.3);
      }
    } catch (e) {
      console.warn('Audio play error:', e);
    }
  }

  // --- Voice Announcements (Native Urdu / Subcontinental Phonetics) ---
  getUrduVoice() {
    if (!('speechSynthesis' in window)) return null;
    const voices = (this.cachedVoices && this.cachedVoices.length > 0)
      ? this.cachedVoices
      : window.speechSynthesis.getVoices();
    if (!voices || voices.length === 0) return null;

    // 1. Look for native Urdu (Pakistan / India)
    let v = voices.find(v => v.lang && (v.lang.toLowerCase() === 'ur-pk' || v.lang.toLowerCase() === 'ur_pk' || v.lang.toLowerCase().startsWith('ur')));
    if (v) return v;

    // 2. Look for subcontinental phonetic voices that pronounce regional names accurately
    v = voices.find(v => v.lang && (v.lang.toLowerCase().includes('ur') || v.lang.toLowerCase().includes('hi-in') || v.lang.toLowerCase().includes('pa-pk') || v.lang.toLowerCase().includes('en-in')));
    return v || null;
  }

  speakAnnouncement(fullName, status) {
    if (this.soundMode !== 'voice' || !('speechSynthesis' in window)) return;

    // Extract preferred call name (e.g. "Muhammad Sohail" -> "Sohail")
    let callName = (fullName || 'طالب علم').trim();
    const parts = callName.split(/\s+/);
    if (parts.length > 1) {
      if (['muhammad', 'mohammad', 'm.', 'md'].includes(parts[0].toLowerCase()) && parts[1]) {
        callName = parts[1];
      } else {
        callName = parts[0];
      }
    }

    let phrase = `${callName}، حاضر`;
    if (status === 'already') {
      phrase = `${callName}، پہلے سے حاضر ہے`;
    } else if (status === 'late') {
      phrase = `${callName}، لیٹ حاضری`;
    } else if (status === 'leave') {
      phrase = `${callName}، رخصت پر ہے`;
    }

    this.speakVoice(phrase);
  }

  speakVoice(text) {
    if (!('speechSynthesis' in window)) return;
    try {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      const v = this.getUrduVoice();
      if (v) {
        utterance.voice = v;
        utterance.lang = v.lang || 'ur-PK';
      } else {
        utterance.lang = 'ur-PK';
      }
      utterance.rate = 1.0;
      utterance.pitch = 1.0;
      utterance.volume = 1.0;
      window.speechSynthesis.speak(utterance);
    } catch (e) {
      console.warn('Speech synthesis error:', e);
    }
  }

  // --- Screen WakeLock API ---
  async setupWakeLock() {
    if ('wakeLock' in navigator) {
      try {
        this.wakeLock = await navigator.wakeLock.request('screen');
        console.log('[WakeLock] Screen kept awake');
        document.addEventListener('visibilitychange', async () => {
          if (this.wakeLock !== null && document.visibilityState === 'visible') {
            this.wakeLock = await navigator.wakeLock.request('screen');
          }
        });
      } catch (err) {
        console.log('[WakeLock] Could not acquire:', err);
      }
    }
  }

  // --- Network Listeners ---
  setupNetworkListeners() {
    window.addEventListener('online', () => {
      this.isOnline = true;
      this.showToast('Internet restored! Syncing...', 'info');
      this.syncPendingScans();
      this.updatePendingCountUI();
    });

    window.addEventListener('offline', () => {
      this.isOnline = false;
      this.showToast('Working Offline. Scans are saved locally.', 'warning');
      this.updatePendingCountUI();
    });
  }

  // --- UI and Clock ---
  updateClock() {
    const clockElem = document.getElementById('live-clock');
    if (clockElem) {
      const now = new Date();
      clockElem.textContent = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    }
  }

  setupUIListeners() {
    // Camera switch button
    const switchCamBtn = document.getElementById('switch-cam-btn');
    if (switchCamBtn) {
      switchCamBtn.addEventListener('click', () => {
        this.currentCamera = this.currentCamera === 'environment' ? 'user' : 'environment';
        localStorage.setItem('sphs_camera', this.currentCamera);
        this.switchCamera();
      });
    }

    // Mirror toggle button
    const mirrorBtn = document.getElementById('mirror-toggle-btn');
    const readerEl = document.getElementById('qr-reader');
    // Load saved mirror preference or default to false (natural view)
    const savedMirror = localStorage.getItem('sphs_scanner_mirrored') === 'true';
    if (savedMirror && readerEl) {
      readerEl.classList.add('mirrored');
    }
    if (mirrorBtn && readerEl) {
      mirrorBtn.addEventListener('click', () => {
        const isMirrored = readerEl.classList.toggle('mirrored');
        localStorage.setItem('sphs_scanner_mirrored', isMirrored ? 'true' : 'false');
        this.showToast(isMirrored ? 'Camera Mirrored (Selfie mode)' : 'Camera Normal (Right is Right)', 'info');
      });
    }

    // 3-Way Sound mode toggle button (🗣️ Urdu Voice -> 🔔 Beep Chime -> 🔇 Mute)
    const soundBtn = document.getElementById('voice-toggle-btn');
    if (soundBtn) {
      const updateSoundUI = () => {
        if (this.soundMode === 'voice') {
          soundBtn.textContent = '🗣️';
          soundBtn.title = 'آواز: اردو آواز (Urdu Voice) — کلک کر کے صرف بیپ کریں';
        } else if (this.soundMode === 'beep') {
          soundBtn.textContent = '🔔';
          soundBtn.title = 'آواز: صرف بیپ چائم (Beep Only) — کلک کر کے خاموش کریں';
        } else {
          soundBtn.textContent = '🔇';
          soundBtn.title = 'آواز: خاموش (Muted) — کلک کر کے اردو آواز چلائیں';
        }
      };

      updateSoundUI();

      soundBtn.addEventListener('click', () => {
        if (this.soundMode === 'voice') {
          this.soundMode = 'beep';
          this.showToast('🔔 آواز: صرف بیپ چائم (Beep Only)', 'info');
          this.playBeep('success');
        } else if (this.soundMode === 'beep') {
          this.soundMode = 'mute';
          this.showToast('🔇 آواز: خاموش (Muted)', 'info');
        } else {
          this.soundMode = 'voice';
          this.showToast('🗣️ آواز: اردو آواز (Urdu Voice)', 'info');
          this.speakVoice('خوش آمدید');
        }
        localStorage.setItem('sphs_sound_mode', this.soundMode);
        updateSoundUI();
      });
    }

    // Manual Sync button
    const syncBtn = document.getElementById('sync-btn');
    if (syncBtn) {
      syncBtn.addEventListener('click', () => {
        this.syncPendingScans(true);
      });
    }

    // Manual student search / input modal
    const manualBtn = document.getElementById('manual-entry-btn');
    const manualModal = document.getElementById('manual-modal');
    const closeManualBtn = document.getElementById('close-manual-btn');
    const submitManualBtn = document.getElementById('submit-manual-btn');

    if (manualBtn && manualModal) {
      manualBtn.addEventListener('click', () => {
        manualModal.classList.remove('hidden');
        document.getElementById('manual-roll-input').focus();
      });
      closeManualBtn.addEventListener('click', () => manualModal.classList.add('hidden'));
      submitManualBtn.addEventListener('click', () => this.handleManualSubmit());
      document.getElementById('manual-roll-input').addEventListener('keydown', (e) => {
        if (e.key === 'Enter') this.handleManualSubmit();
      });
    }

    // Offline Scanned Attendance Drawer
    const drawerBtn = document.getElementById('view-offline-list-btn');
    const drawerModal = document.getElementById('offline-drawer-modal');
    const closeDrawerBtn = document.getElementById('close-drawer-btn');
    const drawerSearch = document.getElementById('drawer-search-input');
    const drawerCsvBtn = document.getElementById('drawer-export-csv-btn');

    if (drawerBtn && drawerModal) {
      drawerBtn.addEventListener('click', () => {
        this.renderOfflineDrawer();
        drawerModal.classList.remove('hidden');
      });
      closeDrawerBtn.addEventListener('click', () => drawerModal.classList.add('hidden'));
      if (drawerSearch) {
        drawerSearch.addEventListener('input', () => this.renderOfflineDrawer(drawerSearch.value));
      }
      if (drawerCsvBtn) {
        drawerCsvBtn.addEventListener('click', () => this.exportOfflineCsv());
      }
    }
  }

  // --- Offline Attendance History on Phone ---
  getTodayKey() {
    return 'sphs_offline_log_' + getLocalDateString();
  }

  getOfflineHistory() {
    try {
      return JSON.parse(localStorage.getItem(this.getTodayKey()) || '[]');
    } catch (e) {
      return [];
    }
  }

  recordToOfflineHistory(item) {
    const history = this.getOfflineHistory();
    // Check if code already recorded today
    const exists = history.some(h => h.code === item.code);
    if (!exists) {
      history.unshift(item); // latest first
      localStorage.setItem(this.getTodayKey(), JSON.stringify(history));
    }
  }

  renderOfflineDrawer(filterText = '') {
    const list = this.getOfflineHistory();
    const tbody = document.getElementById('drawer-table-body');
    const countEl = document.getElementById('drawer-total-count');

    if (countEl) countEl.textContent = list.length;
    if (!tbody) return;

    const term = (filterText || '').toLowerCase().trim();
    const filtered = list.filter(item => {
      if (!term) return true;
      return (item.name || '').toLowerCase().includes(term) ||
             (item.code || '').toLowerCase().includes(term) ||
             (item.roll || '').toLowerCase().includes(term) ||
             (item.class || '').toLowerCase().includes(term);
    });

    if (!filtered.length) {
      tbody.innerHTML = '<tr><td colspan="3" style="text-align: center; padding: 20px; color: #64748b;">No matching scans found.</td></tr>';
      return;
    }

    tbody.innerHTML = filtered.map(item => `
      <tr style="border-bottom: 1px solid #1e293b;">
        <td style="padding: 7px 4px; color: #38bdf8; font-family: monospace;">${item.time}</td>
        <td style="padding: 7px 4px;">
          <strong style="color: #fff;">${item.name || item.code}</strong>
          <div style="font-size: 10px; color: #94a3b8;">${item.class ? 'Class: ' + item.class + ' | Roll: ' + item.roll : item.code}</div>
        </td>
        <td style="padding: 7px 4px;">
          <span style="font-size: 10px; padding: 2px 6px; border-radius: 4px; font-weight: 700; ${item.status === 'Late' ? 'background: #78350f; color: #fde68a;' : 'background: #065f46; color: #a7f3d0;'}">
            ${item.status || 'Present'}
          </span>
        </td>
      </tr>
    `).join('');
  }

  exportOfflineCsv() {
    const list = this.getOfflineHistory();
    if (!list.length) {
      this.showToast('No scans recorded yet to export', 'warning');
      return;
    }

    const today = getLocalDateString();
    let csv = "Date,Time,Student Code,Student Name,Class,Roll No,Status\n";

    list.forEach(item => {
      csv += `"${today}","${item.time}","${item.code}","${item.name || ''}","${item.class || ''}","${item.roll || ''}","${item.status || 'Present'}"\n`;
    });

    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.setAttribute("href", url);
    link.setAttribute("download", `SPHS_Attendance_Offline_${today}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    this.showToast('CSV downloaded to your phone!', 'success');
  }

  async clearLocalTodayHistory() {
    try {
      localStorage.removeItem(this.getTodayKey());
      await this.clearAllPendingDB();
      await this.updatePendingCountUI();
      const countEl = document.getElementById('today-total-scanned');
      if (countEl) countEl.textContent = '0';
      this.renderOfflineDrawer();
      this.showToast('Local scan cache cleared', 'info');
    } catch (e) {
      console.warn('Error clearing local cache:', e);
    }
  }

  // --- Security Access Control (Method 2: 52186) ---
  async checkScannerAccess() {
    const urlParams = new URLSearchParams(window.location.search);
    const urlKey = urlParams.get('key');
    const candidateKey = (urlKey || localStorage.getItem('sphs_scanner_key') || '').trim();

    if (candidateKey) {
      const isValid = await this.verifyKeyWithServer(candidateKey);
      if (isValid) {
        localStorage.setItem('sphs_scanner_key', candidateKey);
        this.scannerKey = candidateKey;
        this.isLocked = false;
        this.hideLockOverlay();
        if (urlKey) {
          try {
            history.replaceState({}, document.title, window.location.pathname);
          } catch (e) {}
        }
        await this.startScanner();
        return;
      }
    }

    // Lock if no valid key
    this.isLocked = true;
    this.showLockOverlay();
  }

  async verifyKeyWithServer(code) {
    if (!navigator.onLine) {
      const saved = localStorage.getItem('sphs_scanner_key');
      return Boolean(saved && saved === code);
    }
    try {
      const res = await fetch('/api/scanner/verify-key', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code: code })
      });
      if (res.ok) {
        const data = await res.json();
        return Boolean(data.success);
      }
      return false;
    } catch (err) {
      console.warn('Network error during verify-key:', err);
      if (!navigator.onLine) {
        const saved = localStorage.getItem('sphs_scanner_key');
        return Boolean(saved && saved === code);
      }
      return false;
    }
  }

  showLockOverlay() {
    const overlay = document.getElementById('scanner-lock-overlay');
    if (overlay) {
      overlay.classList.remove('hidden');
      overlay.style.setProperty('display', 'flex', 'important');
    }
    const input = document.getElementById('lock-passcode-input');
    const submitBtn = document.getElementById('lock-submit-btn');
    const errorEl = document.getElementById('lock-error-msg');
    if (errorEl) errorEl.style.display = 'none';
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.textContent = 'Unlock Scanner';
    }
    if (input) {
      input.value = '';
      setTimeout(() => input.focus(), 300);
      input.oninput = (e) => {
        if (e.target.value.length === 5) {
          window.submitScannerPasscode();
        }
      };
    }
  }

  hideLockOverlay() {
    const overlay = document.getElementById('scanner-lock-overlay');
    if (overlay) {
      overlay.classList.add('hidden');
      overlay.style.setProperty('display', 'none', 'important');
    }
  }

  async unlockWithCode(code) {
    if (this.isVerifyingCode) return;
    this.isVerifyingCode = true;

    const errorEl = document.getElementById('lock-error-msg');
    const submitBtn = document.getElementById('lock-submit-btn');
    if (errorEl) errorEl.style.display = 'none';

    const cleanCode = (code || '').trim();
    if (!cleanCode) {
      if (errorEl) {
        errorEl.textContent = 'Please enter the access code';
        errorEl.style.display = 'block';
      }
      this.isVerifyingCode = false;
      return;
    }

    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.textContent = 'Verifying...';
    }

    try {
      const isValid = await this.verifyKeyWithServer(cleanCode);
      if (isValid) {
        localStorage.setItem('sphs_scanner_key', cleanCode);
        this.scannerKey = cleanCode;
        this.isLocked = false;
        this.hideLockOverlay();
        this.showToast('✅ Scanner unlocked successfully!', 'success');
        try {
          await this.startScanner();
        } catch (camErr) {
          console.error('Camera init error after unlock:', camErr);
        }
      } else {
        if (errorEl) {
          errorEl.textContent = '❌ Invalid Access Code. Try again.';
          errorEl.style.display = 'block';
        }
        const input = document.getElementById('lock-passcode-input');
        if (input) {
          input.value = '';
          setTimeout(() => input.focus(), 100);
        }
      }
    } catch (err) {
      if (errorEl) {
        errorEl.textContent = 'Connection error. Please try again.';
        errorEl.style.display = 'block';
      }
    } finally {
      this.isVerifyingCode = false;
      if (submitBtn && this.isLocked) {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Unlock Scanner';
      }
    }
  }

  // --- Camera & Scanner ---
  async startScanner() {
    try {
      if (this.html5QrCode) {
        try {
          if (this.html5QrCode.isScanning) {
            await this.html5QrCode.stop();
          }
          this.html5QrCode.clear();
        } catch (e) {}
      }

      this.html5QrCode = new Html5Qrcode('qr-reader');
      const config = {
        fps: 20,
        qrbox: (viewfinderWidth, viewfinderHeight) => {
          const edge = Math.floor(Math.min(viewfinderWidth, viewfinderHeight) * 0.72);
          const safeW = Math.max(160, Math.min(edge, viewfinderWidth - 20));
          const safeH = Math.max(160, Math.min(edge, viewfinderHeight - 20));
          return { width: safeW, height: safeH };
        },
        aspectRatio: 1.0,
        experimentalFeatures: {
          useBarCodeDetectorIfSupported: true
        }
      };

      // Clean mobile constraints (no 'min' width/height which crashes mobile cameras in portrait)
      const cameraConstraints = {
        facingMode: this.currentCamera || 'environment'
      };

      try {
        await this.html5QrCode.start(
          cameraConstraints,
          config,
          (decodedText) => this.onScanSuccess(decodedText),
          () => {} // Ignore scan frame decode misses
        );
      } catch (camErr) {
        console.warn('[Scanner] facingMode start failed, trying camera list enumeration fallback:', camErr);
        // Fallback: enumerate available cameras and start by device ID
        const devices = await Html5Qrcode.getCameras().catch(() => []);
        if (devices && devices.length > 0) {
          const targetCam = devices.find(d => {
            const label = (d.label || '').toLowerCase();
            return this.currentCamera === 'user' 
              ? (label.includes('front') || label.includes('user'))
              : (label.includes('back') || label.includes('rear') || label.includes('environment'));
          }) || devices[0];

          await this.html5QrCode.start(
            targetCam.id,
            config,
            (decodedText) => this.onScanSuccess(decodedText),
            () => {}
          );
        } else {
          throw camErr;
        }
      }

      this.isScanning = true;
      const statusEl = document.getElementById('camera-status');
      if (statusEl) statusEl.textContent = 'Camera active • Point QR at screen';
      
      // Apply hardware continuous autofocus after stream settles
      setTimeout(() => this.applyHardwareCameraFocus(), 800);
    } catch (err) {
      console.error('Failed to start camera:', err);
      const statusEl = document.getElementById('camera-status');
      if (statusEl) statusEl.textContent = 'Camera access denied or error. Check browser permissions.';
      this.showToast('Please allow camera access in browser', 'error');
    }
  }

  async applyHardwareCameraFocus() {
    try {
      const videoEl = document.querySelector('#qr-reader video');
      if (!videoEl || !videoEl.srcObject) return;
      const track = videoEl.srcObject.getVideoTracks()[0];
      if (!track) return;

      const capabilities = track.getCapabilities ? track.getCapabilities() : {};
      const advanced = [];

      // Continuous hardware autofocus
      if (capabilities.focusMode && capabilities.focusMode.includes('continuous')) {
        advanced.push({ focusMode: 'continuous' });
      }

      // Continuous exposure
      if (capabilities.exposureMode && capabilities.exposureMode.includes('continuous')) {
        advanced.push({ exposureMode: 'continuous' });
      }

      // Continuous white balance
      if (capabilities.whiteBalanceMode && capabilities.whiteBalanceMode.includes('continuous')) {
        advanced.push({ whiteBalanceMode: 'continuous' });
      }

      if (advanced.length > 0 && track.applyConstraints) {
        await track.applyConstraints({ advanced });
        console.log('[Camera] Hardware autofocus applied successfully');
      }
    } catch (e) {
      console.warn('[Camera] Hardware autofocus setup error:', e);
    }
  }

  setupTapToFocus() {
    const readerEl = document.getElementById('qr-reader');
    if (!readerEl) return;

    readerEl.addEventListener('click', async (e) => {
      // Don't trigger if click is on buttons, modals, or result popup
      if (e.target.closest('button') || e.target.closest('#result-card') || e.target.closest('.modal-backdrop')) return;
      
      this.flashFocusIndicator(e.clientX, e.clientY);

      try {
        const videoEl = document.querySelector('#qr-reader video');
        if (!videoEl || !videoEl.srcObject) return;
        const track = videoEl.srcObject.getVideoTracks()[0];
        if (!track || !track.applyConstraints) return;

        const capabilities = track.getCapabilities ? track.getCapabilities() : {};
        if (capabilities.focusMode) {
          // Pulse focus from auto back to continuous to re-lock focus on the subject
          await track.applyConstraints({ advanced: [{ focusMode: 'auto' }] }).catch(() => {});
          setTimeout(() => {
            track.applyConstraints({ advanced: [{ focusMode: 'continuous' }] }).catch(() => {});
          }, 350);
        }
      } catch (err) {
        console.log('[Focus] Tap re-focus error:', err);
      }
    });
  }

  flashFocusIndicator(x, y) {
    const ring = document.createElement('div');
    ring.className = 'focus-ring';
    ring.style.left = `${x}px`;
    ring.style.top = `${y}px`;
    document.body.appendChild(ring);
    requestAnimationFrame(() => {
      ring.classList.add('active');
    });
    setTimeout(() => ring.remove(), 400);
  }

  async switchCamera() {
    try {
      if (this.html5QrCode) {
        try {
          if (this.html5QrCode.isScanning) {
            await this.html5QrCode.stop();
          }
          this.html5QrCode.clear();
        } catch (e) {}
      }
      await this.startScanner();
      this.showToast(`Switched to ${this.currentCamera === 'environment' ? 'Back' : 'Front'} Camera`, 'info');
    } catch (err) {
      console.error('Camera switch error:', err);
    }
  }

  // --- Scan Handlers ---
  async onScanSuccess(decodedText) {
    const now = Date.now();
    // 2.5 second cooldown per student code to prevent duplicate trigger while holding card
    if (decodedText === this.lastScannedCode && (now - this.lastScanTime) < 2500) {
      return;
    }

    this.lastScannedCode = decodedText;
    this.lastScanTime = now;

    // Trigger visual scan effect
    this.flashScanTarget();

    // Process scan (Online or Offline)
    await this.processAttendanceScan(decodedText);
  }

  flashScanTarget() {
    const box = document.querySelector('.scanner-laser');
    if (box) {
      box.classList.add('pulse');
      setTimeout(() => box.classList.remove('pulse'), 500);
    }
  }

  generateUUID() {
    return 'sync-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);
  }

  async processAttendanceScan(qrPayload) {
    const timestamp = new Date().toISOString();
    const syncId = this.generateUUID();

    if (navigator.onLine) {
      try {
        const response = await fetch('/api/scan', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-Scanner-Key': this.scannerKey || localStorage.getItem('sphs_scanner_key') || ''
          },
          body: JSON.stringify({
            qr_payload: qrPayload,
            timestamp: timestamp,
            sync_id: syncId
          })
        });

        if (response.ok) {
          const data = await response.json();
          this.displayScanResult(data);
          this.updateTodayStats();
          return;
        }
      } catch (err) {
        console.warn('Network request failed, falling back to offline IndexedDB storage:', err);
      }
    }

    // --- Offline Fallback Flow ---
    const offlineRecord = {
      sync_id: syncId,
      qr_payload: qrPayload,
      timestamp: timestamp,
      created_at: Date.now()
    };

    await this.saveScanToDB(offlineRecord);
    await this.updatePendingCountUI();

    // Show simulated result on phone
    const mockData = {
      success: true,
      offline: true,
      status: 'Present',
      message: 'Saved Offline • Will sync when online',
      scan_time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
      student: {
        full_name: 'Student Scanned',
        class_name: 'Code Recorded',
        roll_no: qrPayload.split(':')[1] || qrPayload.substr(0, 10),
        student_code: qrPayload
      }
    };
    this.displayScanResult(mockData);
  }

  displayScanResult(data) {
    const card = document.getElementById('result-card');
    const bannerEl = document.getElementById('res-status-banner');
    const statusTextEl = document.getElementById('res-status-text');
    const timeEl = document.getElementById('res-scan-time');
    const photoEl = document.getElementById('res-student-photo');
    const avatarEl = document.getElementById('res-student-avatar');
    const nameEl = document.getElementById('res-student-name');
    const fatherEl = document.getElementById('res-father-name');
    const classPill = document.getElementById('res-class-pill');
    const rollPill = document.getElementById('res-roll-pill');
    const codePill = document.getElementById('res-code-pill');
    const msgEl = document.getElementById('res-message');
    const undoBtn = document.getElementById('res-undo-btn');
    const screenFlash = document.getElementById('screen-flash');

    if (!data.success) {
      this.playBeep('error');
      if (screenFlash) this.triggerScreenFlash('red');
      this.showToast(data.message || 'Student not found', 'error');
      return;
    }

    const student = data.student || {};
    const status = data.status || 'Present';
    const isAlready = data.already_marked;
    const scanDate = data.date || getLocalDateString();

    // Populate student details
    if (nameEl) nameEl.textContent = student.full_name || 'Student';
    if (fatherEl) {
      fatherEl.textContent = student.father_name ? `S/D of ${student.father_name}` : 'Shaheen Public High School';
    }
    if (classPill) classPill.textContent = `Class: ${student.class_name || '-'}`;
    if (rollPill) rollPill.textContent = `Roll: ${student.roll_no || '-'}`;
    if (codePill) codePill.textContent = student.student_code || student.roll_no || 'SPHS';
    if (timeEl) {
      timeEl.textContent = data.scan_time || new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    }

    // Populate student photo or avatar initial
    if (photoEl && avatarEl) {
      if (student.photo_url) {
        photoEl.src = student.photo_url;
        photoEl.style.display = 'block';
        avatarEl.style.display = 'none';
        photoEl.onerror = () => {
          photoEl.style.display = 'none';
          avatarEl.style.display = 'flex';
          avatarEl.textContent = (student.full_name || 'S').charAt(0).toUpperCase();
        };
      } else {
        photoEl.style.display = 'none';
        avatarEl.style.display = 'flex';
        avatarEl.textContent = (student.full_name || 'S').charAt(0).toUpperCase();
      }
    }

    // Reset base card class
    if (card) card.className = 'result-card';

    // Audio beep
    if (isAlready) {
      this.playBeep('already_marked');
      if (bannerEl) bannerEl.className = 'status-banner already';
      if (statusTextEl) statusTextEl.textContent = 'ℹ️ ALREADY MARKED';
      if (card) card.classList.add('status-already');
      if (msgEl) msgEl.textContent = data.message || 'Already marked today';
      this.triggerScreenFlash('amber');
      this.speakAnnouncement(student.full_name, 'already');
    } else if (status === 'Late') {
      this.playBeep('late');
      if (bannerEl) bannerEl.className = 'status-banner late';
      if (statusTextEl) statusTextEl.textContent = '⚠️ LATE';
      if (card) card.classList.add('status-late');
      if (msgEl) msgEl.textContent = data.offline ? 'Recorded offline as Late' : 'Arrival after late threshold';
      this.triggerScreenFlash('amber');
      this.speakAnnouncement(student.full_name, 'late');
    } else if (status === 'Leave') {
      this.playBeep('already_marked');
      if (bannerEl) bannerEl.className = 'status-banner leave';
      if (statusTextEl) statusTextEl.textContent = '📅 ON LEAVE';
      if (card) card.classList.add('status-leave');
      if (msgEl) msgEl.textContent = 'Student has approved leave';
      this.triggerScreenFlash('blue');
      this.speakAnnouncement(student.full_name, 'leave');
    } else {
      this.playBeep('success');
      if (bannerEl) bannerEl.className = 'status-banner present';
      if (statusTextEl) statusTextEl.textContent = '✅ PRESENT';
      if (card) card.classList.add('status-present');
      if (msgEl) msgEl.textContent = data.offline ? 'Saved locally (Offline Mode)' : 'Attendance marked successfully';
      this.triggerScreenFlash('green');
      this.speakAnnouncement(student.full_name, 'present');
    }

    // Configure Undo Button
    if (undoBtn) {
      undoBtn.onclick = (e) => {
        e.stopPropagation();
        this.undoScan(student.id, scanDate, student.full_name);
      };
    }

    // Record to phone's local offline history
    if (data.success && !isAlready) {
      this.recordToOfflineHistory({
        id: student.id,
        code: student.student_code || student.roll_no || 'Student',
        name: student.full_name || 'Student',
        class: student.class_name || '',
        roll: student.roll_no || '',
        time: data.scan_time || new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
        status: status
      });
      const todayCount = this.getOfflineHistory().length;
      const countEl = document.getElementById('today-total-scanned');
      if (countEl) countEl.textContent = todayCount;
    }

    // Show pop-up card
    if (card) {
      card.classList.remove('hidden');
      requestAnimationFrame(() => {
        card.classList.add('visible');
      });

      // Tap anywhere on card to dismiss immediately
      card.onclick = () => {
        if (this.hideCardTimeout) clearTimeout(this.hideCardTimeout);
        card.classList.remove('visible');
        setTimeout(() => card.classList.add('hidden'), 250);
      };
    }

    // Auto-dismiss after 2.8 seconds
    if (this.hideCardTimeout) clearTimeout(this.hideCardTimeout);
    this.hideCardTimeout = setTimeout(() => {
      if (card) {
        card.classList.remove('visible');
        setTimeout(() => card.classList.add('hidden'), 250);
      }
    }, 2800);
  }

  async undoScan(studentId, dateStr, studentName) {
    if (!studentId) return;
    try {
      const res = await fetch('/api/scan/undo', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Scanner-Key': this.scannerKey || localStorage.getItem('sphs_scanner_key') || ''
        },
        body: JSON.stringify({
          student_id: studentId,
          date: dateStr || getLocalDateString()
        })
      });
      const resData = await res.json();
      if (resData.success) {
        this.showToast(`Removed attendance for ${studentName || 'student'}`, 'warning');

        // Hide pop-up immediately
        const card = document.getElementById('result-card');
        if (card) {
          if (this.hideCardTimeout) clearTimeout(this.hideCardTimeout);
          card.classList.remove('visible');
          setTimeout(() => card.classList.add('hidden'), 200);
        }

        // Remove from local phone history
        const history = this.getOfflineHistory();
        const filtered = history.filter(h => h.id !== studentId && h.name !== studentName);
        localStorage.setItem(this.getTodayKey(), JSON.stringify(filtered));
        const countEl = document.getElementById('today-total-scanned');
        if (countEl) countEl.textContent = filtered.length;

        // Reset cooldown so student can be re-scanned if needed
        this.lastScannedCode = null;
        this.lastScanTime = 0;

        this.updateTodayStats();
      } else {
        this.showToast(resData.message || 'Could not remove scan', 'error');
      }
    } catch (e) {
      console.error('Undo scan error:', e);
      this.showToast('Could not reach server to undo scan', 'error');
    }
  }

  triggerScreenFlash(color) {
    const flash = document.getElementById('screen-flash');
    if (!flash) return;
    flash.className = `screen-flash flash-${color}`;
    setTimeout(() => {
      flash.className = 'screen-flash';
    }, 450);
  }

  async handleManualSubmit() {
    const input = document.getElementById('manual-roll-input');
    const classSelect = document.getElementById('manual-class-select');
    const val = input.value.trim();
    const cls = classSelect ? classSelect.value : '';

    if (!val) {
      this.showToast('Please enter Roll No or Student Code', 'warning');
      return;
    }

    document.getElementById('manual-modal').classList.add('hidden');
    input.value = '';

    // Search by code or roll
    const queryPayload = cls ? `${cls}:${val}` : val;
    await this.processAttendanceScan(queryPayload);
  }

  // --- Background Sync with VPS ---
  async syncPendingScans(isManual = false) {
    if (this.pendingSyncInProgress || !navigator.onLine) return;

    const pendingList = await this.getAllPendingFromDB();
    if (!pendingList.length) {
      if (isManual) this.showToast('All scans are already synced!', 'success');
      return;
    }

    this.pendingSyncInProgress = true;
    const syncBtn = document.getElementById('sync-btn');
    if (syncBtn) syncBtn.classList.add('spinning');

    try {
      const response = await fetch('/api/sync', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Scanner-Key': this.scannerKey || localStorage.getItem('sphs_scanner_key') || ''
        },
        body: JSON.stringify({ scans: pendingList })
      });

      if (response.ok) {
        const result = await response.json();
        const syncedIds = pendingList.map(item => item.sync_id);
        await this.removeSyncedFromDB(syncedIds);
        await this.updatePendingCountUI();
        this.showToast(`Synced ${result.synced_count || pendingList.length} scans to VPS!`, 'success');
        this.updateTodayStats();
      } else {
        this.showToast('Sync server returned error. Will retry.', 'warning');
      }
    } catch (err) {
      console.warn('Sync failed:', err);
      if (isManual) this.showToast('Could not reach VPS. Scans remain safely in phone.', 'warning');
    } finally {
      this.pendingSyncInProgress = false;
      if (syncBtn) syncBtn.classList.remove('spinning');
      this.updatePendingCountUI();
    }
  }

  async updateTodayStats() {
    try {
      const res = await fetch('/api/scanner-info');
      if (res.ok) {
        const info = await res.json();
        const serverResetToken = String(info.reset_token || '0');
        const clientResetToken = localStorage.getItem('sphs_reset_token') || '0';

        // If server was reset and client hasn't cleared local queue yet
        if (serverResetToken !== '0' && serverResetToken !== clientResetToken) {
          localStorage.setItem('sphs_reset_token', serverResetToken);
          await this.clearLocalTodayHistory();
        }

        const countEl = document.getElementById('today-total-scanned');
        if (countEl) countEl.textContent = info.today_scanned_count ?? '0';
      }
    } catch (e) {}
  }

  showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    if (!toast) return;
    toast.textContent = message;
    toast.className = `toast toast-${type} show`;
    setTimeout(() => {
      toast.className = 'toast';
    }, 3000);
  }
}

// Boot application
window.addEventListener('DOMContentLoaded', () => {
  window.app = new AttendanceApp();
});

window.submitScannerPasscode = function() {
  const input = document.getElementById('lock-passcode-input');
  if (input && window.app) {
    window.app.unlockWithCode(input.value);
  }
};
