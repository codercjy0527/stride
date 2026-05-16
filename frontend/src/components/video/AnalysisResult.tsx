import { Target, AlertCircle, CheckCircle, ChevronDown, ChevronUp, ArrowDown, ArrowUp } from 'lucide-react'
import { useState } from 'react'
import type { PoseAnalysisResult, PoseMetric } from '@/types'

const STATUS_COLORS: Record<string, string> = {
  good: 'text-emerald-400 bg-emerald-950/20 border-emerald-800/20',
  info: 'text-cyan-400 bg-cyan-950/20 border-cyan-800/20',
  warning: 'text-amber-400 bg-amber-950/20 border-amber-800/20',
  unknown: 'text-[#5A6080] bg-[rgba(255,255,255,0.02)] border-[rgba(255,255,255,0.05)]',
}

const STATUS_ICONS: Record<string, typeof CheckCircle> = {
  good: CheckCircle,
  info: AlertCircle,
  warning: AlertCircle,
  unknown: AlertCircle,
}

const CHAIN_ICONS: Record<number, string> = {
  0: 'text-red-400', 1: 'text-amber-400', 2: 'text-cyan-400',
}

export default function AnalysisResult({ result }: { result: PoseAnalysisResult }) {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({})

  const scoreColor = result.score >= 80 ? 'text-emerald-400' : result.score >= 60 ? 'text-amber-400' : 'text-red-400'

  // Collect all metrics
  const basicMetrics = [
    { k: 'cadence', label: '步频', unit: 'spm', v: result.cadence },
    { k: 'ground_contact_time', label: '触地时间', unit: 'ms', v: result.ground_contact_time },
    { k: 'vertical_oscillation', label: '垂直振幅', unit: 'cm', v: result.vertical_oscillation },
    { k: 'trunk_lean', label: '躯干前倾', unit: '°', v: result.trunk_lean },
  ]

  const checkMetrics: { k: string; label: string; data: PoseMetric }[] = [
    { k: 'foot_strike', label: '落脚位置', data: result.foot_strike },
    { k: 'knee_valgus', label: '膝盖对齐', data: result.knee_valgus },
    { k: 'hip_drop', label: '髋部下沉', data: result.hip_drop },
    { k: 'arm_cross', label: '手臂交叉', data: result.arm_cross },
    { k: 'shoulder_rotation', label: '肩部旋转', data: result.shoulder_rotation },
    { k: 'head_stability', label: '头部稳定', data: result.head_stability },
  ]

  const totalWarnings = checkMetrics.filter(m => m.data.status === 'warning').length

  return (
    <div className="space-y-5">
      {/* Score card */}
      <div className="glass-card rounded-xl p-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="font-semibold text-lg text-[#C8CCD8]">跑姿分析报告</h2>
            <p className="text-xs text-[#5A6080] mt-0.5">
              {result.view_angle === 'side' ? '侧面' : result.view_angle === 'rear' ? '后方' : '正面'}拍摄 · 7点连锁检查
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Target className="w-5 h-5 text-red-400" />
            <span className={`text-3xl font-bold ${scoreColor}`}>{result.score}</span>
            <span className="text-[#5A6080] text-sm">/ 100</span>
          </div>
        </div>

        {/* Summary bar */}
        <div className="mt-4 flex items-center gap-2 text-xs">
          <span className={`px-2 py-0.5 rounded ${totalWarnings > 0 ? 'bg-amber-950/30 text-amber-400 border border-amber-800/20' : 'bg-emerald-950/30 text-emerald-400 border border-emerald-800/20'}`}>
            {totalWarnings > 0 ? `${totalWarnings} 项需注意` : '全部通过'}
          </span>
          <span className="text-[#5A6080]">
            连锁系统 · {result.chain_analysis.lower_count > 0 ? '从下肢开始修复' : result.chain_analysis.core_count > 0 ? '核心待加强' : '保持当前状态'}
          </span>
        </div>
      </div>

      {/* Basic metrics grid */}
      <div className="glass-card rounded-xl p-5">
        <h3 className="text-sm font-medium text-[#C8CCD8] mb-3">基础数据</h3>
        <div className="grid grid-cols-4 gap-3">
          {basicMetrics.map(m => (
            <div key={m.k} className="text-center p-3 bg-[rgba(255,255,255,0.015)] rounded-lg border border-[rgba(255,255,255,0.03)]">
              <p className="text-xs text-[#5A6080]">{m.label}</p>
              <p className="font-bold text-lg text-[#C8CCD8]">{m.v}</p>
              <p className="text-xs text-[#3A4060]">{m.unit}</p>
            </div>
          ))}
        </div>
      </div>

      {/* 7 Checkpoints */}
      <div className="glass-card rounded-xl p-5">
        <h3 className="text-sm font-medium text-[#C8CCD8] mb-3">7项检查点</h3>
        <div className="grid grid-cols-2 gap-2">
          {checkMetrics.map(({ k, label, data }) => {
            const Icon = STATUS_ICONS[data.status]
            return (
              <div key={k}
                className={`flex items-start gap-3 p-3 rounded-lg border ${STATUS_COLORS[data.status]}`}>
                <Icon className="w-4 h-4 mt-0.5 shrink-0" />
                <div className="min-w-0">
                  <p className="text-sm font-medium">{label}</p>
                  <p className="text-xs opacity-80 mt-0.5">{data.detail}</p>
                  {data.value !== null && (
                    <p className="text-xs font-mono opacity-50 mt-1">{data.value}</p>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Chain analysis - bottom-up priority */}
      {result.chain_analysis.groups.length > 0 && (
        <div className="glass-card rounded-xl p-5">
          <h3 className="text-sm font-medium text-[#C8CCD8] mb-4 flex items-center gap-2">
            连锁分析
            <span className="text-xs text-[#5A6080] font-normal">从下肢 → 核心 → 上肢，渐进修复</span>
          </h3>

          <div className="space-y-1">
            {result.chain_analysis.groups.map((group, gi) => {
              const isExpanded = expanded[`g${gi}`] !== false
              const LevelIcon = gi === 0 ? ArrowDown : gi === 1 ? ArrowUp : ArrowDown
              const hasItems = group.items.length > 0

              return (
                <div key={gi}>
                  <button
                    onClick={() => setExpanded({ ...expanded, [`g${gi}`]: !isExpanded })}
                    className={`w-full flex items-center gap-3 p-3 rounded-lg border text-left transition-all ${
                      hasItems
                        ? STATUS_COLORS[gi === 0 ? 'warning' : gi === 1 ? 'info' : 'info']
                        : 'bg-[rgba(255,255,255,0.01)] border-[rgba(255,255,255,0.04)]'
                    }`}>
                    <LevelIcon className={`w-4 h-4 ${CHAIN_ICONS[gi] || 'text-[#5A6080]'}`} />
                    <div className="flex-1 min-w-0">
                      <span className="text-sm font-medium">{group.level}</span>
                      <span className="text-xs text-[#5A6080] ml-2">
                        {hasItems ? `${group.items.length} 项` : '无问题'}
                      </span>
                    </div>
                    {hasItems && (isExpanded ? <ChevronUp className="w-4 h-4 text-[#5A6080]" /> : <ChevronDown className="w-4 h-4 text-[#5A6080]" />)}
                  </button>

                  {isExpanded && hasItems && (
                    <div className="ml-4 mt-1 mb-2 pl-6 border-l-2 border-[rgba(255,255,255,0.06)] space-y-2 pt-2">
                      <p className="text-xs text-[#5A6080] italic">{group.rationale}</p>
                      {group.items.map((item, ii) => (
                        <div key={ii} className="p-2.5 rounded-lg bg-[rgba(255,255,255,0.015)] border border-[rgba(255,255,255,0.03)]">
                          <p className="text-sm font-medium text-[#C8CCD8]">{item.label}</p>
                          <p className="text-xs text-[#8A94A6] mt-0.5">{item.detail}</p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
