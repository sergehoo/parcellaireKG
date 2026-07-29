import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { sendCopilotMessage } from '../api/copilot'
import { downloadFile } from '../api/client'
import { getCopilotContext } from './pageContext'
import { requestMapFocus, requestMapDraw, requestMapCommand } from './mapBus'
import { miniMarkdown } from './markdown'

const WELCOME = {
  role: 'assistant',
  content: "Bonjour 👋 Je suis le **Copilote KAYDAN**. Je connais la page ouverte et "
    + "je peux : rechercher des programmes/parcelles, résumer le tableau de bord, "
    + "centrer la carte sur un programme, préparer un rapport. Que puis-je faire ?",
}

const MODELS = [
  { value: 'auto', label: 'Auto' },
  { value: 'deepseek', label: 'DeepSeek' },
]

// Défense en profondeur : n'autorise que des chemins relatifs same-origin
// (les actions proviennent déjà du backend, mais on ne suit jamais une URL
// absolue/externe — anti open-redirect / exfiltration).
function isSafeInternalPath(u) {
  if (typeof u !== 'string' || !u.startsWith('/') || u.startsWith('//')) return false
  try {
    return new URL(u, window.location.origin).origin === window.location.origin
  } catch {
    return false
  }
}

function onMapRoute() {
  const h = window.location.hash
  return h.startsWith('#/carte') || h === '#/' || h === ''
}

function runActions(actions, navigate) {
  for (const action of actions || []) {
    if (!action || !action.type) continue
    if (action.type === 'navigate' && isSafeInternalPath(action.to)) {
      navigate(action.to)
    } else if (action.type === 'download' && isSafeInternalPath(action.url)) {
      downloadFile(action.url, action.filename || 'export')
    } else if (action.type === 'map.focus') {
      if (!onMapRoute()) navigate('/carte')
      requestMapFocus({ center: action.center, zoom: action.zoom, name: action.name })
    } else if (action.type === 'map.circle') {
      if (!onMapRoute()) navigate('/carte')
      requestMapDraw({ kind: 'circle', center: action.center, radius_m: action.radius_m, label: action.name })
    } else if (action.type === 'map.line') {
      if (!onMapRoute()) navigate('/carte')
      requestMapDraw({ kind: 'line', points: action.points, label: action.label })
    } else if (action.type === 'map.basemap') {
      if (!onMapRoute()) navigate('/carte')
      requestMapCommand({ type: 'basemap', value: action.basemap })
    } else if (action.type === 'map.ortho') {
      if (!onMapRoute()) navigate('/carte')
      requestMapCommand({ type: 'ortho', program_id: action.program_id, on: action.on, center: action.center })
    }
    // action.type === 'confirm' : traité séparément (carte de confirmation),
    // jamais exécuté automatiquement — c'est le garde-fou effet de bord.
  }
}

// Libellés lisibles pour les actions à effet de bord soumises à confirmation.
const CONFIRM_LABELS = {
  retry_orthophoto_processing: "Relancer le traitement d'une orthophoto",
}

function describeConfirm(a) {
  const base = CONFIRM_LABELS[a.tool] || `Exécuter l'action « ${a.tool} »`
  const args = a.arguments && Object.keys(a.arguments).length
    ? ' — ' + Object.entries(a.arguments).map(([k, v]) => `${k}: ${v}`).join(', ')
    : ''
  return base + args
}

