import os
import io
import re
import queue
import uuid
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from flask import Flask, request, send_file, render_template_string, jsonify, Response
from openai import OpenAI

# ========================
# Config básica
# ========================
app = Flask(__name__)

# Pool de threads para paralelización
executor = ThreadPoolExecutor(max_workers=4)

# Sistema de logs con sesión
current_session_logs = []
current_session_id = None
current_progress = 0  # Progreso actual 0-100

# Carpeta para guardar traducciones
TRANSLATIONS_DIR = "/app/traducciones" if os.path.exists("/app") else "./traducciones"
os.makedirs(TRANSLATIONS_DIR, exist_ok=True)

# Carpeta para guardar traducciones
TRANSLATIONS_DIR = "/app/traducciones" if os.path.exists("/app") else "./traducciones"
os.makedirs(TRANSLATIONS_DIR, exist_ok=True)

def add_log(message):
    """Añade un mensaje a los logs de la sesión actual."""
    global current_session_logs
    current_session_logs.append(message)
    print(message)  # También imprime en servidor

def update_progress(progress: int, message: str = ""):
    """Actualiza el progreso actual."""
    global current_progress
    current_progress = max(0, min(100, progress))
    if message:
        add_log(f"📊 {message}")
DEFAULT_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

HTML = r"""
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <title>Traductor SRT con OpenAI</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    :root { --bg:#0b1220; --card:#111a2b; --muted:#8aa0c7; --text:#e8eefc; --accent:#52a8ff; --ok:#19c37d; --err:#ff6b6b }
    * { box-sizing:border-box; }
    body { margin:0; font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, "Helvetica Neue", Arial; background:var(--bg); color:var(--text); }
    .wrap { max-width: 860px; margin: 40px auto; padding: 24px; }
    .card { background: var(--card); border-radius: 18px; padding: 24px; box-shadow: 0 8px 30px rgba(0,0,0,.3) }
    h1 { margin:0 0 8px; font-size: 28px; }
    p.lead { margin:0 0 20px; color: var(--muted); }
    label { display:block; font-weight:600; margin:14px 0 6px; }
    input[type="file"], input[type="text"], input[type="password"], select {
      width:100%; padding:12px 14px; border-radius:12px; border:1px solid #29324a; background:#0a1322; color:var(--text);
    }
    .row { display:grid; grid-template-columns: 1fr 1fr; gap:16px; }
    .btn { margin-top:18px; display:inline-flex; gap:8px; align-items:center; padding:12px 16px; border-radius:12px; border:1px solid #2b77ff; color:#fff; background:linear-gradient(90deg,#2b77ff,#7aa8ff); cursor:pointer; font-weight:700; }
    .btn:disabled { opacity:.6; cursor:not-allowed; }
    .hint { font-size:12px; color: var(--muted); margin-top:6px;}
    .footer { margin-top:18px; font-size:12px; color: var(--muted);}
    .pill { display:inline-block; font-size:12px; padding:4px 8px; border-radius:999px; border:1px solid #2e3b58; background:#0b1629; color:var(--muted); }
    .progress { margin-top:14px; height:10px; background:#0a1322; border-radius:999px; overflow:hidden; }
    .bar { height:100%; width:0%; background:linear-gradient(90deg,#52a8ff,#19c37d); transition:width .25s; }
    .status { margin-top:10px; font-size:13px; color:var(--muted); }
    .ok { color:var(--ok) }
    .err { color:var(--err) }
    code { background:#0a1322; padding:2px 6px; border-radius:6px; }
    .header-links { display:flex; gap:12px; justify-content:space-between; align-items:center; margin-bottom:20px; }
    .header-links a { color:var(--accent); text-decoration:none; font-size:14px; }
    .header-links a:hover { text-decoration:underline; }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="header-links">
      <span></span>
      <a href="/" id="homeLink">🏠 Traductor</a>
      <a href="/historial" id="historialLink">📜 Historial</a>
    </div>
    <div class="card">
      <h1>Traductor de subtítulos .srt</h1>
      <p class="lead">Sube un archivo <code>.srt</code>, elige idioma destino, proveedor de IA y API key para traducir con contexto global y paralelización.</p>
      <form id="form">
        <label>Archivo .srt</label>
        <input type="file" id="file" accept=".srt" required />

        <div class="row">
          <div>
            <label>Idioma destino</label>
            <select id="target">
              <option value="español" selected>Español</option>
              <option value="portugués">Portugués</option>
              <option value="francés">Francés</option>
              <option value="alemán">Alemán</option>
              <option value="italiano">Italiano</option>
            </select>
          </div>
          <div>
            <label>Proveedor de IA</label>
            <select id="provider" onchange="updateModelOptions()">
              <option value="openai">OpenAI</option>
              <option value="deepseek" selected>Deepseek</option>
            </select>
          </div>
        </div>

        <div class="row">
          <div>
            <label>Modelo</label>
            <select id="model">
              <!-- OpenAI Models -->
              <option value="gpt-3.5-turbo" data-provider="openai">GPT-3.5 Turbo</option>
              <option value="gpt-5.1" data-provider="openai">GPT-5.1 (mejor calidad)</option>
              <option value="gpt-5-mini" data-provider="openai">GPT-5 Mini (rápido)</option>
              <option value="gpt-5-nano" data-provider="openai">GPT-5 Nano (muy rápido)</option>
              <option value="gpt-4o" data-provider="openai">GPT-4o</option>
              <option value="gpt-4o-mini" data-provider="openai">GPT-4o Mini</option>
              <option value="gpt-4-turbo" data-provider="openai">GPT-4 Turbo</option>
              <option value="gpt-3.5-turbo" data-provider="openai">GPT-3.5 Turbo</option>
              <!-- Deepseek Models -->
              <option value="deepseek-chat" data-provider="deepseek" selected>Deepseek Chat</option>
              <option value="deepseek-coder" data-provider="deepseek">Deepseek Coder</option>
              <option value="deepseek-reasoner" data-provider="deepseek">Deepseek Reasoner (Advanced)</option>
            </select>
          </div>
        </div>

        <div class="row">
          <div>
            <label>OPENAI_API_KEY</label>
            <input type="password" id="apikey" placeholder="sk-..." />
            <div class="hint">Si lo dejas vacío, se usará la variable de entorno del servidor.</div>
          </div>
          <div>
            <label>DEEPSEEK_API_KEY</label>
            <input type="password" id="deepseek_apikey" placeholder="sk-..." />
            <div class="hint">Si lo dejas vacío, se usará la variable de entorno del servidor.</div>
          </div>
        </div>

        <div class="row">
          <div>
            <label>Estrategia</label>
            <select id="strategy">
              <option value="context" selected>Contexto global (mejor calidad)</option>
              <option value="chunks">Por bloques (ahorra tokens)</option>
            </select>
          </div>
        </div>

        <div class="btnrow">
          <button class="btn" id="btn" type="submit">⬆️ Subir y traducir</button>
          <button class="btn" id="downloadBtn" type="button" style="display:none; background:linear-gradient(90deg,#19c37d,#52a8ff);">⬇️ Descargar archivo</button>
          <span class="pill">La clave no se guarda</span>
        </div>

        <div class="progress" aria-hidden="true">
          <div class="bar" id="bar"></div>
        </div>
        <div class="status" id="status"></div>
        
        <div id="logsContainer" style="display:none; margin-top:20px;">
          <label>📋 Logs de traducción</label>
          <div id="logs" style="background:#0a1322; border:1px solid #29324a; border-radius:8px; padding:12px; max-height:200px; overflow-y:auto; font-size:12px; color:#8aa0c7; font-family:monospace; line-height:1.4;"></div>
        </div>
      </form>
    </div>
    <div class="footer">Hecho con ❤️ + Flask + OpenAI</div>
  </div>
<script>
// Actualizar modelos disponibles según el proveedor seleccionado
function updateModelOptions() {
  const provider = document.getElementById('provider').value;
  const modelSelect = document.getElementById('model');
  const options = modelSelect.querySelectorAll('option');
  
  // Mostrar/ocultar opciones según proveedor
  options.forEach(option => {
    const optProvider = option.getAttribute('data-provider');
    if (optProvider === provider) {
      option.style.display = 'block';
    } else {
      option.style.display = 'none';
    }
  });
  
  // Seleccionar modelo por defecto según proveedor
  let defaultModel;
  if (provider === 'deepseek') {
    defaultModel = 'deepseek-chat';
  } else if (provider === 'openai') {
    defaultModel = 'gpt-3.5-turbo';
  }
  
  // Buscar y seleccionar la opción
  const targetOption = Array.from(options).find(opt => 
    opt.getAttribute('data-provider') === provider && opt.value === defaultModel
  );
  
  if (targetOption) {
    modelSelect.value = defaultModel;
  } else {
    // Fallback: primer modelo visible
    const firstVisible = Array.from(options).find(opt => 
      opt.getAttribute('data-provider') === provider && opt.style.display !== 'none'
    );
    if (firstVisible) {
      modelSelect.value = firstVisible.value;
    }
  }
}

const form = document.getElementById('form');
const bar = document.getElementById('bar');
const statusEl = document.getElementById('status');
const btn = document.getElementById('btn');
const downloadBtn = document.getElementById('downloadBtn');
const logsContainer = document.getElementById('logsContainer');
const logsEl = document.getElementById('logs');

let startTime = null;
let timerInterval = null;
let logEventSource = null;
let lastTranslatedBlob = null;
let lastTranslatedName = null;
let progressInterval = null;

function formatTime(seconds) {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) return `${h}h ${m}m ${s}s`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

function startProgressPolling() {
  if (progressInterval) clearInterval(progressInterval);
  progressInterval = setInterval(async () => {
    try {
      const res = await fetch('/progress');
      const data = await res.json();
      if (data.progress > 10) {
        bar.style.width = data.progress + '%';
      }
    } catch (e) {}
  }, 500);
}

function stopProgressPolling() {
  if (progressInterval) {
    clearInterval(progressInterval);
    progressInterval = null;
  }
}

function addLog(message) {
  const line = document.createElement('div');
  line.textContent = message;
  logsEl.appendChild(line);
  logsEl.scrollTop = logsEl.scrollHeight; // Auto-scroll al final
}

function clearLogs() {
  logsEl.innerHTML = '';
}

function startTimer() {
  startTime = Date.now();
  if (timerInterval) clearInterval(timerInterval);
  timerInterval = setInterval(() => {
    const elapsed = Math.floor((Date.now() - startTime) / 1000);
    statusEl.textContent = `⏱️ Traduciendo… ${formatTime(elapsed)}`;
  }, 100);
}

function stopTimer() {
  if (timerInterval) clearInterval(timerInterval);
  const elapsed = Math.floor((Date.now() - startTime) / 1000);
  return formatTime(elapsed);
}

function downloadFile() {
  if (!lastTranslatedBlob || !lastTranslatedName) {
    alert('No hay archivo para descargar');
    return;
  }
  const a = document.createElement('a');
  a.href = URL.createObjectURL(lastTranslatedBlob);
  a.download = lastTranslatedName;
  a.click();
  URL.revokeObjectURL(a.href);
  addLog(`📥 Descarga iniciada: ${lastTranslatedName}`);
}

function setProgress(p, text) {
  bar.style.width = (p||0) + '%';
  if (text) statusEl.textContent = text;
}

function startLogStream() {
  // Cerrar conexión anterior de forma segura
  if (logEventSource) {
    try {
      logEventSource.close();
    } catch (e) {}
    logEventSource = null;
  }
  
  // Limpiar y mostrar
  clearLogs();
  logsContainer.style.display = 'block';
  
  // Esperar a que se cierre completamente
  setTimeout(() => {
    logEventSource = new EventSource('/logs-stream?' + Date.now());
    
    logEventSource.onopen = () => {
      console.log('Conexión de logs abierta');
    };
    
    logEventSource.onmessage = (event) => {
      const msg = event.data.trim();
      if (msg && !msg.startsWith(':')) {  // Ignorar keep-alive
        addLog(msg);
        console.log('Log:', msg);
      }
    };
    
    logEventSource.onerror = (err) => {
      console.error('Error en logs:', err);
      try {
        logEventSource.close();
      } catch (e) {}
    };
  }, 100);
}

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const file = document.getElementById('file').files[0];
  if (!file) { alert('Selecciona un .srt'); return; }

  const fd = new FormData();
  fd.append('file', file);
  fd.append('target', document.getElementById('target').value);
  fd.append('provider', document.getElementById('provider').value);
  fd.append('apikey', document.getElementById('apikey').value);
  fd.append('deepseek_apikey', document.getElementById('deepseek_apikey').value);
  fd.append('model', document.getElementById('model').value);
  fd.append('strategy', document.getElementById('strategy').value);

  btn.disabled = true;
  downloadBtn.style.display = 'none';
  setProgress(10, 'Subiendo archivo…');
  startTimer();
  startProgressPolling();
  
  // Inicializar sesión de logs
  await fetch('/init-session', { method: 'POST' });
  startLogStream();

  try {
    const res = await fetch('/translate', { method:'POST', body: fd });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Error al traducir');
    }
    setProgress(80, 'Generando archivo traducido…');
    const blob = await res.blob();
    
    // Guardar blob y nombre para descargar después
    lastTranslatedBlob = blob;
    lastTranslatedName = file.name.replace(/\.srt$/i, '') + '_traducido.srt';
    
    setProgress(100, 'Listo. Descargando…');

    // Intentar descarga automática
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = lastTranslatedName;
    a.click();
    URL.revokeObjectURL(a.href);
    
    const duration = stopTimer();
    const completeMsg = `✅ Traducción completada en ${duration}<br>📥 Se descargó: ${lastTranslatedName}<br>💡 Si no se descargó, usa el botón de abajo`;
    statusEl.innerHTML = `<span class="ok">${completeMsg}</span>`;
    addLog(`✅ Traducción completada en ${duration}`);
    addLog(`📥 Archivo: ${lastTranslatedName}`);
    
    // Mostrar botón de descarga como respaldo
    downloadBtn.style.display = 'inline-flex';
  } catch (err) {
    console.error(err);
    stopTimer();
    stopProgressPolling();
    statusEl.innerHTML = '<span class="err">❌ ' + err.message + '</span>';
    addLog(`❌ Error: ${err.message}`);
  } finally {
    btn.disabled = false;
    stopProgressPolling();
    
    // Cerrar logs de forma segura
    setTimeout(() => {
      if (logEventSource) {
        try {
          logEventSource.close();
        } catch (e) {}
        logEventSource = null;
      }
    }, 100);
    
    setTimeout(()=> setProgress(0,''), 1200);
  }
});

downloadBtn.addEventListener('click', downloadFile);
</script>
</body>
</html>
"""

