import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, privateMediaUrl, request } from './api';

afterEach(() => vi.unstubAllGlobals());

describe('Private Medien', () => {
  it('erlaubt nur private gleichursprüngliche API-Medien, keine fremden oder script URLs', () => {
    vi.stubGlobal('window', { location: { origin: 'https://studio.example' } });
    expect(privateMediaUrl('/api/media/abc?download=1')).toBe('/api/media/abc?download=1');
    expect(privateMediaUrl('https://attacker.example/api/media/abc')).toBeUndefined();
    expect(privateMediaUrl('javascript:alert(1)')).toBeUndefined();
    expect(privateMediaUrl('/api/media/../../public/photo')).toBeUndefined();
    expect(privateMediaUrl('/images/public.jpg')).toBeUndefined();
    expect(privateMediaUrl(undefined)).toBeUndefined();
  });
});

describe('Sitzung und CSRF', () => {
  it('hält den CSRF-Token im Speicher und überträgt ihn bei Änderungen zusammen mit der Cookie-Sitzung', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: 'session', csrf_token: 'csrf-token' })))
      .mockResolvedValueOnce(new Response(JSON.stringify({ accepted: true })));
    vi.stubGlobal('fetch', fetchMock);
    await request('/api/session');
    await request('/api/studios/studio/select', { method: 'POST', body: JSON.stringify({ revision_id: 'rev' }) });
    const options = fetchMock.mock.calls[1][1] as RequestInit;
    expect(options.credentials).toBe('same-origin');
    expect(options.cache).toBe('no-store');
    expect(new Headers(options.headers).get('X-CSRF-Token')).toBe('csrf-token');
    expect(new Headers(options.headers).get('Content-Type')).toBe('application/json');
  });
  it('wertet eine technische Antwort niemals als Erfolg', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: 'Kostenstopp aktiv' }), { status: 503 })));
    await expect(request('/api/studios')).rejects.toEqual(new ApiError('Kostenstopp aktiv', 503));
  });
  it('sendet keine API-Anfragen an beliebige Ziele', async () => {
    const fetchMock = vi.fn(); vi.stubGlobal('fetch', fetchMock);
    await expect(request('https://attacker.example')).rejects.toThrow('Ungültiger API-Pfad.');
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe('Abgelaufene oder beschädigte Sitzung', () => {
  it('verwirft den CSRF-Token nach 401 und verwendet erst den Token einer neu geöffneten Sitzung', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ csrf_token: 'old-csrf' })))
      .mockResolvedValueOnce(new Response(JSON.stringify({ detail: 'Abgelaufen' }), { status: 401 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ accepted: false })))
      .mockResolvedValueOnce(new Response(JSON.stringify({ csrf_token: 'new-csrf' })))
      .mockResolvedValueOnce(new Response(JSON.stringify({ resumed: true })));
    vi.stubGlobal('fetch', fetchMock);
    await request('/api/session');
    await expect(request('/api/studios/expired')).rejects.toEqual(new ApiError('Abgelaufen', 401));
    await request('/api/session/resume', { method: 'POST', body: JSON.stringify({ token: 'test-only-no-session' }) });
    expect(new Headers(fetchMock.mock.calls[2][1].headers).get('X-CSRF-Token')).toBeNull();
    await request('/api/session');
    await request('/api/session/resume', { method: 'POST', body: JSON.stringify({ token: 'test-only-continuation' }) });
    expect(new Headers(fetchMock.mock.calls[4][1].headers).get('X-CSRF-Token')).toBe('new-csrf');
  });
  it('meldet ungültige erfolgreiche Serverantworten als Fehler statt Daten oder Erfolg zu erfinden', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('<html>Proxy error</html>', { status: 200 })));
    await expect(request('/api/studios/test')).rejects.toEqual(new ApiError('Der Server hat keine lesbare Antwort geliefert. Bitte prüfe die Verbindung erneut.', 502));
  });
});
