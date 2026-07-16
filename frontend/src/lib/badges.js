// Couleur de badge déduite du libellé de statut (français). Classes
// statiques → non purgées par Tailwind.
export function badgeClass(value) {
  const v = (value || '').toLowerCase()
  if (/(disponible|ouvert|nouveau)/.test(v)) return 'bg-sky-100 text-sky-700'
  if (/(réserv|reserv|attente|planifi|négoc|negoc|documents)/.test(v)) return 'bg-amber-100 text-amber-700'
  if (/(vendu|confirm|signé|signe|finalisé|finalise|converti|terminé|termine|payé|paye)/.test(v)) return 'bg-emerald-100 text-emerald-700'
  if (/(bloqu|litige|rejet|annul|perdu|échec|echec)/.test(v)) return 'bg-rose-100 text-rose-700'
  return 'bg-slate-100 text-slate-700'
}
