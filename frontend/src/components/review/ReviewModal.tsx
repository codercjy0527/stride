import { useState, useEffect, useRef } from 'react'
import { X, Loader2, Heart, Timer, Footprints, TrendingUp, Zap, MapPin, ChevronRight, ArrowUpRight, ArrowDownRight, Minus } from 'lucide-react'
import { activities as activitiesApi } from '@/services/api'
import type { ActivityRecord, ReviewResult, ReviewSection, ReviewComparison } from '@/types'

const SECTION_ICONS: Record<string, any> = {
  '概要': Footprints,
  '强度': TrendingUp,
  '对比': Timer,
  '负荷': Heart,
  '建议': ChevronRight,
  '下次': Zap,
}

interface Props {
  activity: ActivityRecord
  onClose: () => void
}

export default function ReviewModal({ activity, onClose }: Props) {
  const [result, setResult] = useState<ReviewResult | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const provider = localStorage.getItem('ai_provider') || 'deepseek'
    const apiKey = localStorage.getItem('ai_api_key') || ''
    activitiesApi.review(activity.id, provider, apiKey)
      .then((r) => setResult(r.data))
      .catch(() => setError('复盘请求失败，请检查网络连接'))
      .finally(() => setLoading(false))
  }, [activity.id])

  const a = activity

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="glass-card rounded-2xl w-full max-w-2xl max-h-[88vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[rgba(255,255,255,0.05)] shrink-0">
          <div>
            <h2 className="text-lg font-bold text-[#E8ECF2]">{a.date} 运动复盘</h2>
            <p className="text-xs text-[#5A6080] mt-0.5">
              {a.distance_km}km · {a.avg_pace}/km · {a.duration_min}min
            </p>
          </div>
          <button onClick={onClose} className="p-1.5 text-[#5A6080] hover:text-[#C8CCD8] hover:bg-[rgba(255,255,255,0.05)] rounded-lg transition-all">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Key metrics bar */}
        <div className="px-6 py-3 border-b border-[rgba(255,255,255,0.03)] grid grid-cols-3 sm:grid-cols-6 gap-3 text-center shrink-0">
          <MetricBadge icon={Footprints} label="距离" value={`${a.distance_km ?? '--'} km`} />
          <MetricBadge icon={Timer} label="配速" value={a.avg_pace ? `${a.avg_pace}/km` : '--'} />
          <MetricBadge icon={Heart} label="心率" value={a.avg_hr ? `${a.avg_hr} bpm` : '--'} />
          <MetricBadge icon={TrendingUp} label="时长" value={a.duration_min ? `${a.duration_min}min` : '--'} />
          <MetricBadge icon={Zap} label="消耗" value={a.calories ? `${a.calories} kcal` : '--'} />
          <MetricBadge icon={Footprints} label="步频" value={a.avg_cadence ? `${a.avg_cadence} spm` : '--'} />
          {a.avg_stride_length ? <MetricBadge icon={MapPin} label="步幅" value={`${a.avg_stride_length}m`} /> : <MetricBadge icon={MapPin} label="地点" value={a.location || '--'} />}
        </div>

        {/* Content */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto px-6 py-5 space-y-4">
          {loading && <LoadingState />}
          {error && <ErrorState error={error} onClose={onClose} />}

          {result && (
            <>
              {/* Offline banner */}
              {result.offline && (
                <div className="px-3 py-2.5 bg-[rgba(234,179,8,0.04)] border border-[rgba(234,179,8,0.1)] rounded-lg text-xs text-[#8A94A6] flex items-center gap-2">
                  <Zap className="w-3.5 h-3.5 text-yellow-500 shrink-0" />
                  配置 API Key 可解锁 AI 深度分析，当前为基础数据总结
                </div>
              )}

              {/* Comparison cards */}
              {result.comparison && <ComparisonCards comp={result.comparison} />}

              {/* Review sections */}
              {result.sections.map((section, i) => (
                <SectionCard key={i} section={section} />
              ))}

              {/* Recent runs */}
              {result.comparison?.recent_runs.length > 0 && (
                <RecentRuns runs={result.comparison.recent_runs} />
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}

function MetricBadge({ icon: Icon, label, value }: { icon: any; label: string; value: string }) {
  return (
    <div className="p-2 bg-[rgba(255,255,255,0.015)] rounded-lg border border-[rgba(255,255,255,0.03)]">
      <Icon className="w-3.5 h-3.5 text-red-400 mx-auto mb-1 opacity-60" />
      <p className="text-[10px] text-[#5A6080]">{label}</p>
      <p className="text-xs font-semibold text-[#C8CCD8] mt-0.5">{value}</p>
    </div>
  )
}

function SectionCard({ section }: { section: ReviewSection }) {
  const Icon = SECTION_ICONS[section.title] || ChevronRight
  return (
    <div className="p-4 bg-[rgba(255,255,255,0.015)] rounded-xl border border-[rgba(255,255,255,0.04)]">
      <div className="flex items-center gap-2 mb-2">
        <Icon className="w-4 h-4 text-red-400" />
        <h3 className="text-sm font-semibold text-[#E5E5E7]">{section.title}</h3>
      </div>
      <p className="text-sm text-[#8A94A6] leading-relaxed">{section.content}</p>
    </div>
  )
}

function ComparisonCards({ comp }: { comp: ReviewComparison }) {
  const trends = [
    comp.trend_distance && { label: '距离', ...comp.trend_distance, unit: 'km', format: (v: number) => `${v}km` },
    comp.trend_pace && { label: '配速', current: comp.trend_pace.current, recent_avg: comp.trend_pace.recent_avg, direction: comp.trend_pace.direction, unit: '', format: (v: string) => v },
    comp.trend_hr && { label: '心率', current: comp.trend_hr.current, recent_avg: comp.trend_hr.recent_avg, direction: comp.trend_hr.direction, unit: '', format: (v: number) => `${v}bpm` },
  ].filter(Boolean)

  if (trends.length === 0) return null

  return (
    <div className="grid grid-cols-3 gap-3">
      {trends.map((t: any) => (
        <div key={t.label} className="p-3 bg-[rgba(255,255,255,0.015)] rounded-xl border border-[rgba(255,255,255,0.04)] text-center">
          <p className="text-[10px] text-[#5A6080] mb-1.5">{t.label}</p>
          <p className="text-lg font-bold text-[#E8ECF2] font-mono">{t.format(t.current)}</p>
          <p className="text-[10px] text-[#3A4060] mt-0.5">近期均值 {t.format(t.recent_avg)}</p>
          <div className="flex items-center justify-center gap-0.5 mt-1.5">
            {t.direction === 'up'
              ? <ArrowUpRight className="w-3.5 h-3.5 text-emerald-400" />
              : t.direction === 'down'
                ? <ArrowDownRight className="w-3.5 h-3.5 text-red-400" />
                : <Minus className="w-3.5 h-3.5 text-[#5A6080]" />
            }
            <span className={`text-xs font-medium ${
              t.direction === 'up' ? 'text-emerald-400' : t.direction === 'down' ? 'text-red-400' : 'text-[#5A6080]'
            }`}>
              {t.direction === 'up' ? '上升' : t.direction === 'down' ? '下降' : '持平'}
            </span>
          </div>
        </div>
      ))}
    </div>
  )
}

function RecentRuns({ runs }: { runs: any[] }) {
  return (
    <div className="p-4 bg-[rgba(255,255,255,0.015)] rounded-xl border border-[rgba(255,255,255,0.04)]">
      <h3 className="text-sm font-semibold text-[#E5E5E7] mb-3 flex items-center gap-2">
        <Timer className="w-4 h-4 text-red-400" />
        近期训练记录
      </h3>
      <div className="space-y-1.5">
        {runs.map((r, i) => (
          <div key={i} className="flex items-center justify-between py-1.5 px-2 rounded-lg hover:bg-[rgba(255,255,255,0.02)] transition-colors">
            <span className="text-xs text-[#5A6080] font-mono w-24">{r.date}</span>
            <span className="text-xs text-[#C8CCD8] font-mono">{r.distance_km ?? '?'}km</span>
            <span className="text-xs text-[#8A94A6] font-mono">{r.avg_pace || '--'}</span>
            <span className="text-xs text-[#8A94A6] font-mono w-16 text-right">
              {r.avg_hr ? `${r.avg_hr}bpm` : '--'}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

function LoadingState() {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-[#5A6080]">
      <Loader2 className="w-8 h-8 animate-spin mb-4 text-red-400" />
      <p className="text-sm">正在分析运动数据</p>
      <p className="text-xs mt-1 opacity-50">综合心率、配速、近期训练等多维度分析</p>
    </div>
  )
}

function ErrorState({ error, onClose }: { error: string; onClose: () => void }) {
  return (
    <div className="text-center py-16">
      <p className="text-sm text-red-400">{error}</p>
      <button onClick={onClose} className="mt-4 px-4 py-2 text-sm text-[#5A6080] hover:text-[#C8CCD8] hover:bg-[rgba(255,255,255,0.05)] rounded-lg transition-all">
        关闭
      </button>
    </div>
  )
}
