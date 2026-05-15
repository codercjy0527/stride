import { useState } from 'react'
import { Calculator, Clock, Gauge } from 'lucide-react'
import { race } from '@/services/api'

const DISTANCES = [
  { value: '5K', label: '5公里' }, { value: '10K', label: '10公里' },
  { value: 'half_marathon', label: '半马 (21.1K)' }, { value: 'marathon', label: '全马 (42.2K)' },
]

export default function RacePlanner() {
  const [targetDist, setTargetDist] = useState('half_marathon')
  const [recent5k, setRecent5k] = useState('')
  const [recent10k, setRecent10k] = useState('')
  const [recentHalf, setRecentHalf] = useState('')
  const [result, setResult] = useState<any>(null)
  const [loading, setLoading] = useState(false)

  const handleCalculate = async () => {
    setLoading(true)
    try {
      const res = await race.calculate({ target_distance: targetDist, recent_5k_time: recent5k || undefined,
        recent_10k_time: recent10k || undefined, recent_half_time: recentHalf || undefined })
      setResult(res.data)
    } catch {
      const refTime = recent5k || recent10k || recentHalf || '25:00'
      const refDist = recent10k ? 10 : recentHalf ? 21.1 : 5
      const targetDistKm = { '5K': 5, '10K': 10, half_marathon: 21.1, marathon: 42.2 }[targetDist] || 21.1
      const totalSec = _parseTime(refTime)
      const predictedSec = totalSec * Math.pow(targetDistKm / refDist, 1.06)
      const pacePerKm = predictedSec / targetDistKm
      const splits = []
      const splitCount = targetDist === 'marathon' ? 42 : targetDist === 'half_marathon' ? 21 : targetDist === '10K' ? 10 : 5
      for (let i = 1; i <= splitCount; i++) splits.push({ km: i, time: _formatTime(i * pacePerKm) })
      setResult({ target_distance: targetDist, predicted_time: _formatTime(predictedSec), pace_per_km: _formatTime(pacePerKm), splits })
    } finally { setLoading(false) }
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="text-xl font-bold text-[#E8ECF2] tracking-tight">赛事配速规划</h1>
        <p className="text-xs text-[#5A6080] mt-0.5">Race Pace Planner</p>
      </div>

      <div className="glass-card rounded-xl p-6 space-y-4">
        <div>
          <label className="block text-xs font-medium text-[#8A94A6] uppercase tracking-wider mb-1.5">目标赛事</label>
          <select value={targetDist} onChange={(e) => setTargetDist(e.target.value)}
            className="w-full px-3 py-2.5 bg-[rgba(255,255,255,0.03)] border border-[rgba(255,255,255,0.06)] rounded-lg text-sm text-[#E8ECF2] focus:outline-none focus:ring-2 focus:ring-red-600/30">
            {DISTANCES.map((d) => (<option key={d.value} value={d.value}>{d.label}</option>))}
          </select>
        </div>
        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className="block text-xs font-medium text-[#8A94A6] uppercase tracking-wider mb-1.5">最近 5K 成绩</label>
            <input type="text" value={recent5k} onChange={(e) => setRecent5k(e.target.value)} placeholder="25:30"
              className="w-full px-3 py-2.5 bg-[rgba(255,255,255,0.03)] border border-[rgba(255,255,255,0.06)] rounded-lg text-sm text-[#E8ECF2] placeholder-[#5A6080] focus:outline-none focus:ring-2 focus:ring-red-600/30" />
          </div>
          <div>
            <label className="block text-xs font-medium text-[#8A94A6] uppercase tracking-wider mb-1.5">最近 10K 成绩</label>
            <input type="text" value={recent10k} onChange={(e) => setRecent10k(e.target.value)} placeholder="52:00"
              className="w-full px-3 py-2.5 bg-[rgba(255,255,255,0.03)] border border-[rgba(255,255,255,0.06)] rounded-lg text-sm text-[#E8ECF2] placeholder-[#5A6080] focus:outline-none focus:ring-2 focus:ring-red-600/30" />
          </div>
          <div>
            <label className="block text-xs font-medium text-[#8A94A6] uppercase tracking-wider mb-1.5">最近半马成绩</label>
            <input type="text" value={recentHalf} onChange={(e) => setRecentHalf(e.target.value)} placeholder="1:55:00"
              className="w-full px-3 py-2.5 bg-[rgba(255,255,255,0.03)] border border-[rgba(255,255,255,0.06)] rounded-lg text-sm text-[#E8ECF2] placeholder-[#5A6080] focus:outline-none focus:ring-2 focus:ring-red-600/30" />
          </div>
        </div>
        <button onClick={handleCalculate} disabled={loading}
          className="flex items-center gap-2 px-6 py-2.5 bg-red-700 text-white rounded-lg font-medium hover:bg-red-600 transition-colors disabled:opacity-40 text-sm">
          <Calculator className="w-4 h-4" /> {loading ? '计算中...' : '推算配速'}
        </button>
      </div>

      {result && (
        <div className="space-y-4">
          <div className="grid grid-cols-3 gap-4">
            <RCard icon={Clock} label="预测完赛时间" value={result.predicted_time} />
            <RCard icon={Gauge} label="配速 (/km)" value={result.pace_per_km} />
            <RCard icon={Calculator} label="目标赛事" value={DISTANCES.find(d => d.value === result.target_distance)?.label || result.target_distance} />
          </div>
          <div className="glass-card rounded-xl p-5">
            <h3 className="text-xs font-semibold text-[#B8BEC8] uppercase tracking-wider mb-3">分段时间表</h3>
            <div className="grid grid-cols-3 md:grid-cols-5 gap-2">
              {result.splits?.map((s: any) => (
                <div key={s.km} className="p-2 bg-[rgba(255,255,255,0.02)] rounded-lg text-center text-sm border border-[rgba(255,255,255,0.03)]">
                  <p className="text-[#5A6080]">{s.km}K</p>
                  <p className="font-mono font-semibold text-[#C8CCD8]">{s.time}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function RCard({ icon: Icon, label, value }: { icon: any; label: string; value: string }) {
  return (
    <div className="glass-card-solid rounded-xl p-4 text-center">
      <Icon className="w-5 h-5 text-red-400 mx-auto mb-2" />
      <p className="text-[10px] text-[#5A6080] uppercase tracking-wider">{label}</p>
      <p className="font-bold text-base font-mono text-[#E8ECF2] tabular-nums">{value}</p>
    </div>
  )
}

function _parseTime(s: string): number {
  const parts = s.split(':').map(Number)
  if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2]
  if (parts.length === 2) return parts[0] * 60 + parts[1]
  return parts[0]
}

function _formatTime(sec: number): string {
  const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = Math.floor(sec % 60)
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  return `${m}:${String(s).padStart(2, '0')}`
}
