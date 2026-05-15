import { useState } from 'react'
import { X } from 'lucide-react'
import type { PlanCreate } from '@/types'

export default function PlanSettingsModal({ onClose, onCreate }: { onClose: () => void; onCreate: (data: PlanCreate) => void }) {
  const [form, setForm] = useState<PlanCreate>({
    name: '我的 80/20 训练计划', weeks: 12, weekly_mileage_cap: 0.10, high_intensity_max: 2,
    low_intensity_max: 4, target_race: '半马', base_weekly_km: 30,
  })

  const handleSubmit = (e: React.FormEvent) => { e.preventDefault(); onCreate(form); onClose() }

  const inputClass = "w-full px-3 py-2.5 bg-[rgba(255,255,255,0.03)] border border-[rgba(255,255,255,0.08)] rounded-lg text-sm text-[#E8ECF2] placeholder-[#5A6080] focus:outline-none focus:ring-2 focus:ring-red-600/40 focus:border-red-700/30 transition-all"
  const selectClass = "w-full px-3 py-2.5 bg-[rgba(255,255,255,0.03)] border border-[rgba(255,255,255,0.08)] rounded-lg text-sm text-[#E8ECF2] focus:outline-none focus:ring-2 focus:ring-red-600/40"
  const labelClass = "block text-sm font-medium text-[#8A94A6] mb-1.5"

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50">
      <div className="glass-card rounded-2xl p-6 w-full max-w-md max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-5">
          <h3 className="text-lg font-bold text-[#E8ECF2]">创建训练计划</h3>
          <button onClick={onClose} className="text-[#5A6080] hover:text-[#C8CCD8] transition-colors"><X className="w-5 h-5" /></button>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className={labelClass}>计划名称</label>
            <input type="text" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className={inputClass} required />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className={labelClass}>训练周数</label>
              <input type="number" min={4} max={24} value={form.weeks} onChange={(e) => setForm({ ...form, weeks: Number(e.target.value) })} className={inputClass} />
            </div>
            <div>
              <label className={labelClass}>基础周跑量 (km)</label>
              <input type="number" step="0.5" value={form.base_weekly_km} onChange={(e) => setForm({ ...form, base_weekly_km: Number(e.target.value) })} className={inputClass} />
            </div>
          </div>
          <div>
            <label className={labelClass}>周增幅上限: {Math.round(form.weekly_mileage_cap * 100)}%</label>
            <input type="range" min={0} max={0.20} step={0.01} value={form.weekly_mileage_cap}
              onChange={(e) => setForm({ ...form, weekly_mileage_cap: Number(e.target.value) })}
              className="w-full accent-red-600" />
            <div className="flex justify-between text-xs text-[#3A4060]"><span>0%</span><span>20%</span></div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className={labelClass}>每周高强度上限</label>
              <select value={form.high_intensity_max} onChange={(e) => setForm({ ...form, high_intensity_max: Number(e.target.value) })} className={selectClass}>
                <option value={1}>1 次</option><option value={2}>2 次</option><option value={3}>3 次</option>
              </select>
            </div>
            <div>
              <label className={labelClass}>每周低强度上限</label>
              <select value={form.low_intensity_max} onChange={(e) => setForm({ ...form, low_intensity_max: Number(e.target.value) })} className={selectClass}>
                <option value={2}>2 次</option><option value={3}>3 次</option><option value={4}>4 次</option>
                <option value={5}>5 次</option><option value={6}>6 次</option>
              </select>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className={labelClass}>目标赛事</label>
              <select value={form.target_race} onChange={(e) => setForm({ ...form, target_race: e.target.value })} className={selectClass}>
                <option value="5K">5K</option><option value="10K">10K</option>
                <option value="半马">半马</option><option value="全马">全马</option>
              </select>
            </div>
            <div>
              <label className={labelClass}>目标日期</label>
              <input type="date" onChange={(e) => setForm({ ...form, target_date: e.target.value })} className={inputClass} />
            </div>
          </div>
          <button type="submit" className="w-full py-2.5 bg-red-700 text-white rounded-lg font-medium hover:bg-red-600 transition-colors">
            生成训练计划
          </button>
        </form>
      </div>
    </div>
  )
}
