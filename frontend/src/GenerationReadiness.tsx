import type { Config } from './api';

export default function GenerationReadiness({ config, hasResults }: { config: Config | null; hasResults: boolean }) {
  if (!config || config.generation_ready) return null;
  return <p id="generation-readiness" className="readiness-note" role="status">{config.blocked_reason || 'Die Bilderstellung ist noch nicht freigegeben.'}{hasResults && ' Deine vorhandenen Bilder kannst Du weiter ansehen und herunterladen.'}</p>;
}
