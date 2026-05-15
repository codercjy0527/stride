import { useState, useEffect, useMemo } from 'react'
import { Footprints, Heart, Timer, Search, TrendingUp, Activity, ChevronDown, ChevronUp, BarChart3 } from 'lucide-react'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { activities as activitiesApi } from '@/services/api'
import type { ActivityRecord } from '@/types'
import ReviewModal from '@/components/review/ReviewModal'

type SortKey = 'date' | 'distance_km' | 'avg_pace' | 'avg_hr' | 'duration_min' | 'sport_type'
type SortDir = 'asc' | 'desc'

export default function ExerciseData() {
  const [allActivities, setAllActivities] = useState<ActivityRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [reviewActivity, setReviewActivity] = useState<ActivityRecord | null>(null)
  const [sortKey, setSortKey] = useState<SortKey>('date')
  const [sortDir, setSortDir] = useState<SortDir>('desc')
  const [search, setSearch] = useState('')
  const [filterDays, setFilterDays] = useState(90)

  useEffect(() => {
    activitiesApi.list(filterDays)
      .then((r) => setAllActivities(r.data.activities || []))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [filterDays])

  const filtered = useMemo(() => {
    let list = [...allActivities]
    if (search) {
      const q = search.toLowerCase()
      list = list.filter((a) =>
        (a.location && a.location.toLowerCase().includes(q)) ||
        (a.date && a.date.includes(q)) ||
        (a.avg_pace && a.avg_pace.includes(q))
      )
    }
    list.sort((a, b) => {
      let va: any, vb: any
      if (sortKey === 'avg_pace') {
        va = a.avg_pace ? a.avg_pace.split(':').map(Number).reduce((m, s) => m * 60 + s) : Infinity
        vb = b.avg_pace ? b.avg_pace.split(':').map(Number).reduce((m, s) => m * 60 + s) : Infinity
        return sortDir === 'asc' ? va - vb : vb - va
      }
      va = a[sortKey] ?? 0
      vb = b[sortKey] ?? 0
      return sortDir === 'asc' ? (va > vb ? 1 : -1) : (vb > va ? 1 : -1)
    })
    return list
  }, [allActivities, search, sortKey, sortDir])

  const stats = useMemo(() => {
    const valid = filtered.filter((a) => a.distance_km)
    const totalKm = valid.reduce((s, a) => s + (a.distance_km || 0), 0)
    const totalRuns = valid.length
    const avgHrAll = valid.filter((a) => a.avg_hr).map((a) => a.avg_hr!) as number[]
    const avgHr = avgHrAll.length > 0 ? Math.round(avgHrAll.reduce((s, v) => s + v, 0) / avgHrAll.length) : null
    const allPaces = valid
      .filter((a) => a.avg_pace)
      .map((a) => a.avg_pace!.split(':').map(Number).reduce((m, s) => m * 60 + s))
    const avgPaceSec = allPaces.length > 0 ? Math.round(allPaces.reduce((s, v) => s + v, 0) / allPaces.length) : null
    const avgPace = avgPaceSec ? `${Math.floor(avgPaceSec / 60)}:${String(avgPaceSec % 60).padStart(2, '0')}` : null

    // Weekly breakdown
    const weekMap: Record<string, { km: number; runs: number }> = {}
    valid.forEach((a) => {
      const d = new Date(a.date)
      const monday = new Date(d)
      monday.setDate(d.getDate() - d.getDay() + 1)
      const wk = monday.toISOString().slice(0, 10)
      if (!weekMap[wk]) weekMap[wk] = { km: 0, runs: 0 }
      weekMap[wk].km += a.distance_km || 0
      weekMap[wk].runs += 1
    })
    const weeks = Object.entries(weekMap).sort((a, b) => b[0].localeCompare(a[0]))

    return { totalKm: Math.round(totalKm * 10) / 10, totalRuns, avgHr, avgPace, weeks }
  }, [filtered])

  const handleSort = (key: SortKey) => {
    if (sortKey === key) setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    else { setSortKey(key); setSortDir('desc') }
  }

  const sportLabel = (t: number) => {
    const map: Record<number, string> = { 100: '跑步', 101: '越野跑', 102: '操场跑', 103: '室内跑' }
    return map[t] || '运动'
  }

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-[#E8ECF2] tracking-tight flex items-center gap-2">
            <Activity className="w-5 h-5 text-red-400" />
            运动数据
          </h1>
          <p className="text-xs text-[#5A6080] mt-0.5 ml-7">Exercise Data</p>
        </div>
      </div>

      {/* Stats Overview */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard icon={Footprints} label="总跑量" value={`${stats.totalKm} km`} accent="text-red-400" />
        <StatCard icon={TrendingUp} label="跑步次数" value={`${stats.totalRuns} 次`} accent="text-emerald-400" />
        <StatCard icon={Timer} label="平均配速" value={stats.avgPace ? `${stats.avgPace}/km` : '--'} accent="text-blue-400" />
        <StatCard icon={Heart} label="平均心率" value={stats.avgHr ? `${stats.avgHr} bpm` : '--'} accent="text-purple-400" />
      </div>

      {/* Weekly breakdown */}
      {stats.weeks.length > 0 && (
        <div className="glass-card rounded-xl p-5">
          <h2 className="text-xs font-semibold text-[#B8BEC8] mb-4 flex items-center gap-2 uppercase tracking-wider">
            <BarChart3 className="w-3.5 h-3.5 text-red-400" />
            每周跑量趋势
          </h2>
          <div style={{ width: '100%', height: 200 }}>
            <ResponsiveContainer>
              <LineChart
                data={stats.weeks.slice(0, 12).reverse().map(([wk, d]) => ({
                  week: wk.slice(5),
                  km: Math.round(d.km * 10) / 10,
                  runs: d.runs,
                }))}
                margin={{ top: 5, right: 10, left: 0, bottom: 5 }}
              >
                <XAxis
                  dataKey="week"
                  tick={{ fontSize: 11, fill: '#5A6080' }}
                  axisLine={{ stroke: 'rgba(255,255,255,0.06)' }}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fontSize: 11, fill: '#5A6080' }}
                  axisLine={false}
                  tickLine={false}
                  width={35}
                />
                <Tooltip
                  contentStyle={{
                    background: '#0E1018',
                    border: '1px solid rgba(255,255,255,0.08)',
                    borderRadius: 8,
                    fontSize: 12,
                    color: '#C8CCD8',
                  }}
                />
                <Line
                  type="monotone"
                  dataKey="km"
                  stroke="#DC2626"
                  strokeWidth={2}
                  dot={{ fill: '#DC2626', strokeWidth: 0, r: 3 }}
                  activeDot={{ fill: '#EF4444', strokeWidth: 0, r: 5 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Toolbar */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[200px] max-w-sm">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-[#5A6080]" />
          <input
            type="text"
            placeholder="搜索日期 / 地点 / 配速..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-3 py-2 bg-[rgba(255,255,255,0.03)] border border-[rgba(255,255,255,0.06)] rounded-lg text-sm text-[#E8ECF2] placeholder-[#5A6080] focus:outline-none focus:ring-2 focus:ring-red-600/30 focus:border-red-700/30 transition-all"
          />
        </div>
        <select
          value={filterDays}
          onChange={(e) => setFilterDays(Number(e.target.value))}
          className="px-3 py-2 bg-[rgba(255,255,255,0.03)] border border-[rgba(255,255,255,0.06)] rounded-lg text-sm text-[#C8CCD8] focus:outline-none focus:ring-2 focus:ring-red-600/30"
        >
          <option value={30}>最近 30 天</option>
          <option value={60}>最近 60 天</option>
          <option value={90}>最近 90 天</option>
          <option value={180}>最近 180 天</option>
          <option value={365}>最近 1 年</option>
        </select>
      </div>

      {/* Activity List */}
      <div className="glass-card rounded-xl overflow-hidden">
        {loading ? (
          <div className="text-center py-12 text-[#5A6080]">加载中...</div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-12">
            <Footprints className="w-10 h-10 mx-auto mb-3 opacity-20 text-[#5A6080]" />
            <p className="text-[#5A6080] text-sm">暂无运动记录</p>
            <p className="text-[#3A4060] text-xs mt-1">
              {allActivities.length === 0 ? '前往「设置」同步 COROS 数据' : '尝试调整筛选条件'}
            </p>
          </div>
        ) : (
          <>
            {/* Table header */}
            <div className="grid grid-cols-6 gap-2 px-5 py-2.5 bg-[rgba(255,255,255,0.02)] border-b border-[rgba(255,255,255,0.04)] text-xs text-[#5A6080] font-medium">
              <SortHeader label="日期" field="date" {...{ sortKey, sortDir, handleSort }} />
              <SortHeader label="类型" field="sport_type" {...{ sortKey, sortDir, handleSort }} />
              <SortHeader label="距离" field="distance_km" {...{ sortKey, sortDir, handleSort }} />
              <SortHeader label="配速" field="avg_pace" {...{ sortKey, sortDir, handleSort }} />
              <SortHeader label="心率" field="avg_hr" {...{ sortKey, sortDir, handleSort }} />
              <span className="text-right">复盘</span>
            </div>

            <div className="divide-y divide-[rgba(255,255,255,0.02)]">
              {filtered.map((a) => (
                <div
                  key={a.id}
                  className="grid grid-cols-6 gap-2 px-5 py-3 items-center hover:bg-[rgba(255,255,255,0.025)] transition-colors cursor-pointer"
                  onClick={() => setReviewActivity(a)}
                >
                  <span className="text-sm text-[#C8CCD8] font-mono">{a.date}</span>
                  <span className="text-xs text-[#8A94A6]">{sportLabel(a.sport_type)}</span>
                  <span className="text-sm font-semibold text-[#E8ECF2] font-mono">
                    {a.distance_km ? `${a.distance_km} km` : '--'}
                  </span>
                  <span className="text-sm text-[#8A94A6] font-mono">{a.avg_pace || '--'}</span>
                  <span className="text-sm text-[#8A94A6] font-mono">
                    {a.avg_hr ? (
                      <span className={`${a.avg_hr > 160 ? 'text-orange-400' : a.avg_hr > 140 ? 'text-yellow-400' : 'text-emerald-400'}`}>
                        {a.avg_hr} bpm
                      </span>
                    ) : '--'}
                  </span>
                  <div className="text-right">
                    <button
                      onClick={(e) => { e.stopPropagation(); setReviewActivity(a) }}
                      className="px-3 py-1.5 text-xs font-medium bg-red-700/20 text-red-400 border border-red-700/30 rounded-lg hover:bg-red-700/40 transition-colors"
                    >
                      复盘
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </div>

      {/* Pagination summary */}
      {filtered.length > 0 && (
        <p className="text-xs text-[#3A4060] text-center">
          显示 {filtered.length} / {allActivities.length} 条记录
        </p>
      )}

      {/* Review Modal */}
      {reviewActivity && <ReviewModal activity={reviewActivity} onClose={() => setReviewActivity(null)} />}
    </div>
  )
}

function StatCard({ icon: Icon, label, value, accent }: { icon: any; label: string; value: string; accent: string }) {
  return (
    <div className="glass-card-solid rounded-xl p-4 flex items-center gap-3">
      <div className={`p-2 rounded-lg bg-[rgba(255,255,255,0.04)] border border-[rgba(255,255,255,0.05)] ${accent}`}>
        <Icon className="w-5 h-5" />
      </div>
      <div>
        <p className="text-[10px] text-[#5A6080] uppercase tracking-wider">{label}</p>
        <p className="font-bold text-lg text-[#E8ECF2] tabular-nums">{value}</p>
      </div>
    </div>
  )
}

function SortHeader({ label, field, sortKey, sortDir, handleSort }: {
  label: string
  field: SortKey
  sortKey: SortKey
  sortDir: SortDir
  handleSort: (k: SortKey) => void
}) {
  const active = sortKey === field
  return (
    <button onClick={() => handleSort(field)} className="flex items-center gap-1 hover:text-[#C8CCD8] transition-colors text-left">
      {label}
      {active && (sortDir === 'asc' ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />)}
    </button>
  )
}
