# Contrato Backend ↔ MCP de Vector52

## Flujo autorizado

```text
Claude / Codex / cliente MCP
            │ tool vector52_wallet_flow
            ▼
       vector52-mcp
            │ POST sin pago
            ▼
v52-backend responde HTTP 402 + PAYMENT-REQUIRED
            │
            ▼
MCP valida Fuji + USDC + precio + receptor + límites
            │ firma EIP-3009 y reintenta
            ▼
Facilitator liquida ──> backend ejecuta Alchemy ──> resultado MCP
```

La PWA no llama directamente al MCP y nunca recibe su private key. Para mostrar el estado de Agent Access consume exclusivamente:

- `GET /v1/integrations/mcp/status`
- `GET /v1/integrations/mcp/tools`

## Endpoints de producto

| Servicio | Endpoint/tool | Pago | Uso |
|---|---|---:|---|
| Backend | `GET /v1/agent/capabilities` | No | Red, activo, receptor, precio y readiness. |
| Backend | `POST /v1/agent/investigations/wallet-flow` | x402 | Investigación compartida con el canal web. |
| MCP | `GET /health` | No | Identidad y salud del proceso. |
| MCP | `GET /capabilities` | No | Handshake verificable y catálogo vivo. |
| MCP | `vector52_status` | No | Diagnóstico agente → MCP → backend. |
| MCP | `vector52_wallet_flow` | x402 | Descubre precio, paga una vez y devuelve el resultado. |

## Configuración cruzada

En `v52-mcp`:

```dotenv
V52_BACKEND_URL=https://v52-backend.onrender.com
X402_ALLOWED_HOSTS=v52-backend.onrender.com
```

En `v52-backend`, después de desplegar el MCP:

```dotenv
V52_MCP_SERVER_URL=https://TU-MCP.example/mcp
```

No apuntar `V52_MCP_SERVER_URL` a localhost desde Render. El MCP debe tener una URL pública HTTPS y autenticación para clientes autorizados.

## Estados para el frontend

- `UNAVAILABLE`: no existe URL MCP configurada.
- `UNKNOWN`: URL inválida, servicio inaccesible o handshake incompatible.
- `READY`: `/health` identifica `vector52-mcp`, el backend objetivo está listo y aparecen `vector52_status` + `vector52_wallet_flow`.

El frontend no debe convertir `UNKNOWN` en conectado. Un cold start puede resolverse reintentando el endpoint de estado con backoff, sin iniciar pagos.

## Precio actual de Buildathon

- Modelo agente: `PER_REQUEST`.
- Red: Avalanche Fuji (`eip155:43113`).
- Activo: USDC Fuji, 6 decimales.
- Precio: `1000` atómicos = `0.001 USDC` por `wallet-flow`.

El eventual paquete web (`2 USDC / 30 consultas`) es un producto distinto y no debe mezclarse con este precio M2M.

## Evidencia de prueba E2E

El 12/09/2026 una llamada a `vector52_wallet_flow`:

- descubrió el precio del backend;
- pagó exactamente `0.001 USDC`;
- obtuvo respuesta `AGENT_X402` y `request_id` real;
- liquidó la transacción Fuji `0xb8b4dc3dbaa9d802e56cabbd0f5d16379c1db156aceca9474e7e3feda89a7c06`.

La prueba devolvió listas vacías para la wallet consultada; esto es un resultado válido del dataset de transferencias directas, no evidencia de ausencia absoluta de actividad onchain.
