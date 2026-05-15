import { NavLink } from 'react-router-dom'
import { LayoutDashboard, Dumbbell, MessageCircle, Video, Trophy, Settings, Footprints, BarChart3 } from 'lucide-react'

const links = [
  { to: '/', icon: LayoutDashboard, label: '仪表盘' },
  { to: '/exercise', icon: BarChart3, label: '运动数据' },
  { to: '/training', icon: Dumbbell, label: '训练计划' },
  { to: '/ai-coach', icon: MessageCircle, label: 'AI 教练' },
  { to: '/video', icon: Video, label: '跑姿分析' },
  { to: '/race', icon: Trophy, label: '赛事配速' },
  { to: '/settings', icon: Settings, label: '设置' },
]

export default function Sidebar() {
  return (
    <aside className="w-56 bg-[#070A0E] flex flex-col shrink-0 border-r border-[rgba(255,255,255,0.04)]">
      {/* Logo */}
      <div className="flex items-center gap-3 px-5 py-5 border-b border-[rgba(255,255,255,0.04)]">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-red-700 to-red-900 flex items-center justify-center shadow-[0_2px_8px_rgba(185,28,28,0.2)]">
          <Footprints className="w-4.5 h-4.5 text-white" />
        </div>
        <div>
          <h1 className="text-sm font-bold text-[#E8ECF2] tracking-wide">Stride</h1>
          <p className="text-[10px] text-[#5A6080] tracking-wider uppercase">Performance Lab</p>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-4">
        <ul className="space-y-0 px-3">
          {links.map(({ to, icon: Icon, label }) => (
            <li key={to}>
              <NavLink
                to={to}
                end={to === '/'}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2.5 rounded-r-lg text-[13px] font-medium transition-all duration-200 border-l-[3px] -ml-[13px] ${
                    isActive
                      ? 'border-red-600 bg-[rgba(185,28,28,0.06)] text-[#E8ECF2]'
                      : 'border-transparent text-[#7A8094] hover:bg-[rgba(255,255,255,0.02)] hover:text-[#B8BEC8]'
                  }`
                }
              >
                <Icon className="w-4 h-4" />
                {label}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>

      {/* Footer */}
      <div className="px-5 py-4 border-t border-[rgba(255,255,255,0.04)]">
        <p className="text-[10px] text-[#4A5070] tracking-wider">本地桌面版</p>
      </div>
    </aside>
  )
}
