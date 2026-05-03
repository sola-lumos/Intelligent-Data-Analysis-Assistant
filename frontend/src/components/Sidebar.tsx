import { useCallback, useMemo, useRef, useState, type KeyboardEvent } from 'react'
import type { SessionDTO } from '../types/session'

const TITLE_MAX = 200

type Props = {
  sessions: SessionDTO[]
  activeId: string | null
  onSelect: (id: string) => void
  onNew: () => void
  onDelete: (id: string) => void
  onRename: (id: string, title: string) => void | Promise<void>
}

export function Sidebar({
  sessions,
  activeId,
  onSelect,
  onNew,
  onDelete,
  onRename,
}: Props) {
  const sorted = useMemo(
    () => [...sessions].sort((a, b) => b.updated_at - a.updated_at),
    [sessions],
  )

  const sessionIds = useMemo(
    () => new Set(sorted.map((s) => s.id)),
    [sorted],
  )

  const [editingId, setEditingId] = useState<string | null>(null)
  const [draftTitle, setDraftTitle] = useState('')
  const finalizePending = useRef(false)

  if (editingId !== null && !sessionIds.has(editingId)) {
    setEditingId(null)
    setDraftTitle('')
  }

  const beginEdit = useCallback((s: SessionDTO) => {
    setEditingId(s.id)
    setDraftTitle(s.title.slice(0, TITLE_MAX))
  }, [])

  const cancelEdit = useCallback(() => {
    setEditingId(null)
    setDraftTitle('')
  }, [])

  const finalizeEdit = useCallback(async () => {
    if (!editingId || finalizePending.current) return
    const trimmed = draftTitle.trim()
    if (!trimmed) {
      cancelEdit()
      return
    }
    const current = sessions.find((s) => s.id === editingId)?.title
    if (trimmed === current) {
      cancelEdit()
      return
    }
    finalizePending.current = true
    try {
      await onRename(editingId, trimmed.slice(0, TITLE_MAX))
      cancelEdit()
    } catch {
      /* 父级在 PATCH 失败时抛错，保留输入便于重试 */
    } finally {
      finalizePending.current = false
    }
  }, [editingId, draftTitle, sessions, onRename, cancelEdit])

  const onEditKeyDown = useCallback(
    (e: KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        cancelEdit()
      }
    },
    [cancelEdit],
  )

  return (
    <aside className="das-sidebar">
      <div className="das-sidebar-head">
        <h1 className="das-brand">智能数据分析助手</h1>
        <button type="button" className="das-btn-new" onClick={onNew}>
          ＋ 新会话
        </button>
      </div>
      <nav className="das-session-nav" aria-label="会话列表">
        {sorted.length === 0 ? (
          <p className="das-empty">暂无会话，点击新建开始</p>
        ) : (
          <ul className="das-session-list">
            {sorted.map((s) => {
              const isActive = s.id === activeId
              const isEditing = editingId === s.id
              return (
                <li
                  key={s.id}
                  className={'das-session-row' + (isActive ? ' is-active' : '')}
                >
                  {isEditing ? (
                    <form
                      className="das-session-edit-form"
                      onSubmit={(e) => {
                        e.preventDefault()
                        void finalizeEdit()
                      }}
                    >
                      <input
                        className="das-session-input"
                        value={draftTitle}
                        maxLength={TITLE_MAX}
                        aria-label="会话标题"
                        autoFocus
                        onFocus={(e) => e.target.select()}
                        onChange={(e) =>
                          setDraftTitle(e.target.value.slice(0, TITLE_MAX))
                        }
                        onBlur={() => void finalizeEdit()}
                        onKeyDown={onEditKeyDown}
                      />
                    </form>
                  ) : (
                    <button
                      type="button"
                      className="das-session-item"
                      onClick={() => onSelect(s.id)}
                      onDoubleClick={(e) => {
                        e.preventDefault()
                        beginEdit(s)
                      }}
                    >
                      <span className="das-session-title">{s.title}</span>
                    </button>
                  )}
                  {!isEditing ? (
                    <div className="das-session-actions">
                      <button
                        type="button"
                        className="das-session-rename"
                        title="重命名"
                        aria-label="重命名会话"
                        onClick={(e) => {
                          e.stopPropagation()
                          beginEdit(s)
                        }}
                      >
                        ✎
                      </button>
                      <button
                        type="button"
                        className="das-session-del"
                        title="删除"
                        aria-label="删除会话"
                        onClick={(e) => {
                          e.stopPropagation()
                          onDelete(s.id)
                        }}
                      >
                        ×
                      </button>
                    </div>
                  ) : null}
                </li>
              )
            })}
          </ul>
        )}
      </nav>
    </aside>
  )
}
