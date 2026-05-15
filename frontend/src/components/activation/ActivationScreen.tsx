import { useState } from 'react'
import { Key, Loader2, Footprints } from 'lucide-react'
import { activation } from '@/services/api'

interface Props {
  onActivated: () => void
}

export default function ActivationScreen({ onActivated }: Props) {
  const [code, setCode] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [showDeactivate, setShowDeactivate] = useState(false)
  const [deactMsg, setDeactMsg] = useState('')

  const handleActivate = async () => {
    if (!code.trim()) return
    setLoading(true)
    setError('')
    try {
      const res = await activation.activate(code.trim())
      if (res.data.ok) {
        onActivated()
      } else {
        setError(res.data.message || '激活失败')
      }
    } catch {
      setError('无法连接激活服务器，请检查网络')
    } finally {
      setLoading(false)
    }
  }

  const handleDeactivate = async () => {
    try {
      const res = await activation.deactivate()
      setDeactMsg(res.data.message || '已解除')
      setShowDeactivate(false)
    } catch {
      setDeactMsg('操作失败')
    }
  }

  return (
    <div className="fixed inset-0 bg-[#0A0C12] flex items-center justify-center z-50">
      <div className="w-full max-w-md mx-4">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-[rgba(168,24,24,0.1)] mb-4">
            <Footprints className="w-8 h-8 text-red-400" />
          </div>
          <h1 className="text-2xl font-bold text-[#E8ECF2]">80/20 极化训练</h1>
          <p className="text-sm text-[#5A6080] mt-2">输入激活码以解锁全部功能</p>
        </div>

        <div className="glass-card rounded-2xl p-6 space-y-4">
          {/* Activation input */}
          <div>
            <label className="block text-xs text-[#5A6080] mb-1.5 ml-1">激活码</label>
            <input
              type="text"
              value={code}
              onChange={(e) => { setCode(e.target.value.toUpperCase()); setError('') }}
              onKeyDown={(e) => e.key === 'Enter' && handleActivate()}
              placeholder="XXXX-XXXX-XXXX-XXXX"
              className="w-full px-4 py-3 bg-[rgba(255,255,255,0.03)] border border-[rgba(255,255,255,0.08)] rounded-lg text-sm text-[#E8ECF2] placeholder-[#3A4060] focus:outline-none focus:ring-2 focus:ring-red-600/40 focus:border-red-700/30 transition-all text-center tracking-widest font-mono"
              disabled={loading}
            />
          </div>

          {error && (
            <p className="text-sm text-red-400 text-center">{error}</p>
          )}

          <button
            onClick={handleActivate}
            disabled={loading || !code.trim()}
            className="w-full py-3 bg-red-700 text-white rounded-lg font-medium hover:bg-red-600 transition-colors disabled:opacity-40 flex items-center justify-center gap-2"
          >
            {loading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Key className="w-4 h-4" />
            )}
            {loading ? '验证中...' : '激活'}
          </button>

          {/* Deactivate */}
          <div className="border-t border-[rgba(255,255,255,0.04)] pt-3">
            {!showDeactivate ? (
              <button
                onClick={() => setShowDeactivate(true)}
                className="w-full text-xs text-[#3A4060] hover:text-[#5A6080] transition-colors py-1"
              >
                解除绑定
              </button>
            ) : (
              <div className="flex items-center gap-2">
                <button
                  onClick={handleDeactivate}
                  className="flex-1 py-2 text-xs font-medium text-red-400 border border-red-700/30 rounded-lg hover:bg-red-700/10 transition-colors"
                >
                  确认解除
                </button>
                <button
                  onClick={() => setShowDeactivate(false)}
                  className="flex-1 py-2 text-xs text-[#5A6080] border border-[rgba(255,255,255,0.06)] rounded-lg hover:bg-[rgba(255,255,255,0.03)] transition-colors"
                >
                  取消
                </button>
              </div>
            )}
            {deactMsg && <p className="text-xs text-[#5A6080] text-center mt-2">{deactMsg}</p>}
          </div>
        </div>

        <p className="text-[10px] text-[#3A4060] text-center mt-4">
          需要激活码？联系客服获取
        </p>
      </div>
    </div>
  )
}
