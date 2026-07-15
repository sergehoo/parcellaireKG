/**
 * Upload multipart direct navigateur → MinIO via presigned URLs.
 *
 * Le backend (POST /orthophotos/upload/init/) fournit une URL signée
 * PUT par part ; on découpe le fichier, on PUT chaque tranche (3 en
 * parallèle, 2 retries par part), on collecte les ETag renvoyés par
 * MinIO puis on appelle /orthophotos/upload/complete/.
 *
 * XMLHttpRequest plutôt que fetch : fetch n'expose pas la progression
 * d'envoi, indispensable pour des TIFF de plusieurs Go.
 */

const CONCURRENCY = 3
const RETRIES_PER_PART = 2

function putPart({ url, blob, signal, onProgress }) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('PUT', url)

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
        reject(new Error(`PUT part échoué (HTTP ${xhr.status})`))
      }
    }
    xhr.onerror = () => reject(new Error('Erreur réseau pendant l’upload de la part'))
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
 *        Réponse de /orthophotos/upload/init/.
 * @param {{signal?: AbortSignal, onProgress?: (sentBytes: number, totalBytes: number) => void}} options
 * @returns {Promise<{PartNumber: number, ETag: string}[]>} parts pour /upload/complete/
 */
export async function uploadFileMultipart(file, session, { signal, onProgress } = {}) {
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
      const { part_number: partNumber, url } = parts[index]
      const start = (partNumber - 1) * partSize
      const blob = file.slice(start, Math.min(start + partSize, file.size))

      let lastError = null
      for (let attempt = 0; attempt <= RETRIES_PER_PART; attempt += 1) {
        try {
          const etag = await putPart({
            url,
            blob,
            signal,
            onProgress: (loaded) => {
              sentByPart[index] = loaded
              reportProgress()
            },
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
        }
      }
      if (lastError) {
        throw new Error(`Part ${partNumber}/${parts.length} : ${lastError.message}`)
      }
    }
  }

  const workers = Array.from(
    { length: Math.min(CONCURRENCY, parts.length) },
    () => worker(),
  )
  await Promise.all(workers)
  return results
}
