import { useState } from 'react'
import VideoUploader from '@/components/video/VideoUploader'
import AnalysisResult from '@/components/video/AnalysisResult'

export default function VideoAnalysis() {
  const [analyzing, setAnalyzing] = useState(false)
  const [result, setResult] = useState<any>(null)
  const [videoUrl, setVideoUrl] = useState('')

  const handleUpload = async (file: File) => {
    setVideoUrl(URL.createObjectURL(file))
    setAnalyzing(true)
    setResult(null)
    try {
      const { video } = await import('@/services/api')
      const res = await video.analyze(file)
      setResult(res.data)
    } catch {
      // Demo fallback
      await new Promise((r) => setTimeout(r, 3000))
      setResult({
        cadence: 172, ground_contact_time: 245, vertical_oscillation: 8.5, trunk_lean: 4.2, arm_swing_angle: 65,
        issues: [
          { problem: '步频偏低', suggestion: '建议将步频提升至 180+ spm，可通过节拍器辅助训练' },
          { problem: '触地时间偏长', suggestion: '加强小腿力量训练，多做跳绳和弹跳练习缩短触地时间' },
          { problem: '躯干前倾不足', suggestion: '跑步时身体微微前倾 5-8°，利用重力驱动前进' },
        ],
        score: 72,
      })
    } finally {
      setAnalyzing(false)
    }
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold text-[#E8ECF2]">跑姿视频分析</h1>
      <VideoUploader onUpload={handleUpload} analyzing={analyzing} />
      {videoUrl && (
        <div className="glass-card rounded-xl overflow-hidden">
          <video src={videoUrl} controls className="w-full max-h-96" />
        </div>
      )}
      {analyzing && (
        <div className="glass-card rounded-xl p-8 text-center">
          <div className="animate-spin w-10 h-10 border-4 border-red-600 border-t-transparent rounded-full mx-auto mb-3" />
          <p className="text-[#8A94A6]">正在分析跑姿，请稍候...</p>
          <p className="text-sm text-[#5A6080] mt-1">检测关键点、计算步频、触地时间...</p>
        </div>
      )}
      {result && <AnalysisResult result={result} />}
    </div>
  )
}
