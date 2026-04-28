export class SSEClient {
  constructor(url, options = {}) {
    this.url = url
    this.options = options
    this.eventSource = null
    this.reconnectAttempts = 0
    this.maxReconnects = options.maxReconnects || 3
    this.reconnectDelay = options.reconnectDelay || 1000
  }

  connect() {
    return new Promise((resolve, reject) => {
      this.eventSource = new EventSource(this.url)
      
      this.eventSource.onopen = () => {
        this.reconnectAttempts = 0
        if (this.options.onOpen) this.options.onOpen()
        resolve()
      }
      
      this.eventSource.onerror = (error) => {
        if (this.options.onError) this.options.onError(error)
        
        if (this.eventSource.readyState === EventSource.CLOSED) {
          if (this.reconnectAttempts < this.maxReconnects) {
            this.reconnectAttempts++
            setTimeout(() => this.connect(), this.reconnectDelay * this.reconnectAttempts)
          } else {
            reject(new Error('Max reconnection attempts reached'))
          }
        }
      }
      
      this.eventSource.onmessage = (event) => {
        if (this.options.onMessage) {
          try {
            const data = JSON.parse(event.data)
            this.options.onMessage(data, event)
          } catch (e) {
            this.options.onMessage(event.data, event)
          }
        }
      }
    })
  }

  addEventListener(type, callback) {
    if (this.eventSource) {
      this.eventSource.addEventListener(type, (event) => {
        try {
          const data = JSON.parse(event.data)
          callback(data, event)
        } catch (e) {
          callback(event.data, event)
        }
      })
    }
  }

  close() {
    if (this.eventSource) {
      this.eventSource.close()
      this.eventSource = null
    }
  }
}

export function createSSE(url, callbacks = {}) {
  const client = new SSEClient(url, callbacks)
  client.connect()
  return client
}
