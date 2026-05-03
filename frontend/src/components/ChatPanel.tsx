import { useCallback, useRef } from 'react'
import type { KeyboardEvent } from 'react'
import type { ChatThreadMessage } from '../types/session'
import { AssistantMessageContent } from '../utils/chatMessageFormat'

export type SampleQueryGroup = {
  title: string
  prompts: readonly string[]
}

type Props = {
  messages: ChatThreadMessage[]
  sending: boolean
  onSend: (text: string) => void
  /** Phase 4：API / SSE 用户可读错误 */
  errorBanner?: string | null
  /** 业务参考：分组查询案例 */
  sampleGroups?: readonly SampleQueryGroup[]
}

export function ChatPanel({
  messages,
  sending,
  onSend,
  errorBanner,
  sampleGroups,
}: Props) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const submit = useCallback(() => {
    const el = textareaRef.current
    if (!el || sending) return
    const t = el.value.trim()
    if (!t) return
    el.value = ''
    onSend(t)
  }, [onSend, sending])

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  const fillSample = useCallback((q: string) => {
    const el = textareaRef.current
    if (!el || sending) return
    el.value = q
    el.focus()
    el.selectionStart = el.selectionEnd = q.length
  }, [sending])

  const showSamples =
    Array.isArray(sampleGroups) &&
    sampleGroups.some((g) => g.prompts && g.prompts.length > 0)

  return (
    <section
      className={`das-chat-panel${errorBanner ? ' has-banner' : ''}`}
      aria-label="问答"
    >
      <header className="das-panel-head das-chat-head">
        <h2 className="das-panel-title">问答</h2>
      </header>
      {errorBanner ? (
        <div className="das-chat-error-banner" role="alert">
          {errorBanner}
        </div>
      ) : null}
      <div className="das-chat-messages">
        {messages.length === 0 ? (
          <p className="das-empty-chat">暂无消息，请输入数据分析问题。</p>
        ) : (
          messages.map((m) => (
            <div
              key={m.id}
              className={`das-bubble-wrap ${m.role === 'user' ? 'user' : 'ai'}`}
            >
              <div className={`das-bubble ${m.role}`}>
                <div className="das-bubble-content">
                  {m.role === 'assistant' ? (
                    <AssistantMessageContent text={m.content} />
                  ) : (
                    m.content
                  )}
                </div>
                {m.role === 'assistant' && m.sql_text && (
                  <details className="das-sql-block">
                    <summary>查看 SQL</summary>
                    <pre>{m.sql_text}</pre>
                  </details>
                )}
              </div>
            </div>
          ))
        )}
      </div>
      <footer className="das-chat-foot">
        {showSamples ? (
          <details className="das-chat-samples" open={messages.length === 0}>
            <summary className="das-chat-samples-sum">
              查询案例参考
              <span className="das-chat-samples-hint">
                （点击填入输入框，可修改后发送）
              </span>
            </summary>
            <div className="das-chat-samples-body">
              {(sampleGroups ?? []).map((g: SampleQueryGroup) => {
                const lines = g.prompts
                return !lines.length ? null : (
                  <div key={g.title} className="das-chat-sample-block">
                    <div className="das-chat-sample-cat">{g.title}</div>
                    <ul className="das-chat-sample-chips">
                      {lines.map((prompt: string) => (
                        <li key={prompt}>
                          <button
                            type="button"
                            className="das-chat-sample-chip"
                            disabled={sending}
                            title={prompt}
                            onClick={() => fillSample(prompt)}
                          >
                            {prompt}
                          </button>
                        </li>
                      ))}
                    </ul>
                  </div>
                )
              })}
            </div>
          </details>
        ) : null}
        <div className="das-chat-input-row">
          <textarea
            ref={textareaRef}
            className="das-textarea"
            placeholder="输入数据分析问题（指标、维度、时间范围等）… Enter 发送，Shift+Enter 换行"
            rows={2}
            disabled={sending}
            onKeyDown={onKeyDown}
          />
          <button
            type="button"
            className="das-send"
            onClick={submit}
            disabled={sending}
          >
            {sending ? '…' : '发送'}
          </button>
        </div>
      </footer>
    </section>
  )
}
