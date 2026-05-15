import { User, Sparkles } from 'lucide-react'
import type { ChatMessage } from '@/types'
import Markdown from '@/components/chat/Markdown'

export default function ChatMessageComponent({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user'

  if (isUser) {
    return (
      <div className="flex gap-3 flex-row-reverse">
        <div className="w-8 h-8 rounded-full bg-red-700 flex items-center justify-center shrink-0 shadow-[0_2px_6px_rgba(185,28,28,0.3)]">
          <User className="w-4 h-4 text-white" />
        </div>
        <div className="max-w-[80%] rounded-2xl rounded-tr-none px-4 py-3 bg-red-700 text-white text-sm leading-relaxed shadow-[0_1px_3px_rgba(185,28,28,0.2)]">
          {message.imageUrl && (
            <img src={message.imageUrl} alt="uploaded" className="max-w-xs rounded-lg mb-2 border border-[rgba(255,255,255,0.15)]" />
          )}
          <p className="whitespace-pre-wrap">{message.content}</p>
        </div>
      </div>
    )
  }

  // AI message — with markdown rendering and section icons
  const content = message.content

  return (
    <div className="flex gap-3">
      <div className="w-8 h-8 rounded-full bg-[rgba(255,255,255,0.06)] border border-[rgba(255,255,255,0.08)] flex items-center justify-center shrink-0">
        <Sparkles className="w-4 h-4 text-red-400" />
      </div>
      <div className="max-w-[85%] rounded-2xl rounded-tl-none px-5 py-4 bg-[rgba(255,255,255,0.025)] border border-[rgba(255,255,255,0.04)] shadow-[0_1px_3px_rgba(0,0,0,0.3)]">
        <Markdown content={content} />
      </div>
    </div>
  )
}
