# Vector52 Backend

**Owner:** Franco

**Integraciones:** Saúl

**Consumidores API:** Omar + Jhamil

**Stack:** Python 3.11+, FastAPI, Pydantic, HTTPX, web3.py, pytest y Ruff

## Estado implementado

- `GET /healthz`;
- `POST /v1/claim-audit`;
- `GET /v1/wallets/{chain_id}/{address}/flow` mediante Alchemy Transfers API;
- endpoints de casos, evidencia, paquete y verificación;
- provider Ethereum RPC y provider The Graph;
- Evidence Vault con SHA-256;
- modelos y módulos iniciales de protocol, contribution, claims y packaging;
- redacción de credenciales en errores de transporte;
- CORS explícito mediante `V52_CORS_ORIGINS`;
- pruebas unitarias.

La suite fue verificada el 12 de septiembre: **73 tests pasaron**. Esto valida adquisición, modelos, configuración, CORS, evidencia, providers y wallet flow; no prueba un Claim Audit forense completo. `UniswapV3Resolver`, Contribution Analysis, predicados y auditor todavía son stubs, y el endpoint público devuelve `UNKNOWN` de forma intencional.

## Trabajo Buildathon

- Franco: Alchemy Ethereum/Avalanche, RPC HSK separado, reconciliación, endpoints y pruebas.
- Saúl: conectar The Graph, Relayer/x402 y contratos/subgraph.
- Omar + Jhamil: congelar con Franco los schemas consumidos por frontend.

## Ejecutar

```bash
python -m venv .venv
python -m pip install -e ".[dev]"
python -m pytest
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Copiar `.env.example` a `.env` y completar valores localmente. `.env` nunca se versiona.

Para conectar un frontend desplegado, configurar una allowlist exacta:

```text
V52_ENV=production
V52_CORS_ORIGINS=https://vector52.vercel.app
```

No usar `*` ni exponer URLs de Alchemy/The Graph al navegador.

## Cambios obligatorios

- reemplazar `V52_RPC_URL` único por configuración por red;
- verificar `eth_chainId` al iniciar cada adapter;
- conservar endpoint/keys redactados en evidencia y errores;
- añadir `/v1/providers/status`;
- acordar compatibilidad entre `/v1/claim-audit` existente y `/v1/audits` canónico;
- añadir endpoints Agent Access descritos en el contrato oficial;
- evitar guardar evidencia sensible on-chain.
