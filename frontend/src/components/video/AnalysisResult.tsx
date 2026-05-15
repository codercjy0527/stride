import { AlertCircle, CheckCircle, Target } from 'lucide-react'

interface AnalysisResultProps {
  result: {
    cadence: number; ground_contact_time: number; vertical_oscillation: number
    trunk_lean: number; arm_swing_angle: number; issues: { problem: string; suggestion: string }[]; score: number
  }
}

export default function AnalysisResult({ result }: AnalysisResultProps) {
  const scoreColor = result.score >= 80 ? 'text-emerald-400' : result.score >= 60 ? 'text-yellow-400' : 'text-red-400'

  return (
    <div className="glass-card rounded-xl p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold text-lg text-[#C8CCD8]">分析报告</h2>
        <div className="flex items-center gap-2">
          <Target className="w-5 h-5 text-red-400" />
          <span className={`text-2xl font-bold ${scoreColor}`}>{result.score}</span>
          <span className="text-[#5A6080] text-sm">/ 100</span>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <M label="步频" value={`${result.cadence}`} unit="spm" />
        <M label="触地时间" value={`${result.ground_contact_time}`} unit="ms" />
        <M label="垂直振幅" value={`${result.vertical_oscillation}`} unit="cm" />
        <M label="躯干前倾" value={`${result.trunk_lean}`} unit="°" />
        <M label="摆臂角度" value={`${result.arm_swing_angle}`} unit="°" />
      </div>

      <div>
        <h3 className="font-semibold text-[#C8CCD8] mb-3 flex items-center gap-2">
          <AlertCircle className="w-5 h-5 text-amber-400" /> 发现的问题与矫正建议
        </h3>
        <div className="space-y-3">
          {result.issues.map((issue, i) => (
            <div key={i} className="border border-[rgba(255,255,255,0.05)] rounded-lg p-4 bg-[rgba(255,255,255,0.015)]">
              <p className="font-medium text-[#C8CCD8] text-sm flex items-center gap-2">
                <span className="w-1.5 h-1.5 bg-amber-500 rounded-full" /> {issue.problem}
              </p>
              <p className="text-sm text-[#8A94A6] mt-1.5 ml-3.5">
                <CheckCircle className="w-4 h-4 text-emerald-400 inline mr-1" /> {issue.suggestion}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function M({ label, value, unit }: { label: string; value: string; unit: string }) {
  return (
    <div className="text-center p-3 bg-[rgba(255,255,255,0.015)] rounded-lg border border-[rgba(255,255,255,0.03)]">
      <p className="text-xs text-[#5A6080]">{label}</p>
      <p className="font-bold text-lg text-[#C8CCD8]">{value}</p>
      <p className="text-xs text-[#3A4060]">{unit}</p>
    </div>
  )
}
