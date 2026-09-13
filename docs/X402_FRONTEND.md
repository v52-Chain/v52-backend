# Guía de Integración x402 — Frontend (PWA)

> Este manual es la contraparte frontend de [`FUNCIONAMIENTO.md` §13](./FUNCIONAMIENTO.md#13-modelo-de-acceso-dual-humanos-siwe-vs-agentes-artificiales-x402) y [`API.md` §3.13–3.14](./API.md#313-canal-de-agentes-e-ias-con-x402-m2m). La integración del servidor MCP, incluyendo el canal x402 operativo de Nivel 2, está documentada en [`X402_MCP.md`](./X402_MCP.md).

---

## 1. Estado actual: el canal humano **no usa x402**

Para el usuario humano en el navegador, `POST /v1/web/investigations/wallet-flow` usa sesión Bearer vía **Sign-In with Ethereum (SIWE)**, no x402 (ver `FUNCIONAMIENTO.md` §13.2). Esto es intencional: pedirle una firma de pago on-chain por cada clic destruiría la UX. El frontend de hoy **no necesita** integrar ningún cliente x402 para ese flujo.

Nada que implementar aquí más allá de lo ya descrito en `API.md` para `/v1/auth/wallet/*` y `/v1/web/investigations/wallet-flow`.

## 2. Dónde SÍ aparecerá x402 en el frontend (Nivel 3, pendiente de implementar en backend)

La matriz de `API.md` §3.14 y `FUNCIONAMIENTO.md` §13.5 documenta que `POST /v1/paid/claim-audit` (deep/IA), `POST /v1/cases/{case_id}/anchor` y `GET /v1/cases/{case_id}/package` deben cobrar **tanto a humanos como a agentes** vía x402 — pero hoy **no está implementado en el backend** (`claim_audit.py` y `cases.py` no tienen `RouteConfig` en `x402.py`; no existe endpoint `anchor`). Cuando se implemente el lado servidor (siguiendo el patrón de [`X402_MCP.md`](./X402_MCP.md) §7), el frontend deberá:

1. Llamar el endpoint normalmente.
2. Si recibe `402`, decodificar `Payment-Required` (igual que el agente).
3. Pedirle a la wallet conectada del usuario (vía `wagmi`/`viem`, MetaMask, etc.) que firme la autorización EIP-712 `exact` — **no** una clave privada cruda como en el servidor MCP, sino `walletClient.signTypedData(...)` del proveedor inyectado.
4. Reintentar con el header `Payment-Signature`.

Boceto (para cuando el backend exponga esos endpoints con x402):

```typescript
// frontend/src/lib/x402Browser.ts
import { wrapFetchWithPayment } from "@x402/fetch";
import { x402Client } from "@x402/core/client";
import { ExactEvmScheme } from "@x402/evm/exact/client";
import type { WalletClient } from "viem";

export function createBrowserX402Fetch(walletClient: WalletClient) {
  const client = new x402Client();
  // spendControls habilitado en el navegador: limitar monto máximo por pago
  // para que un sitio comprometido no pueda drenar la wallet del usuario.
  client.spendControls = { allowedAssets: true, maxAmountPerPayment: "10000" };

  const browserSigner = {
    address: walletClient.account!.address,
    signTypedData: (domain: unknown, types: unknown, primaryType: string, message: unknown) =>
      walletClient.signTypedData({
        account: walletClient.account!,
        domain: domain as never,
        types: types as never,
        primaryType: primaryType as never,
        message: message as never,
      }),
  };

  client.register("eip155:43113", new ExactEvmScheme(browserSigner as never));
  return wrapFetchWithPayment(fetch, client);
}
```

> ⚠️ A diferencia del servidor MCP, en el navegador **siempre** hay que dejar `spendControls` activo con un tope (`maxAmountPerPayment`) — nunca `false`. El servidor MCP corre en un entorno controlado por el propio proyecto; el frontend corre en la máquina del usuario final con su wallet real conectada.

## 3. Manejo de errores relevante para el frontend

El frontend debe tratar el `503` del facilitador como retryable (backoff y reintento), a diferencia de un `402` (que requiere una firma nueva) o un `500` genuino (bug, no reintentar sin investigar). La tabla completa de respuestas del canal x402 está en [`X402_MCP.md`](./X402_MCP.md) §6:

- `200`: pago verificado y liquidado; usar el resultado.
- `402`: decodificar el reto base64, firmar y reintentar.
- `503` por canal deshabilitado: no reintentar en loop; revisar `ready`.
- `503` por facilitador no disponible: reintentar con backoff.
- `422`: corregir el payload.
- `500`: reportar el error, sin reintentar igual.

## 4. Seguridad para el frontend

- Nunca envíes `V52_X402_FACILITATOR_API_KEY` al navegador — no existe ninguna razón para que el frontend lo necesite; solo el backend habla con el facilitador.
- Todo pago x402 desde el navegador debe pasar por la wallet conectada del usuario (firma explícita), nunca por una clave privada embebida en el bundle del frontend.
- En frontend, `spendControls` nunca está en `false`.
- Ningún secreto (`V52_X402_FACILITATOR_API_KEY`, claves privadas de servidor) llega al bundle del frontend ni a logs.

## 5. Prueba local

Cuando el túnel ngrok/relayer no esté disponible, puede usarse el facilitador mock documentado en [`X402_MCP.md`](./X402_MCP.md) §8. Con ese mock, el frontend puede ejercitar el ciclo 402 → firma → 200 completo sin gastar fondos reales ni depender de que el relayer de OpenZeppelin esté arriba.