HISTORIAL_HTML = r"""
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <title>Historial de Traducciones</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    :root { --bg:#0b1220; --card:#111a2b; --muted:#8aa0c7; --text:#e8eefc; --accent:#52a8ff; --ok:#19c37d; --err:#ff6b6b }
    * { box-sizing:border-box; }
    body { margin:0; font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, "Helvetica Neue", Arial; background:var(--bg); color:var(--text); }
    .wrap { max-width: 900px; margin: 40px auto; padding: 24px; }
    .card { background: var(--card); border-radius: 18px; padding: 24px; box-shadow: 0 8px 30px rgba(0,0,0,.3) }
    h1 { margin:0 0 8px; font-size: 28px; }
    p.lead { margin:0 0 20px; color: var(--muted); }
    table { width:100%; border-collapse:collapse; }
    th { text-align:left; padding:12px; border-bottom:2px solid #29324a; font-weight:700; color:var(--accent); }
    td { padding:12px; border-bottom:1px solid #29324a; }
    tr:hover { background:#0a1629; }
    .btn-download { background:linear-gradient(90deg,#19c37d,#52a8ff); color:#fff; border:none; padding:6px 12px; border-radius:6px; cursor:pointer; font-size:12px; text-decoration:none; display:inline-block; }
    .btn-download:hover { opacity:.85; }
    .header-links { display:flex; gap:12px; justify-content:space-between; align-items:center; margin-bottom:20px; }
    .header-links a { color:var(--accent); text-decoration:none; font-size:14px; }
    .header-links a:hover { text-decoration:underline; }
    .empty { text-align:center; color:var(--muted); padding:40px; }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="header-links">
      <a href="/" id="homeLink">🏠 Traductor</a>
      <a href="/historial" id="historialLink">📜 Historial</a>
    </div>
    <div class="card">
      <h1>📜 Historial de Traducciones</h1>
      <p class="lead">Todos los archivos traducidos disponibles para descargar</p>
      
      {% if files %}
        <table>
          <thead>
            <tr>
              <th>Nombre del archivo</th>
              <th>Fecha</th>
              <th>Tamaño</th>
              <th>Acción</th>
            </tr>
          </thead>
          <tbody>
            {% for file in files %}
            <tr>
              <td><code>{{ file.name }}</code></td>
              <td>{{ file.mtime }}</td>
              <td>{{ file.size_mb }}</td>
              <td><a href="/descargar/{{ file.name }}" class="btn-download">⬇️ Descargar</a></td>
            </tr>
            {% endfor %}
          </tbody>
        </table>
      {% else %}
        <div class="empty">
          <p>No hay archivos traducidos aún</p>
        </div>
      {% endif %}
    </div>
  </div>
</body>
</html>
"""

