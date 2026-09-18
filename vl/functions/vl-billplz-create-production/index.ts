import "jsr:@supabase/functions-js@2/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const ANON_KEY = Deno.env.get("SUPABASE_ANON_KEY") || Deno.env.get("SUPABASE_PUBLISHABLE_KEY") || "";
const API_KEY = (Deno.env.get("BILLPLZ_API_SECRET_KEY") || "").trim();
const COLLECTION_ID = (Deno.env.get("BILLPLZ_COLLECTION_ID") || "").trim();
const ALLOWED_ORIGIN = (Deno.env.get("LUNDUS_COMMERCIAL_ORIGIN") || "").trim();

const db = createClient(SUPABASE_URL, SERVICE_KEY, { auth: { persistSession: false } });

const cors = (origin: string | null) => ({
  "access-control-allow-origin": origin && origin === ALLOWED_ORIGIN ? origin : "null",
  "access-control-allow-headers": "authorization, apikey, content-type",
  "access-control-allow-methods": "POST, OPTIONS",
  "vary": "Origin",
});
const J = (body: unknown, status = 200, origin: string | null = null) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json", "cache-control": "no-store", ...cors(origin) },
  });

Deno.serve(async (req) => {
  const origin = req.headers.get("origin");
  if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: cors(origin) });
  if (req.method !== "POST") return J({ error: "POST required" }, 405, origin);
  if (!ALLOWED_ORIGIN || origin !== ALLOWED_ORIGIN) return J({ error: "origin not allowed" }, 403, origin);
  if (!API_KEY || !COLLECTION_ID) return J({ error: "production billing not configured", blocked: true }, 503, origin);

  const auth = req.headers.get("authorization") || "";
  if (!auth.startsWith("Bearer ")) return J({ error: "authenticated customer required" }, 401, origin);

  const userClient = createClient(SUPABASE_URL, ANON_KEY, {
    global: { headers: { Authorization: auth } },
    auth: { persistSession: false },
  });
  const { data: { user }, error: userErr } = await userClient.auth.getUser();
  if (userErr || !user) return J({ error: "authenticated customer required" }, 401, origin);

  const body = await req.json().catch(() => ({}));
  const offerKey = String(body.offer_key || "").trim();
  if (!offerKey) return J({ error: "offer_key required" }, 400, origin);

  const { data: account, error: accountErr } = await db
    .from("customer_accounts")
    .select("id,status,terms_accepted_at,display_name")
    .eq("owner_user_id", user.id)
    .eq("status", "active")
    .not("terms_accepted_at", "is", null)
    .limit(1)
    .maybeSingle();
  if (accountErr) return J({ error: "customer account lookup failed" }, 500, origin);
  if (!account) return J({ error: "active customer account with accepted terms required", blocked: true }, 403, origin);

  const { data: offer, error: offerErr } = await db
    .schema("private")
    .from("commercial_offers")
    .select("offer_key,offer_type,customer_account_id,display_name,amount_minor,currency,status,fulfillment_mode,valid_until")
    .eq("offer_key", offerKey)
    .eq("status", "active")
    .maybeSingle();

  if (offerErr) return J({ error: "offer lookup failed" }, 500, origin);
  if (!offer) return J({ error: "offer unavailable", blocked: true }, 404, origin);
  if (offer.currency !== "MYR" || !Number.isInteger(offer.amount_minor) || offer.amount_minor <= 0) {
    return J({ error: "offer invariant failed", blocked: true }, 409, origin);
  }
  if (offer.offer_type === "customer_quote") {
    if (offer.customer_account_id !== account.id) return J({ error: "offer not assigned to this customer", blocked: true }, 403, origin);
    if (!offer.valid_until || new Date(offer.valid_until).getTime() <= Date.now()) {
      return J({ error: "offer expired", blocked: true }, 410, origin);
    }
  } else if (offer.offer_type !== "public_fixed" || offer.customer_account_id !== null) {
    return J({ error: "offer scope invariant failed", blocked: true }, 409, origin);
  }

  const merchantReference = `lds-${offer.offer_key}-${crypto.randomUUID()}`;

  // Persist an authoritative pending order first. The partial unique index blocks
  // duplicate active orders for the same customer + offer before any provider bill exists.
  const { data: order, error: orderErr } = await db
    .schema("private")
    .from("payment_production_orders")
    .insert({
      adapter_key: "billplz-payment-v1",
      provider_bill_id: null,
      merchant_reference: merchantReference,
      amount_minor: offer.amount_minor,
      currency: "MYR",
      environment: "production",
      purpose: "commercial_order",
      status: "pending",
      fulfillment_state: "unfulfilled",
      checkout_url: null,
      created_by: user.id,
      offer_key: offer.offer_key,
      customer_account_id: account.id,
      metadata: {
        offer_key: offer.offer_key,
        offer_name: offer.display_name,
        offer_type: offer.offer_type,
        customer_account_id: account.id,
        fulfillment_mode: offer.fulfillment_mode,
        amount_source: "server_offer_catalog",
        client_amount_accepted: false,
        provider_bill_created: false,
      },
    })
    .select("id,merchant_reference,amount_minor,currency,status")
    .single();

  if (orderErr) {
    if (String(orderErr.code || "") === "23505") {
      return J({ error: "active order already exists for this offer", blocked: true }, 409, origin);
    }
    return J({ error: "order reservation failed", blocked: true }, 500, origin);
  }

  const callbackUrl = `${SUPABASE_URL}/functions/v1/vl-billplz-webhook-production`;
  const form = new URLSearchParams();
  form.set("collection_id", COLLECTION_ID);
  form.set("description", offer.display_name);
  form.set("email", user.email || "");
  form.set("name", account.display_name || "Customer");
  form.set("amount", String(offer.amount_minor));
  form.set("callback_url", callbackUrl);
  form.set("reference_1_label", "Offer");
  form.set("reference_1", offer.offer_key);
  form.set("reference_2_label", "Merchant Reference");
  form.set("reference_2", merchantReference);

  const basic = btoa(`${API_KEY}:`);
  const response = await fetch("https://www.billplz.com/api/v3/bills", {
    method: "POST",
    headers: {
      Authorization: `Basic ${basic}`,
      "content-type": "application/x-www-form-urlencoded",
    },
    body: form.toString(),
  });

  const data = await response.json().catch(() => null);
  if (!response.ok || !data?.id || !data?.url) {
    await db.schema("private").from("payment_production_orders").update({
      status: "failed",
      updated_at: new Date().toISOString(),
      metadata: {
        offer_key: offer.offer_key,
        offer_name: offer.display_name,
        offer_type: offer.offer_type,
        customer_account_id: account.id,
        fulfillment_mode: offer.fulfillment_mode,
        amount_source: "server_offer_catalog",
        client_amount_accepted: false,
        provider_bill_created: false,
        provider_create_failed: true,
        provider_status: response.status,
      },
    }).eq("id", order.id).eq("status", "pending");

    return J({ error: "payment provider create bill failed", blocked: true, provider_status: response.status }, 502, origin);
  }

  const { data: finalOrder, error: updateErr } = await db
    .schema("private")
    .from("payment_production_orders")
    .update({
      provider_bill_id: String(data.id),
      checkout_url: String(data.url),
      updated_at: new Date().toISOString(),
      metadata: {
        offer_key: offer.offer_key,
        offer_name: offer.display_name,
        offer_type: offer.offer_type,
        customer_account_id: account.id,
        fulfillment_mode: offer.fulfillment_mode,
        amount_source: "server_offer_catalog",
        client_amount_accepted: false,
        provider_bill_created: true,
      },
    })
    .eq("id", order.id)
    .eq("status", "pending")
    .select("id,provider_bill_id,merchant_reference,amount_minor,currency,status,checkout_url")
    .single();

  if (updateErr) {
    return J({ error: "provider bill created but order finalisation failed", blocked: true, manual_review: true }, 500, origin);
  }

  return J({
    ok: true,
    order_id: finalOrder.id,
    merchant_reference: finalOrder.merchant_reference,
    amount_minor: finalOrder.amount_minor,
    currency: finalOrder.currency,
    checkout_url: finalOrder.checkout_url,
    payment_status: "pending",
    fulfillment_state: "unfulfilled",
  }, 200, origin);
});
