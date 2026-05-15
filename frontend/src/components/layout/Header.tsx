export default function Header() {
  return (
    <header className="h-12 bg-[#070A0E] border-b border-[rgba(255,255,255,0.03)] flex items-center justify-between px-6 shrink-0">
      <div className="flex items-center gap-3">
        <div className="w-1.5 h-1.5 rounded-full bg-red-600 shadow-[0_0_6px_rgba(185,28,28,0.4)]" />
        <span className="text-xs text-[#7A8094] tracking-wider uppercase">训练有度，进步有数</span>
      </div>
      <div className="flex items-center gap-2">
        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[rgba(255,255,255,0.02)] border border-[rgba(255,255,255,0.04)]">
          <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 shadow-[0_0_4px_rgba(16,185,129,0.3)]" />
          <span className="text-[10px] text-[#5A6080] tracking-wider">SYNCED</span>
        </div>
      </div>
    </header>
  )
}
