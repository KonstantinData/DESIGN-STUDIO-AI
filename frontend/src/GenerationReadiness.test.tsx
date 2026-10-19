import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import GenerationReadiness from './GenerationReadiness';
import type { Config } from './api';

const config: Config = { brand: 'Test', expert_name: 'Test', turnstile_site_key: null, generation_ready: false };
describe('Ehrlicher Bereitschaftshinweis', () => {
  it('erfindet weder Kostenverbrauch noch vorhandene Ergebnisse', () => {
    const markup = renderToStaticMarkup(<GenerationReadiness config={config} hasResults={false} />);
    expect(markup).toContain('Die Bilderstellung ist noch nicht freigegeben.');
    expect(markup).not.toMatch(/Kosten|Budget|vorhandenen|Neue Entwürfe sind derzeit/);
  });
  it('zeigt den konkreten Servergrund und nennt Ergebnisse nur wenn tatsächlich vorhanden', () => {
    const markup = renderToStaticMarkup(<GenerationReadiness config={{ ...config, blocked_reason: 'Bilderstellung wurde manuell pausiert.' }} hasResults />);
    expect(markup).toContain('Bilderstellung wurde manuell pausiert.');
    expect(markup).toContain('Deine vorhandenen Bilder kannst Du weiter ansehen und herunterladen.');
  });
  it('zeigt keinen Sperrhinweis wenn bereit oder noch keine Konfiguration geladen ist', () => {
    expect(renderToStaticMarkup(<GenerationReadiness config={{ ...config, generation_ready: true }} hasResults />)).toBe('');
    expect(renderToStaticMarkup(<GenerationReadiness config={null} hasResults={false} />)).toBe('');
  });
});