# ========================
# Utilidades SRT
# ========================
SRT_BLOCK_RE = re.compile(
    r"(\d+)\s*\n(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})(?:.*)?\n([\s\S]*?)(?=\n\n|\Z)",
    re.MULTILINE
)

def parse_srt(text: str):
    blocks = []
    for m in SRT_BLOCK_RE.finditer(text.strip()):
        idx = int(m.group(1))
        start = m.group(2)
        end = m.group(3)
        content = m.group(4).strip()
        blocks.append({"index": idx, "start": start, "end": end, "text": content})
    return blocks

def render_srt(blocks):
    out = []
    for b in blocks:
        txt = b["text"].replace("\r", "")
        out.append(f"{b['index']}\n{b['start']} --> {b['end']}\n{txt}\n")
    return "\n".join(out).strip() + "\n"

def detect_language_of_text(text: str) -> str:
    """
    Detecta el idioma probable de un texto.
    Retorna: 'español', 'inglés', 'otro' basado en palabras clave comunes.
    """
    text_lower = text.lower()
    
    # Palabras clave españolas
    spanish_words = ['el', 'la', 'de', 'que', 'y', 'a', 'en', 'es', 'se', 'por', 'para', 'con', 'está', 'son', 'fue', 'están']
    
    # Palabras clave inglesas
    english_words = ['the', 'and', 'to', 'of', 'a', 'in', 'is', 'it', 'that', 'was', 'you', 'for', 'are', 'be', 'on']
    
    spanish_count = sum(1 for word in spanish_words if f' {word} ' in f' {text_lower} ')
    english_count = sum(1 for word in english_words if f' {word} ' in f' {text_lower} ')
    
    if spanish_count > english_count:
        return 'español'
    elif english_count > spanish_count:
        return 'inglés'
    return 'otro'

