// Mini-rendu Markdown SÉCURISÉ : on échappe d'abord tout le HTML (la sortie LLM
// est du contenu non fiable → jamais injectée telle quelle), puis on applique
// quelques motifs simples + les tableaux GFM. Le contenu des cellules reste
// échappé (le HTML a été neutralisé avant tout traitement).
function escapeHtml(s) {
  return (s || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

function splitRow(line) {
  return line.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map((c) => c.trim())
}

// Convertit les blocs de tableau GFM (| a | b | / | --- | --- | / lignes) en <table>.
function renderTables(html) {
  const lines = html.split('\n')
  const out = []
  const isRow = (l) => /^\s*\|.*\|\s*$/.test(l)
  const isSep = (l) => /-/.test(l) && /^\s*\|?[\s:|-]+\|?\s*$/.test(l)
  let i = 0
  while (i < lines.length) {
    if (isRow(lines[i]) && i + 1 < lines.length && isSep(lines[i + 1])) {
      const header = splitRow(lines[i])
      i += 2
      const rows = []
      while (i < lines.length && isRow(lines[i])) { rows.push(splitRow(lines[i])); i += 1 }
      const th = header.map((c) => `<th>${c}</th>`).join('')
      const body = rows.map((r) => `<tr>${r.map((c) => `<td>${c}</td>`).join('')}</tr>`).join('')
      out.push(`<div class="cp-table-wrap"><table class="cp-table">`
        + `<thead><tr>${th}</tr></thead><tbody>${body}</tbody></table></div>`)
    } else {
      out.push(lines[i])
      i += 1
    }
  }
  return out.join('\n')
}

export function miniMarkdown(text) {
  let html = escapeHtml(text)
  html = html.replace(/```([\s\S]*?)```/g,
    (_, code) => `<pre class="cp-code">${code.trim()}</pre>`)
  html = renderTables(html)  // avant la conversion des retours à la ligne
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>')
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/^\s*[-*]\s+(.*)$/gm, '<li>$1</li>')
  html = html.replace(/(?:<li>[\s\S]*?<\/li>)(?:\s*<li>[\s\S]*?<\/li>)*/g,
    (m) => `<ul>${m}</ul>`)
  // Ne pas insérer de <br/> entre les balises de tableau (sinon lignes vides).
  html = html.replace(/\n/g, '<br/>').replace(/<br\/>(?=\s*<(?:div class="cp-table-wrap"|\/table|thead|tbody|tr|th|td))/g, '')
  return html
}
