const API_BASE = '/api'

export interface AnalyzeResponse {
  job_id: string
  github_url: string
  status: string
}

export interface StatusResponse {
  job_id: string
  status: string
  current_step: string | null
  error: string | null
  completed_at: string | null
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  sources?: Array<{
    file_path: string
    node_type: string
    name: string
    start_line: number
    end_line: number
  }>
}

export async function analyzeRepo(githubUrl: string): Promise<AnalyzeResponse> {
  const res = await fetch(`${API_BASE}/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ github_url: githubUrl }),
  })
  if (!res.ok) {
    const err = await res.json()
    throw new Error(err.detail || 'Analysis failed')
  }
  return res.json()
}

export async function getStatus(jobId: string): Promise<StatusResponse> {
  const res = await fetch(`${API_BASE}/status/${jobId}`)
  if (!res.ok) throw new Error('Job not found')
  return res.json()
}

export async function getReport(jobId: string) {
  const res = await fetch(`${API_BASE}/report/${jobId}`)
  if (!res.ok) {
    const err = await res.json()
    throw new Error(err.detail || 'Report not available')
  }
  return res.json()
}

export async function getDiagram(jobId: string) {
  const res = await fetch(`${API_BASE}/diagram/${jobId}`)
  if (!res.ok) {
    const err = await res.json()
    throw new Error(err.detail || 'Diagram not available')
  }
  return res.json()
}

export async function sendChat(jobId: string, question: string) {
  const res = await fetch(`${API_BASE}/chat/${jobId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
  })
  if (!res.ok) {
    const err = await res.json()
    throw new Error(err.detail || 'Chat failed')
  }
  return res.json()
}

export function extractRepoName(url: string): string {
  return url.replace(/\/$/, '').split('/').pop()?.replace('.git', '') || 'unknown'
}
