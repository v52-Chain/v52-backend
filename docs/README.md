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
- Fixtures reales de Ethereum Mainnet (`fixtures/known_case/`) y suite de 72 pruebas automáticas.

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
- Catálogo de validaciones de entrada y códigos de error HTTP 422, 400, 404, 413 y 500.
- Guías y snippets de integración en TypeScript (frontend con tipos `DecodedTransfer`) y Python.

