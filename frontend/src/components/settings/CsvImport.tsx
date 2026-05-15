import { useState, useRef } from 'react'
import { Upload, FileText, Check, Loader2, AlertTriangle, X } from 'lucide-react'
import { csvImport } from '@/services/api'

interface ImportResult {
  ok: boolean
  format?: string
  imported?: number
  skipped?: number
  errors?: string[]
  message?: string
}

const PLATFORM_TIPS: Record<string, string> = {
  garmin: 'Garmin Connect → 活动 → 导出 CSV',
  apple_health: '健康 App → 导出 → 跑步训练',
  strava: 'Strava → 设置 → 导出数据',
  coros: 'COROS Training Hub → 导出 CSV',
  huawei: '华为运动健康 → 我的 → 导出数据',
  xiaomi: '小米运动 → 设置 → 导出健康数据',
  keep: 'Keep → 我 → 导出跑步记录',
}

export default function CsvImport({ onImport }: { onImport: () => void }) {
  const [file, setFile] = useState<File | null>(null)
  const [mode, setMode] = useState<'activities' | 'health'>('activities')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<ImportResult | null>(null)
  const [dragOver, setDragOver] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    const f = e.dataTransfer.files[0]
    if (f && f.name.endsWith('.csv')) {
      setFile(f)
      setResult(null)
    }
  }

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    if (f) {
      setFile(f)
      setResult(null)
    }
  }

  const handleImport = async () => {
    if (!file) return
    setLoading(true)
    setResult(null)
    try {
      const res = mode === 'activities'
        ? await csvImport.activities(file)
        : await csvImport.health(file)
      setResult(res.data)
      onImport()
    } catch (err: any) {
      setResult({ ok: false, message: err.response?.data?.detail || '导入失败' })
    } finally {
      setLoading(false)
    }
  }

  const reset = () => {
    setFile(null)
    setResult(null)
  }

  return (
    <div className="space-y-3">
      {/* Mode toggle */}
      <div className="flex gap-2">
        {(['activities', 'health'] as const).map((m) => (
          <button key={m} onClick={() => { setMode(m); setResult(null) }}
            className={`px-3 py-1.5 text-xs font-medium rounded-lg border transition-all ${
              mode === m
                ? 'bg-[rgba(168,24,24,0.12)] border-[rgba(168,24,24,0.2)] text-red-400'
                : 'bg-[rgba(255,255,255,0.02)] border-[rgba(255,255,255,0.05)] text-[#5A6080] hover:bg-[rgba(255,255,255,0.04)]'
            }`}
          >
            {m === 'activities' ? '运动记录' : '健康数据'}
          </button>
        ))}
      </div>

      {/* Drop zone / file info */}
      {!file ? (
        <div
          onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          onClick={() => inputRef.current?.click()}
          className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-colors ${
            dragOver
              ? 'border-red-600/40 bg-[rgba(168,24,24,0.04)]'
              : 'border-[rgba(255,255,255,0.06)] hover:border-[rgba(255,255,255,0.12)] bg-[rgba(255,255,255,0.01)]'
          }`}
        >
          <Upload className={`w-8 h-8 mx-auto mb-2 ${dragOver ? 'text-red-400' : 'text-[#3A4060]'}`} />
          <p className="text-sm text-[#8A94A6]">拖拽 CSV 文件到此处或点击选择</p>
          <p className="text-xs text-[#3A4060] mt-1">
            支持 Garmin · Apple Health · 华为 · 小米 · Keep · 悦跑圈 · Strava
          </p>
          <input ref={inputRef} type="file" accept=".csv" onChange={handleFileSelect} className="hidden" />
        </div>
      ) : (
        <div className="bg-[rgba(255,255,255,0.015)] border border-[rgba(255,255,255,0.06)] rounded-xl p-4 space-y-3">
          {/* File info */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <FileText className="w-4 h-4 text-red-400" />
              <span className="text-sm text-[#C8CCD8]">{file.name}</span>
              <span className="text-xs text-[#3A4060]">({(file.size / 1024).toFixed(0)} KB)</span>
            </div>
            <button onClick={reset} className="p-1 text-[#5A6080] hover:text-[#C8CCD8] transition-colors">
              <X className="w-3.5 h-3.5" />
            </button>
          </div>

          {/* Import button */}
          <button onClick={handleImport} disabled={loading}
            className="w-full py-2 bg-red-700 text-white rounded-lg text-sm font-medium hover:bg-red-600 transition-colors disabled:opacity-40 flex items-center justify-center gap-2"
          >
            {loading ? <><Loader2 className="w-4 h-4 animate-spin" /> 解析中...</> : <>开始导入</>}
          </button>

          {/* Result */}
          {result && (
            <div className={`p-3 rounded-lg text-xs ${
              result.ok
                ? 'bg-[rgba(16,185,129,0.04)] border border-[rgba(16,185,129,0.1)] text-emerald-300'
                : 'bg-[rgba(239,68,68,0.04)] border border-[rgba(239,68,68,0.1)] text-red-400'
            }`}>
              <div className="flex items-center gap-1.5 mb-1">
                {result.ok ? <Check className="w-3.5 h-3.5" /> : <AlertTriangle className="w-3.5 h-3.5" />}
                <span className="font-medium">{result.message || '导入完成'}</span>
              </div>
              {result.format && (
                <p className="ml-5 opacity-70">识别格式：{result.format === 'activity' ? '运动记录' : result.format === 'health' ? '健康数据' : result.format}</p>
              )}
              {result.imported !== undefined && (
                <p className="ml-5 opacity-70">导入 {result.imported} 条{result.skipped ? `，跳过 ${result.skipped} 条` : ''}</p>
              )}
              {result.errors && result.errors.length > 0 && (
                <div className="ml-5 mt-1 opacity-60 space-y-0.5">
                  {result.errors.slice(0, 3).map((e, i) => <p key={i}>{e}</p>)}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Platform tips */}
      <details className="text-xs text-[#3A4060]">
        <summary className="cursor-pointer hover:text-[#5A6080] transition-colors">各平台导出指南</summary>
        <div className="mt-2 space-y-1 pl-2">
          {Object.entries(PLATFORM_TIPS).map(([k, v]) => (
            <p key={k}><span className="text-[#5A6080] font-medium">{k}:</span> {v}</p>
          ))}
        </div>
      </details>
    </div>
  )
}
