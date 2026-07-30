/**
 * Upload multipart direct navigateur → MinIO via presigned URLs.
 *
 * Le backend (POST /orthophotos/upload/init/) fournit une URL signée PUT par
 * part ; on découpe le fichier et on PUT chaque tranche en parallèle. Résilience :
 *  - retries avec backoff exponentiel + jitter (une coupure réseau transitoire
 *    ne tue plus les essais instantanément) ;
 *  - timeout de STALL, pas de durée totale : on n'échoue que si AUCUN octet ne
 *    progresse pendant STALL_TIMEOUT_MS. Un upload lent (uplink limité, plusieurs
 *    parts en parallèle) n'est donc jamais coupé tant qu'il avance ;
 *  - re-signature de la part sur échec réseau/expiration (refreshPartUrl) →
 *    l'URL peut être périmée ou la connexion coupée : on repart d'une URL fraîche.
 *
 * XMLHttpRequest plutôt que fetch : fetch n'expose pas la progression d'envoi,
 * indispensable pour des TIFF de plusieurs Go.
 */

// Concurrence modérée : sur un uplink limité, trop de parts en parallèle se
// partagent la bande passante et ralentissent CHAQUE part (sans gagner de débit
// total). 3 = bon compromis débit/latence.
const CONCURRENCY = 3
const RETRIES_PER_PART = 4
// On échoue une part uniquement si elle N'AVANCE PLUS pendant ce délai
// (connexion réellement morte) — pas parce qu'elle est simplement lente.
const STALL_TIMEOUT_MS = 45_000

function delay(ms, signal) {
  return new Promise((resolve, reject) => {
    const t = setTimeout(resolve, ms)
    if (signal) {
      signal.addEventListener('abort', () => {
        clearTimeout(t)
        reject(new DOMException('Upload annulé', 'AbortError'))
      }, { once: true })
    }
  })
}

function putPart({ url, blob, signal, onProgress }) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('PUT', url)

    // Timeout de STALL : réarmé à chaque octet envoyé ; ne se déclenche que si
    // le transfert cesse de progresser (≠ transfert lent mais vivant).
    let stalled = false
    let stallTimer = null
    const armStall = () => {
      if (stallTimer) clearTimeout(stallTimer)
      stallTimer = setTimeout(() => { stalled = true; xhr.abort() }, STALL_TIMEOUT_MS)
    }
    const clearStall = () => { if (stallTimer) { clearTimeout(stallTimer); stallTimer = null } }

    xhr.upload.onloadstart = armStall
    xhr.upload.onprogress = (event) => {
      armStall()
      if (event.lengthComputable) onProgress(event.loaded)
    }
    xhr.onload = () => {
      clearStall()
      if (xhr.status >= 200 && xhr.status < 300) {
        // Nécessite ExposeHeaders: ETag dans la config CORS du bucket
        // (posée par storage.ensure_bucket_and_cors côté Django).
        const etag = xhr.getResponseHeader('ETag')
        if (!etag) {
          reject(new Error(
            "MinIO n'a pas exposé l'en-tête ETag (vérifier la config CORS du bucket).",
          ))
          return
        }
        resolve(etag)
      } else {
        const err = new Error(`PUT part échoué (HTTP ${xhr.status})`)
        // 4xx (hors 408/429) = permanent : ne pas s'entêter à ré-essayer.
        err.retryable = xhr.status >= 500 || xhr.status === 408 || xhr.status === 429
        reject(err)
      }
    }
    xhr.onerror = () => {
      clearStall()
      const err = new Error('Erreur réseau pendant l’upload de la part')
      err.retryable = true
      reject(err)
    }
    xhr.onabort = () => {
      clearStall()
      if (stalled) {
        const err = new Error('Transfert bloqué (aucune progression) pendant l’upload de la part')
        err.retryable = true
        reject(err)
      } else {
        reject(new DOMException('Upload annulé', 'AbortError'))
      }
    }

    if (signal) {
      if (signal.aborted) {
        reject(new DOMException('Upload annulé', 'AbortError'))
        return
      }
      signal.addEventListener('abort', () => xhr.abort(), { once: true })
    }
    xhr.send(blob)
  })
}

/**
 * @param {File} file
 * @param {{part_size: number, parts: {part_number: number, url: string}[]}} session
 * @param {{
 *   signal?: AbortSignal,
 *   onProgress?: (sentBytes: number, totalBytes: number) => void,
 *   refreshPartUrl?: (partNumber: number) => Promise<string>,
 *   concurrency?: number,
 * }} options
 * @returns {Promise<{PartNumber: number, ETag: string}[]>} parts pour /upload/complete/
 */
export async function uploadFileMultipart(file, session, options = {}) {
  const { signal, onProgress, refreshPartUrl } = options
  const concurrency = options.concurrency || CONCURRENCY
  const { part_size: partSize, parts } = session
  const sentByPart = new Array(parts.length).fill(0)
  const results = new Array(parts.length)

  const reportProgress = () => {
    if (onProgress) {
      const sent = sentByPart.reduce((a, b) => a + b, 0)
      onProgress(Math.min(sent, file.size), file.size)
    }
  }

  let nextIndex = 0
  async function worker() {
    while (nextIndex < parts.length) {
      const index = nextIndex
      nextIndex += 1
      const { part_number: partNumber } = parts[index]
      let url = parts[index].url
      const start = (partNumber - 1) * partSize
      const blob = file.slice(start, Math.min(start + partSize, file.size))

      let lastError = null
      for (let attempt = 0; attempt <= RETRIES_PER_PART; attempt += 1) {
        try {
          const etag = await putPart({
            url,
            blob,
            signal,
            onProgress: (loaded) => { sentByPart[index] = loaded; reportProgress() },
          })
          results[index] = { PartNumber: partNumber, ETag: etag }
          sentByPart[index] = blob.size
          reportProgress()
          lastError = null
          break
        } catch (error) {
          if (error.name === 'AbortError') throw error
          lastError = error
          sentByPart[index] = 0
          reportProgress()
          if (error.retryable === false || attempt === RETRIES_PER_PART) break
          // Backoff exponentiel + jitter avant de ré-essayer.
          const backoff = Math.min(1000 * 2 ** attempt, 8000) + Math.floor(Math.random() * 400)
          await delay(backoff, signal)
          // Re-signer la part : l'URL peut être périmée ou la connexion morte.
          if (refreshPartUrl) {
            try {
              const fresh = await refreshPartUrl(partNumber)
              if (fresh) url = fresh
            } catch { /* on garde l'URL courante si la re-signature échoue */ }
          }
        }
      }
      if (lastError) {
        throw new Error(`Part ${partNumber}/${parts.length} : ${lastError.message}`)
      }
    }
  }

  const workers = Array.from(
    { length: Math.min(concurrency, parts.length) },
    () => worker(),
  )
  await Promise.all(workers)
  return results
}
