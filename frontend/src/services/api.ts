import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
})

// Training
export const training = {
  listPlans: () => api.get('/training-plans'),
  getPlan: (id: number) => api.get(`/training-plans/${id}`),
  createPlan: (data: any) => api.post('/training-plans', data),
  updatePlan: (id: number, data: any) => api.put(`/training-plans/${id}`, data),
  deletePlan: (id: number) => api.delete(`/training-plans/${id}`),
  regeneratePlan: (id: number, baseWeeklyKm: number) =>
    api.post(`/training-plans/${id}/generate`, null, { params: { base_weekly_km: baseWeeklyKm } }),
  listSessions: (planId: number) => api.get(`/training-plans/${planId}/sessions`),
  toggleComplete: (sessionId: number) => api.put(`/sessions/${sessionId}/complete`),
  // Guardrail system
  listPhilosophies: () => api.get('/philosophies'),
  createFromQuestionnaire: (data: import('@/types').QuestionnaireInput) =>
    api.post('/training-plans/questionnaire', data),
  submitCheckpoint: (sessionId: number, data: import('@/types').CheckpointResult) =>
    api.post(`/sessions/${sessionId}/checkpoint`, data),
  getCheckpointAnalysis: (planId: number, week: number) =>
    api.get(`/training-plans/${planId}/checkpoint/${week}`),
  getCheckpointAIAnalysis: (planId: number, week: number, provider = 'deepseek', apiKey = '', model = '') =>
    api.post(`/training-plans/${planId}/checkpoint/${week}/ai`, { provider, api_key: apiKey, model }),
}

// Checkin
export const checkin = {
  list: () => api.get('/checkins'),
  create: (data: any) => api.post('/checkins', data),
  stats: () => api.get('/checkins/stats'),
}

// AI
export const ai = {
  chat: (message: string, image?: File, provider?: string, apiKey?: string, model?: string) => {
    const fd = new FormData()
    fd.append('message', message)
    if (image) fd.append('image', image)
    fd.append('provider', provider || localStorage.getItem('ai_provider') || 'deepseek')
    fd.append('api_key', apiKey || localStorage.getItem('ai_api_key') || '')
    fd.append('model', model || localStorage.getItem('ai_model') || '')
    return api.post('/ai/chat', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
}

// Video
export const video = {
  analyze: (file: File, viewAngle: import('@/types').ViewAngle = 'side') => {
    const fd = new FormData()
    fd.append('video', file)
    fd.append('view_angle', viewAngle)
    return api.post('/video/analyze', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  analyzeBarefoot: (file: File, shodKey: string, viewAngle: import('@/types').ViewAngle = 'side') => {
    const fd = new FormData()
    fd.append('video', file)
    fd.append('shod_video_key', shodKey)
    fd.append('view_angle', viewAngle)
    return api.post('/video/analyze/barefoot', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  listAnalyses: () => api.get('/video/analyses'),
}

// Race
export const race = {
  calculate: (data: {
    target_distance: string
    recent_5k_time?: string
    recent_10k_time?: string
    recent_half_time?: string
  }) => api.post('/race/calculate', data),
}

// Coros / Health Metrics
export const coros = {
  // OAuth
  getAuthUrl: (redirectUri?: string) =>
    api.get('/coros/auth/url', { params: redirectUri ? { redirect_uri: redirectUri } : {} }),
  authCallback: (code: string, state: string, redirectUri?: string) =>
    api.post('/coros/auth/callback', null, { params: { code, state, redirect_uri: redirectUri || '' } }),
  authStatus: () => api.get('/coros/auth/status'),
  disconnect: () => api.delete('/coros/auth/disconnect'),
  // Cookie
  saveCookie: (cookie: string) => api.post('/coros/save-cookie', { cookie }),
  testCookie: () => api.post('/coros/test-cookie'),
  autoLogin: (email: string, password: string, region?: string) =>
    api.post('/coros/auto-login', { email, password, region: region || 'cn' }),
  // Data
  sync: () => api.post('/coros/sync'),
  activities: (days?: number) => api.get('/coros/activities', { params: { days: days || 30 } }),
  plans: () => api.get('/coros/plans'),
  importPlan: (index?: number) => api.post('/coros/plans/import', null, { params: { plan_index: index || 0 } }),
  // Manual / CSV
  manual: (data: any) => api.post('/coros/manual', data),
  importCsv: (file: File) => {
    const fd = new FormData()
    fd.append('file', file)
    return api.post('/coros/import-csv', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  dashboard: () => api.get('/coros/dashboard'),
  fitnessAssessment: () => api.get('/coros/fitness-assessment'),
  // Credentials
  saveCredentials: (email: string, password: string, region: string) =>
    api.post('/coros/credentials', { email, password, region }),
  getCredentials: () => api.get('/coros/credentials'),
}

// Activities (public)
export const activities = {
  list: (days = 90) => api.get('/activities', { params: { days } }),
  detail: (id: number) => api.get(`/activities/${id}`),
  review: (id: number, provider = 'deepseek', apiKey = '', model = '') =>
    api.post(`/activities/${id}/review`, null, {
      params: { provider, api_key: apiKey, model: model || localStorage.getItem('ai_model') || '' },
    }),
}

// CSV Import
export const csvImport = {
  activities: (file: File) => {
    const fd = new FormData()
    fd.append('file', file)
    return api.post('/coros/import/activities', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  health: (file: File) => {
    const fd = new FormData()
    fd.append('file', file)
    return api.post('/coros/import/health', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
}

// Activation
export const activation = {
  status: () => api.get('/license/status'),
  activate: (code: string) => api.post(`/license/activate?code=${encodeURIComponent(code)}`),
  deactivate: () => api.post('/license/deactivate'),
}

export default api
