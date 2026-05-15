import { useState, useEffect } from 'react'
import { Plus, Trash2 } from 'lucide-react'
import { training } from '@/services/api'
import type { TrainingPlan as TPlan, PlanCreate } from '@/types'
import PlanSettingsModal from '@/components/training/PlanSettingsModal'
import PlanCalendar from '@/components/training/PlanCalendar'

export default function TrainingPlan() {
  const [plans, setPlans] = useState<TPlan[]>([])
  const [selectedPlan, setSelectedPlan] = useState<TPlan | null>(null)
  const [showCreate, setShowCreate] = useState(false)

  const loadPlans = () => {
    training.listPlans().then((r) => {
      setPlans(r.data)
      if (r.data.length > 0 && !selectedPlan) setSelectedPlan(r.data[0])
    })
  }

  useEffect(() => { loadPlans() }, [])

  const handleCreate = async (data: PlanCreate) => {
    const res = await training.createPlan(data)
    loadPlans()
    setSelectedPlan(res.data)
  }

  const handleDelete = async (id: number) => {
    await training.deletePlan(id)
    setSelectedPlan(null)
    loadPlans()
  }

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-[#E8ECF2] tracking-tight">训练计划</h1>
          <p className="text-xs text-[#5A6080] mt-0.5">Training Plan</p>
        </div>
        <button onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 px-4 py-2 bg-red-700 text-white rounded-lg font-medium hover:bg-red-600 transition-colors text-sm shadow-[0_2px_8px_rgba(185,28,28,0.2)]">
          <Plus className="w-4 h-4" /> 创建计划
        </button>
      </div>

      {plans.length > 0 && (
        <div className="flex gap-2 flex-wrap">
          {plans.map((p) => (
            <button key={p.id} onClick={() => setSelectedPlan(p)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-all border ${
                selectedPlan?.id === p.id
                  ? 'bg-[rgba(185,28,28,0.1)] border-[rgba(185,28,28,0.2)] text-red-400'
                  : 'bg-[rgba(255,255,255,0.02)] border-[rgba(255,255,255,0.05)] text-[#8A94A6] hover:bg-[rgba(255,255,255,0.04)]'
              }`}>
              {p.name}
              <span className="ml-2 text-xs opacity-60">{p.completed_sessions}/{p.total_sessions}</span>
            </button>
          ))}
        </div>
      )}

      {selectedPlan ? (
        <div className="space-y-4">
          <div className="glass-card rounded-xl p-5">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="font-semibold text-lg text-[#C8CCD8]">{selectedPlan.name}</h2>
                <p className="text-sm text-[#5A6080]">
                  {selectedPlan.weeks}周 · 目标{selectedPlan.target_race} · 周增幅≤{Math.round(selectedPlan.weekly_mileage_cap * 100)}%
                  · 高强度≤{selectedPlan.high_intensity_max}次/周
                </p>
              </div>
              <button onClick={() => handleDelete(selectedPlan.id)}
                className="p-2 text-[#5A6080] hover:text-red-400 transition-colors">
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          </div>
          <PlanCalendar planId={selectedPlan.id} onUpdate={loadPlans} />
        </div>
      ) : (
        <div className="glass-card rounded-xl p-12 text-center">
          <p className="text-[#5A6080]">还没有训练计划，点击上方按钮创建</p>
        </div>
      )}

      {showCreate && <PlanSettingsModal onClose={() => setShowCreate(false)} onCreate={handleCreate} />}
    </div>
  )
}
