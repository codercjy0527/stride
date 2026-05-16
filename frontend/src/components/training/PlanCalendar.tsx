import { useState, useEffect } from 'react'
import { Check, Circle, Timer, EyeOff } from 'lucide-react'
import { training } from '@/services/api'
import type { TrainingSession } from '@/types'
import CheckpointModal from './CheckpointModal'

const DAY_NAMES = ['一', '二', '三', '四', '五', '六', '日']
const SESSION_LABELS: Record<string, string> = {
  easy: '轻松跑', tempo: '节奏跑', interval: '间歇跑', long_run: '长距离', rest: '休息',
  checkpoint: '测量', fartlek: '法特莱克', hills: '坡道训练',
}
const SESSION_COLORS: Record<string, string> = {
  easy: 'bg-emerald-950/40 text-emerald-400 border-emerald-800/20',
  tempo: 'bg-amber-950/40 text-amber-400 border-amber-800/20',
  interval: 'bg-red-950/50 text-red-400 border-red-800/30',
  long_run: 'bg-indigo-950/40 text-indigo-400 border-indigo-800/20',
  rest: 'bg-[rgba(255,255,255,0.02)] text-[#5A6080] border-transparent',
  checkpoint: 'bg-purple-950/50 text-purple-400 border-purple-700/40',
  fartlek: 'bg-cyan-950/40 text-cyan-400 border-cyan-800/20',
  hills: 'bg-lime-950/30 text-lime-400 border-lime-800/20',
}

export default function PlanCalendar({ planId, onUpdate: _onUpdate }: { planId: number; onUpdate: () => void }) {
  const [sessions, setSessions] = useState<TrainingSession[]>([])
  const [checkpointSession, setCheckpointSession] = useState<TrainingSession | null>(null)

  useEffect(() => {
    training.listSessions(planId).then(r => setSessions(r.data))
  }, [planId])

  const handleToggle = async (id: number) => {
    await training.toggleComplete(id)
    setSessions(prev => prev.map(s => s.id === id ? { ...s, completed: !s.completed } : s))
  }

  const handleCheckpointSaved = () => {
    training.listSessions(planId).then(r => setSessions(r.data))
    setCheckpointSession(null)
  }

  const weeks = new Map<number, TrainingSession[]>()
  sessions.forEach(s => {
    if (!weeks.has(s.week)) weeks.set(s.week, [])
    weeks.get(s.week)!.push(s)
  })

  return (
    <div className="space-y-3">
      {Array.from(weeks.entries()).sort(([a], [b]) => a - b).map(([weekNum, weekSessions]) => {
        const weekKm = weekSessions.reduce((sum, s) => sum + s.distance_km, 0)
        const completed = weekSessions.filter(s => s.completed).length
        const hasCheckpoint = weekSessions.some(s => s.is_checkpoint)
        return (
          <div key={weekNum} className="glass-card rounded-xl p-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-semibold text-[#C8CCD8] text-sm flex items-center gap-2">
                第 {weekNum} 周
                {hasCheckpoint && (
                  <span className="text-xs px-1.5 py-0.5 rounded bg-purple-950/50 text-purple-400 border border-purple-700/40">
                    <Timer className="w-3 h-3 inline mr-0.5" />
                    测量周
                  </span>
                )}
                {!hasCheckpoint && weekNum % 4 === 0 && (
                  <span className="text-xs text-[#5A6080]">减量周</span>
                )}
              </h3>
              <span className="text-xs text-[#5A6080]">
                周跑量 {weekKm}km · 完成 {completed}/{weekSessions.filter(s => s.session_type !== 'rest').length}
              </span>
            </div>
            <div className="grid grid-cols-7 gap-1.5">
              {Array.from({ length: 7 }).map((_, dayIdx) => {
                const session = weekSessions.find(s => s.day_of_week === dayIdx)
                if (!session) return <div key={dayIdx} className="h-20" />
                const isCheckpoint = session.is_checkpoint
                const isBlind = session.is_blind_run
                return (
                  <button key={dayIdx}
                    onClick={() => {
                      if (isCheckpoint) {
                        setCheckpointSession(session)
                      } else if (session.session_type !== 'rest') {
                        handleToggle(session.id)
                      }
                    }}
                    className={`h-20 rounded-lg text-xs p-1.5 flex flex-col items-center justify-center text-center transition-all border relative ${
                      session.completed
                        ? 'bg-emerald-950/30 border-emerald-700/40'
                        : `${SESSION_COLORS[session.session_type]} hover:brightness-125`
                    }`}>
                    <span className="font-medium text-[10px] opacity-70">{DAY_NAMES[dayIdx]}</span>
                    {session.session_type === 'rest' ? (
                      <span className="text-[#5A6080] mt-1"><Circle className="w-4 h-4" /></span>
                    ) : (
                      <>
                        <span className="font-semibold mt-0.5">{SESSION_LABELS[session.session_type] || session.session_type}</span>
                        <span className="opacity-60">{session.distance_km}km</span>
                        {session.completed && <Check className="w-4 h-4 text-emerald-400 mt-0.5" />}
                        {isBlind && !session.completed && (
                          <span className="absolute top-0.5 right-0.5" title="盲跑训练">
                            <EyeOff className="w-3 h-3 text-cyan-400/60" />
                          </span>
                        )}
                      </>
                    )}
                  </button>
                )
              })}
            </div>
          </div>
        )
      })}

      {checkpointSession && (
        <CheckpointModal session={checkpointSession} onClose={() => setCheckpointSession(null)} onSaved={handleCheckpointSaved} />
      )}
    </div>
  )
}
