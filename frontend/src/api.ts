export type SourceKind = 'text' | 'photo' | 'floorplan';
export type RevisionKind = 'initial' | 'material' | 'layout';
export interface Config {
  brand: string;
  expert_name: string;
  turnstile_site_key: string | null;
  generation_ready: boolean;
  blocked_reason?: string | null;
}
export interface Session {
  csrf_token: string;
  id: string;
  changes_remaining: number;
  studio_id?: string | null;
  studios?: { id: string; status: string; created_at?: string }[];
}
export interface Revision {
  id: string;
  number: number;
  kind: RevisionKind;
  image_url: string;
  download_url: string;
  media_id: string;
  curation: string[];
  assumptions: string[];
  created_at: string;
  room_version: number;
  previous_room_basis?: boolean;
  review?: { mode?: string; requires_human_acceptance?: boolean; critical_error?: boolean; critical_reason?: string };
}
export interface Concept {
  key: 'A' | 'B' | 'C';
  title: string;
  status: string;
  error?: string | null;
  revisions: Revision[];
}
export interface Room {
  version?: number;
  source_kind?: SourceKind;
  assumptions?: string[];
  description?: string;
  features?: { name: string; value: string; provenance: 'USER_GIVEN' | 'DETECTED' | 'ASSUMED' | 'UNKNOWN' }[];
  constraints?: string[];
  [key: string]: unknown;
}
export interface Studio {
  id: string;
  status: string;
  source_kind?: SourceKind;
  error?: string | null;
  room: Room | null;
  selected_revision_id?: string | null;
  changes_remaining: number;
  concepts: Concept[];
}
export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message); }
}
let csrfToken = "";

export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  if (!path.startsWith('/api/')) throw new Error('Ungültiger API-Pfad.');
  const headers = new Headers(options.headers);
  if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json');
  headers.set('Accept', 'application/json');
  if (options.method && !['GET', 'HEAD', 'OPTIONS'].includes(options.method.toUpperCase()) && csrfToken) headers.set('X-CSRF-Token', csrfToken);
  let response: Response;
  try { response = await fetch(path, { ...options, headers, credentials: 'same-origin', cache: 'no-store' }); }
  catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error;
    throw new ApiError('Die Verbindung zum Studio ist unterbrochen. Deine vorhandenen Ergebnisse bleiben erhalten. Versuche es erneut.', 0);
  }
  if (response.status === 401) csrfToken = '';
  if (!response.ok) {
    const payload: unknown = await response.json().catch(() => null);
    const detail = payload && typeof payload === 'object' && 'detail' in payload ? payload.detail : null;
    throw new ApiError(typeof detail === 'string' ? detail : `Die Anfrage konnte nicht abgeschlossen werden (${response.status}).`, response.status);
  }
  if (response.status === 204) return undefined as T;
  let payload;
  try { payload = await response.json(); }
  catch { throw new ApiError('Der Server hat keine lesbare Antwort geliefert. Bitte prüfe die Verbindung erneut.', 502); }
  if (path === '/api/session' && typeof payload.csrf_token === 'string') csrfToken = payload.csrf_token;
  return payload as T;
}
export function privateMediaUrl(value: string | undefined): string | undefined {
  if (!value) return undefined;
  try {
    const url = new URL(value, window.location.origin);
    if (url.origin !== window.location.origin || !url.pathname.startsWith('/api/media/')) return undefined;
    return url.pathname + url.search;
  } catch { return undefined; }
}
export function isPending(status: string) { return ['queued', 'running', 'pending', 'generating', 'processing', 'analyzing'].includes(status); }
export function revisionLabel(revision: Revision) {
  const names: Record<RevisionKind, string> = { initial: 'Erster Entwurf', material: 'Materialänderung', layout: 'Aufbauänderung' };
  return `Version ${revision.number} · ${names[revision.kind] || 'Entwurf'}`;
}
