import { useState } from 'react'
import { X, Timer, Loader2, Zap } from 'lucide-react'
import { training } from '@/services/api'
import type { TrainingSession, CheckpointAnalysis } from '@/types'

export default function CheckpointModal({
  session, onClose, onSaved,
}: {
  session: TrainingSession
  onClose: () => void
  onSaved: () => void
}) {
  const [minutes, setMinutes] = useState(session.checkpoint_result_sec ? Math.floor(session.checkpoint_result_sec / 60) : 0)
  const [seconds, setSeconds] = useState(session.checkpoint_result_sec ? session.checkpoint_result_sec % 60 : 0)
  const [notes, setNotes] = useState(session.checkpoint_notes || '')
  const [saving, setSaving] = useState(false)
  const [aiResult, setAiResult] = useState<string | null>(null)
  const [aiLoading, setAiLoading] = useState(false)
  const [analysis, setAnalysis] = useState<CheckpointAnalysis | null>(null)

  const hasResult = session.checkpoint_result_sec

  const handleSubmit = async () => {
    const totalSecs = minutes * 60 + seconds
    if (totalSecs <= 0) return
    setSaving(true)
    await training.submitCheckpoint(session.id, { result_seconds: totalSecs, notes: notes || undefined })
    setSaving(false)
    onSaved()
    // Refresh session data
    const res = await training.listSessions(session.plan_id)
    const updated = res.data.find((s: TrainingSession) => s.id === session.id)
    if (updated?.checkpoint_result_sec) {
      setMinutes(Math.floor(updated.checkpoint_result_sec / 60))
      setSeconds(updated.checkpoint_result_sec % 60)
      // Fetch analysis after submit
      fetchAnalysis()
    }
  }

  const fetchAnalysis = async () => {
    try {
      const res = await training.getCheckpointAnalysis(session.plan_id, session.week)
      setAnalysis(res.data)
    } catch { /* no analysis available */ }
  }

  const handleAIAnalyze = async () => {
    setAiLoading(true)
    try {
      const provider = localStorage.getItem('ai_provider') || 'deepseek'
      const apiKey = localStorage.getItem('ai_api_key') || ''
      const model = localStorage.getItem('ai_model') || ''
      const res = await training.getCheckpointAIAnalysis(session.plan_id, session.week, provider, apiKey, model)
      setAiResult(res.data.reply)
    } catch (e: any) {
      setAiResult(e.response?.data?.detail || 'AI 分析失败，请确认已配置 API Key')
    }
    setAiLoading(false)
  }

  // Load analysis on mount if result exists
  useState(() => {
    if (session.checkpoint_result_sec) fetchAnalysis()
  })

  const trendLabels: Record<string, string> = {
    baseline: '基准线', improving: '进步中', declining: '下滑中', plateauing: '平台期',
  }
  const trendColors: Record<string, string> = {
    baseline: 'text-[#5A6080]', improving: 'text-emerald-400', declining: 'text-red-400', plateauing: 'text-amber-400',
  }

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50">
      <div className="glass-card rounded-2xl p-6 w-full max-w-sm max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-2">
            <Timer className="w-5 h-5 text-purple-400" />
            <h3 className="text-lg font-bold text-[#E8ECF2]">检查点测试</h3>
          </div>
          <button onClick={onClose} className="text-[#5A6080] hover:text-[#C8CCD8] transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        <p className="text-sm text-[#8A94A6] mb-4">
          第 {session.week} 周 · {session.description}
        </p>

        {/* Result Input */}
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-[#8A94A6] mb-2">测试成绩</label>
            <div className="flex items-center gap-2">
              <input type="number" min={0} max={120} value={minutes || ''}
                onChange={e => setMinutes(Number(e.target.value) || 0)}
                className="w-20 px-3 py-2.5 bg-[rgba(255,255,255,0.03)] border border-[rgba(255,255,255,0.08)] rounded-lg text-sm text-center text-[#E8ECF2] focus:outline-none focus:ring-2 focus:ring-purple-600/40" />
              <span className="text-[#C8CCD8] font-bold">:</span>
              <input type="number" min={0} max={59} value={seconds || ''}
                onChange={e => setSeconds(Number(e.target.value) || 0)}
                className="w-20 px-3 py-2.5 bg-[rgba(255,255,255,0.03)] border border-[rgba(255,255,255,0.08)] rounded-lg text-sm text-center text-[#E8ECF2] focus:outline-none focus:ring-2 focus:ring-purple-600/40" />
              <span className="text-xs text-[#5A6080]">分:秒</span>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-[#8A94A6] mb-1.5">体感备注</label>
            <textarea value={notes} onChange={e => setNotes(e.target.value)}
              placeholder="天气、路面、体感状态..."
              rows={2} className="w-full px-3 py-2.5 bg-[rgba(255,255,255,0.03)] border border-[rgba(255,255,255,0.08)] rounded-lg text-sm text-[#E8ECF2] placeholder-[#5A6080] focus:outline-none focus:ring-2 focus:ring-purple-600/40 resize-none" />
          </div>

          <button onClick={handleSubmit} disabled={saving}
            className="w-full py-2.5 bg-purple-700 text-white rounded-lg font-medium hover:bg-purple-600 transition-colors text-sm disabled:opacity-50">
            {saving ? '保存中...' : hasResult ? '更新成绩' : '提交成绩'}
          </button>
        </div>

        {/* Analysis Section */}
        {(hasResult || analysis) && (
          <div className="mt-5 pt-4 border-t border-[rgba(255,255,255,0.06)]">
            {analysis && (
              <div className="space-y-2 mb-4">
                <h4 className="text-sm font-medium text-[#C8CCD8]">趋势分析</h4>
                <div className="flex items-center gap-3 text-sm">
                  <span className={`font-semibold ${trendColors[analysis.trend]}`}>
                    {trendLabels[analysis.trend]}
                  </span>
                  {analysis.delta_pct !== null && (
                    <span className={`text-xs ${analysis.delta_pct > 0 ? 'text-emerald-400' : analysis.delta_pct < 0 ? 'text-red-400' : 'text-[#5A6080]'}`}>
                      {analysis.delta_pct > 0 ? '↑' : '↓'} {Math.abs(analysis.delta_pct)}%
                    </span>
                  )}
                </div>
              </div>
            )}

            {aiResult ? (
              <div className="bg-[rgba(255,255,255,0.03)] rounded-lg p-3 text-sm text-[#C8CCD8] whitespace-pre-wrap">
                {aiResult}
              </div>
            ) : (
              <button onClick={handleAIAnalyze} disabled={aiLoading}
                className="w-full flex items-center justify-center gap-2 py-2.5 border border-[rgba(255,255,255,0.08)] rounded-lg text-sm text-[#8A94A6] hover:text-[#C8CCD8] hover:border-[rgba(255,255,255,0.15)] transition-all disabled:opacity-50">
                {aiLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Zap className="w-4 h-4" />}
                {aiLoading ? 'AI 分析中...' : 'AI 分析检查点'}
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
