# Imagen base ligera
FROM python:3.11-slim

# Evita bytecode y buffering
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Crea usuario no-root
RUN useradd -m -u 10001 appuser

# Instala dependencias del sistema (opcional: curl p/healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
 && rm -rf /var/lib/apt/lists/*

# Carpeta de la app
WORKDIR /app

# Copia requerimientos primero (mejor cache)
COPY requirements.txt /app/

# Instala dependencias Python
RUN pip install --no-cache-dir -r requirements.txt

# Copia la app (tu app.py ya parcheado)
COPY app.py /app/

# Crea carpeta para traducciones
RUN mkdir -p /app/traducciones && chown -R appuser:appuser /app/traducciones

# Ajustes Gunicorn por defecto (puedes override con env)
ENV HOST=0.0.0.0 \
    PORT=5000 \
    WORKERS=1 \
    THREADS=4 \
    TIMEOUT=600 \
    OPENAI_MODEL=gpt-3.5-turbo

# Puerto de la app
EXPOSE 5000

# Cambia a usuario no-root
USER appuser

# Healthcheck sencillo
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -fsS http://127.0.0.1:5000/ || exit 1

# Ejecuta con Gunicorn (más robusto que flask dev server)
CMD gunicorn app:app -b 0.0.0.0:5000 --workers 1 --threads 4 --timeout 600
