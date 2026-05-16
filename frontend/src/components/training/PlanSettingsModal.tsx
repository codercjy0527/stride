import { useState, useEffect } from 'react'
import { X, ChevronLeft, ChevronRight, Check } from 'lucide-react'
import { training } from '@/services/api'
import type { TrainingPlan, Philosophy, QuestionnaireInput } from '@/types'

const FITNESS_LEVELS = [
  { key: 'beginner', label: '初级跑者', desc: '规律跑步 < 1年，月跑量 < 100km' },
  { key: 'intermediate', label: '中级跑者', desc: '规律跑步 1-3年，月跑量 100-200km' },
  { key: 'advanced', label: '高级跑者', desc: '规律跑步 > 3年，月跑量 > 200km' },
]

const RACES = ['5K', '10K', '半马', '全马']

export default function PlanSettingsModal({ onClose, onCreate }: { onClose: () => void; onCreate: (data: TrainingPlan) => void }) {
  const [step, setStep] = useState(0)
  const [philosophies, setPhilosophies] = useState<Philosophy[]>([])

  // Step 0: Fitness Assessment
  const [fitnessLevel, setFitnessLevel] = useState('intermediate')
  const [trainDays, setTrainDays] = useState(4)
  const [recentResult, setRecentResult] = useState('')
  const [injuryNotes, setInjuryNotes] = useState('')

  // Step 1: Philosophy
  const [philosophy, setPhilosophy] = useState('polarised_80_20')

  // Step 2: Plan Parameters
  const [planName, setPlanName] = useState('我的 80/20 训练计划')
  const [weeks, setWeeks] = useState(12)
  const [baseKm, setBaseKm] = useState(30)
  const [cap, setCap] = useState(0.10)
  const [targetRace, setTargetRace] = useState('半马')
  const [targetDate, setTargetDate] = useState('')

  useEffect(() => {
    training.listPhilosophies().then(r => setPhilosophies(r.data)).catch(() => {})
  }, [])

  const selectedPhil = philosophies.find(p => p.key === philosophy)

  const handleSubmit = async () => {
    const q: QuestionnaireInput = {
      fitness_level: fitnessLevel,
      training_days_per_week: trainDays,
      recent_race_result: recentResult || undefined,
      injury_notes: injuryNotes || undefined,
      name: planName,
      weeks,
      weekly_mileage_cap: cap,
      philosophy,
      target_race: targetRace,
      target_date: targetDate || undefined,
      base_weekly_km: baseKm,
    }
    const res = await training.createFromQuestionnaire(q)
    onCreate(res.data)
    onClose()
  }

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50">
      <div className="glass-card rounded-2xl p-6 w-full max-w-lg max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-3">
            <h3 className="text-lg font-bold text-[#E8ECF2]">创建训练计划</h3>
            <span className="text-xs text-[#5A6080]">步骤 {step + 1}/3</span>
          </div>
          <button onClick={onClose} className="text-[#5A6080] hover:text-[#C8CCD8] transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Progress bar */}
        <div className="flex gap-1.5 mb-6">
          {[0, 1, 2].map(i => (
            <div key={i} className={`h-1 flex-1 rounded-full transition-all ${i <= step ? 'bg-red-600' : 'bg-[rgba(255,255,255,0.08)]'}`} />
          ))}
        </div>

        {/* ── Step 0: Fitness Assessment ── */}
        {step === 0 && (
          <div className="space-y-4">
            <p className="text-sm text-[#8A94A6]">请先完成体能评估，这是设置训练护栏的第一步。</p>

            <div>
              <label className="block text-sm font-medium text-[#8A94A6] mb-2">跑步水平</label>
              <div className="space-y-2">
                {FITNESS_LEVELS.map(l => (
                  <button key={l.key} onClick={() => setFitnessLevel(l.key)}
                    className={`w-full text-left p-3 rounded-lg border transition-all ${
                      fitnessLevel === l.key
                        ? 'border-red-700/50 bg-red-950/20 text-[#E8ECF2]'
                        : 'border-[rgba(255,255,255,0.08)] bg-[rgba(255,255,255,0.02)] text-[#8A94A6] hover:bg-[rgba(255,255,255,0.04)]'
                    }`}>
                    <div className="font-medium text-sm">{l.label}</div>
                    <div className="text-xs opacity-70 mt-0.5">{l.desc}</div>
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-[#8A94A6] mb-2">
                每周训练天数: {trainDays} 天
              </label>
              <input type="range" min={3} max={7} value={trainDays}
                onChange={e => setTrainDays(Number(e.target.value))}
                className="w-full accent-red-600" />
              <div className="flex justify-between text-xs text-[#3A4060]">
                <span>3</span><span>4</span><span>5</span><span>6</span><span>7</span>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-[#8A94A6] mb-1.5">近期最好成绩（可选）</label>
              <input type="text" value={recentResult} onChange={e => setRecentResult(e.target.value)}
                placeholder='如 "5K 22:30" 或 "半马 1:45"' className="w-full px-3 py-2.5 bg-[rgba(255,255,255,0.03)] border border-[rgba(255,255,255,0.08)] rounded-lg text-sm text-[#E8ECF2] placeholder-[#5A6080] focus:outline-none focus:ring-2 focus:ring-red-600/40" />
            </div>

            <div>
              <label className="block text-sm font-medium text-[#8A94A6] mb-1.5">伤病备注（可选）</label>
              <textarea value={injuryNotes} onChange={e => setInjuryNotes(e.target.value)}
                placeholder="如：左膝不适、足底筋膜炎史、近期无伤病..."
                rows={2} className="w-full px-3 py-2.5 bg-[rgba(255,255,255,0.03)] border border-[rgba(255,255,255,0.08)] rounded-lg text-sm text-[#E8ECF2] placeholder-[#5A6080] focus:outline-none focus:ring-2 focus:ring-red-600/40 resize-none" />
            </div>
          </div>
        )}

        {/* ── Step 1: Philosophy ── */}
        {step === 1 && (
          <div className="space-y-4">
            <div className="bg-amber-950/30 border border-amber-800/30 rounded-lg p-3 text-xs text-amber-300/80">
              选定训练体系后，请在 12 周内保持执行，不要随意切换。混合多种体系容易导致训练效果差甚至受伤。
            </div>

            <div className="space-y-2">
              {philosophies.map(p => (
                <button key={p.key} onClick={() => setPhilosophy(p.key)}
                  className={`w-full text-left p-4 rounded-lg border transition-all ${
                    philosophy === p.key
                      ? 'border-red-700/50 bg-red-950/20 text-[#E8ECF2]'
                      : 'border-[rgba(255,255,255,0.08)] bg-[rgba(255,255,255,0.02)] text-[#8A94A6] hover:bg-[rgba(255,255,255,0.04)]'
                  }`}>
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-sm text-[#C8CCD8]">{p.name}</span>
                    {philosophy === p.key && <Check className="w-4 h-4 text-red-400" />}
                  </div>
                  <p className="text-xs mt-1 opacity-80">{p.description}</p>
                  <div className="flex gap-3 mt-2 text-xs text-[#5A6080]">
                    <span>强度比 {p.intensity_ratio}</span>
                    <span>周增幅 ≤{Math.round(p.weekly_mileage_cap * 100)}%</span>
                    <span>高强度 ≤{p.high_max}次/周</span>
                    <span>每{p.checkpoint_interval}周检查点</span>
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* ── Step 2: Parameters ── */}
        {step === 2 && (
          <div className="space-y-4">
            {/* Guardrail summary */}
            {selectedPhil && (
              <div className="bg-[rgba(255,255,255,0.03)] border border-[rgba(255,255,255,0.08)] rounded-lg p-3 space-y-1">
                <p className="text-xs font-medium text-[#C8CCD8]">护栏约束: {selectedPhil.name}</p>
                <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-[#5A6080]">
                  <span>强度比 {selectedPhil.intensity_ratio}</span>
                  <span>周增幅 ≤{Math.round(selectedPhil.weekly_mileage_cap * 100)}%</span>
                  <span>高强度 ≤{selectedPhil.high_max}次/周</span>
                </div>
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-[#8A94A6] mb-1.5">计划名称</label>
              <input type="text" value={planName} onChange={e => setPlanName(e.target.value)}
                className="w-full px-3 py-2.5 bg-[rgba(255,255,255,0.03)] border border-[rgba(255,255,255,0.08)] rounded-lg text-sm text-[#E8ECF2] focus:outline-none focus:ring-2 focus:ring-red-600/40" />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm font-medium text-[#8A94A6] mb-1.5">训练周数</label>
                <input type="number" min={4} max={24} value={weeks}
                  onChange={e => setWeeks(Number(e.target.value))}
                  className="w-full px-3 py-2.5 bg-[rgba(255,255,255,0.03)] border border-[rgba(255,255,255,0.08)] rounded-lg text-sm text-[#E8ECF2] focus:outline-none focus:ring-2 focus:ring-red-600/40" />
              </div>
              <div>
                <label className="block text-sm font-medium text-[#8A94A6] mb-1.5">基础周跑量 (km)</label>
                <input type="number" step="0.5" value={baseKm}
                  onChange={e => setBaseKm(Number(e.target.value))}
                  className="w-full px-3 py-2.5 bg-[rgba(255,255,255,0.03)] border border-[rgba(255,255,255,0.08)] rounded-lg text-sm text-[#E8ECF2] focus:outline-none focus:ring-2 focus:ring-red-600/40" />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-[#8A94A6] mb-1.5">
                周增幅上限: {Math.round(cap * 100)}%
              </label>
              <input type="range" min={0} max={0.20} step={0.01} value={cap}
                onChange={e => setCap(Number(e.target.value))} className="w-full accent-red-600" />
              <div className="flex justify-between text-xs text-[#3A4060]"><span>0%</span><span>20%</span></div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm font-medium text-[#8A94A6] mb-1.5">目标赛事</label>
                <div className="flex gap-1">
                  {RACES.map(r => (
                    <button key={r} onClick={() => setTargetRace(r)}
                      className={`flex-1 py-2 text-xs rounded-lg border transition-all ${
                        targetRace === r
                          ? 'border-red-700/50 bg-red-950/20 text-red-400'
                          : 'border-[rgba(255,255,255,0.08)] text-[#5A6080] hover:text-[#8A94A6]'
                      }`}>{r}</button>
                  ))}
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-[#8A94A6] mb-1.5">目标日期</label>
                <input type="date" value={targetDate}
                  onChange={e => setTargetDate(e.target.value)}
                  className="w-full px-3 py-2.5 bg-[rgba(255,255,255,0.03)] border border-[rgba(255,255,255,0.08)] rounded-lg text-sm text-[#E8ECF2] focus:outline-none focus:ring-2 focus:ring-red-600/40" />
              </div>
            </div>
          </div>
        )}

        {/* Navigation */}
        <div className="flex items-center gap-3 mt-6 pt-4 border-t border-[rgba(255,255,255,0.06)]">
          {step > 0 && (
            <button onClick={() => setStep(step - 1)}
              className="flex items-center gap-1 px-3 py-2 text-sm text-[#8A94A6] hover:text-[#C8CCD8] transition-colors">
              <ChevronLeft className="w-4 h-4" /> 上一步
            </button>
          )}
          <div className="flex-1" />
          {step < 2 ? (
            <button onClick={() => setStep(step + 1)}
              className="flex items-center gap-1 px-4 py-2 bg-[rgba(255,255,255,0.06)] text-[#C8CCD8] rounded-lg text-sm font-medium hover:bg-[rgba(255,255,255,0.1)] transition-colors">
              下一步 <ChevronRight className="w-4 h-4" />
            </button>
          ) : (
            <button onClick={handleSubmit}
              className="flex items-center gap-1 px-6 py-2 bg-red-700 text-white rounded-lg text-sm font-medium hover:bg-red-600 transition-colors shadow-[0_2px_8px_rgba(185,28,28,0.2)]">
              生成训练计划
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
