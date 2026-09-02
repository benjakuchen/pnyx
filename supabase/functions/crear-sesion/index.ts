// Pnyx · Edge Function: crear-sesion
// La app la llama para iniciar la verificacion. Crea una sesion en Didit
// y devuelve la URL donde el usuario hace selfie + DNI.
// La API Key de Didit vive aca (secreta), nunca en la app.

import { serve } from "https://deno.land/std@0.224.0/http/server.ts";

const DIDIT_API_KEY = Deno.env.get("DIDIT_API_KEY")!;
const DIDIT_WORKFLOW_ID = Deno.env.get("DIDIT_WORKFLOW_ID")!;
const DIDIT_BASE = "https://verification.didit.me";

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

function json(obj, status, extra) {
  return new Response(JSON.stringify(obj), {
    status: status || 200,
    headers: { ...cors, "Content-Type": "application/json" },
  });
}

serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });

  try {
    const { user_id } = await req.json();
    if (!user_id) return json({ error: "falta user_id" }, 400);

    const r = await fetch(`${DIDIT_BASE}/v3/session/`, {
      method: "POST",
      headers: {
        "x-api-key": DIDIT_API_KEY,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        workflow_id: DIDIT_WORKFLOW_ID,
        vendor_data: user_id,   // asi el webhook sabe de que usuario es
      }),
    });

    const data = await r.json();
    if (!r.ok) return json({ error: "didit fallo", detalle: data }, 502);

    // data.url = pagina de verificacion; data.session_id = id de la sesion
    return json({ url: data.url, session_id: data.session_id }, 200);
  } catch (e) {
    return json({ error: String(e) }, 500);
  }
});