def verify_translation_blocks(blocks, target_lang: str) -> tuple[bool, list]:
    """
    Verifica que todos los bloques hayan sido traducidos al idioma correcto.
    Retorna (is_valid, list_of_untranslated_indices)
    """
    untranslated = []
    
    for block in blocks:
        text = block.get("text", "")
        if not text:
            untranslated.append(block["index"])
            continue
        
        detected_lang = detect_language_of_text(text)
        
        # Si el idioma detectado es inglés y debería ser español, marcar como no traducido
        if target_lang == "español" and detected_lang == "inglés":
            untranslated.append(block["index"])
    
    return len(untranslated) == 0, untranslated

def normalize_case(text: str) -> str:
    """Normaliza mayúsculas excesivas. Si >60% es mayúsculas, convierte a minúsculas con capitalización."""
    if not text:
        return text
    
    # Contar mayúsculas
    upper_count = sum(1 for c in text if c.isupper())
    total_alpha = sum(1 for c in text if c.isalpha())
    
    if total_alpha == 0:
        return text
    
    uppercase_ratio = upper_count / total_alpha
    
    # Si >60% es mayúsculas, normalizar
    if uppercase_ratio > 0.6:
        # Convertir a minúsculas y capitalizar inicio de oraciones
        text = text.lower()
        # Capitalizar después de punto, interrogación, admiración
        import re as regex_module
        text = regex_module.sub(r'([.!?]\s+)([a-z])', lambda m: m.group(1) + m.group(2).upper(), text)
        # Capitalizar inicio de línea
        lines = text.split('\n')
        lines = [line[0].upper() + line[1:] if line else line for line in lines]
        text = '\n'.join(lines)
    
    return text

def chunk_blocks(blocks, max_chars=12000):
    """Agrupa bloques en 'trozos' por número de caracteres (para evitar límites de tokens)."""
    chunks, cur, cur_len = [], [], 0
    for b in blocks:
        btxt = f"{b['index']}\n{b['start']} --> {b['end']}\n{b['text']}\n\n"
        if cur_len + len(btxt) > max_chars and cur:
            chunks.append(cur)
            cur, cur_len = [], 0
        cur.append(b)
        cur_len += len(btxt)
    if cur:
        chunks.append(cur)
    return chunks

