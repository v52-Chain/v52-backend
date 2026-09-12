# Vector52 Backend

**Owner:** Franco

**Integraciones:** Saul

**Consumidores API:** Omar + Jhamil

**Stack:** Python 3.11+, FastAPI, Pydantic, HTTPX, web3.py, pytest y Ruff

## Estado actual

- `GET /healthz`
- `GET /v1/providers/status`
- `GET /v1/rpc/transactions/{chain}/{tx_hash}`
- `GET /v1/rpc/receipts/{chain}/{tx_hash}`
- `POST /v1/audits`
- `GET /v1/audits/{job_id}`
- `GET /v1/jobs/{job_id}` como alias de compatibilidad
- `POST /v1/claim-audit` como endpoint legacy compatible
- endpoints de casos, evidencia, paquete y verificacion
- provider RPC uniforme para Alchemy Ethereum, Alchemy Avalanche y HSK RPC
- validacion de `eth_chainId`
- Evidence Vault con SHA-256 para raw payloads
- reconciliacion Graph/RPC con estados tipados

La suite local actual pasa con mocks: **82 tests**.

## Configuracion

Copiar `.env.example` a `.env` y completar valores localmente. `.env` nunca se versiona.

```dotenv
ALCHEMY_ETH_RPC_URL=
ALCHEMY_AVAX_RPC_URL=
HSK_RPC_URL=
RPC_TIMEOUT_MS=12000
RPC_MAX_RETRIES=2
```

`V52_RPC_URL` sigue aceptado como fallback legacy para Ethereum, pero el nombre preferido es
`ALCHEMY_ETH_RPC_URL`.

Las URLs de providers son backend-only. No deben aparecer en `VITE_*`, respuestas HTTP, logs,
screenshots ni expedientes `.v52`.

## Ejecutar

```bash
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev]"
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## Cadenas

Aliases aceptados por endpoints RPC:

| Chain | Aliases | Provider |
|---|---|---|
| Ethereum Mainnet | `ethereum`, `eth`, `1` | Alchemy |
| Avalanche | `avalanche`, `avax`, `43114`, `43113`, `fuji` | Alchemy |
| HSK | `hsk`, `hashkey`, `177` | HSK RPC |

`ALCHEMY_AVAX_CHAIN_ID` permite usar Mainnet `43114` o Fuji `43113` con el mismo adapter.

## Reconciliacion Graph/RPC

Estados permitidos:

```text
CORROBORATED
MISMATCH
INDEXER_LAG_SUSPECTED
RPC_UNAVAILABLE
INSUFFICIENT_DATA
```

Un mismatch se reporta como warning con procedencia preservada. No es una conclusion automatica
de fraude, identidad ni ownership.

## Pendiente de otros repos/equipo

- Saul: fixtures Graph finales, contratos, subgraph HSK y pruebas x402/Avalanche.
- Omar + Jhamil: consumo de los endpoints versionados desde frontend y Agent Access.
- MCP/onchain: settlement real, anchors HSK y ABIs/direcciones verificadas.
