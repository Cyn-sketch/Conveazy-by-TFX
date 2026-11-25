export type ApiError = { status: number; code: string; message: string };

export async function api<T = unknown>(path: string, init: RequestInit & { json?: unknown } = {}): Promise<T> {
  const { json, headers, ...rest } = init;
  const res = await fetch(`/api${path}`, {
    credentials: "same-origin",
    ...rest,
    headers: {
      "X-Conveazy-Client": "web",
      ...(json !== undefined ? { "Content-Type": "application/json" } : {}),
      ...headers,
    },
    body: json !== undefined ? JSON.stringify(json) : rest.body,
  });
  if (res.status === 204) return undefined as T;
  let data: any = null;
  try { data = await res.json(); } catch { /* non-JSON */ }
  if (!res.ok) {
    const d = data?.detail;
    const err: ApiError = {
      status: res.status,
      code: (typeof d === "object" && d?.code) || "error",
      message: (typeof d === "object" && d?.message) || (typeof d === "string" ? d : "Something went wrong. Please try again."),
    };
    throw err;
  }
  return data as T;
}

export const isApiError = (e: unknown): e is ApiError => typeof e === "object" && !!e && "code" in e && "status" in e;

// ---- shared types (mirror backend contracts; see docs/API.md) ----
export type User = { id: string; email: string; display_name: string; pronouns: string | null; onboarded: boolean };
export type Crisis = { level: "concern" | "urgent"; message: string; resources: { region: string; name: string; contact: string }[] };
export type Citation = { id: string; title: string; publisher: string; url: string; kind: string; evidence_level: string };
export type AIEnvelope<T> = {
  module: string; status: "ok" | "crisis" | "declined"; live: boolean; provider: string; prompt_version: string | null;
  result: T | null; citations: Citation[]; crisis: Crisis | null; notice: string | null; conversation_id?: string;
};
export type TranslatorResult = {
  intent_summary: string; feelings_detected: string[]; needs_detected: string[];
  flags: { phrase: string; category: string; how_it_may_land: string }[];
  how_original_may_land: string; versions: { style: string; text: string }[];
  changes: { what: string; why: string }[]; preserved: string[]; boundary_note: string | null;
};
export type PartnerAnswer = {
  answer: string; evidence: { claim: string; level: "established" | "possible" | "individual"; source_ids: string[] }[];
  what_cannot_be_inferred: string; try_this: string[]; avoid: string[]; ask_your_partner: string[];
  professional_help_note: string | null;
};
export type Reflection = {
  situation: string; interpretation: string; evidence_check: string; alternative_interpretations: string[];
  emotions: string[]; validation: string; possible_needs: string[]; communication: string;
  escalation_signs: string[]; next_step: string;
};
export type Trait = { trait: string; sign: string };
export type Exercise = { id: string; name: string; good: string; source: string; steps: string[]; caution?: string };
export type FeelingBrief = { feeling: string; intensity: number | null; why: string; like: string[]; need: string; traits: Trait[] };
export type BridgeResult = {
  raw_feelings: { right_now: string; feelings: string[]; underneath: string | null; feelings_line: string; intensity: number | null; traits: Trait[] } | null;
  brief: FeelingBrief | null; calm: { id: string; why: string; exercise: Exercise }[];
  understood_meaning: string; core_points: string[]; sender_feelings: string[]; clarifying_question: string | null;
  message: string; short_version: string | null; alternatives: { style: string; text: string }[];
  why_this_works: { choice: string; reason: string; grounded_in: "their_profile" | "evidence" | "general" }[];
  avoided: { pattern: string; because: string }[]; kept_true: string[]; timing_note: string | null; source_ids: string[];
};
export type BridgeEnvelope = AIEnvelope<BridgeResult> & { recipient: { name: string | null; profile_items_used: number; checkin_signal: boolean } };