def chunk_blocks_multiple_of_4(blocks, max_chars=12000):
    """
    Agrupa bloques en chunks garantizando que el total sea múltiplo de 4.
    Esto optimiza el paralelismo: 4, 8, 12, 16, etc. workers sin dejar ociosos.
    """
    # Primero, divide por caracteres
    initial_chunks = chunk_blocks(blocks, max_chars)
    
    num_chunks = len(initial_chunks)
    
    # Si ya es múltiplo de 4, devuelve tal cual
    if num_chunks % 4 == 0:
        return initial_chunks
    
    # Calcula el próximo múltiplo de 4
    target_chunks = ((num_chunks // 4) + 1) * 4
    
    # Redistribuye los bloques en `target_chunks` partes lo más equilibradas posible
    total_blocks = len(blocks)
    blocks_per_chunk = total_blocks // target_chunks
    remainder = total_blocks % target_chunks
    
    result = []
    start_idx = 0
    
    for i in range(target_chunks):
        # Los primeros `remainder` chunks reciben un bloque extra
        size = blocks_per_chunk + (1 if i < remainder else 0)
        if size > 0:
            result.append(blocks[start_idx:start_idx + size])
            start_idx += size
    
    return result

def format_blocks_for_prompt(blocks):
    # Formato fijo para mapear 1:1
    lines = []
    for b in blocks:
        lines.append(f"### BLOQUE {b['index']}")
        lines.append(f"TIME {b['start']} --> {b['end']}")
        lines.append(b['text'])
        lines.append("")  # separación
    return "\n".join(lines).strip()

# ------- NUEVAS utilidades de tolerancia/validación -------
def count_template_headers(text: str) -> int:
    return len(re.findall(r"^###\s*BLOQUE\s+\d+\s*$", text, flags=re.MULTILINE))

def extract_map_from_template(translated_text: str) -> dict[int, str]:
    pattern = re.compile(
        r"###\s*BLOQUE\s+(\d+)\s*\nTIME\s+\d{2}:\d{2}:\d{2},\d{3}\s*-->\s*\d{2}:\d{2}:\d{2},\d{3}\s*\n([\s\S]*?)(?=\n###\s*BLOQUE|\Z)",
        re.MULTILINE
    )
    m = {}
    for g in pattern.finditer(translated_text.strip()):
        idx = int(g.group(1))
        m[idx] = g.group(2).strip()
    return m

def extract_map_from_srt_fallback(translated_text: str, original_chunk: list[dict]) -> dict[int, str]:
    """
    Si el modelo devolvió SRT crudo, lo parseamos y alineamos por orden.
    """
    parsed = parse_srt(translated_text)
    if not parsed:
        return {}
    m = {}
    # alineación por posición dentro del chunk:
    for pos, b in enumerate(original_chunk):
        if pos < len(parsed):
            m[b["index"]] = parsed[pos]["text"]
    return m

def merge_translated_text_to_blocks(translated_text, original_blocks):
    # 1) Intenta con plantilla "### BLOQUE"
    mapped = extract_map_from_template(translated_text)

    # 2) Si faltan, intenta interpretar SRT crudo y alinear por orden
    if len(mapped) < len(original_blocks):
        fallback = extract_map_from_srt_fallback(translated_text, original_blocks)
        for k, v in fallback.items():
            if k not in mapped:
                mapped[k] = v

    # 3) Construye el resultado usando originales cuando falten
    result = []
    for b in original_blocks:
        t = mapped.get(b["index"], b["text"])
        # Normalizar mayúsculas si es necesario
        t = normalize_case(t)
        result.append({**b, "text": t})
    return result

# ========================
# OpenAI y Deepseek Clients
# ========================
def get_api_client(provider: str, apikey: str|None = None, deepseek_apikey: str|None = None):
    """
    Retorna un cliente OpenAI compatible según el proveedor.
    - OpenAI: usa base_url por defecto de OpenAI
    - Deepseek: usa base_url de Deepseek con compatibilidad OpenAI
    """
    if provider == "deepseek":
        key = deepseek_apikey or os.getenv("DEEPSEEK_API_KEY")
        if not key:
            raise RuntimeError("No hay DEEPSEEK_API_KEY (ni en formulario ni en entorno).")
        # Deepseek usa compatible con OpenAI client library
        return OpenAI(
            api_key=key,
            base_url="https://api.deepseek.com"
        )
    else:  # openai
        key = apikey or os.getenv("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("No hay OPENAI_API_KEY (ni en formulario ni en entorno).")
        return OpenAI(api_key=key)

# Legacy function for compatibility
def openai_client(apikey: str|None):
    return get_api_client("openai", apikey=apikey)

SYSTEM_PROMPT = (
    "Eres un traductor experto en subtítulos (.srt). "
    "Traduce de forma natural y consistente con el contexto, mantén nombres propios y tono. "
    "Conserva estrictamente formato y tiempos tal como se entregan. "
    "No agregues líneas nuevas ni cambies la división de subtítulos."
)

def get_temperature(model: str) -> float:
    """Retorna la temperature correcta según el modelo.
    GPT-5 y Deepseek usan temperature=1.0, otros modelos usan 0.0 para determinismo."""
    if model.startswith("gpt-5") or model.startswith("deepseek"):
        return 1.0  # GPT-5 y Deepseek requieren temperature=1
    return 0.0  # Otros modelos usan temperature=0.0 para mayor determinismo

def translate_chunk(client, model, chunk_blocks, target_lang, global_summary=None, prev_glossary=None):
    base_header = [
        f"Traduce los subtítulos siguientes al {target_lang}.",
        "DEBES devolver UN bloque por CADA subtítulo, con este esquema EXACTO:",
        "### BLOQUE <index>",
        "TIME <inicio> --> <fin>",
        "<líneas traducidas (misma división de líneas que el original)>",
        "",
        "No cambies números, ni tiempos, ni la cantidad de bloques. No combines bloques.",
    ]
    if global_summary:
        base_header.append("\nResumen de contexto (no lo reescribas):\n" + global_summary)
    if prev_glossary:
        base_header.append("\nGlosario previo:\n" + prev_glossary)

    user_content = "\n".join(base_header) + "\n\n" + format_blocks_for_prompt(chunk_blocks)

    # Intento 1 (temperature adaptada al modelo)
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role":"system", "content": SYSTEM_PROMPT},
            {"role":"user", "content": user_content}
        ],
        temperature=get_temperature(model),
    )
    out = resp.choices[0].message.content.strip()
    mapped = extract_map_from_template(out)

    # Si faltan bloques, reintento estricto
    if len(mapped) < len(chunk_blocks):
        strict_user = user_content + (
            "\n\nIMPORTANTE: No devuelvas SRT crudo. "
            "Repite el encabezado '### BLOQUE' para CADA subtítulo. "
            f"Debes emitir exactamente {len(chunk_blocks)} bloques etiquetados."
        )
        resp2 = client.chat.completions.create(
            model=model,
            messages=[
                {"role":"system", "content": SYSTEM_PROMPT},
                {"role":"user", "content": strict_user}
            ],
            temperature=get_temperature(model),
        )
        out = resp2.choices[0].message.content.strip()

    return out

def build_global_summary(client, model, full_text, target_lang):
    """Crea un breve resumen/guía de estilo a partir del SRT completo para dar contexto."""
    prompt = (
        f"Lee este subtítulo (.srt) y genera un breve resumen de contexto (personajes, tono, jerga, chistes recurrentes), "
        f"además de 5-10 decisiones de estilo útiles para traducirlo al {target_lang}. "
        "Máximo 180-220 palabras. No reescribas subtítulos; solo el resumen y lineamientos."
    )
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role":"system", "content":"Eres un asistente experto en análisis de guion y estilo."},
            {"role":"user", "content": prompt + "\n\n---\n" + full_text[:18000]}
        ],
        temperature=get_temperature(model)
    )
    return resp.choices[0].message.content.strip()

