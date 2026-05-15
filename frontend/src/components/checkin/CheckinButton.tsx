import { useState } from 'react'
import { CalendarCheck, X } from 'lucide-react'
import { checkin } from '@/services/api'

export default function CheckinButton({ onSuccess }: { onSuccess: () => void }) {
  const [show, setShow] = useState(false)
  const [mood, setMood] = useState<number>(3)
  const [weight, setWeight] = useState('')
  const [notes, setNotes] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleCheckin = async () => {
    setLoading(true)
    setError('')
    try {
      await checkin.create({ mood, weight: weight ? parseFloat(weight) : undefined, notes: notes || undefined })
      setShow(false)
      onSuccess()
    } catch (err: any) {
      setError(err.response?.data?.detail || '打卡失败')
    } finally { setLoading(false) }
  }

  return (
    <>
      <button onClick={() => setShow(true)}
        className="flex items-center gap-2 px-4 py-2 bg-red-700 text-white rounded-lg font-medium hover:bg-red-600 transition-colors shadow-lg shadow-red-900/20">
        <CalendarCheck className="w-4 h-4" /> 今日打卡
      </button>

      {show && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="glass-card rounded-2xl p-6 w-full max-w-sm">
            <div className="flex items-center justify-between mb-5">
              <h3 className="text-lg font-bold text-[#E8ECF2]">今日打卡</h3>
              <button onClick={() => setShow(false)} className="text-[#5A6080] hover:text-[#C8CCD8] transition-colors">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-[#8A94A6] mb-2">体感评分</label>
                <div className="flex gap-1">
                  {[1, 2, 3, 4, 5].map((n) => (
                    <button key={n} onClick={() => setMood(n)}
                      className={`w-10 h-10 rounded-lg text-sm font-bold transition-all ${
                        mood === n
                          ? 'bg-[rgba(168,24,24,0.2)] text-red-400 border border-[rgba(168,24,24,0.25)]'
                          : 'bg-[rgba(255,255,255,0.03)] text-[#5A6080] hover:bg-[rgba(255,255,255,0.05)] border border-transparent'
                      }`}>{n}</button>
                  ))}
                </div>
                <div className="flex justify-between text-xs text-[#3A4060] mt-1.5">
                  <span>很差</span><span>很好</span>
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-[#8A94A6] mb-1.5">体重 (kg)</label>
                <input type="number" step="0.1" value={weight} onChange={(e) => setWeight(e.target.value)} placeholder="可选"
                  className="w-full px-3 py-2.5 bg-[rgba(255,255,255,0.03)] border border-[rgba(255,255,255,0.08)] rounded-lg text-sm text-[#E8ECF2] placeholder-[#5A6080] focus:outline-none focus:ring-2 focus:ring-red-600/40" />
              </div>
              <div>
                <label className="block text-sm font-medium text-[#8A94A6] mb-1.5">备注</label>
                <textarea value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="训练感受、身体状况..." rows={3}
                  className="w-full px-3 py-2.5 bg-[rgba(255,255,255,0.03)] border border-[rgba(255,255,255,0.08)] rounded-lg text-sm text-[#E8ECF2] placeholder-[#5A6080] focus:outline-none focus:ring-2 focus:ring-red-600/40 resize-none" />
              </div>
              {error && <p className="text-red-400 text-sm">{error}</p>}
              <button onClick={handleCheckin} disabled={loading}
                className="w-full py-2.5 bg-red-700 text-white rounded-lg font-medium hover:bg-red-600 transition-colors disabled:opacity-40">
                {loading ? '打卡中...' : '确认打卡'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
