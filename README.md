# Vector52 Backend

**Owner:** Franco

**Integraciones:** Saúl

**Consumidores API:** Omar + Jhamil

**Stack:** Python 3.11+, FastAPI, Pydantic, HTTPX, web3.py, pytest y Ruff

## Estado implementado

- `GET /healthz`;
- `POST /v1/claim-audit`;
- Wallet Flow mediante Alchemy Transfers API, con `from_date` y `to_date` opcionales, publicado solamente detrás de las fronteras WEB y AGENT;
- endpoints de casos, evidencia, paquete y verificación;
- provider Ethereum RPC y provider The Graph;
- Evidence Vault con SHA-256;
- modelos y módulos iniciales de protocol, contribution, claims y packaging;
- redacción de credenciales en errores de transporte;
- CORS explícito mediante `V52_CORS_ORIGINS`;
- pruebas unitarias.
- challenge de wallet single-use, verificación EVM y bearer session para la PWA;
- endpoint web autenticado que reutiliza el motor Wallet Flow;
- capabilities y endpoint máquina protegido por x402 para `v52-mcp`;
- configuración x402 fail-closed: si no puede verificar/liquidar, no ejecuta el recurso.

La suite contiene **81 pruebas y todas pasan**. Las pruebas de acceso cubren challenge firmado, nonce de un solo uso, autenticación web obligatoria, retiro del endpoint anónimo y configuración segura del middleware x402. `UniswapV3Resolver`, Contribution Analysis, predicados y auditor todavía son stubs, y el endpoint público devuelve `UNKNOWN` de forma intencional.

## Contrato de acceso

| Método | Ruta | Consumidor | Protección |
|---|---|---|---|
| `POST` | `/v1/auth/wallet/challenge` | PWA | pública; nonce de 5 minutos |
| `POST` | `/v1/auth/wallet/verify` | PWA | firma EVM del challenge |
| `GET` | `/v1/auth/wallet/me` | PWA | bearer session de 8 horas |
| `POST` | `/v1/web/investigations/wallet-flow` | PWA | bearer session |
| `GET` | `/v1/agent/capabilities` | MCP | pública; no expone secretos |
| `POST` | `/v1/agent/investigations/wallet-flow` | MCP | x402 exact EVM |

Las rutas web y agente terminan en la misma función determinista `acquire_wallet_flow`; cambian autenticación y pago, no el resultado forense. Ver [`ACCESS-CONTRACT.md`](../../ACCESS-CONTRACT.md).

## Ventanas temporales

Ejemplo:

```json
POST /v1/web/investigations/wallet-flow
{
  "target_address": "0x...",
  "chain_id": 1,
  "limit": 25,
  "from_date": "2026-08-01",
  "to_date": "2026-08-31"
}
```

Alchemy entrega transferencias en orden descendente. El adapter pagina hasta 10 páginas por dirección, filtra por `metadata.blockTimestamp` y detiene la búsqueda al cruzar el límite inferior. La respuesta advierte que una búsqueda acotada sin resultados no demuestra ausencia de actividad.

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

Para Reown y x402:

```text
V52_PUBLIC_ORIGIN=https://vector52.vercel.app
V52_X402_ENABLED=false
V52_X402_FACILITATOR_URL=
V52_X402_FACILITATOR_API_KEY=
V52_X402_PAY_TO=
V52_X402_NETWORK=eip155:43113
V52_X402_ASSET=0x5425890298aed601595a70AB815c96711a31Bc65
V52_X402_WALLET_FLOW_PRICE=1000
```

Activar x402 solamente después de demostrar `verify` y `settle` en Fuji. Challenges/sesiones están en memoria para el MVP; usar Redis, TTL y rate limiting antes de escalar horizontalmente.

## Cambios obligatorios

- reemplazar `V52_RPC_URL` único por configuración por red;
- verificar `eth_chainId` al iniciar cada adapter;
- conservar endpoint/keys redactados en evidencia y errores;
- añadir `/v1/providers/status`;
- acordar compatibilidad entre `/v1/claim-audit` existente y `/v1/audits` canónico;
- conectar `v52-mcp` a los endpoints Agent Access ya implementados;
- evitar guardar evidencia sensible on-chain.