def translate_chunks_parallel(client, model, chunks, target_lang, global_summary=None):
    """
    Traduce múltiples chunks en paralelo usando threads con límite de 4 peticiones simultáneas.
    Respeta el rate limit de Deepseek: máximo 4 requests en paralelo.
    Retorna lista de (index, translated_text) tuplas.
    """
    from concurrent.futures import as_completed
    
    def translate_single_chunk(index, chunk_blocks):
        """Traduce un único chunk."""
        try:
            translated_text = translate_chunk(
                client, model, chunk_blocks, target_lang, 
                global_summary=global_summary, 
                prev_glossary=None
            )
            return (index, translated_text, None)
        except Exception as e:
            add_log(f"⚠️ Error traduciendo chunk {index}: {str(e)}")
            return (index, None, str(e))
    
    # Limitar a máximo 4 requests paralelos para no saturar API Deepseek
    max_parallel = 4
    total_chunks = len(chunks)
    results = []
    completed = 0
    
    # Cola de tareas pendientes: lista de (idx, chunk)
    pending_chunks = list(enumerate(chunks, 1))
    # Diccionario para mapear future -> index
    future_to_index = {}
    
    # Llenar el pool inicial con hasta 4 tareas
    active_futures = []
    while pending_chunks and len(active_futures) < max_parallel:
        idx, chunk = pending_chunks.pop(0)
        future = executor.submit(translate_single_chunk, idx, chunk)
        active_futures.append(future)
        future_to_index[future] = idx
    
    # Procesar resultados conforme se completan y enviar nuevas tareas
    while active_futures:
        # Obtener el siguiente future que se complete
        done, pending = None, active_futures
        for future in as_completed(pending):
            done = future
            break
        
        if done:
            active_futures.remove(done)
            
            index, translated_text, error = done.result()
            completed += 1
            
            if not error:
                results.append((index, translated_text))
                add_log(f"✅ Chunk {index} traducido")
            else:
                add_log(f"❌ Chunk {index} falló: {error}")
            
            # Actualizar progreso
            progress = 50 + int((completed / total_chunks) * 40)
            update_progress(progress)
            
            # Enviar siguiente tarea si hay pendientes
            if pending_chunks:
                idx, chunk = pending_chunks.pop(0)
                future = executor.submit(translate_single_chunk, idx, chunk)
                active_futures.append(future)
                future_to_index[future] = idx
    
    return results

def retranslate_untranslated_blocks(client, model, translated_blocks, untranslated_indices, original_blocks, target_lang, max_retries=2):
    """
    Reintenta traducir los bloques que no fueron traducidos correctamente.
    Retorna la lista de bloques actualizada.
    """
    if not untranslated_indices:
        return translated_blocks
    
    add_log(f"🔄 Reintentando traducción de {len(untranslated_indices)} subtítulos no traducidos...")
    
    # Crear chunks solo con los bloques no traducidos
    untranslated_blocks = [b for b in original_blocks if b["index"] in untranslated_indices]
    
    # Agrupar en chunks para reintento
    retry_chunks = chunk_blocks(untranslated_blocks, max_chars=6000)
    
    add_log(f"📦 Agrupados en {len(retry_chunks)} chunks para reintento")
    
    # Traducir en paralelo con límite de reintentos
    for attempt in range(max_retries):
        add_log(f"⚡ Reintento {attempt + 1}/{max_retries}...")
        
        results = translate_chunks_parallel(client, model, retry_chunks, target_lang, global_summary=None)
        
        # Actualizar bloques traducidos
        retry_translated = []
        for chunk_idx, ch in enumerate(retry_chunks, 1):
            translated_text = None
            for idx, txt in results:
                if idx == chunk_idx:
                    translated_text = txt
                    break
            
            if translated_text:
                tmp = merge_translated_text_to_blocks(translated_text, ch)
                retry_translated.extend(tmp)
            else:
                retry_translated.extend(ch)
        
        # Reemplazar los bloques retraducidos en translated_blocks
        for retry_block in retry_translated:
            for i, block in enumerate(translated_blocks):
                if block["index"] == retry_block["index"]:
                    translated_blocks[i] = retry_block
                    break
        
        # Verificar si ahora está todo bien
        is_valid, still_untranslated = verify_translation_blocks(translated_blocks, target_lang)
        if is_valid:
            add_log(f"✅ Reintento {attempt + 1} exitoso: todos los subtítulos traducidos")
            return translated_blocks
        elif len(still_untranslated) < len(untranslated_indices):
            add_log(f"✅ Reintento {attempt + 1}: reducidos a {len(still_untranslated)} subtítulos sin traducir (de {len(untranslated_indices)})")
            untranslated_indices = still_untranslated
        else:
            add_log(f"⚠️ Reintento {attempt + 1}: sin cambios, {len(still_untranslated)} subtítulos aún sin traducir")
    
    return translated_blocks

