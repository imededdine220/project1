/* pr.js — Frontend logic connected to the real FastAPI backend */

const API = "http://localhost:8000";   // ← change to your server URL in production

const dropZone    = document.getElementById('dropZone');
const fileInput   = document.getElementById('fileInput');
const filePreview = document.getElementById('filePreview');
const fileName    = document.getElementById('fileName');
const fileSize    = document.getElementById('fileSize');
const removeBtn   = document.getElementById('removeBtn');
const convertWrap = document.getElementById('convertBtnWrap');
const convertBtn  = document.getElementById('convertBtn');
const progressSec = document.getElementById('progressSection');
const progressFill= document.getElementById('progressFill');
const progressPct = document.getElementById('progressPct');
const progressTxt = document.getElementById('progressText');
const doneSec     = document.getElementById('doneSection');
const doneFileName= document.getElementById('doneFileName');
const downloadBtn = document.getElementById('downloadBtn');

let selectedFile = null;
let pollInterval = null;

// ── Helpers ──────────────────────────────

function fmtSize(bytes) {
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
}

// Map API status → progress percentage & label
const STATUS_MAP = {
  queued:     { pct: 10,  txt: 'En file d\'attente…' },
  processing: { pct: 60,  txt: 'Conversion en cours…' },
  done:       { pct: 100, txt: 'Terminé !' },
};

// ── File handling ─────────────────────────

function showFile(file) {
  selectedFile = file;
  fileName.textContent = file.name;
  fileSize.textContent = fmtSize(file.size);
  filePreview.style.display = 'block';
  convertWrap.style.display = 'block';
  progressSec.style.display = 'none';
  doneSec.style.display     = 'none';
  progressFill.style.width  = '0%';
}

function clearFile() {
  selectedFile = null;
  fileInput.value = '';
  filePreview.style.display = 'none';
  convertWrap.style.display = 'none';
  progressSec.style.display = 'none';
  doneSec.style.display     = 'none';
  stopPolling();
}

function setProgress(pct, txt) {
  progressFill.style.width = pct + '%';
  progressPct.textContent  = pct + '%';
  progressTxt.textContent  = txt;
}

// ── Polling ───────────────────────────────

function stopPolling() {
  if (pollInterval) { clearInterval(pollInterval); pollInterval = null; }
}

async function pollStatus(jobId, outputFilename) {
  try {
    const res  = await fetch(`${API}/api/status/${jobId}`);
    const data = await res.json();

    if (!res.ok) {
      stopPolling();
      setProgress(0, '❌ Erreur serveur');
      return;
    }

    const mapped = STATUS_MAP[data.status] || { pct: 50, txt: 'Traitement…' };
    setProgress(mapped.pct, mapped.txt);

    if (data.status === 'done') {
      stopPolling();
      progressSec.style.display = 'none';
      doneSec.style.display     = 'flex';
      doneFileName.textContent  = outputFilename + ' est prêt';
      downloadBtn.onclick       = () => triggerDownload(jobId, outputFilename);
    }

    if (data.status === 'error') {
      stopPolling();
      setProgress(0, '❌ Échec : ' + (data.error || 'Erreur inconnue'));
    }

  } catch (err) {
    console.error('Poll error:', err);
    setProgress(0, '⚠️ Connexion perdue…');
  }
}

// ── Download ──────────────────────────────

async function triggerDownload(jobId, filename) {
  const url = `${API}/api/download/${jobId}`;
  const a   = document.createElement('a');
  a.href     = url;
  a.download = filename;
  a.click();
}

// ── Conversion ────────────────────────────

convertBtn.addEventListener('click', async () => {
  if (!selectedFile) return;

  // Switch UI to progress mode
  convertWrap.style.display = 'none';
  progressSec.style.display = 'block';
  doneSec.style.display     = 'none';
  setProgress(5, 'Envoi du fichier…');

  const formData = new FormData();
  formData.append('file', selectedFile);

  try {
    const res  = await fetch(`${API}/api/convert`, {
      method: 'POST',
      body:   formData,
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Erreur inconnue' }));
      setProgress(0, '❌ ' + (err.detail || 'Erreur serveur'));
      convertWrap.style.display = 'block';
      return;
    }

    const { job_id, filename } = await res.json();
    setProgress(10, 'En file d\'attente…');

    // Poll every 1.5 s
    pollInterval = setInterval(() => pollStatus(job_id, filename), 1500);

  } catch (err) {
    setProgress(0, '⚠️ Impossible de joindre le serveur.');
    convertWrap.style.display = 'block';
    console.error('Upload error:', err);
  }
});

// ── Drag & drop ───────────────────────────

fileInput.addEventListener('change', e => {
  if (e.target.files[0]) showFile(e.target.files[0]);
});

removeBtn.addEventListener('click', e => { e.stopPropagation(); clearFile(); });

dropZone.addEventListener('dragover',  e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
dropZone.addEventListener('dragleave', ()  => dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', e => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');
  const f = e.dataTransfer.files[0];
  if (f && f.type === 'application/pdf') showFile(f);
  else alert('Veuillez déposer un fichier PDF valide.');
});