import service, { requestWithRetry } from './index'

export const ingestWorldInfo = (data) => {
  return requestWithRetry(() => service.post('/api/world-info/ingest', data), 2, 800)
}

export const searchWorldInfo = (data) => {
  return requestWithRetry(() => service.post('/api/world-info/search', data), 2, 800)
}

export const listWorldInfoItems = (projectId, params = {}) => {
  return service.get(`/api/world-info/project/${projectId}/items`, { params })
}

export const getWorldInfoStats = (projectId) => {
  return service.get(`/api/world-info/project/${projectId}/stats`)
}
