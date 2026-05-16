import { useState } from 'react'
import { Camera, Video, Footprints } from 'lucide-react'
import VideoUploader from '@/components/video/VideoUploader'
import AnalysisResult from '@/components/video/AnalysisResult'
import type { ViewAngle, PoseAnalysisResult } from '@/types'

const ANGLE_GUIDES: { key: ViewAngle; label: string; icon: typeof Camera; desc: string; tips: string[] }[] = [
  {
    key: 'side', label: '侧面拍摄', icon: Camera, desc: '最佳角度。观察步频、落脚位置、触地时间。',
    tips: ['相机与髋部同高', '距离 3-5 米', '全身入镜，水平拍摄', '跑步机或直线跑道'],
  },
  {
    key: 'rear', label: '后方拍摄', icon: Video, desc: '观察膝盖对齐、髋部下沉、肩部旋转。',
    tips: ['相机在跑道正后方', '与腰部同高', '能看到双脚着地方式', '适于检测不对称问题'],
  },
  {
    key: 'front', label: '正面拍摄', icon: Footprints, desc: '观察膝盖内扣、摆臂交叉、头部晃动。',
    tips: ['相机在跑道正前方', '与胸部同高', '注意手臂是否越过中线', '检测左右不平衡'],
  },
]

export default function VideoAnalysis() {
  const [analyzing, setAnalyzing] = useState(false)
  const [result, setResult] = useState<PoseAnalysisResult | null>(null)
  const [videoUrl, setVideoUrl] = useState('')
  const [viewAngle, setViewAngle] = useState<ViewAngle>('side')
  const [lastKey, setLastKey] = useState('')

  const currentGuide = ANGLE_GUIDES.find(g => g.key === viewAngle)!

  const handleUpload = async (file: File) => {
    setVideoUrl(URL.createObjectURL(file))
    setAnalyzing(true)
    setResult(null)
    try {
      const fd = new FormData()
      fd.append('video', file)
      fd.append('view_angle', viewAngle)
      const res = await fetch('/api/video/analyze', { method: 'POST', body: fd })
      const data = await res.json()
      setResult(data.error ? null : data)
      if (!data.error) setLastKey('')
    } catch {
      // Demo fallback if backend unavailable
      setResult(null)
    } finally {
      setAnalyzing(false)
    }
  }

  const handleBarefootUpload = async (file: File) => {
    if (!lastKey) return
    setVideoUrl(URL.createObjectURL(file))
    setAnalyzing(true)
    try {
      const fd = new FormData()
      fd.append('video', file)
      fd.append('shod_video_key', lastKey)
      fd.append('view_angle', viewAngle)
      const res = await fetch('/api/video/analyze/barefoot', { method: 'POST', body: fd })
      const data = await res.json()
      setResult(data.result)
    } catch {
    } finally {
      setAnalyzing(false)
    }
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-[#E8ECF2]">跑姿视频分析</h1>
        <p className="text-sm text-[#5A6080] mt-1">7点连锁检查系统 · 从下肢到上肢渐进分析</p>
      </div>

      {/* 角度选择 */}
      <div className="glass-card rounded-xl p-5 space-y-3">
        <h3 className="text-sm font-medium text-[#C8CCD8]">选择拍摄角度</h3>
        <div className="grid grid-cols-3 gap-2">
          {ANGLE_GUIDES.map(g => {
            const Icon = g.icon
            return (
              <button key={g.key} onClick={() => setViewAngle(g.key)}
                className={`p-3 rounded-lg border text-left transition-all ${
                  viewAngle === g.key
                    ? 'border-red-700/50 bg-red-950/20'
                    : 'border-[rgba(255,255,255,0.08)] bg-[rgba(255,255,255,0.02)] hover:bg-[rgba(255,255,255,0.04)]'
                }`}>
                <div className="flex items-center gap-2 mb-1">
                  <Icon className={`w-4 h-4 ${viewAngle === g.key ? 'text-red-400' : 'text-[#5A6080]'}`} />
                  <span className={`text-sm font-medium ${viewAngle === g.key ? 'text-[#E8ECF2]' : 'text-[#8A94A6]'}`}>
                    {g.label}
                  </span>
                </div>
                <p className="text-xs text-[#5A6080]">{g.desc}</p>
              </button>
            )
          })}
        </div>
        {/* 拍摄提示 */}
        <div className="bg-[rgba(255,255,255,0.02)] rounded-lg p-3">
          <p className="text-xs font-medium text-[#8A94A6] mb-1.5">{currentGuide.label}技巧</p>
          <ul className="space-y-0.5">
            {currentGuide.tips.map(t => (
              <li key={t} className="text-xs text-[#5A6080] flex items-center gap-1.5">
                <span className="w-1 h-1 rounded-full bg-red-700/50 shrink-0" /> {t}
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* 上传区 */}
      <VideoUploader onUpload={handleUpload} analyzing={analyzing} />

      {/* 预览 */}
      {videoUrl && (
        <div className="glass-card rounded-xl overflow-hidden">
          <video src={videoUrl} controls className="w-full max-h-96" />
        </div>
      )}

      {/* 加载 */}
      {analyzing && (
        <div className="glass-card rounded-xl p-8 text-center">
          <div className="animate-spin w-10 h-10 border-4 border-red-600 border-t-transparent rounded-full mx-auto mb-3" />
          <p className="text-[#8A94A6]">正在分析跑姿，请稍候...</p>
          <p className="text-sm text-[#5A6080] mt-1">检测 33 个关键点 → 计算 7 项指标 → 连锁分析</p>
        </div>
      )}

      {/* 结果 */}
      {result && <AnalysisResult result={result} />}

      {/* 赤足对比 */}
      {result && !analyzing && (
        <div className="glass-card rounded-xl p-5 space-y-3">
          <h3 className="text-sm font-medium text-[#C8CCD8]">赤足对比（可选）</h3>
          <p className="text-xs text-[#5A6080]">
            脱掉鞋子，用同样的角度再拍一段。赤足时的跑姿更接近身体的自然模式，
            对比穿鞋与赤足的差异可以帮你选择更适合的跑鞋。
          </p>
          <VideoUploader onUpload={handleBarefootUpload} analyzing={analyzing} barefoot />
        </div>
      )}
    </div>
  )
}
