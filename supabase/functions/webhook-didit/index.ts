// Pnyx · Edge Function: webhook-didit
// Didit la llama cuando cambia el estado de una verificacion.
// Si aprobo, marca verificado=true y guarda un hash del DNI (no el DNI en claro).
// Valida la firma HMAC + el timestamp (anti-reataque) como pide la doc de Didit.

import { serve } from "https://deno.land/std@0.224.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL");
const SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
const WEBHOOK_SECRET = Deno.env.get("DIDIT_WEBHOOK_SECRET");

// Hash SHA-256 del DNI: guardamos huella, no el numero real.
async function hashDni(dni) {
  const data = new TextEncoder().encode(dni + "|pnyx-sal");
  const buf = await crypto.subtle.digest("SHA-256", data);
  return Array.from(new Uint8Array(buf)).map((b) => b.toString(16).padStart(2, "0")).join("");
}

// HMAC-SHA256 en hex, para validar que el webhook viene de Didit.
async function hmacHex(payload, secret) {
  const key = await crypto.subtle.importKey(
    "raw", new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" }, false, ["sign"],
  );
  const sig = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(payload));
  return Array.from(new Uint8Array(sig)).map((b) => b.toString(16).padStart(2, "0")).join("");
}

serve(async (req) => {
  try {
    const raw = await req.text();

    // 1) Validar firma y timestamp (headers de Didit)
    const firma = req.headers.get("x-signature") || "";
    const ts = req.headers.get("x-timestamp") || "";
    if (!firma || !ts) return new Response("faltan headers", { status: 401 });

    // El timestamp debe ser reciente (±5 min) para evitar reenvios maliciosos
    const ahora = Math.floor(Date.now() / 1000);
    if (Math.abs(ahora - parseInt(ts)) > 300) {
      return new Response("timestamp viejo", { status: 401 });
    }

    const esperada = await hmacHex(raw, WEBHOOK_SECRET);
    if (firma !== esperada) return new Response("firma invalida", { status: 401 });

    // 2) Procesar el evento
    const evento = JSON.parse(raw);
    const userId = evento.vendor_data;     // el user_id que mandamos al crear la sesion
    const estado = evento.status;          // "Approved", "Declined", "In Review", etc.
    const sessionId = evento.session_id;

    if (!userId) return new Response("sin vendor_data", { status: 200 });

    const sb = createClient(SUPABASE_URL, SERVICE_KEY);

    if (estado === "Approved") {
      // El DNI viene dentro de decision (resultado de RENAPER / ID verification).
      // Los nombres exactos del campo pueden variar; probamos las ubicaciones tipicas.
      const dec = evento.decision || {};
      const dni =
        dec?.id_verification?.document_number ||
        dec?.kyc?.document_number ||
        dec?.arg_renaper?.document_number ||
        null;
      const dniHash = dni ? await hashDni(String(dni)) : null;

      await sb.from("identidad_verificada").upsert({
        user_id: userId,
        verificado: true,
        metodo: "didit_renaper",
        dni_hash: dniHash,
        verificado_en: new Date().toISOString(),
        didit_session_id: sessionId,
      }, { onConflict: "user_id" });
    } else {
      // Cualquier otro estado: registrar el intento sin marcar verificado.
      await sb.from("identidad_verificada").upsert({
        user_id: userId,
        verificado: false,
        metodo: "didit_renaper",
        didit_session_id: sessionId,
      }, { onConflict: "user_id" });
    }

    return new Response("ok", { status: 200 });
  } catch (e) {
    return new Response("error: " + String(e), { status: 500 });
  }
});
