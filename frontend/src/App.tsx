import { useState, useEffect } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Sidebar from '@/components/layout/Sidebar'
import Header from '@/components/layout/Header'
import Dashboard from '@/pages/Dashboard'
import TrainingPlan from '@/pages/TrainingPlan'
import AICoach from '@/pages/AICoach'
import VideoAnalysis from '@/pages/VideoAnalysis'
import RacePlanner from '@/pages/RacePlanner'
import ExerciseData from '@/pages/ExerciseData'
import Settings from '@/pages/Settings'
import ActivationScreen from '@/components/activation/ActivationScreen'
import { activation } from '@/services/api'

export default function App() {
  const [activated, setActivated] = useState<boolean | null>(null)

  useEffect(() => {
    activation.status()
      .then((r) => setActivated(r.data.activated))
      .catch(() => setActivated(true)) // offline = allow access
  }, [])

  // Loading state
  if (activated === null) {
    return (
      <div className="h-screen bg-[#090C10] flex items-center justify-center">
        <p className="text-sm text-[#5A6080]">加载中...</p>
      </div>
    )
  }

  // Not activated — show activation screen
  if (!activated) {
    return <ActivationScreen onActivated={() => setActivated(true)} />
  }

  // Activated — normal app
  return (
    <BrowserRouter>
      <div className="flex h-screen">
        <Sidebar />
        <div className="flex-1 flex flex-col overflow-hidden">
          <Header />
          <main className="flex-1 overflow-y-auto p-6">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/training" element={<TrainingPlan />} />
              <Route path="/ai-coach" element={<AICoach />} />
              <Route path="/video" element={<VideoAnalysis />} />
              <Route path="/race" element={<RacePlanner />} />
              <Route path="/exercise" element={<ExerciseData />} />
              <Route path="/settings" element={<Settings />} />
            </Routes>
          </main>
        </div>
      </div>
    </BrowserRouter>
  )
}
