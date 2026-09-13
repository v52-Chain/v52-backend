# Guía de Integración — DeFi Subgraph Intel (The Graph: HSK / Avalanche / Ethereum)

> Complementa [`API.md` §1.6 y §3.17](./API.md#317-defi-subgraph-intel--hsk--avalanche--ethereum-mainnet),
> [`FUNCIONAMIENTO.md` §7.3](./FUNCIONAMIENTO.md#73-the-graph-provider-l1-e-interpolación-de-api_key)
> y [`X402_MCP.md`](./X402_MCP.md) (protocolo de pago). Este documento explica
> **qué** se integró, **por qué** se tomaron esas decisiones y **cómo**
> configurar o extender cada cadena.

---

## 1. Objetivo

Vector52 ya usaba The Graph como fuente L1 (`app/providers/the_graph.py`)
para un único subgrafo fijo (Uniswap V3, Ethereum Mainnet), consumido por el
pipeline de auditoría de una transacción puntual. Esta integración añade una
segunda superficie, independiente del pipeline de auditoría: un **escáner de
puntos vitales DeFi** multi-cadena — pools/pairs (los contratos que ejecutan
swaps) y su actividad reciente — para **HSK Chain, Avalanche C-Chain y
Ethereum Mainnet**, siguiendo el mismo principio rector de todo el backend:

> *La evidencia nunca se inventa. Si una fuente no está configurada o falla,
> eso se reporta honestamente — nunca se rellena con datos simulados.*

## 2. Cómo se eligió qué indexar por cadena

Este entorno no tenía acceso a un servidor MCP dedicado de catálogo de
subgrafos, así que la selección se hizo directamente contra la documentación
oficial de cada red:

- **Ethereum Mainnet:** ya existía un subgrafo verificado y probado en este
  repo — Uniswap V3 (`5zvR82QoaXYFyDEKLZ9t6v9adgnptxYpKpSbxtgVENFV`,
  `app/providers/the_graph.py`, cubierto por `tests/test_providers.py`). Se
  mantiene como el subgrafo por defecto de Ethereum (fallback de
  `V52_GRAPH_ENDPOINT`/`V52_GRAPH_API_KEY`).
- **Avalanche C-Chain:** la mayoría de los DEX de Avalanche (Trader Joe,
  Pangolin, etc.) publican subgrafos en el mismo formato que el subgrafo V2
  de Uniswap (`pairs`/`reserve0`/`reserve1`/`swaps`). En vez de fijar un
  `subgraph_id` de memoria — y arriesgarnos a apuntar a un despliegue
  incorrecto o desactualizado sin poder verificarlo en este entorno — la
  integración deja `V52_GRAPH_ENDPOINT_AVALANCHE` vacío por defecto y
  documenta cómo encontrar el subgrafo correcto (§3).
- **HSK Chain:** se consultó
  <https://docs.hskchain.net/docs/Build-on-HashKey-Chain/Tools/Subgraph>
  directamente. Esa guía confirma que **The Graph es el servicio de
  indexación soportado** (`hashkeychain`, `eip155:177`), pero **no publica
  ningún subgrafo hosteado ni ID de ejemplo** — cada proyecto debe desplegar
  el suyo (`graph init --protocol ethereum --network hashkeychain`, luego
  `graph deploy --product hosted-service <user>/<name>`). Por eso esta
  integración **crea un subgrafo nuevo** (scaffold, §4) en vez de intentar
  "usar uno existente" que no existe.

Esta decisión (config-driven, sin IDs de subgrafo de terceros hardcodeados
para Avalanche/HSK) es deliberada: `app/providers/the_graph.py` ya declara
como regla que el API key nunca se filtra y que un fallo de proveedor se
marca `DEGRADED`/`FAILED`, nunca se enmascara. Adivinar un `subgraph_id` y
presentarlo como "el subgrafo oficial de Trader Joe" sin poder verificarlo
en vivo violaría exactamente esa regla.

## 3. Cómo configurar cada cadena

Cada cadena es independiente y opcional (`app/providers/factory.py:configured_graph_chains`).
Un chequeo de estado (`GET /v1/intel/defi/status`, gratuito) reporta
`configured: false` con un mensaje accionable para cualquier cadena sin
configurar — nunca datos inventados.

| Variable | Cadena | Notas |
| :--- | :--- | :--- |
| `V52_GRAPH_ENDPOINT_ETHEREUM` / `_API_KEY_ETHEREUM` / `_SCHEMA_ETHEREUM` | Ethereum Mainnet | Si se dejan vacías, caen al `V52_GRAPH_ENDPOINT`/`V52_GRAPH_API_KEY` legacy (compatibilidad hacia atrás). `schema` por defecto: `uniswap_v3`. |
| `V52_GRAPH_ENDPOINT_AVALANCHE` / `_API_KEY_AVALANCHE` / `_SCHEMA_AVALANCHE` | Avalanche C-Chain | Buscar un subgrafo verificado en <https://thegraph.com/explorer> filtrando por Avalanche (ej. Trader Joe, Pangolin). `schema` por defecto: `uniswap_v2`. |
| `V52_GRAPH_ENDPOINT_HSK` / `_API_KEY_HSK` / `_SCHEMA_HSK` | HSK Chain | No hay subgrafo público — desplegar `subgraph/hsk-core/` (§4) u otro propio. `schema` por defecto: `uniswap_v2`. |

`schema` selecciona qué familia de query habla `app/api/defi_core.py`:

- **`uniswap_v3`** — entidad `pools`, con `feeTier`, `liquidity`,
  `totalValueLockedUSD` (Uniswap V3 y forks de rango concentrado).
- **`uniswap_v2`** — entidad `pairs`, con `reserve0`/`reserve1`/`reserveUSD`
  (Uniswap V2 y la gran mayoría de sus forks — Trader Joe V1, Pangolin,
  SushiSwap clásico, etc.).

Verificar en vivo que la configuración es correcta:
```bash
curl http://localhost:8000/v1/intel/defi/status | jq
```

## 4. HSK: subgraph nuevo (`subgraph/hsk-core/`)

Ver [`subgraph/hsk-core/README.md`](../subgraph/hsk-core/README.md) para el
detalle completo. Resumen:

- Manifest (`subgraph.yaml`) con un data source de **Factory** (escucha
  `PairCreated`) y un **template de Pair** que se instancia dinámicamente por
  cada par nuevo — el patrón estándar de un subgrafo estilo Uniswap V2.
  Mapea a la misma forma de entidades (`Pair`, `Token`, `Swap`) que la query
  `uniswap_v2` de `app/api/defi_core.py` ya espera, así que una vez
  desplegado solo hace falta apuntar `V52_GRAPH_ENDPOINT_HSK` a la URL
  resultante.
- **No está desplegado ni wireado por defecto.** Los dos placeholders en
  `subgraph.yaml` (`FACTORY_ADDRESS_PLACEHOLDER`,
  `FACTORY_START_BLOCK_PLACEHOLDER`) deben reemplazarse con una dirección de
  contrato **verificada de forma independiente** en el explorador de HSK
  antes de desplegar — nunca copiada de otra cadena ni adivinada. Hasta que
  eso pase, `V52_GRAPH_ENDPOINT_HSK` se queda vacío y el backend lo reporta
  honestamente como `UNCONFIGURED`.
- Este entorno no tiene Node/`graph-cli` instalado, así que el scaffold no
  se compiló (`graph codegen && graph build`) en esta sesión — sigue el
  patrón estándar de un subgrafo Uniswap-V2 (mismos eventos, misma forma de
  entidades), pero cualquiera que lo despliegue debe correr `codegen`/`build`
  y resolver los tipos generados de AssemblyScript localmente primero.

## 5. Endpoints — resumen (ver `API.md` §3.17 para el detalle completo)

| Endpoint | Método | Protección | Qué hace |
| :--- | :--- | :--- | :--- |
| `/v1/intel/defi/status` | GET | Público | Un query `_meta` por cadena — solo estado de indexación, nunca pools/swaps. |
| `/v1/agent/intel/defi/pools` | POST | x402 (400) | Top pools/pairs por liquidez de una cadena. |
| `/v1/agent/intel/defi/pool-activity` | POST | x402 (900) | Swaps recientes de un pool/pair específico. |
| `/v1/agent/intel/defi/scan` | POST | x402 (2500) | Agrega `status` + `pools` de varias cadenas en una sola llamada. |

## 6. §4 — Por qué estas tres tarifas x402

Siguiendo la matriz de protección ya existente en `API.md` §3.14 (pública
para bienes de bajo costo/alto valor social, x402 para lo que consume cuota
de proveedores externos), las tres nuevas rutas pagadas se tarifican por
costo/valor de la consulta (`app/config.py`, `V52_X402_DEFI_*_PRICE`):

1. **`pools` (400 atomic units)** — una sola query GraphQL a un subgrafo, el
   nivel más barato, comparable a una lectura simple.
2. **`pool-activity` (900 atomic units)** — un drill-down dirigido a un pool
   específico; más valioso para un agente que ya identificó un objetivo.
3. **`scan` (2500 atomic units)** — hace fan-out a **todas** las cadenas
   solicitadas (`status` + `pools` por cada una), multiplicando el costo de
   proveedor por el número de cadenas; el más caro por diseño.

Todas reutilizan el mismo servidor/facilitador x402 ya configurado
(`app/payments/x402.py:configure_x402`) — no se duplicó infraestructura de
pago, solo se agregaron entradas al diccionario `routes` (mismo patrón que
`X402_MCP.md` §7 ya documentaba para extender a un endpoint nuevo).

## 7. Qué se mantuvo intacto

- **`/v1/providers/status`** conserva `data.the_graph.status` y
  `.network` exactamente como estaban; solo gana `data.the_graph.chains`
  (aditivo).
- **`/v1/agent/capabilities`** conserva `endpoint`/`amount_atomic` del canal
  de wallet-flow; solo gana el objeto `defi_intel` (aditivo).
- El proveedor `TheGraphProvider` (`app/providers/the_graph.py`) no cambió —
  se generalizó su *instanciación* por cadena en
  `app/providers/factory.py:get_graph_provider_for_chain`, pero la clase y
  su contrato (`query()`, `_meta`, redacción de secretos) son los mismos que
  ya cubrían `tests/test_providers.py`.

## 8. Cobertura de pruebas

`tests/test_defi_intel.py` (20 pruebas, sin red real — The Graph se mockea
con `respx`, igual que `tests/test_wallet_flow.py` mockea Alchemy):

- Resolución de configuración por cadena y fallback legacy de Ethereum.
- Validación de `schema` (`uniswap_v3`/`uniswap_v2` únicamente).
- `get_chain_status`, `run_pools_scan`, `run_pool_activity`, `run_full_scan` —
  parseo de ambas familias de query, propagación de `_meta`/warnings, y
  `HTTPException(503)` cuando una cadena no está configurada.
- Endpoint público `/v1/intel/defi/status` end-to-end.
- Los tres endpoints pagados fallan cerrado (`503`) cuando x402 está
  deshabilitado, y devuelven datos cuando x402 y el subgrafo están
  configurados.
- Registro de rutas x402 con la tarifa correcta por endpoint.
- Los campos aditivos en `/v1/providers/status` y `/v1/agent/capabilities`
  no rompen los campos existentes.
