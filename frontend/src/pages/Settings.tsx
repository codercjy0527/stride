import { useState, useEffect } from 'react'
import { Check, RefreshCw, Info, ChevronDown, ChevronUp, ShieldCheck, FileDown, X } from 'lucide-react'
import { coros } from '@/services/api'
import CsvImport from '@/components/settings/CsvImport'
import CorosAccount from '@/components/settings/CorosAccount'

const MODEL_GROUPS: Record<string, { id: string; label: string }[]> = {
  deepseek: [
    { id: 'deepseek-chat', label: 'V3 (通用推荐)' },
    { id: 'deepseek-reasoner', label: 'R1 (深度推理)' },
  ],
  openai: [
    { id: 'gpt-4o', label: 'GPT-4o' },
    { id: 'gpt-4.1', label: 'GPT-4.1' },
  ],
  claude: [
    { id: 'claude-sonnet-4-6', label: 'Sonnet 4.6 (推荐)' },
    { id: 'claude-opus-4-7', label: 'Opus 4.7 (最强)' },
    { id: 'claude-haiku-4-5', label: 'Haiku 4.5 (快速)' },
  ],
  gemini: [
    { id: 'gemini-2.0-flash', label: '2.0 Flash' },
    { id: 'gemini-2.5-pro', label: '2.5 Pro' },
  ],
}

