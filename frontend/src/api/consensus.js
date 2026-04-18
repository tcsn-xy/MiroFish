import service, { requestWithRetry } from './index'

export const startConsensusTask = (data) => {
  return requestWithRetry(() => service.post('/api/consensus/task/start', data), 2, 800)
}

export const getCurrentConsensusTask = () => {
  return service.get('/api/consensus/task/current')
}

export const getCurrentConsensusAgents = () => {
  return service.get('/api/consensus/task/current/agents')
}

export const stopConsensusTask = () => {
  return service.post('/api/consensus/task/stop')
}
