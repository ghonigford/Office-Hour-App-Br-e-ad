import type { OptimizeRequest, OptimizeResponse, OptimizeResult } from "../types";

const JSON_HEADERS = { "Content-Type": "application/json" } as const;

export async function runOptimize(payload: OptimizeRequest): Promise<OptimizeResponse> {
  const response = await fetch("/api/optimize", {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify(payload),
  });
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    throw new Error(`Server returned ${response.status} with no JSON body.`);
  }
  if (!response.ok) {
    const err = body as { error?: string };
    throw new Error(err?.error || `Server error (${response.status}).`);
  }
  return body as OptimizeResponse;
}

export async function fetchSharedResult(token: string): Promise<OptimizeResult> {
  const response = await fetch(`/api/share/${encodeURIComponent(token)}`);
  if (!response.ok) {
    if (response.status === 404) throw new Error("Shared schedule not found.");
    throw new Error(`Failed to load shared schedule (${response.status}).`);
  }
  const body = (await response.json()) as { result: OptimizeResult };
  return body.result;
}