export default function Settings() {
  const [aiProvider, setAiProvider] = useState(localStorage.getItem('ai_provider') || 'deepseek')
  const [aiApiKey, setAiApiKey] = useState(localStorage.getItem('ai_api_key') || '')
  const [aiModel, setAiModel] = useState(localStorage.getItem('ai_model') || MODEL_GROUPS['deepseek'][0].id)
  const [msg, setMsg] = useState('')
  const [syncing, setSyncing] = useState(false)
  const [showManual, setShowManual] = useState(false)
  const [form, setForm] = useState({
    date: new Date().toISOString().split('T')[0],
    sleep_hours: '', sleep_quality: '', resting_hr: '', hrv: '', fatigue_score: '', recovery_score: '',
  })

  useEffect(() => { coros.dashboard().catch(() => {}) }, [])

  const handleSaveKey = () => {
    localStorage.setItem('ai_provider', aiProvider)
    localStorage.setItem('ai_api_key', aiApiKey)
    localStorage.setItem('ai_model', aiModel)
    const providerLabel = { deepseek: 'DeepSeek', openai: 'ChatGPT', claude: 'Claude', gemini: 'Gemini' }[aiProvider] || aiProvider
    setMsg(`${providerLabel} API Key 已保存`)
    setTimeout(() => setMsg(''), 3000)
  }

  const handleSync = async () => {
    setSyncing(true)
    try {
      const res = await coros.sync()
      setMsg(res.data.message || '同步完成')
    } catch (err: any) { setMsg('同步失败: ' + (err.response?.data?.detail || err.message)) }
    setSyncing(false)
    setTimeout(() => setMsg(''), 5000)
  }

  const handleManualSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const data: any = { date: form.date }
    if (form.sleep_hours) data.sleep_hours = parseFloat(form.sleep_hours)
    if (form.sleep_quality) data.sleep_quality = parseInt(form.sleep_quality)
    if (form.resting_hr) data.resting_hr = parseInt(form.resting_hr)
    if (form.hrv) data.hrv = parseInt(form.hrv)
    if (form.fatigue_score) data.fatigue_score = parseFloat(form.fatigue_score)
    if (form.recovery_score) data.recovery_score = parseFloat(form.recovery_score)
    try { await coros.manual(data); setMsg('已保存') } catch (err: any) { setMsg('失败') }
    setTimeout(() => setMsg(''), 3000)
  }

  const ic = "w-full px-3 py-2.5 bg-[rgba(255,255,255,0.03)] border border-[rgba(255,255,255,0.08)] rounded-lg text-sm text-[#E8ECF2] placeholder-[#5A6080] focus:outline-none focus:ring-2 focus:ring-red-600/40"

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      {/* Toast notification — fixed at top, always visible */}
      {msg && (
        <div className="fixed top-4 left-1/2 -translate-x-1/2 z-50 flex items-center gap-2.5 px-5 py-3 bg-[#0E1218] border border-[rgba(16,185,129,0.2)] rounded-xl shadow-[0_4px_20px_rgba(0,0,0,0.5)] toast-enter">
          <div className="w-6 h-6 rounded-full bg-[rgba(16,185,129,0.1)] flex items-center justify-center shrink-0">
            <Check className="w-3.5 h-3.5 text-emerald-400" />
          </div>
          <span className="text-sm text-emerald-300 font-medium">{msg}</span>
          <button onClick={() => setMsg('')} className="ml-2 p-0.5 text-[#5A6080] hover:text-[#8A94A6] transition-colors">
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      <h1 className="text-2xl font-bold text-[#E8ECF2]">设置</h1>

      {/* COROS Sync */}
      <div className="glass-card rounded-xl p-6 space-y-4">
        <div className="flex items-center gap-2">
          <ShieldCheck className="w-5 h-5 text-emerald-400" />
          <h2 className="font-semibold text-lg text-[#C8CCD8]">COROS 数据同步</h2>
        </div>
        <div className="bg-[rgba(16,185,129,0.04)] border border-[rgba(16,185,129,0.1)] rounded-lg p-3 text-sm text-emerald-300">
          <p className="font-medium flex items-center gap-1"><Info className="w-4 h-4" /> 通过 coros-training-mcp 原生 API 同步</p>
          <ol className="list-decimal ml-4 mt-1 space-y-0.5 opacity-80">
            <li>在下方「COROS 账号绑定」区域输入邮箱密码并登录</li>
            <li>点击上方「立即同步」拉取运动与健康数据</li>
          </ol>
        </div>
        <button onClick={handleSync} disabled={syncing}
          className="flex items-center gap-2 px-5 py-2.5 bg-red-700 text-white rounded-lg font-medium hover:bg-red-600 transition-colors disabled:opacity-40 text-sm">
          <RefreshCw className={`w-4 h-4 ${syncing ? 'animate-spin' : ''}`} /> {syncing ? '同步中...' : '立即同步'}
        </button>

        <div className="border-t border-[rgba(255,255,255,0.04)] pt-3 space-y-4">
          <p className="text-sm text-[#5A6080] font-medium flex items-center gap-1.5">
            <FileDown className="w-4 h-4" /> 多平台 CSV 导入
          </p>
          <CsvImport onImport={() => setMsg('导入完成，数据已更新')} />

          <button onClick={() => setShowManual(!showManual)}
            className="flex items-center gap-1 px-3 py-1.5 text-sm text-[#5A6080] hover:text-red-400 transition-colors mt-2">
            手动录入健康数据 {showManual ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
          </button>
          {showManual && (
            <form onSubmit={handleManualSubmit} className="space-y-2 pl-2">
              <div className="grid grid-cols-2 gap-2">
                <F label="日期" type="date" value={form.date} onChange={v => setForm({ ...form, date: v })} />
                <F label="睡眠时长 (h)" type="number" step="0.1" value={form.sleep_hours} onChange={v => setForm({ ...form, sleep_hours: v })} />
                <F label="睡眠质量 (1-5)" type="number" min="1" max="5" value={form.sleep_quality} onChange={v => setForm({ ...form, sleep_quality: v })} />
                <F label="静息心率" type="number" value={form.resting_hr} onChange={v => setForm({ ...form, resting_hr: v })} />
                <F label="HRV" type="number" value={form.hrv} onChange={v => setForm({ ...form, hrv: v })} />
                <F label="疲劳度" type="number" min="0" max="100" value={form.fatigue_score} onChange={v => setForm({ ...form, fatigue_score: v })} />
                <F label="恢复度" type="number" min="0" max="100" value={form.recovery_score} onChange={v => setForm({ ...form, recovery_score: v })} />
              </div>
              <button type="submit" className="px-4 py-1.5 bg-red-700 text-white rounded-lg text-sm font-medium hover:bg-red-600 transition-colors">保存</button>
            </form>
          )}
        </div>
      </div>

      {/* COROS Account */}
      <div className="glass-card rounded-xl p-6 space-y-4">
        <h2 className="font-semibold text-lg text-[#C8CCD8]">COROS 账号绑定</h2>
        <p className="text-sm text-[#5A6080]">输入你的 COROS 账号密码，即可自动同步运动数据。</p>
        <CorosAccount />
      </div>

      {/* AI Config */}
      <div className="glass-card rounded-xl p-6 space-y-4">
        <h2 className="font-semibold text-lg text-[#C8CCD8]">AI 教练模型配置</h2>
        <p className="text-sm text-[#5A6080]">选择 AI 模型提供商并填入对应 API Key。</p>
        <div className="flex gap-2">
          {[
            { id: 'deepseek', label: 'DeepSeek', hint: 'platform.deepseek.com' },
            { id: 'openai', label: 'ChatGPT', hint: 'platform.openai.com' },
            { id: 'claude', label: 'Claude', hint: 'console.anthropic.com' },
            { id: 'gemini', label: 'Gemini', hint: 'aistudio.google.com' },
          ].map(p => (
            <button key={p.id} onClick={() => setAiProvider(p.id)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-all border ${
                aiProvider === p.id
                  ? 'bg-[rgba(168,24,24,0.15)] border-[rgba(168,24,24,0.25)] text-red-400'
                  : 'bg-[rgba(255,255,255,0.02)] border-[rgba(255,255,255,0.05)] text-[#5A6080] hover:bg-[rgba(255,255,255,0.04)]'
              }`}>{p.label}</button>
          ))}
        </div>

        {/* Model selector */}
        <div className="flex items-center gap-3">
          <span className="text-xs text-[#5A6080] shrink-0">模型</span>
          <div className="flex gap-1.5 flex-wrap">
            {(MODEL_GROUPS[aiProvider] || []).map(m => (
              <button key={m.id} onClick={() => setAiModel(m.id)}
                className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all border ${
                  aiModel === m.id
                    ? 'bg-[rgba(168,24,24,0.12)] border-[rgba(168,24,24,0.2)] text-red-400'
                    : 'bg-[rgba(255,255,255,0.02)] border-[rgba(255,255,255,0.05)] text-[#5A6080] hover:bg-[rgba(255,255,255,0.04)] hover:text-[#8A94A6]'
                }`}>{m.label}</button>
            ))}
          </div>
        </div>

        <div className="flex gap-2">
          <input type="password" value={aiApiKey} onChange={e => setAiApiKey(e.target.value)}
            placeholder={
              aiProvider === 'deepseek' ? 'sk-...' :
              aiProvider === 'openai' ? 'sk-proj-...' :
              aiProvider === 'claude' ? 'sk-ant-...' :
              'AIza...'
            } className={ic} />
          <button onClick={handleSaveKey}
            className="px-4 py-2.5 bg-[rgba(255,255,255,0.04)] text-[#8A94A6] rounded-lg font-medium hover:bg-[rgba(255,255,255,0.06)] hover:text-[#C8CCD8] transition-colors text-sm shrink-0">保存</button>
        </div>
        <p className="text-xs text-[#3A4060]">
          {aiProvider === 'deepseek' && 'platform.deepseek.com → API Keys'}
          {aiProvider === 'openai' && 'platform.openai.com → API Keys'}
          {aiProvider === 'claude' && 'console.anthropic.com → API Keys'}
          {aiProvider === 'gemini' && 'aistudio.google.com → API Key'}
        </p>
      </div>

    </div>
  )
}

function F({ label, type, value, placeholder, min, max, step, onChange }: {
  label: string; type?: string; value: string; placeholder?: string; min?: string; max?: string; step?: string; onChange: (v: string) => void
}) {
  return (
    <div>
      <label className="block text-xs font-medium text-[#5A6080] mb-1">{label}</label>
      <input type={type} value={value} placeholder={placeholder} min={min} max={max} step={step}
        onChange={e => onChange(e.target.value)}
        className="w-full px-3 py-2 bg-[rgba(255,255,255,0.03)] border border-[rgba(255,255,255,0.08)] rounded-lg text-sm text-[#E8ECF2] placeholder-[#3A4060] focus:outline-none focus:ring-2 focus:ring-red-600/40" />
    </div>
  )
}
