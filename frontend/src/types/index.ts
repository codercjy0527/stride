// User
export interface User {
  id: number
  username: string
  email: string
}

// Training
export type SessionType = 'easy' | 'tempo' | 'interval' | 'long_run' | 'rest'
export type Intensity = 'low' | 'high'

export interface TrainingPlan {
  id: number
  user_id: number
  name: string
  weeks: number
  weekly_mileage_cap: number
  high_intensity_max: number
  low_intensity_max: number
  target_race: string
  target_date: string | null
  total_sessions: number
  completed_sessions: number
}

export interface TrainingSession {
  id: number
  plan_id: number
  week: number
  day_of_week: number
  session_type: SessionType
  intensity: Intensity
  duration_min: number
  distance_km: number
  description: string
  completed: boolean
}

export interface PlanCreate {
  name: string
  weeks: number
  weekly_mileage_cap: number
  high_intensity_max: number
  low_intensity_max: number
  target_race: string
  target_date?: string
  base_weekly_km: number
}

// Checkin
export interface Checkin {
  id: number
  date: string
  mood: number | null
  weight: number | null
  notes: string | null
}

export interface CheckinStats {
  total_days: number
  streak_days: number
  current_month_days: number
  today_checked: boolean
}

export interface CheckinCreate {
  mood?: number
  weight?: number
  notes?: string
}

// AI Chat
export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  imageUrl?: string
}

// Race
export interface RacePlan {
  distance: string
  predicted_time: string
  pace_per_km: string
  splits: { km: number; time: string }[]
}

// Coros
export interface FitnessMetric {
  id: number
  date: string
  sleep_hours: number | null
  sleep_quality: number | null
  resting_hr: number | null
  hrv: number | null
  fatigue_score: number | null
  recovery_score: number | null
  vo2max: number | null
  lthr: number | null
  ltsp: number | null
  stamina_level: number | null
  stamina_7d: number | null
  training_load_ratio: number | null
  daily_distance_km: number | null
  daily_duration_min: number | null
  deep_sleep_min: number | null
  light_sleep_min: number | null
  rem_sleep_min: number | null
  sleep_avg_hr: number | null
  sleep_min_hr: number | null
  sleep_max_hr: number | null
  tired_rate: number | null
  ati: number | null
  cti: number | null
}

// Activity
export interface ActivityRecord {
  id: number
  date: string
  sport_type: number
  sport_name: string | null
  location: string | null
  duration_sec: number | null
  duration_min: number | null
  distance_km: number | null
  avg_pace: string | null
  avg_hr: number | null
  max_hr: number | null
  calories: number | null
  training_load: number | null
  avg_power: number | null
  elevation_gain: number | null
  avg_cadence: number | null
  max_cadence: number | null
  avg_stride_length: number | null
  hr_zones: any[] | null
  pace_zones: any[] | null
  laps: any[] | null
  label_id: string | null
  user_id: number
}

export interface ReviewSection {
  title: string
  content: string
}

export interface ReviewComparison {
  recent_runs: {
    date: string
    distance_km: number | null
    avg_pace: string | null
    avg_hr: number | null
    duration_min: number | null
  }[]
  trend_distance: {
    current: number
    recent_avg: number
    diff: number
    direction: 'up' | 'down' | 'flat'
  } | null
  trend_hr: {
    current: number
    recent_avg: number
    diff: number
    direction: 'up' | 'down' | 'flat'
  } | null
  trend_pace: {
    current: string
    recent_avg: string
    diff_sec: number
    direction: 'up' | 'down' | 'flat'
  } | null
}

export interface ReviewResult {
  ok: boolean
  activity: ActivityRecord
  sections: ReviewSection[]
  comparison: ReviewComparison
  offline?: boolean
}
