# Vector52 Backend — Referencia Completa de la API REST

> **Versión de API:** v1 (0.1.0)  
> **Protocolo:** HTTP/1.1 y HTTP/2  
> **Formato de Intercambio:** `application/json` (UTF-8) / `multipart/form-data` para verificación de archivos  
> **Raíz Base:** `/` y `/v1`  
> **Documentación Interactiva:** Swagger UI en `/docs` | ReDoc en `/redoc` | OpenAPI JSON en `/openapi.json`  

---

## Tabla de Contenidos

1. [Visión General y Convenciones](#1-visión-general-y-convenciones)
   - 1.1 [Base URL y Versionado](#11-base-url-y-versionado)
   - 1.2 [Autenticación y Seguridad](#12-autenticación-y-seguridad)
   - 1.3 [Política de CORS](#13-política-de-cors)
   - 1.4 [Códigos de Estado HTTP](#14-códigos-de-estado-http)
   - 1.5 [Estructura de Errores](#15-estructura-de-errores)
   - 1.6 [Configuración RPC y The Graph](#16-configuración-rpc-y-the-graph)
2. [Diccionario de Esquemas y Enumeraciones](#2-diccionario-de-esquemas-y-enumeraciones)
   - 2.1 [Enumeraciones (Enums)](#21-enumeraciones-enums)
   - 2.2 [Modelos de Petición y Respuesta](#22-modelos-de-petición-y-respuesta)
3. [Catálogo Detallado de Endpoints](#3-catálogo-detallado-de-endpoints)
   - 3.1 [`GET /healthz` — Comprobación de Salud](#31-get-healthz--comprobación-de-salud)
   - 3.2 [`GET /v1/providers/status` — Estado de Proveedores RPC/Graph](#32-get-v1providersstatus--estado-de-proveedores-rpcgraph)
   - 3.3 [`GET /v1/rpc/transactions/{chain}/{tx_hash}` — Obtener Transacción](#33-get-v1rpctransactionschaintx_hash--obtener-transacción)
   - 3.4 [`GET /v1/rpc/receipts/{chain}/{tx_hash}` — Obtener Recibo](#34-get-v1rpcreceiptschaintx_hash--obtener-recibo)
   - 3.5 [`POST /v1/audits` — Crear Auditoría](#35-post-v1audits--crear-auditoría)
   - 3.6 [`GET /v1/audits/{job_id}` — Estado de Auditoría](#36-get-v1auditsjob_id--estado-de-auditoría)
   - 3.7 [`POST /v1/claim-audit` — Iniciar Auditoría de Reclamo](#37-post-v1claim-audit--iniciar-auditoría-de-reclamo)
   - 3.8 [`GET /v1/cases/{case_id}` — Consultar Caso Persistido](#38-get-v1casescase_id--consultar-caso-persistido)
   - 3.9 [`GET /v1/cases/{case_id}/evidence` — Listar Evidencias del Caso](#39-get-v1casescase_idevidence--listar-evidencias-del-caso)
   - 3.10 [`GET /v1/cases/{case_id}/package` — Descargar Contenedor `.v52.zip`](#310-get-v1casescase_idpackage--descargar-contenedor-v52zip)
   - 3.11 [`POST /v1/verify` — Verificar Integridad de Paquete `.v52.zip`](#311-post-v1verify--verificar-integridad-de-paquete-v52zip)
   - 3.12 [Autenticación Web y Wallet Flow para Frontend (SIWE)](#312-autenticación-web-y-wallet-flow-para-frontend-siwe)
     - 3.12.1 [`POST /v1/auth/wallet/challenge` — Generar Desafío SIWE](#3121-post-v1authwalletchallenge--generar-desafío-siwe)
     - 3.12.2 [`POST /v1/auth/wallet/verify` — Verificar Firma y Emitir Sesión](#3122-post-v1authwalletverify--verificar-firma-y-emitir-sesión)
     - 3.12.3 [`GET /v1/auth/wallet/me` — Identidad de Sesión Actual](#3123-get-v1authwalletme--identidad-de-sesión-actual)
     - 3.12.4 [`POST /v1/web/investigations/wallet-flow` — Flujo Forense Web Autenticado](#3124-post-v1webinvestigationswallet-flow--flujo-forense-web-autenticado)
   - 3.13 [Canal de Agentes e IAs con x402 (M2M)](#313-canal-de-agentes-e-ias-con-x402-m2m)
     - 3.13.1 [`GET /v1/agent/capabilities` — Capacidades de Pago x402](#3131-get-v1agentcapabilities--capacidades-de-pago-x402)
     - 3.13.2 [`POST /v1/agent/investigations/wallet-flow` — Flujo Forense Pagado con x402](#3132-post-v1agentinvestigationswallet-flow--flujo-forense-pagado-con-x402)
   - 3.14 [Matriz de Protección y Políticas x402 (Humanos vs Agentes Artificiales)](#314-matriz-de-protección-y-políticas-x402-humanos-vs-agentes-artificiales)
   - 3.16 [Anclaje HSK (`V52EvidenceRegistry`)](#316-anclaje-hsk-v52evidenceregistry)
     - 3.16.1 [`POST /v1/cases/{case_id}/anchor` — Anclar el manifest de un caso](#3161-post-v1casescase_idanchor--anclar-el-manifest-de-un-caso)
     - 3.16.2 [`GET /v1/anchors/{manifest_root}` — Consultar procedencia de un anchor](#3162-get-v1anchorsmanifest_root--consultar-procedencia-de-un-anchor)
   - 3.17 [DeFi Subgraph Intel — HSK / Avalanche / Ethereum Mainnet](#317-defi-subgraph-intel--hsk--avalanche--ethereum-mainnet)
     - 3.17.1 [`GET /v1/intel/defi/status` — Estado del subgrafo por cadena (Gratuito)](#3171-get-v1inteldefistatus--estado-del-subgrafo-por-cadena-gratuito)
     - 3.17.2 [`POST /v1/agent/intel/defi/pools` — Top pools/pairs (x402)](#3172-post-v1agentinteldefipools--top-poolspairs-por-liquidez-x402-400-atomic-units)
     - 3.17.3 [`POST /v1/agent/intel/defi/pool-activity` — Swaps recientes (x402)](#3173-post-v1agentinteldefipool-activity--swaps-recientes-de-un-pool-x402-900-atomic-units)
     - 3.17.4 [`POST /v1/agent/intel/defi/scan` — Escaneo multi-cadena (x402)](#3174-post-v1agentinteldefiscan--escaneo-multi-cadena-x402-2500-atomic-units)
4. [Casos de Error y Validaciones de Entrada](#4-casos-de-error-y-validaciones-de-entrada)
5. [Guía de Integración para Clientes (TypeScript y Python)](#5-guía-de-integración-para-clientes-typescript-y-python)

---

## 1. Visión General y Convenciones

### 1.1 Base URL y Versionado

La API de Vector52 utiliza prefijos de ruta para separar las rutas de control del sistema de las rutas de negocio:
- Rutas del sistema: `/healthz`
- Rutas versionadas de la API: `/v1/*`

En despliegues locales típicos:
```
http://localhost:8000
```

### 1.2 Autenticación y Seguridad

Para la fase actual (P0 / Demostración ETHOnline):
- **Sin autenticación obligatoria para clientes:** Los endpoints son públicos para facilitar la demostración de jueces y la integración del frontend de Omar.
- **Aislamiento de credenciales:** La API **nunca** devuelve claves privadas, tokens Bearer de subgrafos ni credenciales RPC a los clientes en ninguna respuesta JSON.
- **Sanitización de errores:** Los errores 500 internos jamás exponen stack traces ni rutas del servidor.

### 1.3 Política de CORS

- **Entorno de Desarrollo (`V52_ENV=development`):**  
  Permite peticiones cruzadas originadas desde servidores de desarrollo comunes de Vite y Next.js:
  - `http://localhost:5173`
  - `http://127.0.0.1:5173`
  - `http://localhost:3000`
  - `http://127.0.0.1:3000`
  - Método permitidos: `GET`, `POST`
  - Encabezados permitidos: `Content-Type`, `Accept`, `Payment-Signature`, `Payment-Required`, `X-Payment`
- **Entorno de Producción (`V52_ENV=production`):**  
  Configurable mediante `V52_CORS_ORIGINS` (lista separada por comas). Cuando está vacío, solo se permiten orígenes que coincidan con `V52_PUBLIC_ORIGIN`.

### 1.4 Códigos de Estado HTTP

| Código | Significado | Escenario de Uso en Vector52 |
| :--- | :--- | :--- |
| **200 OK** | Petición Exitosa | Auditoría completada, caso obtenido o paquete verificado. |
| **400 Bad Request** | Error de Solicitud | Archivo ZIP inválido, archivo `manifest.json` faltante o ilegible. |
| **404 Not Found** | No Encontrado | El `case_id` especificado no existe o su paquete no ha sido generado. |
| **413 Payload Too Large** | Carga Excesiva | Archivo ZIP subido a `/v1/verify` supera los 100 MB. |
| **422 Unprocessable Entity**| Validación Fallida | Hash de transacción inválido, dirección no EVM, longitud de reclamo o chain_id no soportado. |
| **502 Bad Gateway** | Proveedor no disponible | RPC o The Graph endpoint no está accesible o devolvió error. |
| **503 Service Unavailable** | Servicio no configurado | RPC o The Graph endpoint no está configurado en `V52_*` variables. |
| **500 Internal Error** | Error del Servidor | Error no controlado. Mensaje genérico de protección activado. |

### 1.5 Estructura de Errores

#### Error de Validación Estándar (HTTP 422):
Generado automáticamente por los validadores Pydantic:
```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body", "transaction_hash"],
      "msg": "Value error, transaction_hash must be a 0x-prefixed 64-character hex string (32 bytes).",
      "input": "0x1234invalido"
    }
  ]
}
```

#### Error de Negocio / Semántico (HTTP 400 / 404):
```json
{
  "detail": "Case 'case_1_4a8b12f0_d8da6b_9f2a1b3c' not found."
}
```

### 1.6 Configuración RPC y The Graph

#### Multi-chain RPC Support

Vector52 soporta tres blockchains:
- **Ethereum Mainnet** (chain_id = 1): Alchemy RPC
- **Avalanche C-Chain** (chain_id = 43114): Alchemy RPC
- **Avalanche Fuji Testnet** (chain_id = 43113): Alchemy RPC (seleccionable)
- **HSK** (chain_id = 177): RPC separado (no disponible en Alchemy)

#### Configuración de Credenciales

**Método Recomendado (v0.1.0+):** Usar una sola clave API de Alchemy:
```
ALCHEMY_API_KEY=tu-api-key-aqui
```
El backend construye automáticamente las URLs de Ethereum y Avalanche usando los subdominios estándar de Alchemy.

**Método Alternativo:** Especificar URLs completas explícitamente (tiene prioridad):
```
ALCHEMY_ETH_RPC_URL=https://eth-mainnet.g.alchemy.com/v2/tu-key
ALCHEMY_AVAX_RPC_URL=https://avax-mainnet.g.alchemy.com/v2/tu-key
HSK_RPC_URL=https://tu-proveedor-hsk/rpc
```

**Parámetros Adicionales:**
- `RPC_TIMEOUT_MS` (default: 12000): Timeout en milisegundos para llamadas RPC
- `RPC_MAX_RETRIES` (default: 2): Reintentos en caso de fallo transitorio
- `ALCHEMY_AVAX_CHAIN_ID` (default: 43114): Configura a 43113 para usar Fuji Testnet en lugar de Mainnet

The Graph endpoint es requerido en producción:
```
V52_GRAPH_ENDPOINT=https://gateway.thegraph.com/api/{api_key}/subgraphs/id/...
V52_GRAPH_API_KEY=tu-api-key-aqui
```

**DeFi Subgraph Intel (§3.17):** además del par legacy de arriba (que sigue
siendo el fallback de Ethereum), cada cadena tiene su propio subgrafo
independiente y opcional — `V52_GRAPH_ENDPOINT_ETHEREUM` / `_AVALANCHE` /
`_HSK` (+ `_API_KEY_*` y `_SCHEMA_*`, `uniswap_v3` o `uniswap_v2`). Ver
[`SUBGRAPHS.md`](./SUBGRAPHS.md) para cómo elegir un subgrafo por cadena y
por qué HSK no trae uno por defecto.

#### Error Global No Controlado (HTTP 500):
```json
{
  "detail": "An internal error occurred. No secrets were exposed."
}
```

---

## 2. Diccionario de Esquemas y Enumeraciones

### 2.1 Enumeraciones (Enums)

#### `AuthorityLevel` (Jerarquía de Evidencia)
Cadena de caracteres que define el nivel de autoridad probatoria del registro.
- `L0_CHAIN_PRIMARY`: Registro primario de la máquina virtual Ethereum (RPC directo: tx, recibo, bloque, logs).
- `L1_INDEXED`: Registro indexado de The Graph (subgrafo Uniswap V3 y metadata `_meta`).
- `L2_DECODED`: Evento decodificado e interpretado con ABI oficial de contratos.
- `L3_DERIVED`: Datos derivados deterministas del análisis de contribución de fondos.
- `L4_ANALYST`: Predicados formales evaluados y veredicto analítico.
- `L5_AI_EXPLANATION`: Resumen explicativo generado por Inteligencia Artificial (no autoritativo).

#### `EvidenceStatus` (Estado Individual de un Registro de Evidencia)
- `PENDING`: La adquisición de este registro aún no ha comenzado.
- `RUNNING`: Solicitud en tránsito hacia el proveedor externo.
- `COMPLETE`: Adquisición exitosa, completa y sin ninguna inconsistencia.
- `PARTIAL`: Se obtuvo respuesta pero faltan campos o hubo errores controlados.
- `WARNING`: El subgrafo reportó `hasIndexingErrors: true` u otra advertencia operativa.
- `FAILED`: El proveedor rechazó la conexión o la llamada falló por completo.
- `UNKNOWN`: La transacción no existe o aún no ha sido minada en un bloque.

#### `ProviderStatus` (Estado Operativo del Proveedor)
- `OK`: El proveedor respondió satisfactoriamente dentro de la ventana de tiempo.
- `DEGRADED`: El proveedor respondió con lentitud o errores recuperables.
- `TIMEOUT`: La llamada excedió el límite de tiempo configurado (`timeout_seconds`).
- `FAILED`: Error HTTP crítico de conexión o formato devuelto por el nodo.
- `UNKNOWN`: Estado inicial previo a la ejecución.

#### `CaseStatus` (Estado Global de la Auditoría del Caso)
- `PENDING`: Caso registrado en base de datos, en cola de procesamiento.
- `RUNNING`: Pipeline de auditoría ejecutándose activamente.
- `COMPLETE`: Todas las fuentes de evidencia L0 y L1 respondieron satisfactoriamente.
- `DEGRADED`: El caso se completó pero al menos un proveedor falló, tardó o presentó advertencias.
- `FAILED`: No fue posible adquirir evidencia suficiente para continuar el proceso.

#### `Verdict` (Veredicto Determinista Formal)
- `SUPPORTED`: La evidencia probatoria sustenta plenamente la afirmación.
- `PARTIALLY_SUPPORTED`: La afirmación es parcialmente correcta, pero difieren montos, rutas o intermediarios.
- `MISLEADING`: La transacción existió pero el sujeto no realizó la acción alegada.
- `REFUTED`: La evidencia demuestra que la afirmación es falsa.
- `UNKNOWN`: La evidencia es inconclusa o insuficiente para emitir un fallo formal.

---

### 2.2 Modelos de Petición y Respuesta

#### `ClaimAuditRequest`
Payload enviado en `POST /v1/claim-audit`:

| Campo | Tipo | Requerido | Restricciones / Reglas de Validación | Descripción |
| :--- | :--- | :--- | :--- | :--- |
| `chain_id` | `integer` | **Sí** | Debe ser exactamente `1` en P0. | Identificador EIP-155 de la red. Ethereum Mainnet = 1. |
| `transaction_hash`| `string` | **Sí** | Regex: `^0x[0-9a-fA-F]{64}$` (66 caracteres). | Hash único de la transacción en Ethereum. Se normaliza a minúsculas. |
| `claim` | `string` | **Sí** | Longitud entre `1` y `1000` caracteres. | La afirmación en lenguaje natural que se desea auditar. |
| `subject` | `string` | **Sí** | Regex: `^0x[0-9a-fA-F]{40}$` (42 caracteres). | Dirección de la cuenta o contrato presuntamente involucrado. |
| `use_ai` | `boolean`| No | Por defecto: `false`. | Si es `true`, agrega una explicación en lenguaje natural (L5). |

#### `ClaimAuditResponse`
Payload devuelto en `POST /v1/claim-audit`:

| Campo | Tipo | Descripción |
| :--- | :--- | :--- |
| `case_id` | `string` | Identificador único y estable del caso generado por Vector52. |
| `status` | `CaseStatus` | Estado global resultante de la auditoría (`COMPLETE`, `DEGRADED`, `FAILED`). |
| `verdict` | `Verdict` \| `null` | Veredicto determinista asignado a la afirmación. |
| `summary` | `string` | Resumen ejecutivo del resultado de la auditoría. |
| `predicates` | `list[Predicate]` | Lista de afirmaciones lógicas descompuestas y su estado booleano. |
| `evidence_for` | `list[EvidenceRecord]`| Registros de evidencia que respaldan la afirmación. |
| `evidence_against`| `list[EvidenceRecord]`| Registros de evidencia que contradicen la afirmación. |
| `gaps` | `list[string]` | Brechas de información o pasos pendientes por resolver. |
| `warnings` | `list[string]` | Advertencias acumuladas durante la ejecución del pipeline. |
| `protocol_action` | `ProtocolAction` \| `null` | Estructura decodificada del protocolo DeFi (Uniswap V3 Swap). |
| `contribution` | `ContributionSummary` \| `null` | Desglose cuantitativo del flujo directo del sujeto. |
| `provenance` | `ProvenanceSummary` \| `null` | Resumen criptográfico de procedencia y trazabilidad de archivos. |
| `timing_ms` | `dict[string, integer]` | Tiempos de ejecución en milisegundos por cada etapa del pipeline. |

#### `EvidenceRecord`
Representa un registro individual de prueba cruda preservada:

| Campo | Tipo | Descripción |
| :--- | :--- | :--- |
| `evidence_id` | `string` | Identificador único (`ev_<source>_<hash8>_<uuid8>`). |
| `authority_level` | `AuthorityLevel` | Nivel de autoridad asignado (`L0_CHAIN_PRIMARY`, `L1_INDEXED`, etc.). |
| `chain_id` | `integer` | Identificador de red (ej. 1). |
| `source` | `string` | Nombre del proveedor (`ethereum_rpc` o `the_graph`). |
| `method` | `string` | Método RPC u operación GraphQL ejecutada. |
| `request_fingerprint`| `string` | Hash SHA-256 canónico de la petición (`sha256:<hex>`). |
| `retrieved_at` | `string` (ISO 8601) | Marca de tiempo UTC de la adquisición. |
| `raw_path` | `string` | Ruta relativa dentro de la bóveda donde reside el archivo crudo. |
| `raw_sha256` | `string` | Resumen criptográfico SHA-256 del archivo en disco. |
| `adapter_version` | `string` | Versión del adaptador que generó el registro (ej. `0.1.0`). |
| `status` | `EvidenceStatus` | Estatus individual del registro (`COMPLETE`, `WARNING`, etc.). |
| `warnings` | `list[string]` | Advertencias específicas registradas para este archivo. |
| `block_number` | `integer` \| `null` | Número de bloque reportado por la fuente (obligatorio en L1). |
| `indexing_errors` | `boolean` \| `null` | Indicador de si el subgrafo reportó errores de indexación. |
| `graph_deployment` | `string` \| `null` | Hash IPFS del despliegue del subgrafo en The Graph. |

#### `CaseRecord`
Documento de persistencia almacenado en el repositorio:

| Campo | Tipo | Descripción |
| :--- | :--- | :--- |
| `case_id` | `string` | Identificador único del caso. |
| `chain_id` | `integer` | Red EIP-155. |
| `transaction_hash`| `string` | Hash de la transacción auditada. |
| `subject` | `string` | Dirección del sujeto investigado. |
| `claim` | `string` | Texto del reclamo auditado. |
| `status` | `CaseStatus` | Estado de la auditoría. |
| `verdict` | `Verdict` \| `null` | Veredicto asignado. |
| `evidence_status` | `EvidenceStatus` | Estado agregado de las evidencias. |
| `evidence_record_ids`| `list[string]` | Lista de identificadores de evidencia asociados. |
| `created_at` | `string` (ISO 8601) | Fecha y hora UTC de creación del caso. |
| `updated_at` | `string` (ISO 8601) | Fecha y hora UTC de la última modificación. |
| `warnings` | `list[string]` | Advertencias registradas. |
| `timing_ms` | `dict[string, integer]` | Tiempos de ejecución por etapa. |

---

### 2.3 Modelos de Decodificación L2 y Transferencias ERC-20

Estos modelos Pydantic (`app/models/transfer.py`) estructuran los eventos de transferencia de tokens decodificados deterministamente desde los logs de la máquina virtual (L0) sin consultar la red:

#### `DecodedTransfer`
Representa un evento `Transfer` ERC-20 validado e indexado:

| Campo | Tipo | Restricciones / Reglas | Descripción |
| :--- | :--- | :--- | :--- |
| `token_address` | `string` | Regex: `^0x[0-9a-fA-F]{40}$` (normalizado a minúsculas). | Dirección del contrato ERC-20 que emitió el log. |
| `from_address` | `string` | Regex: `^0x[0-9a-fA-F]{40}$` (normalizado a minúsculas). | Dirección de origen de los fondos (tópico 1 decodificado). |
| `to_address` | `string` | Regex: `^0x[0-9a-fA-F]{40}$` (normalizado a minúsculas). | Dirección de destino de los fondos (tópico 2 decodificado). |
| `amount_raw` | `string` | Regex: `^(0\|[1-9][0-9]*)$`. | Monto uint256 exacto como cadena entera en base 10 (sin pérdida de precisión de float). |
| `transaction_hash`| `string` | Regex: `^0x[0-9a-fA-F]{64}$` (normalizado a minúsculas). | Hash de la transacción que produjo el evento. |
| `block_number` | `integer`| $\ge 0$. | Número del bloque en que se minó la transacción. |
| `log_index` | `integer`| $\ge 0$. | Índice posicional del log dentro del recibo de la transacción. |
| `evidence_ids` | `list[string]` | Mínimo 1 elemento, sin duplicados ni vacíos. | Identificadores de evidencia L0 de donde provino el log (linaje inmutable). |
| `token_symbol` | `string` \| `null` | Opcional. | Símbolo del token (ej. `"USDC"`, `"WETH"`). |
| `token_decimals` | `integer` \| `null`| Rango: `0` a `255`. | Cantidad de decimales del token según sus metadatos verificados. |
| `amount_formatted`| `string` \| `null`| Opcional. | Representación decimal exacta calculada sin aritmética de punto flotante. |
| `warnings` | `list[string]` | Lista de cadenas. | Advertencias emitidas durante la decodificación (ej. decimales no disponibles). |

#### `TokenMetadata`
Metadatos verificados opcionales empleados exclusivamente para dar formato a los montos:

| Campo | Tipo | Restricciones | Descripción |
| :--- | :--- | :--- | :--- |
| `address` | `string` | Regex: `^0x[0-9a-fA-F]{40}$` (minúsculas). | Dirección del contrato inteligente del token. |
| `symbol` | `string` \| `null` | Opcional. | Símbolo del token (ej. `"DAI"`). |
| `decimals` | `integer` \| `null`| Rango: `0` a `255`. | Número de decimales para la conversión de unidades base. |

---

## 3. Catálogo Detallado de Endpoints

### 3.1 `GET /healthz` — Comprobación de Salud

Verifica la operatividad del servidor HTTP y la disponibilidad básica del backend.

- **Método:** `GET`
- **Ruta:** `/healthz`
- **Autenticación:** No requerida
- **Encabezados:** Ninguno obligatorio

#### Respuesta Exitosa (HTTP 200 OK):
```json
{
  "status": "ok",
  "version": "0.1.0"
}
```

#### Ejemplo con cURL:
```bash
curl -X GET http://localhost:8000/healthz
```

#### Ejemplo en Python (HTTPX):
```python
import httpx

response = httpx.get("http://localhost:8000/healthz")
print(response.json())
```

---

### 3.2 `GET /v1/providers/status` — Estado de Proveedores RPC/Graph

Verifica la disponibilidad y estado operativo de todos los proveedores de datos configurados (RPC de blockchain y The Graph).

- **Método:** `GET`
- **Ruta:** `/v1/providers/status`
- **Autenticación:** No requerida

#### Respuesta Exitosa (HTTP 200 OK):
```json
{
  "status": "ok",
  "data": {
    "rpc": {
      "ethereum": {
        "status": "UP",
        "chain_id": 1,
        "chain_id_expected": 1,
        "block_height": 18850000,
        "latest_block_hash": "0x..."
      },
      "avalanche": {
        "status": "UP",
        "chain_id": 43114,
        "chain_id_expected": 43114
      },
      "hsk": {
        "status": "DOWN",
        "error": "Not configured"
      }
    },
    "graph": {
      "status": "UP",
      "deployment": "5zvR82QoaXYFyDEKLZ9t6v9adgnptxYpKpSbxtgVENFV",
      "has_indexing_errors": false
    }
  },
  "errors": []
}
```

---

### 3.3 `GET /v1/rpc/transactions/{chain}/{tx_hash}` — Obtener Transacción

Obtiene los detalles completos de una transacción desde el RPC y preserva la evidencia en la bóveda.

- **Método:** `GET`
- **Ruta:** `/v1/rpc/transactions/{chain}/{tx_hash}`
- **Parámetros de ruta:**
  - `chain` (string): Nombre de la blockchain (`ethereum`, `avalanche`, `hsk`)
  - `tx_hash` (string): Hash de la transacción (66 caracteres: 0x + 64 hex)

#### Respuesta Exitosa (HTTP 200 OK):
```json
{
  "status": "COMPLETE",
  "data": {
    "result": {
      "hash": "0x4a8b12f0c78a2e1d84f93b5a92c3d4e5f60718293a4b5c6d7e8f901a2b3c4d5e",
      "from": "0xd8da6bf26964af9d7eed9e03e53415d37aa96045",
      "to": "0x1111111254fb6c44bac0bed2854e76f90643097d",
      "value": "0",
      "gas": "150000",
      "gasPrice": "20000000000",
      "nonce": "42",
      "blockNumber": "0x11f4a00",
      "blockHash": "0x..."
    },
    "evidence": {
      "raw_path": "transactions/ethereum/4a8b12f0.json",
      "raw_sha256": "sha256:abc123def456..."
    }
  }
}
```

---

### 3.4 `GET /v1/rpc/receipts/{chain}/{tx_hash}` — Obtener Recibo

Obtiene el recibo de transacción (resultado de ejecución, gas usado, logs) desde el RPC.

- **Método:** `GET`
- **Ruta:** `/v1/rpc/receipts/{chain}/{tx_hash}`
- **Parámetros de ruta:** Igual a transacción

#### Respuesta Exitosa (HTTP 200 OK):
```json
{
  "status": "COMPLETE",
  "data": {
    "result": {
      "transactionHash": "0x4a8b12f0c78a2e1d84f93b5a92c3d4e5f60718293a4b5c6d7e8f901a2b3c4d5e",
      "blockNumber": "0x11f4a00",
      "gasUsed": "123456",
      "status": "0x1",
      "logs": [
        {
          "address": "0x...",
          "topics": ["0x..."],
          "data": "0x..."
        }
      ]
    },
    "evidence": {
      "raw_path": "receipts/ethereum/4a8b12f0.json",
      "raw_sha256": "sha256:xyz789..."
    }
  }
}
```

---

### 3.5 `POST /v1/audits` — Crear Auditoría

Inicia una auditoría asincrónica completa. Retorna inmediatamente con un `job_id` para consultar el progreso.

- **Método:** `POST`
- **Ruta:** `/v1/audits`
- **Content-Type:** `application/json`

#### Cuerpo de la Petición:
```json
{
  "chain_id": 1,
  "transaction_hash": "0x4a8b12f0c78a2e1d84f93b5a92c3d4e5f60718293a4b5c6d7e8f901a2b3c4d5e",
  "subject": "0xd8da6bf26964af9d7eed9e03e53415d37aa96045",
  "claim": "The subject swapped 10 ETH for DAI on Uniswap V3",
  "limits": {
    "max_hops": 5,
    "max_events": 1000
  },
  "use_ai": false
}
```

#### Respuesta Exitosa (HTTP 200 OK):
```json
{
  "status": "RUNNING",
  "data": {
    "job_id": "job_1d73af8d2a8e",
    "case_id": "case_1_4a8b12f0_d8da6b_9f2a1b3c"
  }
}
```

---

### 3.6 `GET /v1/audits/{job_id}` — Estado de Auditoría

Consulta el estado y resultados de una auditoría en progreso o completada.

- **Método:** `GET`
- **Ruta:** `/v1/audits/{job_id}`

#### Respuesta Exitosa (HTTP 200 OK):
```json
{
  "status": "COMPLETE",
  "data": {
    "job_id": "job_1d73af8d2a8e",
    "case_id": "case_1_4a8b12f0_d8da6b_9f2a1b3c",
    "verdict": "SUPPORTED",
    "summary": "Evidence supports the claim"
  }
}
```

---

### 3.7 `POST /v1/claim-audit` — Iniciar Auditoría de Reclamo

Ejecuta el pipeline completo de adquisición de evidencia L0 y L1, preservación criptográfica en la bóveda, generación de registros de procedencia y emisión de resultados de auditoría.

- **Método:** `POST`
- **Ruta:** `/v1/claim-audit`
- **Content-Type:** `application/json`

#### Cuerpo de la Petición (JSON):
```json
{
  "chain_id": 1,
  "transaction_hash": "0x4a8b12f0c78a2e1d84f93b5a92c3d4e5f60718293a4b5c6d7e8f901a2b3c4d5e",
  "claim": "Subject swapped 10 ETH for DAI on Uniswap V3",
  "subject": "0xd8da6bf26964af9d7eed9e03e53415d37aa96045",
  "use_ai": false
}
```

#### Respuesta Exitosa (HTTP 200 OK):
```json
{
  "case_id": "case_1_4a8b12f0_d8da6b_9f2a1b3c",
  "status": "COMPLETE",
  "verdict": "UNKNOWN",
  "summary": "Evidence acquisition complete. Protocol analysis and verdict computation are pending integration with Jhamil's modules.",
  "predicates": [],
  "evidence_for": [
    {
      "evidence_id": "ev_ethereumrpc_b4c810ae_f12c8a41",
      "authority_level": "L0_CHAIN_PRIMARY",
      "chain_id": 1,
      "source": "ethereum_rpc",
      "method": "acquire",
      "request_fingerprint": "sha256:d5a6b7c8d9e0f1a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a",
      "retrieved_at": "2026-09-09T04:15:30.123456+00:00",
      "raw_path": "raw/case_1_4a8b12f0_d8da6b_9f2a1b3c/ev_ethereumrpc_b4c810ae_f12c8a41.json",
      "raw_sha256": "ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bb",
      "adapter_version": "0.1.0",
      "status": "COMPLETE",
      "warnings": [],
      "block_number": null,
      "indexing_errors": null,
      "graph_deployment": null
    }
  ],
  "evidence_against": [],
  "gaps": [
    "Protocol decoding (Uniswap V3 resolver) pending.",
    "Contribution Analysis pending.",
    "Claim predicate evaluation pending."
  ],
  "warnings": [],
  "protocol_action": null,
  "contribution": null,
  "provenance": {
    "case_id": "case_1_4a8b12f0_d8da6b_9f2a1b3c",
    "tx_hash": "0x4a8b12f0c78a2e1d84f93b5a92c3d4e5f60718293a4b5c6d7e8f901a2b3c4d5e",
    "chain_id": 1,
    "evidence_record_ids": [
      "ev_ethereumrpc_b4c810ae_f12c8a41",
      "ev_thegraph_e8a109bc_42a8b9f1"
    ],
    "vault_paths": [
      "raw/case_1_4a8b12f0_d8da6b_9f2a1b3c/ev_ethereumrpc_b4c810ae_f12c8a41.json",
      "raw/case_1_4a8b12f0_d8da6b_9f2a1b3c/ev_thegraph_e8a109bc_42a8b9f1.json"
    ],
    "adapter_versions": [
      "0.1.0"
    ]
  },
  "timing_ms": {
    "rpc_ms": 142,
    "graph_ms": 215,
    "total_ms": 361
  }
}
```

#### Ejemplo con cURL:
```bash
curl -X POST http://localhost:8000/v1/claim-audit \
  -H "Content-Type: application/json" \
  -d '{
    "chain_id": 1,
    "transaction_hash": "0x4a8b12f0c78a2e1d84f93b5a92c3d4e5f60718293a4b5c6d7e8f901a2b3c4d5e",
    "claim": "Subject swapped 10 ETH for DAI on Uniswap V3",
    "subject": "0xd8da6bf26964af9d7eed9e03e53415d37aa96045",
    "use_ai": false
  }'
```

---

### 3.8 `GET /v1/cases/{case_id}` — Consultar Caso Persistido

Recupera los metadatos y el estado actual de un caso auditado previamente.

- **Método:** `GET`
- **Ruta:** `/v1/cases/{case_id}`
- **Parámetros de Ruta:**
  - `case_id` (`string`): Identificador del caso (ej. `case_1_4a8b12f0_d8da6b_9f2a1b3c`).

#### Respuesta Exitosa (HTTP 200 OK):
```json
{
  "case_id": "case_1_4a8b12f0_d8da6b_9f2a1b3c",
  "chain_id": 1,
  "transaction_hash": "0x4a8b12f0c78a2e1d84f93b5a92c3d4e5f60718293a4b5c6d7e8f901a2b3c4d5e",
  "subject": "0xd8da6bf26964af9d7eed9e03e53415d37aa96045",
  "claim": "Subject swapped 10 ETH for DAI on Uniswap V3",
  "status": "COMPLETE",
  "verdict": "UNKNOWN",
  "evidence_status": "PENDING",
  "evidence_record_ids": [
    "ev_ethereumrpc_b4c810ae_f12c8a41",
    "ev_thegraph_e8a109bc_42a8b9f1"
  ],
  "created_at": "2026-09-09T04:15:29.800000+00:00",
  "updated_at": "2026-09-09T04:15:30.160000+00:00",
  "warnings": [],
  "timing_ms": {
    "rpc_ms": 142,
    "graph_ms": 215,
    "total_ms": 361
  }
}
```

#### Respuesta de Error (HTTP 404 Not Found):
```json
{
  "detail": "Case 'case_1_00000000_000000_00000000' not found."
}
```

---

### 3.9 `GET /v1/cases/{case_id}/evidence` — Listar Evidencias del Caso

Devuelve la lista detallada de registros de evidencia (`EvidenceRecord`) vinculados a un caso.

- **Método:** `GET`
- **Ruta:** `/v1/cases/{case_id}/evidence`
- **Parámetros de Ruta:**
  - `case_id` (`string`): Identificador del caso.

#### Respuesta Exitosa (HTTP 200 OK):
Devuelve un arreglo JSON con los registros de evidencia deserializados:
```json
[
  {
    "evidence_id": "ev_ethereumrpc_b4c810ae_f12c8a41",
    "authority_level": "L0_CHAIN_PRIMARY",
    "chain_id": 1,
    "source": "ethereum_rpc",
    "method": "acquire",
    "request_fingerprint": "sha256:d5a6b7c8d9e0f1a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a",
    "retrieved_at": "2026-09-09T04:15:30.123456+00:00",
    "raw_path": "raw/case_1_4a8b12f0_d8da6b_9f2a1b3c/ev_ethereumrpc_b4c810ae_f12c8a41.json",
    "raw_sha256": "ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bb",
    "adapter_version": "0.1.0",
    "status": "COMPLETE",
    "warnings": [],
    "block_number": null,
    "indexing_errors": null,
    "graph_deployment": null
  },
  {
    "evidence_id": "ev_thegraph_e8a109bc_42a8b9f1",
    "authority_level": "L1_INDEXED",
    "chain_id": 1,
    "source": "the_graph",
    "method": "query",
    "request_fingerprint": "sha256:1a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f809",
    "retrieved_at": "2026-09-09T04:15:30.340000+00:00",
    "raw_path": "raw/case_1_4a8b12f0_d8da6b_9f2a1b3c/ev_thegraph_e8a109bc_42a8b9f1.json",
    "raw_sha256": "8a7b6c5d4e3f2a1b0c9d8e7f6a5b4c3d2e1f0a9b8c7d6e5f4a3b2c1d0e9f8a7b",
    "adapter_version": "0.1.0",
    "status": "COMPLETE",
    "warnings": [],
    "block_number": 19450120,
    "indexing_errors": false,
    "graph_deployment": "QmZ123..."
  }
]
```

---

### 3.10 `GET /v1/cases/{case_id}/package` — Descargar Contenedor `.v52.zip`

Descarga el contenedor forense autocontenido `.v52.zip` que contiene todas las evidencias crudas y el `manifest.json`.

- **Método:** `GET`
- **Ruta:** `/v1/cases/{case_id}/package`
- **Encabezados de Respuesta:**
  - `Content-Type: application/zip`
  - `Content-Disposition: attachment; filename="<case_id>.v52.zip"`

#### Respuesta Exitosa (HTTP 200 OK):
Flujo binario del archivo ZIP.

#### Respuesta de Error (HTTP 404 Not Found):
```json
{
  "detail": "Package for case 'case_1_4a8b12f0_d8da6b_9f2a1b3c' has not been built yet. Run a full audit to generate the package."
}
```

#### Ejemplo con cURL para Guardar el Archivo:
```bash
curl -O -J http://localhost:8000/v1/cases/case_1_4a8b12f0_d8da6b_9f2a1b3c/package
```

---

### 3.11 `POST /v1/verify` — Verificar Integridad de Paquete `.v52.zip`

Permite a cualquier entidad subir un archivo `.v52.zip` para comprobar su autenticidad e inmutabilidad.

- **Método:** `POST`
- **Ruta:** `/v1/verify`
- **Content-Type:** `multipart/form-data`
- **Parámetro del Formulario:**
  - `file`: Archivo binario `.v52.zip` (máximo 100 MB).

#### Algoritmo de Auditoría Ejecutado:
1. Inspecciona la estructura del ZIP y extrae `manifest.json`.
2. Lee cada archivo declarado en `manifest.json.files` y calcula su resumen SHA-256 en memoria.
3. Detecta discrepancias de hashes o archivos faltantes.
4. **Detección Anti-Manipulación (Tamper Detection):** Verifica que **no existan archivos en el ZIP que no hayan sido declarados en `manifest.json`**. Si alguien inyectó archivos extras, la verificación falla.

#### Respuesta Exitosa de Validación (HTTP 200 OK — PASS):
```json
{
  "status": "PASS",
  "checked_files": 4,
  "errors": []
}
```

#### Respuesta de Validación Fallida (HTTP 200 OK — FAIL):
```json
{
  "status": "FAIL",
  "checked_files": 3,
  "errors": [
    {
      "file": "raw/case_1_4a8b12f0.../ev_ethereumrpc_....json",
      "reason": "Hash mismatch: expected ca978112ca1bbdca…, got f5412a8bc93e4d1f…"
    },
    {
      "file": "unauthorized_file.txt",
      "reason": "File present in ZIP but not declared in manifest."
    }
  ]
}
```

#### Respuestas de Error:
- **HTTP 400 Bad Request:** Archivo no es un archivo ZIP válido o no contiene `manifest.json`.
  ```json
  {"detail": "Uploaded file is not a valid ZIP archive."}
  ```
- **HTTP 413 Payload Too Large:**
  ```json
  {"detail": "Package exceeds maximum size of 100 MB."}
  ```

#### Ejemplo con cURL:
```bash
curl -X POST http://localhost:8000/v1/verify \
  -F "file=@case_1_4a8b12f0_d8da6b_9f2a1b3c.v52.zip"
```

---

### 3.12 Autenticación Web y Wallet Flow para Frontend (SIWE)

Este grupo de endpoints implementa el canal humano (`channel: "WEB"`) basado en el estándar **EIP-4361 (Sign-In with Ethereum - SIWE)**. Permite a los usuarios de la PWA autenticarse firmando un mensaje criptográfico con su billetera Web3 (MetaMask, Rabby, etc.) sin incurrir en costos de gas ni transacciones en cadena, otorgando un token de sesión `Bearer` (TTL 8 horas).

---

#### 3.12.1 `POST /v1/auth/wallet/challenge` — Generar Desafío SIWE

Genera un nonce criptográfico único y un mensaje formateado con EIP-4361 que el usuario debe firmar en su billetera.

- **Método:** `POST`
- **Ruta:** `/v1/auth/wallet/challenge`
- **Autenticación:** Pública (sin credenciales)
- **Cuerpo de la Solicitud (`WalletChallengeRequest`):**
  ```json
  {
    "address": "0xd8da6bf26964af9d7eed9e03e53415d37aa96045",
    "chain_id": 1
  }
  ```
  - `address` (`string`): Dirección EVM de 40 caracteres hexadecimales precedida de `0x`.
  - `chain_id` (`int`): `1` (Ethereum Mainnet) o `43113` (Avalanche Fuji).

##### Respuesta Exitosa (HTTP 200 OK — `WalletChallengeResponse`):
```json
{
  "nonce": "kM98xZ_a1b2c3d4e5f",
  "message": "localhost wants you to sign in with your Ethereum account:\n0xd8da6bf26964af9d7eed9e03e53415d37aa96045\n\nAuthenticate this browser session to Vector52. No blockchain transaction will be sent.\n\nURI: http://localhost:8000\nVersion: 1\nChain ID: 1\nNonce: kM98xZ_a1b2c3d4e5f\nIssued At: 2026-09-12T16:00:00+00:00\nExpiration Time: 2026-09-12T16:05:00+00:00",
  "expires_at": "2026-09-12T16:05:00+00:00"
}
```

---

#### 3.12.2 `POST /v1/auth/wallet/verify` — Verificar Firma y Emitir Sesión

Verifica la firma `personal_sign` del mensaje contra la dirección declarada y genera un token de sesión opaco.

- **Método:** `POST`
- **Ruta:** `/v1/auth/wallet/verify`
- **Cuerpo de la Solicitud (`WalletVerifyRequest`):**
  ```json
  {
    "nonce": "kM98xZ_a1b2c3d4e5f",
    "message": "localhost wants you to sign in with your Ethereum account:\n...",
    "signature": "0x3045022100..."
  }
  ```

##### Respuesta Exitosa (HTTP 200 OK — `WalletSessionResponse`):
```json
{
  "access_token": "v52_sec_9a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d",
  "token_type": "bearer",
  "address": "0xd8da6bf26964af9d7eed9e03e53415d37aa96045",
  "chain_id": 1,
  "expires_at": "2026-09-13T00:00:00+00:00"
}
```

##### Respuestas de Error:
- **HTTP 401 Unauthorized:** Desafío no encontrado, expirado (TTL 5 min) o firma que no coincide con la dirección.
  ```json
  {"detail": "Wallet challenge is invalid or expired."}
  ```

---

#### 3.12.3 `GET /v1/auth/wallet/me` — Identidad de Sesión Actual

Retorna los datos de la billetera asociada al token Bearer activo.

- **Método:** `GET`
- **Ruta:** `/v1/auth/wallet/me`
- **Encabezado Requerido:** `Authorization: Bearer <access_token>`

##### Respuesta Exitosa (HTTP 200 OK — `WalletIdentityResponse`):
```json
{
  "channel": "WEB",
  "address": "0xd8da6bf26964af9d7eed9e03e53415d37aa96045",
  "chain_id": 1,
  "expires_at": "2026-09-13T00:00:00+00:00"
}
```

---

#### 3.12.4 `POST /v1/web/investigations/wallet-flow` — Flujo Forense Web Autenticado

Ejecuta la adquisición forense de transferencias de activos (Alchemy Transfers API) para una sesión web activa de usuario humano.

- **Método:** `POST`
- **Ruta:** `/v1/web/investigations/wallet-flow`
- **Encabezado Requerido:** `Authorization: Bearer <access_token>`
- **Cuerpo de la Solicitud (`WalletFlowJobRequest`):**
  ```json
  {
    "target_address": "0xd8da6bf26964af9d7eed9e03e53415d37aa96045",
    "chain_id": 1,
    "limit": 25,
    "from_date": "2024-01-01",
    "to_date": "2024-03-31"
  }
  ```

##### Respuesta Exitosa (HTTP 200 OK — `WebWalletFlowResponse`):
```json
{
  "channel": "WEB",
  "actor_wallet": "0xd8da6bf26964af9d7eed9e03e53415d37aa96045",
  "result": {
    "address": "0xd8da6bf26964af9d7eed9e03e53415d37aa96045",
    "acquired_at": "2026-09-12T16:05:30.123456+00:00",
    "incoming": [],
    "outgoing": [],
    "limits": {
      "requested_per_direction": 25,
      "returned_incoming": 12,
      "returned_outgoing": 18,
      "truncated": false,
      "from_date": "2024-01-01",
      "to_date": "2024-03-31",
      "max_pages_per_direction": 10
    },
    "warnings": [
      "This view contains direct native/ERC-20 transfers only; internal protocol semantics are not inferred.",
      "A connection is evidence of transfer, not proof of identity, ownership or wrongdoing."
    ]
  }
}
```

---

### 3.13 Canal de Agentes e IAs con x402 (M2M)

Este grupo de endpoints implementa el canal artificial (`channel: "AGENT_X402"`) diseñado para la interacción autónoma de **servidores MCP, agentes LLM y bots** utilizando el protocolo de micropagos **x402 (HTTP 402 Payment Required)**.

---

#### 3.13.1 `GET /v1/agent/capabilities` — Capacidades de Pago x402

Permite al agente o cliente MCP descubrir las reglas de pago vigentes (red, token de pago, monto y estado del servicio) antes de emitir una consulta de pago.

- **Método:** `GET`
- **Ruta:** `/v1/agent/capabilities`
- **Autenticación:** Pública (sin credenciales ni pago)

##### Respuesta Exitosa (HTTP 200 OK — `AgentCapabilitiesResponse`):
```json
{
  "channel": "AGENT_X402",
  "ready": true,
  "endpoint": "/v1/agent/investigations/wallet-flow",
  "payment_protocol": "x402",
  "network": "eip155:43113",
  "asset": "0x5425890298aed601595a70AB815c96711a31Bc65",
  "amount_atomic": "1000",
  "automatic_payment_owner": "MCP_CLIENT",
  "warnings": []
}
```
> **Nota:** `ready: false` indica que el facilitador x402 aún no cuenta con todas las credenciales de settlement configuradas.

---

#### 3.13.2 `POST /v1/agent/investigations/wallet-flow` — Flujo Forense Pagado con x402

Ejecuta la misma adquisición determinista que el canal web, pero requiriendo autorización de micropago x402 en lugar de una sesión interactiva humana.

- **Método:** `POST`
- **Ruta:** `/v1/agent/investigations/wallet-flow`
- **Cuerpo de la Solicitud (`WalletFlowJobRequest`):**
  ```json
  {
    "target_address": "0xd8da6bf26964af9d7eed9e03e53415d37aa96045",
    "chain_id": 1,
    "limit": 25
  }
  ```

##### 1. Flujo Inicial sin Pago (Desafío HTTP 402):
El middleware ASGI de x402 intercepta la petición y responde:
- **HTTP Status:** `402 Payment Required`
- **Header `PAYMENT-REQUIRED`:** Cadena Base64 con especificación JSON del requerimiento de pago:
  ```json
  {
    "scheme": "exact",
    "pay_to": "0xf92A1E3Fa1a163FEeB8c3753165410374fB08339",
    "price": {
      "amount": "1000",
      "asset": "0x5425890298aed601595a70AB815c96711a31Bc65",
      "extra": {
        "name": "USD Coin",
        "version": "2",
        "areFeesSponsored": true
      }
    },
    "network": "eip155:43113",
    "max_timeout_seconds": 300
  }
  ```

##### 2. Reintento con Pago por el Agente:
El agente decodifica el header, firma la autorización off-chain (EIP-3009 o EIP-712 exact scheme) con su clave de agente y reenvía la petición incluyendo:
- **Header:** `PAYMENT-SIGNATURE: <base64_signed_authorization>`

El backend valida la autorización con el Facilitador OpenZeppelin Relayer (`/call/verify`), liquida on-chain (`/call/settle`) y procesa la investigación forense.

##### Respuesta Exitosa (HTTP 200 OK — `AgentWalletFlowResponse`):
```json
{
  "channel": "AGENT_X402",
  "request_id": "agent_c4b912a7f80e4b859940182390f11acb",
  "result": {
    "address": "0xd8da6bf26964af9d7eed9e03e53415d37aa96045",
    "acquired_at": "2026-09-12T16:06:12.871020+00:00",
    "incoming": [],
    "outgoing": [],
    "limits": {
      "requested_per_direction": 25,
      "returned_incoming": 8,
      "returned_outgoing": 14,
      "truncated": false,
      "from_date": null,
      "to_date": null,
      "max_pages_per_direction": 1
    },
    "warnings": [
      "This view contains direct native/ERC-20 transfers only; internal protocol semantics are not inferred.",
      "A connection is evidence of transfer, not proof of identity, ownership or wrongdoing."
    ]
  }
}
```

---

### 3.14 Matriz de Protección y Políticas x402 (Humanos vs Agentes Artificiales)

Vector52 establece una política de seguridad y monetización diferenciada para proteger la estabilidad de sus proveedores de datos (Alchemy, The Graph, RPCs) y garantizar una experiencia fluida:

| Endpoint | Canal Humano (PWA / Browser) | Canal Agente / IA (MCP / Script) | Razón Técnica y Protección |
| :--- | :--- | :--- | :--- |
| **`GET /healthz`** | **Público (Libre)** | **Público (Libre)** | Liveness probe del servidor. Sin acceso a datos sensibles. |
| **`GET /v1/providers/status`** | **Público (Libre)** | **Público (Libre)** | Estado de conectividad de RPC y subgrafos (secretos redactados). |
| **`POST /v1/verify`** | **Público (Libre)** | **Público (Libre)** | Verificación criptográfica de archivos `.v52.zip`. Es un **bien público** para auditoría abierta sin barreras de entrada. |
| **`GET /v1/agent/capabilities`** | **Público (Libre)** | **Público (Libre)** | Introspección previa del agente para consultar tarifas y redes antes de pagar. |
| **`GET /v1/audits/{job_id}`** | **Público (Libre)** | **Público (Libre)** | Polling de estado de auditorías previamente sometidas. No se penaliza al cliente por esperar resultados. |
| **`POST /v1/auth/wallet/challenge`** | **Público (Libre)** | No aplicable | Generación de desafío SIWE. Expiración estricta de 5 minutos por nonce. |
| **`POST /v1/auth/wallet/verify`** | **Público (Libre)** | No aplicable | Verificación de firma criptográfica y emisión de sesión Bearer (TTL 8h). |
| **`GET /v1/auth/wallet/me`** | **Sesión Bearer (SIWE)** | No aplicable | Verificación de identidad activa en la PWA. |
| **`POST /v1/web/investigations/wallet-flow`** | **Sesión Bearer (SIWE)** | No aplicable | Cuota interactiva en navegador para usuarios autenticados. Rate-limited por IP y dirección de billetera. |
| **`POST /v1/agent/investigations/wallet-flow`** | No aplicable | **Protegido con x402** *(1000 atomic units USDC)* | Adquisición intensiva mediante Alchemy Transfers API. Previene consumo excesivo de créditos por agentes autónomos en bucle. |
| **`POST /v1/audits` (Auditoría Estándar)** | **Sesión Bearer / Público Demo** | No aplicable | Auditoría forense estándar (hops = 1, eventos = 500) para demostración y evaluación de jueces. |
| **`POST /v1/paid/claim-audit` (Deep / AI)** | **Protegido con x402** *(5000 atomic units USDC)* | **Protegido con x402** *(5000 atomic units USDC)* | Auditoría multi-hop exhaustiva con resúmenes generativos de IA L5 (`v52_ai_enabled`). |
| **`POST /v1/cases/{case_id}/anchor`** | **Protegido con x402** *(2000 atomic units USDC)* | **Protegido con x402** *(2000 atomic units USDC)* | Registro inmutable de la raíz del manifest en el contrato de HashKey Chain (HSK). El pago cubre el patrocinio de gas del relayer. |
| **`GET /v1/cases/{case_id}/package`** | **Sesión (Demo) / x402** | **Protegido con x402** *(500 atomic units USDC)* | Generación y descarga del contenedor forense autocontenido `.v52.zip` con sello de procedencia. |
| **`GET /v1/intel/defi/status`** | **Público (Libre)** | **Público (Libre)** | Un único query `_meta` por cadena (sin pools/swaps); descubribilidad barata del canal pagado de abajo. |
| **`POST /v1/agent/intel/defi/pools`** | No aplicable | **Protegido con x402** *(400 atomic units USDC)* | Top pools/pairs por liquidez de una cadena — el nivel más barato del DeFi Subgraph Intel. |
| **`POST /v1/agent/intel/defi/pool-activity`** | No aplicable | **Protegido con x402** *(900 atomic units USDC)* | Swaps recientes de un pool/pair específico — drill-down de mayor valor que el listado. |
| **`POST /v1/agent/intel/defi/scan`** | No aplicable | **Protegido con x402** *(2500 atomic units USDC)* | Escaneo agregado multi-cadena (HSK + Avalanche + Ethereum) en una sola llamada — el nivel más caro. |

---

### 3.15 Agent Access — Estado de Integración MCP (para el Frontend)

> Ver `CONTRATO-INTEGRACION.md` ("Interfaz Agent Access preparada para MCP"). Estos endpoints son consumidos por la **PWA**, no por un servidor MCP real — `v52-mcp` es un repositorio/servicio independiente que hoy **no está conectado**. La PWA nunca habla directamente con un proceso MCP privilegiado; consulta estos endpoints del backend para reflejar el estado honestamente.

**Regla de honestidad:** mientras `V52_MCP_SERVER_URL` no esté configurada y verificada, toda respuesta reporta `UNAVAILABLE` (o `UNKNOWN` si la URL está puesta pero sin handshake real). Nunca se transforma un mock en `READY`.

#### `GET /v1/integrations/mcp/status`

```json
{
  "state": "UNAVAILABLE",
  "server_configured": false,
  "reason": "v52-mcp is a separate service that is not connected to this backend yet.",
  "warnings": []
}
```

#### `GET /v1/integrations/mcp/tools`

Catálogo documentado (P0) de tools que existirán cuando `v52-mcp` esté conectado. Con el canal desconectado devuelve `tools: []` y `state: UNAVAILABLE`; con `V52_MCP_SERVER_URL` configurada (pero sin handshake verificado) devuelve el catálogo con `state: UNKNOWN`:

```json
{
  "state": "UNAVAILABLE",
  "tools": [],
  "reason": "v52-mcp is a separate service that is not connected to this backend yet."
}
```

Catálogo documentado (`CONTRATO-INTEGRACION.md` "MCP mapping"): `case_status`, `evidence_get`, `edge_explain`, `package_verify`, `anchor_lookup` (gratuitos) y `claim_audit` (x402).

#### `POST /v1/agent-jobs`

Siempre responde `503` mientras `v52-mcp` no esté conectado — **nunca fabrica un job falso**:

```json
{
  "detail": "v52-mcp is a separate service that is not connected to this backend yet. See docs/ARQUITECTURA-REPOSITORIOS.md and CONTRATO-INTEGRACION.md."
}
```

#### `GET /v1/agent-jobs/{job_id}`

Siempre responde `404`: ningún job puede existir mientras `POST /v1/agent-jobs` no crea ninguno.

---

### 3.16 Anclaje HSK (`V52EvidenceRegistry`)

Ancla y consulta el compromiso criptográfico de un expediente `.v52` en el
contrato `V52EvidenceRegistry` de HashKey Chain
(`v52-onchain/contracts/hsk/V52EvidenceRegistry.sol`). El contrato **nunca**
recibe el manifest completo, la wallet investigada, el claim ni el
veredicto — solo `sha256(manifest.json)`, un hash de metodología, la
versión de esquema y el `case_id` no sensible. Ver
`v52-onchain/README.md` para qué prueba y qué no prueba este anclaje.

#### 3.16.1 `POST /v1/cases/{case_id}/anchor` — Anclar el manifest de un caso

- **Método:** `POST`
- **Ruta:** `/v1/cases/{case_id}/anchor`
- **Content-Type:** `application/json` (cuerpo opcional)
- **Precondición:** el caso debe existir y su paquete `.v52.zip` debe haber
  sido generado (`POST /v1/claim-audit` o el pipeline de auditoría
  correspondiente construye el paquete automáticamente al completar).

##### Cuerpo de la Petición (opcional, `AnchorCaseRequest`):
```json
{
  "supersedes": "0x2407b6f2529df3afbb2ab609cb236ff00b8421c7a57f78128ee58ed6d54f5005"
}
```
- `supersedes` (`string`, opcional): `manifest_root` (0x + 64 hex) de un
  anchor previo que este reemplaza. Omitir para un primer anclaje.

##### Respuesta Exitosa (HTTP 200 OK — `AnchorCaseResponse`):
```json
{
  "case_id": "case_1_4a8b12f0_d8da6b_143161cd",
  "manifest_root": "0x0e9faa2b1757eceb4d45d2cda883e0dbfb6171d8e5896b76201397dfe57b5179",
  "methodology_hash": "0xe0a774b844f155aa02d7513a07fdd5c01ef1ea58d7ece268cc4a2673b38b8ad3",
  "schema_version": "0.1.0",
  "issuer": "0x0f26475928053737C3CCb143Ef9B28F8eDab04C7",
  "supersedes": null,
  "chain_id": 133,
  "tx_hash": "0x966e13422e9c7df2c60b0f7e19f971101a182e8278a18998ac03dc96e33e077a",
  "block_number": 33036560,
  "gas_used": 217512,
  "explorer_tx_url": "https://testnet-explorer.hsk.xyz/tx/0x966e13422e9c7df2c60b0f7e19f971101a182e8278a18998ac03dc96e33e077a",
  "explorer_address_url": "https://testnet-explorer.hsk.xyz/address/0x3422820Ef9FBC8e0206E4CBcB6369dBd14BE18c4",
  "already_anchored": false
}
```
Respuesta real capturada contra HSK Testnet el 13 de septiembre de 2026
(primer anclaje de un caso nunca antes anclado — sin reintentos).

`manifest_root` es siempre `sha256(manifest.json)` **exactamente como fue
empaquetado** dentro del `.v52.zip` — el mismo hash que verificaría
`POST /v1/verify`. Reintentar este endpoint con un paquete sin cambios es
**idempotente**: si el `manifest_root` ya está anclado, no se envía una
nueva transacción y `already_anchored` es `true`.

##### Respuestas de Error:
- **HTTP 404 Not Found:** caso inexistente, o paquete `.v52.zip` no
  construido todavía.
  ```json
  {"detail": "Package for case 'case_...' has not been built yet. Run a full audit to generate the .v52.zip before anchoring."}
  ```
- **HTTP 400 Bad Request:** `manifest.json` ausente/corrupto en el ZIP, o
  el contrato revirtió por una condición de negocio (p. ej.
  `supersedes` desconocido).
- **HTTP 502 Bad Gateway:** el RPC de HSK no respondió, o la transacción
  fue minada pero el registro aún no es legible (se reintenta
  automáticamente 3 veces con backoff de 2s antes de devolver este error).
- **HTTP 503 Service Unavailable:** `HSK_RPC_URL`,
  `HSK_EVIDENCE_REGISTRY_ADDRESS` o `HSK_ANCHOR_PRIVATE_KEY` no están
  configuradas.
  ```json
  {"detail": "HSK anchoring is not configured. Set HSK_RPC_URL, HSK_EVIDENCE_REGISTRY_ADDRESS and HSK_ANCHOR_PRIVATE_KEY."}
  ```

##### Ejemplo con cURL:
```bash
curl -X POST http://localhost:8000/v1/cases/case_1_4a8b12f0_d8da6b_261bc3a1/anchor \
  -H "Content-Type: application/json" -d '{}'
```

#### 3.16.2 `GET /v1/anchors/{manifest_root}` — Consultar procedencia de un anchor

- **Método:** `GET`
- **Ruta:** `/v1/anchors/{manifest_root}`
- **Autenticación:** Pública — cualquiera puede verificar la procedencia de
  un `manifest_root`, sin necesitar la llave firmante del backend.

##### Respuesta Exitosa (HTTP 200 OK — `AnchorLookupResponse`):
```json
{
  "manifest_root": "0x2407b6f2529df3afbb2ab609cb236ff00b8421c7a57f78128ee58ed6d54f5005",
  "methodology_hash": "0x19eb9203d4b018144e7304399823b1bcc9dd19ea94519d4ad1861d8e21041986",
  "schema_version": "0.1.0",
  "case_id": "case_smoke_test_deploy_verification",
  "issuer": "0x0f26475928053737C3CCb143Ef9B28F8eDab04C7",
  "block_number": 33035723,
  "timestamp": 1789258102,
  "supersedes": null,
  "chain_id": 133,
  "tx_hash": "0xd97a0054d252bccbb17cbb4e4f0fc84cbd23eba4bbfc84fc9c40ccf03a8225fb",
  "explorer_tx_url": "https://testnet-explorer.hsk.xyz/tx/0xd97a0054d252bccbb17cbb4e4f0fc84cbd23eba4bbfc84fc9c40ccf03a8225fb",
  "explorer_address_url": "https://testnet-explorer.hsk.xyz/address/0x3422820Ef9FBC8e0206E4CBcB6369dBd14BE18c4"
}
```
Este es el anchor real creado durante la verificación del deploy en HSK
Testnet — ver `v52-onchain/deployments/hsk-testnet.json`.

`tx_hash` y `explorer_tx_url` son `null` si el hash de transacción no pudo
recuperarse de los logs (best-effort: se consulta únicamente el bloque
exacto reportado por el contrato, así que solo falla si el nodo RPC no
tiene ese bloque indexado).

##### Respuestas de Error:
- **HTTP 422 Unprocessable Entity:** `manifest_root` no tiene el formato
  `0x` + 64 caracteres hex.
- **HTTP 404 Not Found:** ningún anchor existe para ese `manifest_root`.
  ```json
  {"detail": "No anchor found for manifest_root '0x...'."}
  ```
- **HTTP 503 Service Unavailable:** `HSK_RPC_URL` o
  `HSK_EVIDENCE_REGISTRY_ADDRESS` no configuradas.

##### Ejemplo con cURL:
```bash
curl http://localhost:8000/v1/anchors/0x2407b6f2529df3afbb2ab609cb236ff00b8421c7a57f78128ee58ed6d54f5005
```

---

### 3.17 DeFi Subgraph Intel — HSK / Avalanche / Ethereum Mainnet

Escanea "puntos vitales" de la superficie DeFi de una cadena — los pools/pairs
que ejecutan swaps y su actividad reciente — consultando en vivo el subgrafo
de The Graph configurado por cadena (`V52_GRAPH_ENDPOINT_ETHEREUM` /
`_AVALANCHE` / `_HSK`, ver [`SUBGRAPHS.md`](./SUBGRAPHS.md) para la
justificación completa y cómo elegir/desplegar un subgrafo por cadena). Nada
aquí se inventa: si una cadena no tiene subgrafo configurado, se reporta
`configured: false` honestamente en vez de simular datos.

Se compone de un endpoint de descubrimiento gratuito y tres endpoints pagados
con x402, ambos consumidos vía `app/api/defi_core.py` (lógica compartida) —
mismo patrón que `wallet_flow.py`/`agent.py` para el canal de wallet-flow.

---

#### 3.17.1 `GET /v1/intel/defi/status` — Estado del subgrafo por cadena (Gratuito)

- **Método:** `GET`
- **Ruta:** `/v1/intel/defi/status`
- **Autenticación:** Pública (sin credenciales ni pago) — ejecuta un único
  query `_meta` por cadena, nunca pools ni swaps.

##### Respuesta Exitosa (HTTP 200 OK — `DefiEntrypointsStatusResponse`):
```json
{
  "chains": [
    {
      "chain": "ethereum",
      "network": "ethereum-mainnet",
      "configured": true,
      "subgraph_schema": "uniswap_v3",
      "meta": {
        "block_number": 18850000,
        "block_hash": "0x...",
        "deployment": "QmTZ8ejXJxRo7vDBS4uwqBeGoxLSWbhaA7oXa1RvxunLy7",
        "has_indexing_errors": false
      },
      "warnings": []
    },
    {
      "chain": "avalanche",
      "network": "avalanche-mainnet",
      "configured": false,
      "subgraph_schema": null,
      "meta": null,
      "warnings": ["The Graph is not configured for chain 'avalanche'. Set V52_GRAPH_ENDPOINT_AVALANCHE to enable it."]
    },
    {
      "chain": "hsk",
      "network": "hsk",
      "configured": false,
      "subgraph_schema": null,
      "meta": null,
      "warnings": ["The Graph is not configured for chain 'hsk'. Set V52_GRAPH_ENDPOINT_HSK to enable it."]
    }
  ],
  "retrieved_at": "2026-09-13T12:00:00+00:00"
}
```

---

#### 3.17.2 `POST /v1/agent/intel/defi/pools` — Top pools/pairs por liquidez (x402, 400 atomic units)

- **Método:** `POST` · **Ruta:** `/v1/agent/intel/defi/pools`
- **Cuerpo (`DefiPoolsJobRequest`):**
  ```json
  { "chain": "ethereum", "limit": 10 }
  ```
- **Respuesta (`AgentDefiPoolsResponse`):**
  ```json
  {
    "channel": "AGENT_X402",
    "request_id": "agent_...",
    "result": {
      "chain": "ethereum",
      "network": "ethereum-mainnet",
      "subgraph_schema": "uniswap_v3",
      "pools": [
        {
          "pool_id": "0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640",
          "subgraph_schema": "uniswap_v3",
          "token0": { "address": "0x...", "symbol": "USDC", "decimals": 6 },
          "token1": { "address": "0x...", "symbol": "WETH", "decimals": 18 },
          "fee_tier": 500,
          "liquidity": "...",
          "total_value_locked_usd": "...",
          "volume_usd": "...",
          "tx_count": "..."
        }
      ],
      "meta": { "block_number": 18850000, "block_hash": "0x...", "deployment": "Qm...", "has_indexing_errors": false },
      "retrieved_at": "2026-09-13T12:00:00+00:00",
      "warnings": ["Pool/pair ranking and amounts reflect the subgraph's own indexing state; they may lag the chain head by the subgraph's indexing delay."]
    }
  }
  ```
- **HTTP 503:** la cadena solicitada no tiene subgrafo configurado.
- **HTTP 402:** falta el header de pago x402 (mismo protocolo que §3.13).

---

#### 3.17.3 `POST /v1/agent/intel/defi/pool-activity` — Swaps recientes de un pool (x402, 900 atomic units)

- **Método:** `POST` · **Ruta:** `/v1/agent/intel/defi/pool-activity`
- **Cuerpo (`DefiPoolActivityJobRequest`):**
  ```json
  { "chain": "ethereum", "pool_address": "0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640", "limit": 20 }
  ```
- **Respuesta (`AgentDefiPoolActivityResponse`):** igual forma que `pools`, pero con `swaps: [DefiSwapEvent]` (id, timestamp, transaction_hash, sender, recipient, amount0/amount1/amount_usd).

---

#### 3.17.4 `POST /v1/agent/intel/defi/scan` — Escaneo multi-cadena (x402, 2500 atomic units)

- **Método:** `POST` · **Ruta:** `/v1/agent/intel/defi/scan`
- **Cuerpo (`DefiScanJobRequest`):**
  ```json
  { "chains": ["ethereum", "avalanche", "hsk"], "pools_limit": 10 }
  ```
- **Respuesta (`AgentDefiScanResponse`):** un `DefiScanChainResult` por cadena
  solicitada (`status` + `pools` + `warnings`); una cadena sin subgrafo
  configurado aparece con `pools: []` y su warning, sin abortar el escaneo de
  las demás.

---

#### 3.17.5 Enriquecimiento aditivo de `GET /v1/providers/status` y `GET /v1/agent/capabilities`

Ambos endpoints existentes **mantienen exactamente sus campos originales** y
solo ganan campos nuevos:

- `GET /v1/providers/status` → `data.the_graph.chains.{ethereum,avalanche,hsk}`
  (status/network/schema por cadena), junto al `data.the_graph.status` y
  `.network` que ya existían (Ethereum, por compatibilidad).
- `GET /v1/agent/capabilities` → nuevo objeto `defi_intel` con los tres
  endpoints y tarifas de arriba; `endpoint`/`amount_atomic` (wallet-flow)
  no cambian.

---

## 4. Casos de Error y Validaciones de Entrada

La API implementa validaciones estrictas en tiempo de análisis de esquemas:

### 1. Hash de Transacción Malformado:
- **Entrada:** `"transaction_hash": "0x1234"`
- **HTTP Status:** `422 Unprocessable Entity`
- **Mensaje:**
  ```json
  {
    "detail": [
      {
        "type": "value_error",
        "loc": ["body", "transaction_hash"],
        "msg": "Value error, transaction_hash must be a 0x-prefixed 64-character hex string (32 bytes).",
        "input": "0x1234"
      }
    ]
  }
  ```

### 2. Dirección de Sujeto Malformada:
- **Entrada:** `"subject": "0xinvalido"`
- **HTTP Status:** `422 Unprocessable Entity`
- **Mensaje:**
  ```json
  {
    "detail": [
      {
        "type": "value_error",
        "loc": ["body", "subject"],
        "msg": "Value error, subject must be a 0x-prefixed 40-character hex string (20 bytes / EVM address).",
        "input": "0xinvalido"
      }
    ]
  }
  ```

### 3. Red no soportada (`chain_id != 1`):
- **Entrada:** `"chain_id": 137` (Polygon)
- **HTTP Status:** `422 Unprocessable Entity`
- **Mensaje:**
  ```json
  {
    "detail": [
      {
        "type": "value_error",
        "loc": ["body", "chain_id"],
        "msg": "Value error, chain_id 137 is not supported. Supported: [1].",
        "input": 137
      }
    ]
  }
  ```

### 4. Texto de Reclamo Vacío:
- **Entrada:** `"claim": ""`
- **HTTP Status:** `422 Unprocessable Entity`
- **Mensaje:**
  ```json
  {
    "detail": [
      {
        "type": "string_too_short",
        "loc": ["body", "claim"],
        "msg": "String should have at least 1 character",
        "input": ""
      }
    ]
  }
  ```

---

## 5. Guía de Integración para Clientes (TypeScript y Python)

### 5.1 Integración en TypeScript / Frontend (Fetch / Axios)

```typescript
// types/vector52.ts
export interface ClaimAuditRequest {
  chain_id: number;
  transaction_hash: string;
  claim: string;
  subject: string;
  use_ai?: boolean;
}

export interface ClaimAuditResponse {
  case_id: string;
  status: 'PENDING' | 'RUNNING' | 'COMPLETE' | 'DEGRADED' | 'FAILED';
  verdict: 'SUPPORTED' | 'PARTIALLY_SUPPORTED' | 'MISLEADING' | 'REFUTED' | 'UNKNOWN' | null;
  summary: string;
  timing_ms: Record<string, number>;
  warnings: string[];
}

export interface TokenMetadata {
  address: string;
  symbol?: string | null;
  decimals?: number | null;
}

export interface DecodedTransfer {
  token_address: string;
  from_address: string;
  to_address: string;
  amount_raw: string;
  transaction_hash: string;
  block_number: number;
  log_index: number;
  evidence_ids: string[];
  token_symbol?: string | null;
  token_decimals?: number | null;
  amount_formatted?: string | null;
  warnings: string[];
}

// services/vector52Api.ts
const API_BASE_URL = 'http://localhost:8000';

export async function submitClaimAudit(payload: ClaimAuditRequest): Promise<ClaimAuditResponse> {
  const response = await fetch(`${API_BASE_URL}/v1/claim-audit`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => null);
    throw new Error(errorData?.detail?.[0]?.msg || errorData?.detail || 'Error al procesar la auditoría.');
  }

  return response.json();
}

export async function verifyPackage(file: File): Promise<{ status: string; checked_files: number; errors: any[] }> {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(`${API_BASE_URL}/v1/verify`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData?.detail || 'Error en la verificación.');
  }

  return response.json();
}
```

### 5.2 Integración en Python (Script Automatizado con HTTPX)

```python
import httpx

API_BASE = "http://localhost:8000"

def audit_and_verify():
    with httpx.Client(base_url=API_BASE, timeout=60.0) as client:
        # 1. Verificar salud del servidor
        health = client.get("/healthz").json()
        print(f"[*] Backend conectado — Versión: {health['version']}")

        # 2. Enviar auditoría de reclamo
        audit_payload = {
            "chain_id": 1,
            "transaction_hash": "0x4a8b12f0c78a2e1d84f93b5a92c3d4e5f60718293a4b5c6d7e8f901a2b3c4d5e",
            "claim": "Subject swapped 10 ETH for DAI on Uniswap V3",
            "subject": "0xd8da6bf26964af9d7eed9e03e53415d37aa96045",
            "use_ai": False,
        }
        res = client.post("/v1/claim-audit", json=audit_payload)
        res.raise_for_status()
        audit_result = res.json()
        case_id = audit_result["case_id"]
        print(f"[+] Auditoría completada: {case_id} — Estatus: {audit_result['status']}")

        # 3. Descargar el paquete .v52.zip
        pkg_res = client.get(f"/v1/cases/{case_id}/package")
        if pkg_res.status_code == 200:
            zip_bytes = pkg_res.content
            print(f"[+] Paquete descargado ({len(zip_bytes)} bytes)")

            # 4. Verificar integridad del paquete recibido
            files = {"file": (f"{case_id}.v52.zip", zip_bytes, "application/zip")}
            verify_res = client.post("/v1/verify", files=files).json()
            print(f"[+] Resultado de verificación: {verify_res['status']} ({verify_res['checked_files']} archivos)")
        else:
            print(f"[-] Paquete aún no generado: {pkg_res.status_code}")

if __name__ == "__main__":
    audit_and_verify()
```
