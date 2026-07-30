/**
 * Upload multipart direct navigateur → MinIO via presigned URLs.
 *
 * Le backend (POST /orthophotos/upload/init/) fournit une URL signée PUT par
 * part ; on découpe le fichier et on PUT chaque tranche en parallèle. Résilience :
 *  - retries avec backoff exponentiel + jitter (une coupure réseau transitoire
 *    ne tue plus les 3 essais instantanément) ;
 *  - timeout par part (une part figée est ré-essayée, pas bloquée) ;
 *  - re-signature de la part sur échec réseau/expiration (refreshPartUrl) →
 *    l'URL peut être périmée ou la connexion coupée : on repart d'une URL fraîche.
 *
 * XMLHttpRequest plutôt que fetch : fetch n'expose pas la progression d'envoi,
 * indispensable pour des TIFF de plusieurs Go.
 */

// Plus de parts en parallèle = upload plus rapide (dans la limite de l'uplink).
const CONCURRENCY = 5
const RETRIES_PER_PART = 4
// Timeout par tentative de part : proportionnel à la taille (min 60 s).
const MIN_PART_TIMEOUT_MS = 60_000
const TIMEOUT_MS_PER_MB = 4_000

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

function putPart({ url, blob, signal, timeoutMs, onProgress }) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('PUT', url)
    xhr.timeout = timeoutMs

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(event.loaded)
    }
    xhr.onload = () => {
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
      const err = new Error('Erreur réseau pendant l’upload de la part')
      err.retryable = true
      reject(err)
    }
    xhr.ontimeout = () => {
      const err = new Error('Délai dépassé pendant l’upload de la part')
      err.retryable = true
      reject(err)
    }
    xhr.onabort = () => reject(new DOMException('Upload annulé', 'AbortError'))

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
      const timeoutMs = Math.max(MIN_PART_TIMEOUT_MS,
        Math.ceil((blob.size / (1024 * 1024)) * TIMEOUT_MS_PER_MB))

      let lastError = null
      for (let attempt = 0; attempt <= RETRIES_PER_PART; attempt += 1) {
        try {
          const etag = await putPart({
            url,
            blob,
            signal,
            timeoutMs,
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
