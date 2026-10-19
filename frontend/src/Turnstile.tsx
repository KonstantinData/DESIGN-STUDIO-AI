import { useEffect, useRef, useState } from 'react';

type TurnstileApi = {
  render: (element: HTMLElement, options: Record<string, unknown>) => string;
  remove: (widget: string) => void;
};
declare global { interface Window { turnstile?: TurnstileApi } }
let scriptPromise: Promise<void> | null = null;

function loadTurnstile() {
  if (window.turnstile) return Promise.resolve();
  if (!scriptPromise) {
    scriptPromise = new Promise<void>((resolve, reject) => {
      const script = document.createElement('script');
      script.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';
      script.async = true;
      script.onload = () => resolve();
      script.onerror = () => reject(new Error('Bot-Schutz konnte nicht geladen werden. Prüfe die Verbindung und lade die Seite neu.'));
      document.head.append(script);
    }).catch((error) => { scriptPromise = null; throw error; });
  }
  return scriptPromise;
}

export default function Turnstile({ siteKey, onToken, resetKey }: { siteKey: string; onToken: (value: string) => void; resetKey: number }) {
  const container = useRef<HTMLDivElement>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    let cancelled = false;
    let widget: string | undefined;
    onToken('');
    setError('');
    loadTurnstile().then(() => {
      if (cancelled || !container.current || !window.turnstile) return;
      widget = window.turnstile.render(container.current, {
        sitekey: siteKey,
        theme: 'light',
        language: 'de',
        callback: (token: string) => onToken(token),
        'expired-callback': () => onToken(''),
        'error-callback': () => { onToken(''); setError('Der Bot-Schutz ist fehlgeschlagen. Lade die Seite neu und versuche es erneut.'); },
      });
    }).catch((reason: Error) => { if (!cancelled) setError(reason.message); });
    return () => { cancelled = true; if (widget && window.turnstile) window.turnstile.remove(widget); };
  }, [siteKey, onToken, resetKey]);
  return <div className="bot-check"><div ref={container} />{error && <p role="alert" className="field-error">{error}</p>}</div>;
}
