type Kind = 'up-right' | 'down-right' | 'down' | 'spark' | 'photo' | 'floorplan' | 'check';
const paths: Record<Kind, string> = {
  'up-right': 'M6 18 18 6M6 6h12v12',
  'down-right': 'M6 6 18 18M6 18h12V6',
  down: 'M12 4v16M5 13l7 7 7-7',
  spark: 'm12 2 3 7 7 3-7 3-3 7-3-7-7-3 7-3Z',
  photo: 'M3 4h18v16H3ZM3 16l5-5 5 5 3-3 5 5M15 8h.01',
  floorplan: 'M3 3h18v18H3ZM3 10h7V3M10 10v11M10 15h11',
  check: 'm5 12 4 4L19 6',
};
export default function Icon({ kind }: { kind: Kind }) {
  return <svg className="ui-icon" viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" focusable="false" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d={paths[kind]} /></svg>;
}
