import os
import io
import re
from flask import Flask, request, send_file, render_template_string, jsonify
from openai import OpenAI

# ========================
# Config básica
# ========================
app = Flask(__name__)
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

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
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <h1>Traductor de subtítulos .srt</h1>
      <p class="lead">Sube un archivo <code>.srt</code>, elige idioma destino y usa tu <code>OPENAI_API_KEY</code> para traducir con contexto global.</p>
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
            <label>Modelo (opcional)</label>
            <input type="text" id="model" placeholder="gpt-4o-mini (por defecto)" />
            <div class="hint">Deja vacío para usar: <span class="pill">{{ default_model }}</span></div>
          </div>
        </div>

        <div class="row">
          <div>
            <label>OPENAI_API_KEY</label>
            <input type="password" id="apikey" placeholder="sk-..." />
            <div class="hint">Si lo dejas vacío, se usará la variable de entorno del servidor.</div>
          </div>
          <div>
            <label>Estrategia</label>
            <select id="strategy">
              <option value="context">Contexto global (mejor calidad)</option>
              <option value="chunks">Por bloques (ahorra tokens)</option>
            </select>
          </div>
        </div>

        <div class="btnrow">
          <button class="btn" id="btn" type="submit">⬆️ Subir y traducir</button>
          <span class="pill">La clave no se guarda</span>
        </div>

        <div class="progress" aria-hidden="true">
          <div class="bar" id="bar"></div>
        </div>
        <div class="status" id="status"></div>
      </form>
    </div>
    <div class="footer">Hecho con ❤️ + Flask + OpenAI</div>
  </div>
<script>
const form = document.getElementById('form');
const bar = document.getElementById('bar');
const statusEl = document.getElementById('status');
const btn = document.getElementById('btn');

function setProgress(p, text) {
  bar.style.width = (p||0) + '%';
  statusEl.textContent = text||'';
}

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const file = document.getElementById('file').files[0];
  if (!file) { alert('Selecciona un .srt'); return; }

  const fd = new FormData();
  fd.append('file', file);
  fd.append('target', document.getElementById('target').value);
  fd.append('apikey', document.getElementById('apikey').value);
  fd.append('model', document.getElementById('model').value);
  fd.append('strategy', document.getElementById('strategy').value);

  btn.disabled = true;
  setProgress(10, 'Subiendo archivo…');

  try {
    const res = await fetch('/translate', { method:'POST', body: fd });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Error al traducir');
    }
    setProgress(80, 'Generando archivo traducido…');
    const blob = await res.blob();
    setProgress(100, 'Listo. Descargando…');

    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    const name = file.name.replace(/\.srt$/i, '') + '_traducido.srt';
    a.download = name;
    a.click();
    URL.revokeObjectURL(a.href);
    statusEl.innerHTML = '<span class="ok">✅ Traducción completada</span>';
  } catch (err) {
    console.error(err);
    statusEl.innerHTML = '<span class="err">❌ ' + err.message + '</span>';
  } finally {
    btn.disabled = false;
    setTimeout(()=> setProgress(0,''), 1200);
  }
});
</script>
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
        result.append({**b, "text": t})
    return result

# ========================
# OpenAI
# ========================
def openai_client(apikey: str|None):
    key = apikey or os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("No hay OPENAI_API_KEY (ni en formulario ni en entorno).")
    return OpenAI(api_key=key)

SYSTEM_PROMPT = (
    "Eres un traductor experto en subtítulos (.srt). "
    "Traduce de forma natural y consistente con el contexto, mantén nombres propios y tono. "
    "Conserva estrictamente formato y tiempos tal como se entregan. "
    "No agregues líneas nuevas ni cambies la división de subtítulos."
)

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

    # Intento 1 (temperature 0.0, más determinista)
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role":"system", "content": SYSTEM_PROMPT},
            {"role":"user", "content": user_content}
        ],
        temperature=0.0,
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
            temperature=0.0,
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
        temperature=0.0
    )
    return resp.choices[0].message.content.strip()

def translate_srt_with_context(srt_text, client, model, target_lang="español", strategy="context"):
    blocks = parse_srt(srt_text)
    if not blocks:
        raise RuntimeError("El archivo no parece ser un .srt válido.")

    # Estrategia 1: contexto global
    if strategy == "context":
        summary = build_global_summary(client, model, srt_text, target_lang)
        chunks = chunk_blocks(blocks, max_chars=12000)
        translated_blocks = []
        prev_glossary = None
        total = len(chunks)
        for i, ch in enumerate(chunks, 1):
            print(f"[SERVIDOR] Traduciendo chunk {i}/{total}… ({len(ch)} subtítulos)")
            translated_text = translate_chunk(client, model, ch, target_lang, global_summary=summary, prev_glossary=prev_glossary)
            tmp = merge_translated_text_to_blocks(translated_text, ch)
            # Memoria simple para siguiente chunk
            prev_glossary = (prev_glossary or "") + "\n" + "\n".join([b["text"] for b in tmp[:2]])[:600]
            translated_blocks.extend(tmp)
        return render_srt(translated_blocks)

    # Estrategia 2: por bloques (ahorra tokens)
    elif strategy == "chunks":
        chunks = chunk_blocks(blocks, max_chars=6000)
        translated_blocks = []
        prev_glossary = None
        total = len(chunks)
        for i, ch in enumerate(chunks, 1):
            print(f"[SERVIDOR] Traduciendo chunk {i}/{total}… ({len(ch)} subtítulos)")
            translated_text = translate_chunk(client, model, ch, target_lang, global_summary=None, prev_glossary=prev_glossary)
            tmp = merge_translated_text_to_blocks(translated_text, ch)
            prev_glossary = (prev_glossary or "") + "\n" + "\n".join([b["text"] for b in tmp[:2]])[:400]
            translated_blocks.extend(tmp)
        return render_srt(translated_blocks)

    else:
        raise RuntimeError("Estrategia desconocida. Usa 'context' o 'chunks'.")

# ========================
# Rutas
# ========================
@app.get("/")
def index():
    return render_template_string(HTML, default_model=DEFAULT_MODEL)

@app.post("/translate")
def translate():
    try:
        f = request.files.get("file")
        if not f or not f.filename.lower().endswith(".srt"):
            return jsonify(detail="Sube un archivo .srt válido"), 400

        target = request.form.get("target", "español").strip()
        apikey = request.form.get("apikey") or None
        strategy = request.form.get("strategy", "context")
        model = (request.form.get("model") or DEFAULT_MODEL).strip()

        client = openai_client(apikey)
        srt_text = f.read().decode("utf-8", errors="replace")

        translated = translate_srt_with_context(
            srt_text=srt_text,
            client=client,
            model=model,
            target_lang=target,
            strategy=strategy
        )

        base = re.sub(r"\.srt$", "", f.filename, flags=re.I)
        out_name = f"{base}_traducido.srt"
        return send_file(
            io.BytesIO(translated.encode("utf-8")),
            mimetype="application/x-subrip",
            as_attachment=True,
            download_name=out_name
        )
    except Exception as e:
        return jsonify(detail=str(e)), 500

# ========================
# Main
# ========================
if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "5000"))
    app.run(host=host, port=port, debug=True)
