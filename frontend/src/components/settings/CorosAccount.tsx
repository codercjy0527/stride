import { useState, useEffect } from 'react'
import { Check, X, Loader2, LogIn } from 'lucide-react'
import { coros } from '@/services/api'

export default function CorosAccount() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loggingIn, setLoggingIn] = useState(false)
  const [msg, setMsg] = useState<{ text: string; ok: boolean } | null>(null)

  useEffect(() => {
    coros.getCredentials().then(r => {
      if (r.data.configured) { setEmail(r.data.email); setPassword('••••••') }
    }).catch(() => {})
  }, [])

  const showMsg = (text: string, ok: boolean) => {
    setMsg({ text, ok })
    setTimeout(() => setMsg(null), 4000)
  }

  const handleAutoLogin = async () => {
    if (!email || !password) return
    const pwd = password === '••••••' ? prompt('请输入 COROS 密码') : password
    if (!pwd) return
    setLoggingIn(true)
    setMsg({ text: '正在验证 COROS 账号...', ok: true })
    try {
      const r = await coros.autoLogin(email, pwd, 'cn')
      const d = r.data
      if (d.native_ok) {
        showMsg(d.native_msg, true)
      } else if (d.cookie_ok) {
        showMsg('Cookie ' + d.cookie_msg, true)
      } else {
        const detail = [d.native_msg, d.cookie_msg].filter(Boolean).join(' | ')
        showMsg(detail || d.message || '登录失败', false)
      }
    } catch (e: any) {
      showMsg('登录失败: ' + (e.response?.data?.message || e.message || '网络超时，请重试'), false)
    }
    setLoggingIn(false)
  }

  const ic = "w-full px-3 py-2.5 bg-[rgba(255,255,255,0.03)] border border-[rgba(255,255,255,0.08)] rounded-lg text-sm text-[#E8ECF2] placeholder-[#5A6080] focus:outline-none focus:ring-2 focus:ring-red-600/40"
  const btn = "flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-40"
  const btnPrimary = `${btn} bg-red-700 text-white hover:bg-red-600`

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <div className="flex items-center gap-1.5">
          <LogIn className="w-4 h-4 text-emerald-400" />
          <span className="text-sm font-medium text-[#C8CCD8]">登录 COROS 账号</span>
        </div>
        <p className="text-xs text-[#5A6080]">输入 COROS 邮箱和密码，点击登录后即可自动同步运动与健康数据。</p>
        <div className="grid grid-cols-3 gap-2">
          <input type="email" value={email} onChange={e => setEmail(e.target.value)}
            placeholder="COROS 邮箱" className={ic} />
          <input type="password" value={password}
            onChange={e => setPassword(e.target.value)}
            onFocus={e => { if (password === '••••••') { setPassword(''); e.target.select() } }}
            placeholder="COROS 密码" className={ic} />
          <button onClick={handleAutoLogin} disabled={loggingIn || !email || !password}
            className={btnPrimary}>
            {loggingIn ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <LogIn className="w-3.5 h-3.5" />}
            登录 COROS
          </button>
        </div>
      </div>

      {msg && (
        <div className={`flex items-center gap-2 p-2.5 rounded-lg text-sm ${
          msg.ok ? 'bg-[rgba(16,185,129,0.06)] border border-[rgba(16,185,129,0.1)] text-emerald-300'
            : 'bg-[rgba(239,68,68,0.06)] border border-[rgba(239,68,68,0.1)] text-red-300'
        }`}>
          {msg.ok ? <Check className="w-4 h-4" /> : <X className="w-4 h-4" />}
          {msg.text}
        </div>
      )}
    </div>
  )
}
