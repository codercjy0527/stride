import { useCallback } from 'react'
import { Upload } from 'lucide-react'

export default function VideoUploader({ onUpload, analyzing }: { onUpload: (file: File) => void; analyzing: boolean }) {
  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    const file = e.dataTransfer.files[0]
    if (file && file.type.startsWith('video/')) onUpload(file)
  }, [onUpload])

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) onUpload(file)
  }

  return (
    <div onDrop={handleDrop} onDragOver={(e) => e.preventDefault()}
      onClick={() => document.getElementById('video-input')?.click()}
      className="glass-card rounded-xl p-10 text-center border-dashed border-[rgba(255,255,255,0.08)] hover:border-red-700/30 transition-all cursor-pointer">
      <Upload className="w-10 h-10 text-[#3A4060] mx-auto mb-3" />
      <p className="text-[#8A94A6] font-medium">{analyzing ? '分析中...' : '点击或拖拽上传跑步视频'}</p>
      <p className="text-sm text-[#5A6080] mt-1">支持 MP4、MOV、AVI 格式</p>
      <input id="video-input" type="file" accept="video/*" onChange={handleChange} className="hidden" />
    </div>
  )
}
