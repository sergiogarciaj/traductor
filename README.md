# 🎬 Traductor SRT - OpenAI & Deepseek

Traductor de subtítulos `.srt` con soporte para **OpenAI** y **Deepseek**, con interfaz web en tiempo real usando Flask.

## ✨ Características

- 🤖 **Múltiples proveedores de IA**: OpenAI (GPT-4, GPT-3.5, etc.) y Deepseek
- 📊 **Traducción con contexto global**: Genera resumen de la película/serie para traducciones más precisas
- ⚡ **Streaming en tiempo real**: Ve los logs en vivo mientras se traduce
- 📈 **Barra de progreso**: Seguimiento de progreso durante la traducción
- 💾 **Historial de traducciones**: Descarga archivos traducidos anteriormente
- 🎨 **Interfaz moderna**: UI responsiva y oscura
- 🐳 **Docker**: Desplegable en cualquier lado

## 🚀 Inicio Rápido

### Requisitos

- Docker y Docker Compose
- Cuenta en OpenAI y/o Deepseek con API keys válidas

### Instalación

1. Clona el repositorio:
```bash
git clone https://github.com/sergiogarciaj/traductor.git
cd traductor
```

2. Crea un archivo `.env` con tus claves:
```bash
cp .env.example .env
```

3. Edita `.env` y agrega tus API keys:
```
OPENAI_API_KEY=sk-...
DEEPSEEK_API_KEY=sk-...
```

4. Levanta los contenedores:
```bash
docker-compose up --build
```

5. Abre en tu navegador: **http://localhost:5000**

## 📖 Uso

1. **Selecciona proveedor**: OpenAI o Deepseek
2. **Elige modelo**: Los modelos se filtran según el proveedor
3. **Carga archivo `.srt`**: Tu archivo de subtítulos
4. **Selecciona idioma destino**: Español, Portugués, Francés, Alemán, Italiano
5. **Elige estrategia**:
   - **Contexto global** (recomendado): Genera resumen de la película/serie
   - **Por bloques**: Traduce sin contexto (más económico)
6. **Traduce**: El archivo se descarga automáticamente

## 🔧 Configuración

### Variables de Entorno (`.env`)

```env
# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-3.5-turbo

# Deepseek
DEEPSEEK_API_KEY=sk-...

# Docker (opcional)
WORKERS=1
THREADS=4
TIMEOUT=600
```

### Modelos Disponibles

**OpenAI:**
- GPT-5.1 (mejor calidad)
- GPT-5-mini
- GPT-5-nano
- GPT-4o
- GPT-4o-mini
- GPT-4-turbo
- GPT-3.5-turbo

**Deepseek:**
- deepseek-chat
- deepseek-coder
- deepseek-reasoner

## 📁 Estructura

```
traductor/
├── app.py                 # Aplicación Flask principal
├── Dockerfile             # Configuración Docker
├── docker-compose.yml     # Orquestación de contenedores
├── requirements.txt       # Dependencias Python
├── .env.example          # Template de variables de entorno
├── .gitignore            # Git ignore
└── README.md             # Este archivo
```

## 🌟 Características Técnicas

### Backend (Python/Flask)
- Procesamiento de SRT con análisis inteligente
- Soporte para múltiples proveedores de IA
- Logs en tiempo real vía Server-Sent Events (SSE)
- Progreso en vivo con polling
- Normalizador de mayúsculas
- Caché de glosarios entre chunks

### Frontend (HTML/CSS/JavaScript)
- Interfaz responsiva
- Selector dinámico de modelos
- Streaming de logs
- Timer en tiempo real
- Descarga automática
- Historial de traducciones

## 🐛 Troubleshooting

### "No hay OPENAI_API_KEY"
- Verifica que tu `.env` esté en la raíz del proyecto
- Asegúrate de que `docker-compose.yml` tiene acceso al `.env`
- Reconstruye: `docker-compose down && docker-compose up --build`

### Los logs no aparecen
- Usa 1 worker en Gunicorn (ya configurado por defecto)
- Verifica que tu navegador no bloquea EventSource

### Traducción muy lenta
- Prueba con "Por bloques" para ahorrar tokens
- Usa un modelo más rápido (ej: GPT-3.5-turbo, deepseek-chat)

## 📝 Licencia

MIT

## 👤 Autor

Sergio García - [@sergiogarciaj](https://github.com/sergiogarciaj)

## 🙏 Agradecimientos

- OpenAI por la API de GPT
- Deepseek por su API compatible
- Flask por el framework web
- Gunicorn por el servidor

---

⭐ Si te útil, déjame una estrella en GitHub
