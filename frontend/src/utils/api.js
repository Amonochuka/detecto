const API_BASE = '/api'

async function handleResponse(res) {
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    const msg = body.detail || body.message || `Request failed (${res.status})`
    throw new Error(msg)
  }
  return res.json()
}

export async function detectImage(file) {
  const form = new FormData()
  form.append('file', file)

  const res = await fetch(`${API_BASE}/detect`, { method: 'POST', body: form })
  return handleResponse(res)
}

export async function fetchHistory({ date, limit = 100 } = {}) {
  const params = new URLSearchParams()
  if (date) params.set('date', date)
  params.set('limit', limit)

  const res = await fetch(`${API_BASE}/history?${params}`)
  return handleResponse(res)
}

export async function resetHistory() {
  const res = await fetch(`${API_BASE}/reset`, { method: 'POST' })
  return handleResponse(res)
}

export async function exportHistory({ date, limit = 100, format = 'csv' } = {}) {
  const params = new URLSearchParams()
  if (date) params.set('date', date)
  params.set('limit', limit)
  params.set('format', format)

  const res = await fetch(`${API_BASE}/export?${params}`)
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || `Export failed (${res.status})`)
  }
  return res.blob()
}
