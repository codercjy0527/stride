import { useState, useRef, useEffect } from 'react'
import { Send, ImagePlus, X, Zap, TrendingUp, BarChart3, MessageCircle } from 'lucide-react'
import { ai } from '@/services/api'
import type { ChatMessage } from '@/types'
import ChatMessageComponent from '@/components/chat/ChatMessage'

const WELCOME_MSG = `你好！我是你的 AI 跑步教练。

我可以基于你的 COROS 数据进行专业分析：

- **训练负荷分析** — AC/CT 比值、风险等级、训练量建议
- **恢复状态评估** — HRV、静息心率、睡眠质量综合判断
- **配速区间计算** — 基于阈值配速的五区间精确配速
- **截图深度解读** — 上传运动数据截图获取短板诊断`

const QUICK_ACTIONS = [
  { icon: Zap, label: '分析训练负荷', prompt: '请分析我当前的训练负荷状态，判断是否存在过度训练风险，并给出本周训练量建议。' },
  { icon: TrendingUp, label: '评估恢复状态', prompt: '请评估我当前的恢复状态（HRV、静息心率、睡眠），判断是否适合进行高强度训练。' },
  { icon: BarChart3, label: '生成训练建议', prompt: '请根据我的体能水平和阈值配速，给出本周具体训练计划（包含配速区间和训练时长）。' },
]

export default function AICoach() {
  const [messages, setMessages] = useState<ChatMessage[]>([
    { role: 'assistant', content: WELCOME_MSG },
  ])
  const [input, setInput] = useState('')
  const [image, setImage] = useState<File | null>(null)
  const [imagePreview, setImagePreview] = useState('')
  const [loading, setLoading] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => { scrollRef.current?.scrollTo(0, scrollRef.current.scrollHeight) }, [messages])

  const handleSend = async (text?: string) => {
    const msg = text || input
    if (!msg.trim() && !image) return
    const userMsg: ChatMessage = { role: 'user', content: msg || '请分析这张截图', imageUrl: imagePreview || undefined }
    setMessages((prev) => [...prev, userMsg])
    setInput('')
    setLoading(true)
    try {
      const res = await ai.chat(msg || '请分析这张运动截图', image || undefined)
      setMessages((prev) => [...prev, { role: 'assistant', content: res.data.reply }])
    } catch {
      setMessages((prev) => [...prev, { role: 'assistant', content: '抱歉，AI 分析暂时不可用。请确保已配置 API Key。' }])
    } finally {
      setLoading(false)
      setImage(null)
      setImagePreview('')
    }
  }

  const handleImageSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) { setImage(file); setImagePreview(URL.createObjectURL(file)) }
  }

  return (
    <div className="max-w-3xl mx-auto h-[calc(100vh-10rem)] flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-xl font-bold text-[#E8ECF2] tracking-tight flex items-center gap-2">
            <MessageCircle className="w-5 h-5 text-red-400" />
            AI 教练对话
          </h1>
          <p className="text-xs text-[#5A6080] mt-0.5">基于 COROS 数据的智能训练分析</p>
        </div>
      </div>

      {/* Chat area */}
      <div className="flex-1 glass-card rounded-xl flex flex-col overflow-hidden">
        <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.map((msg, i) => (
            <ChatMessageComponent key={i} message={msg} />
          ))}

          {/* Quick actions — shown after welcome message */}
          {messages.length === 1 && !loading && (
            <div className="flex flex-wrap gap-2 mt-3 pl-11">
              {QUICK_ACTIONS.map((action, i) => (
                <button
                  key={i}
                  onClick={() => handleSend(action.prompt)}
                  className="flex items-center gap-1.5 px-3 py-2 bg-[rgba(255,255,255,0.03)] border border-[rgba(255,255,255,0.06)] rounded-lg text-xs text-[#8A94A6] hover:bg-[rgba(255,255,255,0.05)] hover:text-[#C8CCD8] hover:border-[rgba(255,255,255,0.1)] transition-all"
                >
                  <action.icon className="w-3 h-3 text-red-400" />
                  {action.label}
                </button>
              ))}
            </div>
          )}

          {/* Loading indicator */}
          {loading && (
            <div className="flex gap-3 pl-11 items-center">
              <div className="flex items-center gap-2 px-4 py-3 bg-[rgba(255,255,255,0.02)] border border-[rgba(255,255,255,0.04)] rounded-2xl rounded-tl-none">
                <div className="flex gap-1">
                  <span className="w-1.5 h-1.5 bg-[#5A6080] rounded-full animate-bounce" />
                  <span className="w-1.5 h-1.5 bg-[#5A6080] rounded-full animate-bounce" style={{ animationDelay: '0.15s' }} />
                  <span className="w-1.5 h-1.5 bg-[#5A6080] rounded-full animate-bounce" style={{ animationDelay: '0.3s' }} />
                </div>
                <span className="text-xs text-[#5A6080]">AI 正在分析你的数据...</span>
              </div>
            </div>
          )}
        </div>

        {/* Image preview */}
        {imagePreview && (
          <div className="px-4 pt-2 flex items-center gap-2">
            <div className="relative">
              <img src={imagePreview} alt="preview" className="h-16 rounded-lg border border-[rgba(255,255,255,0.08)]" />
              <button onClick={() => { setImage(null); setImagePreview('') }}
                className="absolute -top-1.5 -right-1.5 w-5 h-5 bg-red-700 text-white rounded-full flex items-center justify-center shadow-lg">
                <X className="w-3 h-3" />
              </button>
            </div>
          </div>
        )}

        {/* Input area */}
        <div className="border-t border-[rgba(255,255,255,0.04)] p-4 flex items-end gap-2 bg-[rgba(0,0,0,0.15)]">
          <button onClick={() => fileRef.current?.click()}
            className="p-2.5 text-[#5A6080] hover:text-red-400 hover:bg-[rgba(185,28,28,0.08)] rounded-lg transition-all shrink-0" title="上传截图">
            <ImagePlus className="w-4.5 h-4.5" />
          </button>
          <input ref={fileRef} type="file" accept="image/*" onChange={handleImageSelect} className="hidden" />
          <textarea value={input} onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() } }}
            placeholder="描述你的问题，或上传运动截图..."
            rows={2}
            className="flex-1 px-4 py-2.5 bg-[rgba(255,255,255,0.03)] border border-[rgba(255,255,255,0.06)] rounded-xl text-sm text-[#E8ECF2] placeholder-[#5A6080] focus:outline-none focus:ring-2 focus:ring-red-600/30 focus:border-red-700/30 resize-none" />
          <button onClick={() => handleSend()} disabled={loading || (!input.trim() && !image)}
            className="p-2.5 bg-red-700 text-white rounded-xl hover:bg-red-600 transition-colors disabled:opacity-40 shrink-0 shadow-[0_2px_6px_rgba(185,28,28,0.2)]">
            <Send className="w-4.5 h-4.5" />
          </button>
        </div>
      </div>
    </div>
  )
}
