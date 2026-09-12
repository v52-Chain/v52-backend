# Backend

**Owner:** Saúl  
**Collaborators:** Omar for API/orchestration; Jhamil for protocol/claims  
**Stack:** Python 3.11+, FastAPI, Pydantic, HTTPX, web3.py, pytest and Ruff  
**Initial branch:** `feat/saul-fastapi-foundation`  
**Status:** `IN PROGRESS` from 8 September

## Estado implementado

- `pyproject.toml` con dependencias fijadas;
- `app/main.py`;
- `GET /healthz`;
- `POST /v1/claim-audit`;
- endpoints de casos, evidencia, paquete y verificación;
- provider Ethereum RPC y provider The Graph;
- Evidence Vault con SHA-256;
- modelos y módulos iniciales de protocol, contribution, claims y packaging;
- redacción de credenciales en errores de transporte;
- CORS explícito mediante `V52_CORS_ORIGINS`;
- pruebas unitarias (incluye llamadas reales a RPC/The Graph, sin mocks; ver `docs/FUNCIONAMIENTO.md` §12).

La suite fue verificada el 12 de septiembre: **72 tests pasaron** (4 adicionales del gateway de The Graph se omiten automáticamente si `V52_GRAPH_API_KEY` no está configurada). Esto valida adquisición, modelos, configuración, CORS y evidencia; no prueba un Claim Audit forense completo. `UniswapV3Resolver`, Contribution Analysis, predicados y auditor todavía son stubs, y el endpoint público devuelve `UNKNOWN` de forma intencional. El endpoint `GET /v1/wallets/{chain_id}/{address}/flow` (Alchemy Transfers API) fue retirado del alcance de este backend.

## Folder ownership

- `app/api/` — Saúl; Omar reviews contracts.
- `app/models/` — Saúl with domain input from Jhamil.
- `app/providers/` — Saúl.
- `app/evidence/` — Saúl.
- `app/storage/` — Saúl; vault, MongoDB and optional cache adapters.
- `app/protocols/` — Jhamil.
- `app/contribution/` — Jhamil.
- `app/claims/` — Jhamil + Omar.
- `app/packaging/` — Saúl.
- `app/orchestration/` — Omar; all developers review.

No secrets may be returned by API errors or logs.

See [`docs/FUNCIONAMIENTO.md`](docs/FUNCIONAMIENTO.md) for the full architecture and [`docs/API.md`](docs/API.md) for the endpoint reference.

---

## Guía de Ejecución en Otra Máquina (Windows / Linux)

### 1. Requisitos Previos

- **Python 3.11+** instalado.
- **Git** para clonar el repositorio.
- Acceso a internet (para instalar dependencias vía pip y conectar a RPC/The Graph si se configuran).

Comprobar versión de Python:
```bash
python --version   # o python3 --version en Linux
```

---

### 2. Clonar el Repositorio y Navegar a la Carpeta

```bash
git clone <URL_DEL_REPOSITORIO>
cd v52-backend
```

> **Nota:** Todos los comandos siguientes asumen que estás dentro de la raíz de este repositorio (`v52-backend/`).

---

### 3. Crear y Activar el Entorno Virtual

#### En Linux / macOS:
```bash
# Crear entorno virtual
python3 -m venv .venv

# Activar entorno virtual
source .venv/bin/activate
```

#### En Windows (PowerShell):
```powershell
# Crear entorno virtual
python -m venv .venv

# Activar entorno virtual
.venv\Scripts\Activate.ps1
```
*(Si PowerShell bloquea la ejecución de scripts, ejecuta antes: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`)*

#### En Windows (CMD):
```cmd
python -m venv .venv
.venv\Scripts\activate.bat
```

---

### 4. Instalar Dependencias

Actualizar `pip` e instalar el proyecto en modo editable junto con las dependencias base y de desarrollo:

```bash
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

*(Opcional: Si se requiere soporte para MongoDB P1, instalar con: `pip install -e ".[dev,mongo]"`)*

---

### 5. Configurar Variables de Entorno

El backend busca el archivo `.env` en la raíz del repositorio. Puedes copiar la plantilla base `.env.example`:

#### Linux / macOS:
```bash
cp .env.example .env
```

#### Windows (PowerShell):
```powershell
Copy-Item .env.example .env
```

#### Windows (CMD):
```cmd
copy .env.example .env
```

Edita el archivo `.env` según tus necesidades:
```env
V52_ENV=development
V52_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
V52_RPC_URL=https://your-ethereum-rpc-endpoint   # Opcional en dev, requerido en prod
V52_GRAPH_ENDPOINT=https://gateway.thegraph.com/api/{api_key}/subgraphs/id/...
V52_GRAPH_API_KEY=tu_api_key_aqui
V52_DATA_DIR=./evidence_vault
V52_STORAGE_BACKEND=file
V52_CACHE_ENABLED=false
```

Para conectar un frontend desplegado en producción, configura una allowlist exacta (nunca uses `*` ni expongas URLs de RPC/The Graph al navegador):
```env
V52_ENV=production
V52_CORS_ORIGINS=https://vector52.vercel.app
```

---

### 6. Ejecutar el Servidor de Desarrollo

Con el entorno virtual activado y dentro de `backend/`:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- **Healthcheck:** [http://localhost:8000/healthz](http://localhost:8000/healthz)
- **Documentación interactiva (Swagger / OpenAPI):** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Documentación alternativa (Redoc):** [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

### 7. Ejecución de Pruebas y Linter

Para verificar que todo funcione correctamente en la máquina:

```bash
# Correr suite de pruebas con pytest
pytest

# Correr linter con Ruff
ruff check .
```
