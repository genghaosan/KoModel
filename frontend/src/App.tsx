import { useState, useRef, useEffect, useCallback } from 'react'

interface Message {
  role: 'user' | 'ai'
  content: string
  references?: RefDoc[]
}

interface RefDoc {
  text: string
  source: string
}

interface SSEChunk {
  token?: string
  done?: boolean
  conversation_id?: string
  references?: RefDoc[]
}

function App() {
  const [messages, setMessages] = useState<Message[]>([
    { role: 'ai', content: '你好！我是你的本地知识库助手，请问有什么可以帮助你的？' },
  ])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const conversationId = useRef('')
  const chatRef = useRef<HTMLDivElement>(null)

  const scrollToBottom = useCallback(() => {
    requestAnimationFrame(() => {
      if (chatRef.current) {
        chatRef.current.scrollTop = chatRef.current.scrollHeight
      }
    })
  }, [])

  useEffect(() => {
    scrollToBottom()
  }, [messages, scrollToBottom])

  const sendQuestion = useCallback(async () => {
    const question = input.trim()
    if (!question || streaming) return

    setInput('')
    setStreaming(true)

    // Add user message
    setMessages((prev) => [...prev, { role: 'user', content: question }])

    // Add AI placeholder
    const aiMsg: Message = { role: 'ai', content: '' }
    setMessages((prev) => [...prev, aiMsg])

    try {
      const resp = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question,
          conversation_id: conversationId.current || undefined,
        }),
      })

      if (!resp.ok) {
        setMessages((prev) => [
          ...prev.slice(0, -1),
          { role: 'ai', content: '⚠️ 请求失败，请检查后端是否运行。' },
        ])
        setStreaming(false)
        return
      }

      const reader = resp.body!.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let fullAnswer = ''
      let references: RefDoc[] | null = null

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const jsonStr = line.slice(6).trim()
          if (!jsonStr) continue

          try {
            const data: SSEChunk = JSON.parse(jsonStr)

            if (data.conversation_id) {
              conversationId.current = data.conversation_id
            }

            if (data.references) {
              references = data.references
            }

            if (data.token) {
              fullAnswer += data.token
              // Update AI message with answer + cursor
              setMessages((prev) => {
                const updated = [...prev]
                const last = updated[updated.length - 1]
                if (last && last.role === 'ai') {
                  updated[updated.length - 1] = {
                    ...last,
                    content: fullAnswer,
                    references: references ?? undefined,
                  }
                }
                return updated
              })
            }

            if (data.done) {
              // Final update without cursor
              setMessages((prev) => {
                const updated = [...prev]
                const last = updated[updated.length - 1]
                if (last && last.role === 'ai') {
                  updated[updated.length - 1] = {
                    ...last,
                    content: fullAnswer,
                    references: references ?? undefined,
                  }
                }
                return updated
              })
            }
          } catch {
            // ignore parse errors
          }
        }
      }
    } catch {
      setMessages((prev) => [
        ...prev.slice(0, -1),
        { role: 'ai', content: '⚠️ 网络错误，请检查连接。' },
      ])
    }

    setStreaming(false)
  }, [input, streaming])

  const clearChat = useCallback(() => {
    conversationId.current = ''
    setMessages([{ role: 'ai', content: '你好！我是你的本地知识库助手，请问有什么可以帮助你的？' }])
  }, [])

  return (
    <div className="container">
      <div className="header">
        <span>本地知识库问答</span>
        <div className="header-actions">
          <button onClick={clearChat}>新对话</button>
        </div>
      </div>

      <div className="chat-box" ref={chatRef}>
        {messages.map((msg, i) => (
          <div key={i} className={`message ${msg.role}`}>
            <div className="bubble">
              {msg.role === 'ai' && i === messages.length - 1 && streaming && !msg.content ? (
                <span className="thinking">🤔思考中<span className="cursor-blink">|</span></span>
              ) : (
                <>
                  {msg.content}
                  {msg.role === 'ai' && i === messages.length - 1 && streaming && (
                    <span className="cursor-blink">|</span>
                  )}
                </>
              )}
            </div>
            {msg.role === 'ai' && msg.references && msg.references.length > 0 && (
              <details className="reference">
                <summary>参考了 {msg.references.length} 篇文档</summary>
                {msg.references.map((ref, j) => (
                  <blockquote key={j}>
                    【{ref.source}】{ref.text}
                  </blockquote>
                ))}
              </details>
            )}
          </div>
        ))}
      </div>

      <div className="input-area">
        <div className="input-row">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && sendQuestion()}
            placeholder="输入你的问题..."
            disabled={streaming}
          />
          <button onClick={sendQuestion} disabled={streaming}>
            {streaming ? '生成中...' : '发送'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default App