def translate_srt_with_context(srt_text, client, model, target_lang="español", strategy="context"):
    blocks = parse_srt(srt_text)
    if not blocks:
        raise RuntimeError("El archivo no parece ser un .srt válido.")
    
    add_log(f"📋 Se encontraron {len(blocks)} subtítulos")
    add_log(f"🌐 Idioma destino: {target_lang}")
    add_log(f"🤖 Modelo: {model}")
    add_log(f"⚙️ Estrategia: {strategy}")

    # Estrategia 1: contexto global (CON PARALELIZACIÓN)
    if strategy == "context":
        update_progress(15, "Generando resumen de contexto…")
        add_log("📝 Generando resumen de contexto...")
        summary = build_global_summary(client, model, srt_text, target_lang)
        chunks = chunk_blocks_multiple_of_4(blocks, max_chars=12000)
        total = len(chunks)
        add_log(f"📦 Se dividió en {total} chunks (múltiplo de 4 para paralelismo óptimo)")
        add_log(f"⚡ Iniciando traducción paralela de {total} chunks...")
        
        # Traducir chunks en paralelo
        results = translate_chunks_parallel(client, model, chunks, target_lang, global_summary=summary)
        
        # Procesar resultados en orden
        translated_blocks = []
        for chunk_idx, ch in enumerate(chunks, 1):
            # Buscar resultado para este chunk
            translated_text = None
            for idx, txt in results:
                if idx == chunk_idx:
                    translated_text = txt
                    break
            
            if translated_text:
                tmp = merge_translated_text_to_blocks(translated_text, ch)
                translated_blocks.extend(tmp)
            else:
                # Fallback: si no se tradujo, usar original
                add_log(f"⚠️ Chunk {chunk_idx} no fue traducido, usando original")
                translated_blocks.extend(ch)
        
        update_progress(95, "Finalizando…")
        
        # Verificar que todos los bloques fueron traducidos correctamente
        is_valid, untranslated_indices = verify_translation_blocks(translated_blocks, target_lang)
        if not is_valid:
            add_log(f"⚠️ Detectados {len(untranslated_indices)} subtítulos sin traducir, iniciando reintento...")
            translated_blocks = retranslate_untranslated_blocks(client, model, translated_blocks, untranslated_indices, blocks, target_lang)
            
            # Verificar nuevamente
            is_valid, untranslated_indices = verify_translation_blocks(translated_blocks, target_lang)
            if not is_valid:
                add_log(f"⚠️ ADVERTENCIA: Después de reintentos, aún hay {len(untranslated_indices)} subtítulos sin traducir")
                add_log(f"   Índices: {untranslated_indices[:20]}{'...' if len(untranslated_indices) > 20 else ''}")
            else:
                add_log(f"✅ Reintento exitoso: todos los {len(translated_blocks)} subtítulos en {target_lang}")
        else:
            add_log(f"✅ Verificación completa: todos los {len(translated_blocks)} subtítulos están en {target_lang}")
        
        return render_srt(translated_blocks)

    # Estrategia 2: por bloques (CON PARALELIZACIÓN)
    elif strategy == "chunks":
        chunks = chunk_blocks(blocks, max_chars=6000)
        total = len(chunks)
        add_log(f"📦 Se dividió en {total} chunks")
        add_log(f"⚡ Iniciando traducción paralela de {total} chunks...")
        
        # Traducir chunks en paralelo
        results = translate_chunks_parallel(client, model, chunks, target_lang, global_summary=None)
        
        # Procesar resultados en orden
        translated_blocks = []
        for chunk_idx, ch in enumerate(chunks, 1):
            # Buscar resultado para este chunk
            translated_text = None
            for idx, txt in results:
                if idx == chunk_idx:
                    translated_text = txt
                    break
            
            if translated_text:
                tmp = merge_translated_text_to_blocks(translated_text, ch)
                translated_blocks.extend(tmp)
            else:
                # Fallback: si no se tradujo, usar original
                add_log(f"⚠️ Chunk {chunk_idx} no fue traducido, usando original")
                translated_blocks.extend(ch)
        
        update_progress(95, "Finalizando…")
        
        # Verificar que todos los bloques fueron traducidos correctamente
        is_valid, untranslated_indices = verify_translation_blocks(translated_blocks, target_lang)
        if not is_valid:
            add_log(f"⚠️ Detectados {len(untranslated_indices)} subtítulos sin traducir, iniciando reintento...")
            translated_blocks = retranslate_untranslated_blocks(client, model, translated_blocks, untranslated_indices, blocks, target_lang)
            
            # Verificar nuevamente
            is_valid, untranslated_indices = verify_translation_blocks(translated_blocks, target_lang)
            if not is_valid:
                add_log(f"⚠️ ADVERTENCIA: Después de reintentos, aún hay {len(untranslated_indices)} subtítulos sin traducir")
                add_log(f"   Índices: {untranslated_indices[:20]}{'...' if len(untranslated_indices) > 20 else ''}")
            else:
                add_log(f"✅ Reintento exitoso: todos los {len(translated_blocks)} subtítulos en {target_lang}")
        else:
            add_log(f"✅ Verificación completa: todos los {len(translated_blocks)} subtítulos están en {target_lang}")
        
        return render_srt(translated_blocks)

    else:
        raise RuntimeError("Estrategia desconocida. Usa 'context' o 'chunks'.")

