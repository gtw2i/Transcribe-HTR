import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  withCredentials: true,
  timeout: 120_000,
})

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      // Lazy import to avoid circular dep
      import('../store/appStore.js').then(({ useAppStore }) => {
        useAppStore.getState().setError('Your session has expired. Refresh the page to start a new session.', 'Session')
      })
    }
    return Promise.reject(err)
  }
)

export default api