export default function CopilotPanel() {
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState([WELCOME])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [model, setModel] = useState('auto')
  const [pendingConfirm, setPendingConfirm] = useState(null)
  const convRef = useRef(null)
  const scrollRef = useRef(null)
  const navigate = useNavigate()

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight
  }, [messages, open])

  async function send(e) {
    e?.preventDefault()
    const text = input.trim()
    if (!text || busy) return
    setInput('')
    setMessages((m) => [...m, { role: 'user', content: text }])
    setBusy(true)
    try {
      const res = await sendCopilotMessage({
        message: text,
        conversationId: convRef.current,
        context: getCopilotContext(),
        model,
      })
      convRef.current = res.conversation_id || convRef.current
      setMessages((m) => [...m, { role: 'assistant', content: res.reply || '(réponse vide)' }])
      const confirm = (res.actions || []).find((a) => a && a.type === 'confirm')
      runActions(res.actions, navigate)
      if (confirm && confirm.token) {
        // On préfère le résumé lisible résolu côté serveur (nom du programme…) ;
        // l'exécution est liée au jeton signé, pas au libellé affiché.
        setPendingConfirm({ token: confirm.token, label: confirm.summary || describeConfirm(confirm) })
      }
    } catch (err) {
      const msg = err?.status === 503
        ? "Le Copilote n'est pas encore configuré (clé DeepSeek manquante côté serveur)."
        : (err?.message || 'Erreur du Copilote.')
      setMessages((m) => [...m, { role: 'assistant', content: `⚠️ ${msg}`, error: true }])
    } finally {
      setBusy(false)
    }
  }

  async function confirmPending() {
    const pc = pendingConfirm
    if (!pc || busy) return
    setPendingConfirm(null)
    setMessages((m) => [...m, { role: 'user', content: `✔️ ${pc.label}` }])
    setBusy(true)
    try {
      const res = await sendCopilotMessage({
        confirmAction: { token: pc.token },
        conversationId: convRef.current,
        context: getCopilotContext(),
      })
      convRef.current = res.conversation_id || convRef.current
      setMessages((m) => [...m, { role: 'assistant', content: res.reply || '(réponse vide)' }])
      runActions(res.actions, navigate)
    } catch (err) {
      setMessages((m) => [...m, { role: 'assistant',
        content: `⚠️ ${err?.message || "Échec de l'action."}`, error: true }])
    } finally {
      setBusy(false)
    }
  }

  function cancelPending() {
    if (!pendingConfirm) return
    setPendingConfirm(null)
    setMessages((m) => [...m, { role: 'assistant', content: 'Action annulée.' }])
  }

  return (
    <>
      {/* Bouton flottant — présent sur toutes les pages */}
      <button
        type="button" onClick={() => setOpen((v) => !v)}
        aria-label="Copilote IA"
        className="fixed bottom-5 right-5 z-[900] flex h-14 w-14 items-center justify-center rounded-full text-white shadow-xl transition hover:scale-105"
        style={{ background: 'var(--kaydan, #ea580c)' }}>
        <span className="text-2xl">{open ? '×' : '✨'}</span>
      </button>

      {open && (
        <div className="fixed bottom-24 right-5 z-[900] flex h-[70vh] max-h-[640px] w-[min(420px,calc(100vw-2.5rem))] flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl">
          <div className="flex items-center justify-between gap-2 border-b border-slate-200 px-4 py-3">
            <div className="flex items-center gap-2">
              <span className="flex h-7 w-7 items-center justify-center rounded-lg text-sm font-bold text-white"
                style={{ background: 'var(--kaydan, #ea580c)' }}>✨</span>
              <span className="text-sm font-semibold text-slate-800">Copilote KAYDAN</span>
            </div>
            <div className="flex items-center gap-2">
              <select value={model} onChange={(e) => setModel(e.target.value)}
                className="rounded-md border border-slate-300 bg-white px-1.5 py-1 text-xs text-slate-600">
                {MODELS.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
              </select>
              <button type="button" onClick={() => setOpen(false)}
                className="text-slate-400 hover:text-slate-700" aria-label="Fermer">×</button>
            </div>
          </div>

          <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto px-4 py-3">
            {messages.map((m, i) => (
              <div key={i} className={m.role === 'user' ? 'flex justify-end' : 'flex justify-start'}>
                <div className={`max-w-[85%] rounded-2xl px-3 py-2 text-sm ${
                  m.role === 'user'
                    ? 'bg-orange-600 text-white'
                    : m.error ? 'bg-rose-50 text-rose-700' : 'bg-slate-100 text-slate-800'
                }`}>
                  {m.role === 'assistant'
                    ? <div className="cp-md" dangerouslySetInnerHTML={{ __html: miniMarkdown(m.content) }} />
                    : m.content}
                </div>
              </div>
            ))}
            {busy && (
              <div className="flex justify-start">
                <div className="rounded-2xl bg-slate-100 px-3 py-2 text-sm text-slate-500">…</div>
              </div>
            )}
          </div>

          {pendingConfirm && (
            <div className="border-t border-amber-200 bg-amber-50 px-4 py-3">
              <p className="text-sm font-medium text-amber-900">Confirmer cette action ?</p>
              <p className="mt-0.5 text-xs text-amber-800">{pendingConfirm.label}</p>
              <div className="mt-2 flex gap-2">
                <button type="button" onClick={confirmPending} disabled={busy}
                  className="rounded-lg bg-amber-600 px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-50">
                  Confirmer
                </button>
                <button type="button" onClick={cancelPending} disabled={busy}
                  className="rounded-lg border border-amber-300 bg-white px-3 py-1.5 text-xs font-medium text-amber-800 disabled:opacity-50">
                  Annuler
                </button>
              </div>
            </div>
          )}

          <form onSubmit={send} className="border-t border-slate-200 p-3">
            <div className="flex items-end gap-2">
              <textarea
                value={input} onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) send(e) }}
                rows={1} placeholder="Demandez au Copilote…"
                className="max-h-28 min-h-[2.5rem] flex-1 resize-none rounded-xl border border-slate-300 px-3 py-2 text-sm outline-none focus:border-orange-500 focus:ring-1 focus:ring-orange-500" />
              <button type="submit" disabled={busy || !input.trim()}
                className="rounded-xl px-3.5 py-2 text-sm font-semibold text-white disabled:opacity-50"
                style={{ background: 'var(--kaydan, #ea580c)' }}>➤</button>
            </div>
          </form>
        </div>
      )}
    </>
  )
}
