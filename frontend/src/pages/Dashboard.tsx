import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Flame, Target, TrendingUp, Activity, Moon, Heart, Zap, Mountain, Clock, AlertTriangle, ThumbsUp, Footprints, BarChart3, Brain, Timer, Gauge } from 'lucide-react'
import { checkin, training, coros } from '@/services/api'
import type { CheckinStats, TrainingPlan, FitnessMetric } from '@/types'
import CheckinButton from '@/components/checkin/CheckinButton'

export default function Dashboard() {
  const [stats, setStats] = useState<CheckinStats | null>(null)
  const [plans, setPlans] = useState<TrainingPlan[]>([])
  const [metrics, setMetrics] = useState<FitnessMetric[]>([])
  const [adjustment, setAdjustment] = useState<any>(null)
  const [todayMetric, setTodayMetric] = useState<FitnessMetric | null>(null)
  const [weeklyKm, setWeeklyKm] = useState(0)
  const [weeklyRuns, setWeeklyRuns] = useState(0)
  const [weeklyDuration, setWeeklyDuration] = useState(0)
  const [weeklyElevation, setWeeklyElevation] = useState(0)
  const [weeklyLoad, setWeeklyLoad] = useState(0)
  const [vo2max, setVo2max] = useState<number | null>(null)
  const [lthr, setLthr] = useState<number | null>(null)
  const [recentActivities, setRecentActivities] = useState<any[]>([])
  const [fitnessAssess, setFitnessAssess] = useState<any>(null)
  const navigate = useNavigate()

  const loadData = () => {
    checkin.stats().then((r) => setStats(r.data))
    training.listPlans().then((r) => setPlans(r.data))
    coros.dashboard().then((r) => {
      const d = r.data
      setMetrics(d?.recent || [])
      setTodayMetric(d?.today || null)
      setAdjustment(d?.daily_adjustment || null)
      setWeeklyKm(d?.weekly_km || 0)
      setWeeklyRuns(d?.weekly_runs || 0)
      setWeeklyDuration(d?.weekly_duration_min || 0)
      setWeeklyElevation(d?.weekly_elevation || 0)
      setWeeklyLoad(d?.weekly_load || 0)
      setVo2max(d?.vo2max || null)
      setLthr(d?.lthr || null)
      setRecentActivities(d?.recent_activities || [])
    }).catch(() => {})
    coros.fitnessAssessment().then((r) => setFitnessAssess(r.data)).catch(() => {})
  }

  useEffect(() => { loadData() }, [])

  const latestMetric = todayMetric || metrics[0]
  const hasData = !!latestMetric

  // Trend arrays (chronological order)
  const trendData = [...metrics].reverse()
  const vo2maxTrend = trendData.filter(m => m.vo2max != null).map(m => m.vo2max!)
  const hrvTrend = trendData.filter(m => m.hrv != null).map(m => m.hrv!)
  const rhrTrend = trendData.filter(m => m.resting_hr != null).map(m => m.resting_hr!)

  const racePreds = fitnessAssess?.race_predictions

  return (
    <div className="max-w-5xl mx-auto space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-[#E8ECF2] tracking-tight">训练仪表盘</h1>
          <p className="text-xs text-[#5A6080] mt-0.5">Performance Dashboard</p>
        </div>
        <CheckinButton onSuccess={() => { checkin.stats().then((r) => setStats(r.data)) }} />
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard icon={Flame} label="累计打卡" value={`${stats?.total_days || 0} 天`} accent="text-orange-400" />
        <StatCard icon={TrendingUp} label="连胜" value={`${stats?.streak_days || 0} 天`} accent="text-emerald-400" />
        <StatCard icon={Target} label="周跑量" value={`${weeklyKm} km`} accent="text-red-400" />
        <StatCard icon={Activity} label="训练次数" value={`${weeklyRuns} 次`} accent="text-purple-400" />
      </div>

      {/* ===== P0: Recovery + Race Predictions ===== */}
      {hasData && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Recovery Gauge + HRV/RHR trends */}
          <div className="glass-card rounded-xl p-5">
            <SectionLabel icon={Brain} color="text-purple-400">恢复状态</SectionLabel>
            <div className="flex items-center gap-5">
              <RecoveryRing value={latestMetric.recovery_score ?? 0} size={100} strokeWidth={8} />
              <div className="flex-1 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] text-[#5A6080] uppercase tracking-wider">HRV 7日</span>
                  <Sparkline data={hrvTrend} width={100} height={28} color="#8B5CF6" />
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-[10px] text-[#5A6080] uppercase tracking-wider">静息心率 7日</span>
                  <Sparkline data={rhrTrend} width={100} height={28} color="#EF4444" />
                </div>
                {latestMetric.tired_rate != null && (
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] text-[#5A6080] uppercase tracking-wider">疲劳度</span>
                    <span className={`text-sm font-bold tabular-nums ${
                      latestMetric.tired_rate > 0.6 ? 'text-red-400' : latestMetric.tired_rate > 0.3 ? 'text-yellow-400' : 'text-emerald-400'
                    }`}>{latestMetric.tired_rate.toFixed(1)}</span>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Race Predictions */}
          <div className="glass-card rounded-xl p-5">
            <SectionLabel icon={Timer} color="text-amber-400">赛事预测</SectionLabel>
            {racePreds && (racePreds["5k"] || racePreds["10k"] || racePreds.half_marathon || racePreds.marathon) ? (
              <div className="grid grid-cols-4 gap-3">
                {[
                  { key: '5k', label: '5K', dist: '5 km' },
                  { key: '10k', label: '10K', dist: '10 km' },
                  { key: 'half_marathon', label: '半马', dist: '21.1 km' },
                  { key: 'marathon', label: '全马', dist: '42.2 km' },
                ].map(({ key, label, dist }) => (
                  <div key={key} className="text-center p-2.5 bg-[rgba(255,255,255,0.04)] rounded-lg border border-[rgba(255,255,255,0.06)]">
                    <p className="text-[10px] text-[#5A6080] uppercase tracking-wider">{label}</p>
                    <p className="font-bold font-mono text-sm text-[#E8ECF2] tabular-nums mt-1">
                      {racePreds[key] || '--'}
                    </p>
                    <p className="text-[9px] text-[#3A4060] mt-0.5">{dist}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-[#5A6080]">同步 COROS 数据后获取赛事预测</p>
            )}
            {fitnessAssess?.running_level && (
              <div className="flex items-center gap-2 mt-3 pt-3 border-t border-[rgba(255,255,255,0.04)]">
                <Gauge className="w-3.5 h-3.5 text-amber-400" />
                <span className="text-[11px] text-[#8A94A6]">跑步等级</span>
                <span className="text-[11px] font-semibold text-amber-400">{fitnessAssess.running_level}</span>
                {fitnessAssess.threshold_pace && (
                  <>
                    <span className="text-[#3A4060]">·</span>
                    <span className="text-[11px] text-[#8A94A6]">阈值配速</span>
                    <span className="text-[11px] font-mono font-semibold text-[#C8CCD8]">{fitnessAssess.threshold_pace}</span>
                  </>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Weekly Overview */}
      {(weeklyDuration > 0 || weeklyElevation > 0 || weeklyLoad > 0) && (
        <div className="grid grid-cols-3 gap-3">
          <MiniStat icon={Clock} label="本周时长" value={`${Math.round(weeklyDuration)} min`} />
          <MiniStat icon={Mountain} label="累计爬升" value={`${weeklyElevation} m`} />
          <MiniStat icon={Zap} label="训练负荷" value={`${weeklyLoad}`} />
        </div>
      )}

      {/* ===== P0: VO₂max Trend ===== */}
      {hasData && vo2maxTrend.length >= 2 && (
        <div className="glass-card rounded-xl p-5">
          <div className="flex items-center justify-between mb-3">
            <SectionLabel icon={TrendingUp} color="text-emerald-400">VO₂max 趋势</SectionLabel>
            <span className="text-[11px] text-[#5A6080]">14日</span>
          </div>
          <div className="flex items-end gap-2 h-24">
            {vo2maxTrend.map((v, i) => {
              const min = Math.min(...vo2maxTrend)
              const max = Math.max(...vo2maxTrend)
              const range = max - min || 1
              const h = 20 + ((v - min) / range) * 70
              return (
                <div key={i} className="flex-1 flex flex-col items-center gap-1">
                  <span className="text-[9px] font-mono text-[#E8ECF2] tabular-nums">{v}</span>
                  <div
                    className="w-full rounded-t-sm"
                    style={{
                      height: `${h}%`,
                      background: i === vo2maxTrend.length - 1
                        ? 'linear-gradient(180deg, #059669, #065F46)'
                        : 'linear-gradient(180deg, rgba(5,150,105,0.4), rgba(6,95,70,0.2))',
                    }}
                  />
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Sleep Section */}
      {hasData && (
        <div className="glass-card rounded-xl p-5">
          <SectionLabel icon={Moon} color="text-indigo-400">睡眠</SectionLabel>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
            {latestMetric.sleep_hours != null && (
              <MetricBadge label="总时长" value={`${latestMetric.sleep_hours}h`} />
            )}
            {latestMetric.deep_sleep_min != null && (
              <MetricBadge label="深度睡眠" value={`${latestMetric.deep_sleep_min}min`} sub={`${Math.round(latestMetric.deep_sleep_min / (latestMetric.sleep_hours || 1) / 60 * 100)}%`} />
            )}
            {latestMetric.rem_sleep_min != null && (
              <MetricBadge label="REM" value={`${latestMetric.rem_sleep_min}min`} sub={`${Math.round(latestMetric.rem_sleep_min / (latestMetric.sleep_hours || 1) / 60 * 100)}%`} />
            )}
            {latestMetric.light_sleep_min != null && (
              <MetricBadge label="浅睡" value={`${latestMetric.light_sleep_min}min`} />
            )}
            {latestMetric.sleep_avg_hr != null && (
              <MetricBadge label="睡眠心率" value={`${latestMetric.sleep_avg_hr} bpm`} sub={latestMetric.sleep_min_hr && latestMetric.sleep_max_hr ? `${latestMetric.sleep_min_hr}-${latestMetric.sleep_max_hr}` : undefined} />
            )}
            {latestMetric.sleep_quality != null && latestMetric.sleep_quality > 0 && (
              <MetricBadge label="质量评分" value={`${'★'.repeat(Math.min(5, latestMetric.sleep_quality))}`} />
            )}
          </div>
        </div>
      )}

      {/* Training Load: Stamina + Load ratio */}
      {hasData && (latestMetric.stamina_level != null || latestMetric.training_load_ratio != null || latestMetric.ati != null) && (
        <div className="glass-card rounded-xl p-5">
          <SectionLabel icon={Zap} color="text-amber-400">训练负荷</SectionLabel>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
            {latestMetric.stamina_level != null && (
              <MetricBadge label="体能水平" value={latestMetric.stamina_level.toFixed(1)} />
            )}
            {latestMetric.stamina_7d != null && (
              <MetricBadge label="体能趋势(7d)" value={latestMetric.stamina_7d.toFixed(1)} sub={latestMetric.stamina_level && latestMetric.stamina_7d > latestMetric.stamina_level ? '↑ 上升' : '↓ 下降'} />
            )}
            {latestMetric.training_load_ratio != null && (
              <MetricBadge label="负荷比 (AC/CT)" value={latestMetric.training_load_ratio.toFixed(1)} color={latestMetric.training_load_ratio > 1.5 ? 'text-red-400' : latestMetric.training_load_ratio > 1.0 ? 'text-yellow-400' : 'text-emerald-400'} sub={latestMetric.training_load_ratio > 1.5 ? '偏高' : latestMetric.training_load_ratio > 1.0 ? '适中' : '偏低'} />
            )}
            {latestMetric.ati != null && (
              <MetricBadge label="急性负荷 (ATI)" value={latestMetric.ati.toFixed(0)} />
            )}
            {latestMetric.cti != null && (
              <MetricBadge label="慢性负荷 (CTI)" value={latestMetric.cti.toFixed(0)} />
            )}
          </div>
        </div>
      )}

      {/* Daily Training Adjustment */}
      {adjustment && adjustment.adjustment !== 'none' && (
        <div className={`rounded-xl border p-4 flex items-start gap-3 ${
          adjustment.adjustment === 'rest'
            ? 'bg-[rgba(185,28,28,0.04)] border-[rgba(185,28,28,0.12)]'
            : 'bg-[rgba(201,168,76,0.04)] border-[rgba(201,168,76,0.12)]'
        }`}>
          {adjustment.adjustment === 'rest' ? (
            <AlertTriangle className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
          ) : (
            <ThumbsUp className="w-5 h-5 text-accent-gold shrink-0 mt-0.5" />
          )}
          <div className="text-sm">
            <p className="font-semibold text-[#C8CCD8]">今日训练建议</p>
            {adjustment.suggestions?.map((s: string, i: number) => (
              <p key={i} className="text-[#8A94A6] mt-1">• {s}</p>
            ))}
          </div>
        </div>
      )}

      {/* Health + Advanced Metrics */}
      {hasData && (
        <div className="glass-card rounded-xl p-5">
          <SectionLabel icon={Heart} color="text-red-400">生理指标</SectionLabel>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
            {latestMetric.resting_hr != null && <MetricBadge label="静息心率" value={`${latestMetric.resting_hr} bpm`} />}
            {latestMetric.hrv != null && <MetricBadge label="HRV" value={`${latestMetric.hrv} ms`} />}
            {vo2max && <MetricBadge label="VO₂max" value={`${vo2max}`} />}
            {lthr && <MetricBadge label="乳酸阈值心率" value={`${lthr} bpm`} />}
          </div>
        </div>
      )}

      {/* Recent Activities */}
      {recentActivities.length > 0 && (
        <div className="glass-card rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xs font-semibold text-[#B8BEC8] flex items-center gap-2 uppercase tracking-wider">
              <Footprints className="w-3.5 h-3.5 text-red-400" />
              本周运动
            </h2>
            <span className="text-[11px] text-[#5A6080] tabular-nums">{weeklyRuns} 次 · {weeklyKm} km</span>
          </div>
          <div className="space-y-1.5">
            {recentActivities.map((a: any) => (
              <div key={a.id} className="flex items-center justify-between p-3 bg-[rgba(255,255,255,0.02)] rounded-lg border border-[rgba(255,255,255,0.03)] hover:bg-[rgba(255,255,255,0.035)] transition-colors">
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-lg bg-[rgba(185,28,28,0.08)] flex items-center justify-center border border-[rgba(185,28,28,0.1)]">
                    <Footprints className="w-4 h-4 text-red-400" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-[#C8CCD8]">{a.date}</p>
                    <div className="flex items-center gap-2 text-[11px] text-[#5A6080]">
                      {a.max_hr && <span>最大{a.max_hr}bpm</span>}
                      {a.elevation_gain > 0 && <span>爬升{a.elevation_gain}m</span>}
                      {a.training_load > 0 && <span>负荷{a.training_load}</span>}
                    </div>
                  </div>
                </div>
                <div className="text-right">
                  <p className="font-mono font-bold text-[#E8ECF2] text-sm tabular-nums">{a.distance_km} km</p>
                  <p className="text-[11px] text-[#5A6080]">
                    {a.avg_pace ? `配速 ${a.avg_pace}` : ''}
                    {a.avg_hr ? ` · 心率 ${a.avg_hr}` : ''}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* No data prompt */}
      {!hasData && (
        <div className="text-center py-14">
          <div className="w-12 h-12 mx-auto mb-4 rounded-2xl bg-[rgba(255,255,255,0.02)] border border-[rgba(255,255,255,0.04)] flex items-center justify-center">
            <BarChart3 className="w-5 h-5 text-[#3A4060]" />
          </div>
          <p className="text-sm text-[#5A6080]">暂无 COROS 数据</p>
          <p className="text-xs text-[#3A4060] mt-1.5">
            前往 <button onClick={() => navigate('/settings')} className="text-red-400 hover:text-red-300 underline underline-offset-2 transition-colors">设置</button> 页面登录 COROS 并同步
          </p>
        </div>
      )}

      {/* Training Plans */}
      <div className="glass-card rounded-xl p-5">
        <h2 className="text-xs font-semibold text-[#B8BEC8] mb-4 uppercase tracking-wider">训练计划</h2>
        {plans.length === 0 ? (
          <p className="text-xs text-[#5A6080]">暂无计划，前往「训练计划」创建</p>
        ) : (
          <div className="space-y-1.5">
            {plans.map((plan) => {
              const pct = Math.round((plan.completed_sessions / (plan.total_sessions || 1)) * 100)
              return (
                <div key={plan.id} className="flex items-center justify-between p-3 bg-[rgba(255,255,255,0.02)] rounded-lg border border-[rgba(255,255,255,0.03)]">
                  <div>
                    <p className="font-medium text-sm text-[#C8CCD8]">{plan.name}</p>
                    <p className="text-[11px] text-[#5A6080]">{plan.weeks} 周 · 目标{plan.target_race}</p>
                  </div>
                  <div className="text-right">
                    <div className="text-base font-bold font-mono text-red-400 tabular-nums">{pct}%</div>
                    <div className="w-20 h-1 bg-[rgba(255,255,255,0.05)] rounded-full mt-1.5 overflow-hidden">
                      <div className="h-full rounded-full"
                        style={{
                          width: `${pct}%`,
                          background: 'linear-gradient(90deg, #991B1B, #DC2626)',
                          boxShadow: '0 0 6px rgba(220, 38, 38, 0.15)',
                        }} />
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}

// ── Recovery Ring (SVG circular gauge) ──

function RecoveryRing({ value, size = 100, strokeWidth = 8 }: { value: number; size?: number; strokeWidth?: number }) {
  const radius = (size - strokeWidth) / 2
  const circumference = radius * 2 * Math.PI
  const pct = Math.min(100, Math.max(0, value)) / 100
  const offset = circumference * (1 - pct)

  const color = value >= 60 ? '#059669' : value >= 30 ? '#D97706' : '#DC2626'
  const glow = value >= 60 ? 'rgba(5,150,105,0.3)' : value >= 30 ? 'rgba(217,119,6,0.3)' : 'rgba(220,38,38,0.3)'

  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="rgba(255,255,255,0.04)" strokeWidth={strokeWidth} />
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke={color} strokeWidth={strokeWidth}
          strokeLinecap="round" strokeDasharray={circumference} strokeDashoffset={offset}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
          style={{ filter: `drop-shadow(0 0 6px ${glow})`, transition: 'stroke-dashoffset 0.8s ease' }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-xl font-bold text-[#E8ECF2] tabular-nums">{Math.round(value)}</span>
        <span className="text-[9px] text-[#5A6080]">%</span>
      </div>
    </div>
  )
}

// ── Sparkline (SVG mini trend) ──

function Sparkline({ data, width = 80, height = 24, color = '#8B5CF6' }: { data: number[]; width?: number; height?: number; color?: string }) {
  if (data.length < 2) {
    return <div style={{ width: width + 40, height }} className="flex items-center justify-end"><span className="text-[9px] text-[#3A4060]">--</span></div>
  }

  const min = Math.min(...data)
  const max = Math.max(...data)
  const range = max - min || 1
  const p = 2

  const pts = data.map((v, i) => {
    const x = p + (i / (data.length - 1)) * (width - p * 2)
    const y = height - p - ((v - min) / range) * (height - p * 2)
    return `${x},${y}`
  }).join(' ')

  const lastV = data[data.length - 1]
  const firstV = data[0]
  const trend = lastV - firstV
  const lineColor = trend >= 0 ? (color === '#EF4444' ? '#EF4444' : '#059669') : color === '#EF4444' ? '#059669' : '#EF4444'

  return (
    <div className="flex items-center gap-1.5" style={{ width: width + 40 }}>
      <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} className="shrink-0">
        <polyline points={pts} fill="none" stroke={lineColor} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      <span className="text-[10px] font-mono tabular-nums" style={{ color: lineColor }}>
        {trend > 0 ? '↑' : trend < 0 ? '↓' : '→'}
      </span>
    </div>
  )
}

// ── Shared sub-components ──

function SectionLabel({ icon: Icon, color, children }: { icon: any; color: string; children: string }) {
  return (
    <h3 className="text-[11px] font-semibold text-[#8A94A6] uppercase tracking-wider mb-4 flex items-center gap-2">
      <Icon className={`w-3.5 h-3.5 ${color}`} />
      {children}
    </h3>
  )
}

function StatCard({ icon: Icon, label, value, accent }: { icon: any; label: string; value: string; accent: string }) {
  return (
    <div className="glass-card-solid rounded-xl p-3.5 flex items-center gap-3">
      <div className={`p-2 rounded-lg bg-[rgba(255,255,255,0.04)] border border-[rgba(255,255,255,0.05)] ${accent}`}>
        <Icon className="w-4 h-4" />
      </div>
      <div>
        <p className="text-[10px] text-[#5A6080] uppercase tracking-wider">{label}</p>
        <p className="font-bold text-lg text-[#E8ECF2] tabular-nums">{value}</p>
      </div>
    </div>
  )
}

function MiniStat({ icon: Icon, label, value }: { icon: any; label: string; value: string }) {
  return (
    <div className="glass-card rounded-xl p-3.5 flex items-center gap-3">
      <Icon className="w-4 h-4 text-[#5A6080]" />
      <div>
        <p className="text-[10px] text-[#5A6080] uppercase tracking-wider">{label}</p>
        <p className="font-semibold text-sm text-[#C8CCD8] tabular-nums">{value}</p>
      </div>
    </div>
  )
}

function MetricBadge({ label, value, sub, color }: { label: string; value: string; sub?: string; color?: string }) {
  return (
    <div className="text-center p-2.5 bg-[rgba(255,255,255,0.04)] rounded-lg border border-[rgba(255,255,255,0.06)]">
      <span className="text-[10px] text-[#5A6080] uppercase tracking-wider">{label}</span>
      <p className={`font-bold text-sm tabular-nums mt-1 ${color || 'text-[#C8CCD8]'}`}>{value}</p>
      {sub && <p className="text-[10px] text-[#4A5070] mt-0.5">{sub}</p>}
    </div>
  )
}
