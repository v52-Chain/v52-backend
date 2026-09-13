# Vector52 Backend — Centro de Documentación

Bienvenido a la documentación oficial y exhaustiva del backend de **Vector52**, el auditor determinista de afirmaciones en Ethereum basado en evidencia inmutable.

Esta carpeta contiene la documentación técnica y arquitectónica completa del sistema:

---

## 📚 Documentos Disponibles

### 1. [Funcionamiento y Arquitectura Interna](./FUNCIONAMIENTO.md)
Documento en profundidad que aborda los fundamentos técnicos del backend:
- Filosofía *"Evidence-First"* e inmutabilidad.
- Estructura exhaustiva de directorios y responsabilidades de archivos.
- Jerarquía de autoridad de evidencia (niveles L0 a L5).
- Motor de Evidencia (`preservation.py`, `provenance.py`, `acquisition.py`).
- Decodificador Determinista L2 de Transferencias ERC-20 (`erc20.py` y `transfer.py`) con aritmética exacta sin punto flotante.
- Cámara de Evidencia (`EvidenceVault`) de solo anexado y archivos `.sha256` satélite.
- Capa de Proveedores (`EthereumRpcProvider`, `TheGraphProvider`) con soporte de interpolación `{api_key}` y sanitización `redact()`.
- Pipeline de Auditoría de 7 etapas cronometradas (`AuditPipeline`).
- Estructura forense del contenedor comprimido `.v52.zip` y `manifest.json`.
- Puntos de extensión y contratos de integración para Jhamil y Omar.
- Fixtures reales de Ethereum Mainnet (`fixtures/known_case/`) y suite de pruebas automáticas.
- Anclaje HSK (`app/onchain/`, §14): cliente `web3.py` para `V52EvidenceRegistry`, cálculo de `manifest_root`, idempotencia y tolerancia a lag de lectura post-mined.

### 2. [Referencia Completa de la API REST](./API.md)
Manual integral de consumo e integración de la API:
- Convenciones HTTP, políticas CORS y manejo seguro de errores.
- Diccionario de tipos, enums y esquemas Pydantic (`ClaimAuditRequest`, `ClaimAuditResponse`, `EvidenceRecord`, `DecodedTransfer`, `TokenMetadata`, etc.).
- Catálogo detallado de endpoints con ejemplos de Request/Response, cURL y Python:
  - `GET /healthz`
  - `POST /v1/claim-audit`
  - `GET /v1/cases/{case_id}`
  - `GET /v1/cases/{case_id}/evidence`
  - `GET /v1/cases/{case_id}/package`
  - `POST /v1/verify`
  - `POST /v1/cases/{case_id}/anchor` (anclaje HSK)
  - `GET /v1/anchors/{manifest_root}` (procedencia HSK, público)
- Catálogo de validaciones de entrada y códigos de error HTTP 422, 400, 404, 413 y 500.
- Guías y snippets de integración en TypeScript (frontend con tipos `DecodedTransfer`) y Python.

### 3. [Guía de Integración x402 — Servidor MCP y Frontend](./X402_MCP_FRONTEND.md)
Manual práctico para quien consume (no mantiene) el canal de pagos x402:
- Qué está implementado hoy (`wallet-flow` M2M) y qué es solo especificación pendiente (claim-audit/anchor/package Nivel 3).
- Ejemplos completos de cliente x402 para un servidor MCP en TypeScript y en Python.
- Boceto de integración en el navegador (wallet conectada) para el frontend.
- Tabla de manejo de errores (402/503/422/500) y verificación end-to-end realizada, incluyendo un fix de robustez (503 claro cuando el facilitador está caído, en vez de 500 opaco).
- Script de facilitador mock para probar el flujo completo sin depender del relayer real.

### 4. Anclaje HSK — `V52EvidenceRegistry`
Ver [`FUNCIONAMIENTO.md` §14](./FUNCIONAMIENTO.md#14-anclaje-hsk-apponchain-appapianchorpy)
para la arquitectura del cliente (`app/onchain/hsk_registry.py`) y
[`API.md` §3.16](./API.md#316-anclaje-hsk-v52evidenceregistry) para el
contrato HTTP completo (`POST /v1/cases/{case_id}/anchor`,
`GET /v1/anchors/{manifest_root}`) con respuestas reales capturadas contra
HSK Testnet. El contrato en sí, su despliegue, tests de Foundry y modelo de
seguridad viven en el repositorio hermano
[`v52-onchain`](../../v52-onchain/README.md).

