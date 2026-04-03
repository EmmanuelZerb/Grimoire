import { useState, useEffect, useCallback, useRef } from 'react'
import { analyzeRepo, getStatus, type StatusResponse } from '../lib/api'

type AnalysisPhase = 'idle' | 'analyzing' | 'completed' | 'failed'

interface AnalysisState {
  phase: AnalysisPhase
  jobId: string | null
  githubUrl: string
  status: StatusResponse | null
  error: string | null
  repoName: string
}

export function useAnalysis() {
  const [state, setState] = useState<AnalysisState>({
    phase: 'idle',
    jobId: null,
    githubUrl: '',
    status: null,
    error: null,
    repoName: '',
  })

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
  }, [])

  const startPolling = useCallback((jobId: string) => {
    stopPolling()
    pollRef.current = setInterval(async () => {
      try {
        const status = await getStatus(jobId)
        setState(prev => ({ ...prev, status }))

        if (status.status === 'completed' || status.status === 'qa_ready') {
          stopPolling()
          setState(prev => ({ ...prev, phase: 'completed' }))
        } else if (status.status === 'failed') {
          stopPolling()
          setState(prev => ({
            ...prev,
            phase: 'failed',
            error: status.error || 'Analysis failed',
          }))
        }
      } catch (err: any) {
        stopPolling()
        const msg = err?.message?.includes('Job not found')
          ? 'Le serveur a redémarré et a perdu l\'analyse. Relancez l\'analyse.'
          : 'Connexion au serveur perdue. Vérifiez que le backend tourne.'
        setState(prev => ({ ...prev, phase: 'failed', error: msg }))
      }
    }, 2000)
  }, [stopPolling])

  const startAnalysis = useCallback(async (url: string) => {
    setState({
      phase: 'analyzing',
      jobId: null,
      githubUrl: url,
      status: null,
      error: null,
      repoName: extractRepoName(url),
    })

    try {
      const res = await analyzeRepo(url)
      setState(prev => ({ ...prev, jobId: res.job_id }))
      startPolling(res.job_id)
    } catch (err) {
      setState(prev => ({
        ...prev,
        phase: 'failed',
        error: err instanceof Error ? err.message : 'Failed to start analysis',
      }))
    }
  }, [startPolling])

  const reset = useCallback(() => {
    stopPolling()
    setState({
      phase: 'idle',
      jobId: null,
      githubUrl: '',
      status: null,
      error: null,
      repoName: '',
    })
  }, [stopPolling])

  useEffect(() => {
    return () => stopPolling()
  }, [stopPolling])

  return { ...state, startAnalysis, reset }
}

function extractRepoName(url: string): string {
  return url.replace(/\/$/, '').split('/').pop()?.replace('.git', '') || 'unknown'
}
