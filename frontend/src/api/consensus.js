import service from './index'

export const startConsensusTask = (data) => {
  return service.post('/api/consensus/task/start', data)
}

export const getDefaultConsensusCatalog = () => {
  return service.get('/api/consensus/catalog/default')
}

export const getCurrentConsensusTask = (simulationId) => {
  return service.get('/api/consensus/task/current', {
    params: simulationId ? { simulation_id: simulationId } : {}
  })
}

export const getConsensusTask = (taskUid) => {
  return service.get(`/api/consensus/task/${taskUid}`)
}

export const getConsensusTaskAgents = (taskUid) => {
  return service.get(`/api/consensus/task/${taskUid}/agents`)
}

export const stopConsensusTask = (data) => {
  return service.post('/api/consensus/task/stop', data)
}

export const listConsensusTasks = (simulationId) => {
  return service.get('/api/consensus/tasks', {
    params: simulationId ? { simulation_id: simulationId } : {}
  })
}
