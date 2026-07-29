// Mini-rendu Markdown SÉCURISÉ : on échappe d'abord tout le HTML (la sortie LLM
// est du contenu non fiable → jamais injectée telle quelle), puis on applique
// quelques motifs simples. Tableaux / Mermaid viendront en Phase ultérieure.
function escapeHtml(s) {
  return (s || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

export function miniMarkdown(text) {
  let html = escapeHtml(text)
  html = html.replace(/```([\s\S]*?)```/g,
    (_, code) => `<pre class="cp-code">${code.trim()}</pre>`)
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>')
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/^\s*[-*]\s+(.*)$/gm, '<li>$1</li>')
  html = html.replace(/(?:<li>[\s\S]*?<\/li>)(?:\s*<li>[\s\S]*?<\/li>)*/g,
    (m) => `<ul>${m}</ul>`)
  html = html.replace(/\n/g, '<br/>')
  return html
}