# ========================
# Rutas
# ========================
@app.get("/")
def index():
    return render_template_string(HTML, default_model=DEFAULT_MODEL)

@app.post("/init-session")
def init_session():
    """Inicia una nueva sesión de logs."""
    global current_session_logs, current_session_id, current_progress
    # Limpiar completamente la sesión anterior
    current_session_logs.clear()
    current_session_id = str(uuid.uuid4())
    current_progress = 0
    print(f"[SESSION] Nueva sesión iniciada: {current_session_id}. Logs vaciados.")
    return jsonify(session_id=current_session_id)

@app.get("/progress")
def get_progress():
    """Obtiene el progreso actual."""
    return jsonify(progress=current_progress)

@app.get("/logs-stream")
def logs_stream():
    """Streaming de logs en tiempo real con Server-Sent Events (SSE)."""
    import sys
    
    def generate():
        last_index = 0
        print(f"[SSE CONNECT] Cliente conectado a stream. Logs actuales: {len(current_session_logs)}", flush=True)
        sys.stdout.flush()
        
        # Enviar logs existentes al conectar (para no perder los del inicio)
        for msg in current_session_logs:
            print(f"[SSE INIT] Enviando log existente: {msg}", flush=True)
            yield f"data: {msg}\n\n"
            sys.stdout.flush()
        
        last_index = len(current_session_logs)
        
        # Enviar keep-alive y logs nuevos indefinidamente
        import time
        while True:
            # Enviar solo logs NUEVOS desde la última vez
            if last_index < len(current_session_logs):
                for i in range(last_index, len(current_session_logs)):
                    msg = current_session_logs[i]
                    print(f"[SSE SEND] Enviando log #{i}: {msg}", flush=True)
                    yield f"data: {msg}\n\n"
                    sys.stdout.flush()
                last_index = len(current_session_logs)
            else:
                # Keep-alive cuando no hay logs nuevos
                yield ": keep-alive\n\n"
                sys.stdout.flush()
            
            # Pausa para no saturar
            time.sleep(0.05)
    
    return Response(generate(), mimetype="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
        "Connection": "keep-alive"
    })

@app.get("/historial")
def historial():
    """Página del historial de traducciones."""
    try:
        files = []
        if os.path.exists(TRANSLATIONS_DIR):
            for filename in sorted(os.listdir(TRANSLATIONS_DIR), reverse=True):
                filepath = os.path.join(TRANSLATIONS_DIR, filename)
                if os.path.isfile(filepath):
                    size = os.path.getsize(filepath)
                    mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
                    files.append({
                        'name': filename,
                        'size': size,
                        'mtime': mtime.strftime("%Y-%m-%d %H:%M:%S"),
                        'size_mb': f"{size / (1024*1024):.2f}" if size > 1024*1024 else f"{size / 1024:.1f}KB"
                    })
        return render_template_string(HISTORIAL_HTML, files=files)
    except Exception as e:
        return jsonify(detail=str(e)), 500

@app.get("/descargar/<filename>")
def descargar(filename):
    """Descarga un archivo del historial."""
    try:
        filepath = os.path.join(TRANSLATIONS_DIR, filename)
        # Validar que el archivo existe y está en la carpeta permitida
        if not os.path.exists(filepath) or not os.path.isfile(filepath):
            return jsonify(detail="Archivo no encontrado"), 404
        if not os.path.abspath(filepath).startswith(os.path.abspath(TRANSLATIONS_DIR)):
            return jsonify(detail="Acceso denegado"), 403
        
        return send_file(filepath, as_attachment=True, download_name=filename)
    except Exception as e:
        return jsonify(detail=str(e)), 500

@app.post("/translate")
def translate():
    try:
        f = request.files.get("file")
        if not f or not f.filename.lower().endswith(".srt"):
            return jsonify(detail="Sube un archivo .srt válido"), 400

        target = request.form.get("target", "español").strip()
        provider = request.form.get("provider", "openai").strip()
        apikey = request.form.get("apikey") or None
        deepseek_apikey = request.form.get("deepseek_apikey") or None
        strategy = request.form.get("strategy", "context")
        model = (request.form.get("model") or DEFAULT_MODEL).strip()

        # Obtener cliente según el proveedor
        client = get_api_client(provider, apikey=apikey, deepseek_apikey=deepseek_apikey)
        srt_text = f.read().decode("utf-8", errors="replace")

        add_log(f"🔌 Usando proveedor: {provider}")

        translated = translate_srt_with_context(
            srt_text=srt_text,
            client=client,
            model=model,
            target_lang=target,
            strategy=strategy
        )

        base = re.sub(r"\.srt$", "", f.filename, flags=re.I)
        out_name = f"{base}_traducido.srt"
        
        # Guardar archivo en servidor
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        saved_filename = f"{timestamp}_{out_name}"
        saved_path = os.path.join(TRANSLATIONS_DIR, saved_filename)
        with open(saved_path, 'w', encoding='utf-8') as file:
            file.write(translated)
        add_log(f"✅ Archivo guardado en servidor: {saved_filename}")
        
        return send_file(
            io.BytesIO(translated.encode("utf-8")),
            mimetype="application/x-subrip",
            as_attachment=True,
            download_name=out_name
        )
    except Exception as e:
        add_log(f"❌ Error en traducción: {str(e)}")
        return jsonify(detail=str(e)), 500

# ========================
# Main
# ========================
if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "5000"))
    app.run(host=host, port=port, debug=True)
