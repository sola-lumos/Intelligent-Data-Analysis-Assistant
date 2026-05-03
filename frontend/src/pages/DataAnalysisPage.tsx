import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import './DataAnalysisPage.css'
import { postChatApi } from '../api/chat'
import {
  createSessionApi,
  deleteSessionApi,
  listMessagesApi,
  listSessionsApi,
  patchSessionApi,
  postMessageInsightApi,
} from '../api/sessions'
import { postChatStream } from '../api/streamClient'
import { ChartPanel } from '../components/ChartPanel'
import { ChatPanel } from '../components/ChatPanel'
import { Sidebar } from '../components/Sidebar'
import { mockAnalysisReply } from '../mock/analysisMock'
import { SAMPLE_QUERY_GROUPS } from '../demo/mvpPrompts'
import type { MouseEvent as ReactMouseEvent } from 'react'
import type { ChatResponsePayload, MessageOutDTO } from '../types/api'
import type { TableData, VizSpec } from '../types/chart'
import type { ChatThreadMessage, SessionDTO } from '../types/session'
import { vizSpecFromAssistantMeta } from '../utils/assistantMeta'
import {
  assistantTablePayload,
  coerceTable,
} from '../utils/coerceTable'

const LS_SESSION = 'das_active_session_id'

function persistActiveSession(id: string): void {
  try {
    sessionStorage.setItem(LS_SESSION, id)
  } catch {
    /* ignore */
  }
}

/** Phase 4：默认 SSE；`VITE_USE_SSE_CHAT=false` 则仅用非流式 POST /chat */
const USE_CHAT_SSE = import.meta.env.VITE_USE_SSE_CHAT !== 'false'

function friendlyStreamError(payload?: { message?: string; code?: string }) {
  const msg = payload?.message?.trim()
  const code = payload?.code ?? ''
  if (code === 'not_found') {
    return '会话不存在或已删除，请在左侧切换或新建会话。'
  }
  if (code === 'service_unavailable') {
    return '服务端暂不可用（例如未配置大模型密钥），请检查后重试。'
  }
  if (code === 'internal_error') {
    return '服务端处理出错，请换一个问法或稍后重试。'
  }
  return msg ?? '发送中断，已尝试与服务端对齐消息列表。'
}

function localFallbackSession(): SessionDTO {
  const ts = Date.now()
  return {
    id: crypto.randomUUID().replace(/-/g, ''),
    title: '新会话',
    created_at: ts,
    updated_at: ts,
  }
}

function titleFromPrompt(text: string): string {
  const t = text.trim().slice(0, 18)
  return t.length > 0 ? t : '新会话'
}

function dtoToThreadMessage(row: MessageOutDTO): ChatThreadMessage {
  const meta = row.assistant_meta ?? null
  const metaRec =
    meta && typeof meta === 'object'
      ? (meta as Record<string, unknown>)
      : null
  const insightFromMeta =
    metaRec && typeof metaRec.viz_insight === 'string'
      ? metaRec.viz_insight
      : null
  return {
    id: row.id,
    session_id: row.session_id,
    role: row.role === 'assistant' ? 'assistant' : 'user',
    content: row.content,
    sql_text: row.sql_text ?? null,
    assistant_meta: meta,
    created_at: row.created_at,
    table:
      metaRec != null ? coerceTable(metaRec.table) : null,
    viz_insight: insightFromMeta,
  }
}

/** 将服务端末条助手消息的 `extras` 并入展示（落库含 meta.table/viz_spec；SSE 后再对齐尾部）。 */
function mergeAssistantTailPayload(
  msgs: ChatThreadMessage[],
  extras: {
    table?: TableData | null
    viz_spec?: VizSpec | null
    sql_text?: string | null
    viz_insight?: string | null
  },
): ChatThreadMessage[] {
  if (!msgs.length) return msgs
  const li = msgs.length - 1
  const last = msgs[li]
  if (last.role !== 'assistant') return msgs
  const mergedMetaAdds =
    extras.viz_spec != null ||
    extras.table != null ||
    (extras.viz_insight != null && extras.viz_insight !== '')

  let nextAssistantMeta = last.assistant_meta
  if (mergedMetaAdds) {
    nextAssistantMeta = {
      ...(last.assistant_meta ?? {}),
      ...(extras.viz_spec != null ? { viz_spec: extras.viz_spec } : {}),
      ...(extras.table != null ? { table: extras.table } : {}),
      ...(extras.viz_insight != null && extras.viz_insight !== ''
        ? { viz_insight: extras.viz_insight }
        : {}),
    }
  }

  const copy = msgs.slice()
  copy[li] = {
    ...last,
    sql_text: extras.sql_text ?? last.sql_text,
    table: extras.table ?? last.table ?? null,
    assistant_meta: nextAssistantMeta ?? last.assistant_meta,
    viz_insight:
      extras.viz_insight !== undefined ? extras.viz_insight : last.viz_insight,
  }
  return copy
}

function mergeAssistantFromRestResponse(
  msgs: ChatThreadMessage[],
  res: ChatResponsePayload,
): ChatThreadMessage[] {
  return mergeAssistantTailPayload(msgs, {
    table: res.table,
    viz_spec: res.viz_spec,
    sql_text: res.sql ?? null,
    viz_insight: res.viz_insight ?? null,
  })
}

const SPLIT_PX = 6
const SIDEBAR_MIN = 200
const SIDEBAR_MAX = 520
/** 中间可视化区最小宽度（与 CSS .das-chart-pane min-width 一致） */
const CHART_MIDDLE_MIN_WIDTH = 280
/** 右侧聊天列宽度范围 */
const CHAT_PANEL_MIN = 280
const CHAT_PANEL_MAX = 640

/** 侧栏收拢后，`main-col` 至少需容纳：中与右两栏 + 中间分割条 */
const MAIN_COL_MIN_TOTAL =
  CHART_MIDDLE_MIN_WIDTH + SPLIT_PX + CHAT_PANEL_MIN

export function DataAnalysisPage() {
  const [sessions, setSessions] = useState<SessionDTO[]>([])
  const [activeId, setActiveId] = useState<string | null>(null)
  const [messagesBySession, setMessagesBySession] = useState<
    Record<string, ChatThreadMessage[]>
  >({})
  const [sendingId, setSendingId] = useState<string | null>(null)
  /** Phase 4：用户可见的聊天/API 异常（SSE 或非流式） */
  const [chatError, setChatError] = useState<string | null>(null)
  /** 是否已成功连上后端会话 API（其一失败则离线 Mock） */
  const [apiReady, setApiReady] = useState(false)

  const mainColRef = useRef<HTMLDivElement>(null)
  const [sidebarWidth, setSidebarWidth] = useState(260)
  const [rightChatWidth, setRightChatWidth] = useState(() =>
    typeof window !== 'undefined'
      ? Math.round(
          Math.min(
            CHAT_PANEL_MAX,
            Math.max(CHAT_PANEL_MIN, window.innerWidth * 0.34),
          ),
        )
      : 380,
  )
  const [activeDrag, setActiveDrag] = useState<
    'sidebar' | 'chat-pane' | null
  >(null)
  const dragStartRef = useRef({
    clientX: 0,
    clientY: 0,
    sidebarW: 260,
    chatW: 380,
  })
  /** SSE 过程中累积，用于与 GET messages 对齐（表 / viz） */
  const sseTailRef = useRef<{
    sql: string | null
    table: TableData | null
    viz: VizSpec | null
  }>({
    sql: null,
    table: null,
    viz: null,
  })
  const [insightLoading, setInsightLoading] = useState(false)
  const streamErrPayloadRef = useRef<{
    message?: string
    code?: string
  } | null>(null)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const list = await listSessionsApi()
        if (cancelled) return
        setApiReady(true)
        const emptyInit: Record<string, ChatThreadMessage[]> = {}
        if (list.length === 0) {
          const s = await createSessionApi({})
          if (cancelled) return
          setSessions([s])
          setMessagesBySession({ [s.id]: [] })
          setActiveId(s.id)
          persistActiveSession(s.id)
          return
        }
        list.forEach((s) => {
          emptyInit[s.id] = []
        })
        let last: string | null = null
        try {
          last = sessionStorage.getItem(LS_SESSION)
        } catch {
          last = null
        }
        const pick =
          last && list.some((x) => x.id === last) ? last : list[0].id
        let initialMsgs: ChatThreadMessage[] = []
        try {
          initialMsgs = (await listMessagesApi(pick)).map(dtoToThreadMessage)
        } catch {
          initialMsgs = []
        }
        if (cancelled) return
        emptyInit[pick] = initialMsgs
        setSessions(list)
        setMessagesBySession(emptyInit)
        setActiveId(pick)
        persistActiveSession(pick)
      } catch {
        if (cancelled) return
        setApiReady(false)
        const s = localFallbackSession()
        setSessions([s])
        setActiveId(s.id)
        setMessagesBySession({ [s.id]: [] })
        persistActiveSession(s.id)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  const messages = useMemo(
    () => messagesBySession[activeId ?? ''] ?? [],
    [messagesBySession, activeId],
  )

  const vizFromMessages = useMemo(() => {
    let spec: VizSpec | null = null
    let table: TableData | null = null
    let insight: string | null = null
    let assistantMessageId: string | null = null
    for (let i = messages.length - 1; i >= 0; i--) {
      const m = messages[i]
      if (m.role !== 'assistant') continue
      const fromMeta = vizSpecFromAssistantMeta(m.assistant_meta ?? undefined)
      const tbl = assistantTablePayload(m)
      const hasRows = !!(tbl?.rows?.length)
      if (!(fromMeta != null || hasRows || tbl !== null)) continue
      spec = fromMeta ?? { chart_type: 'table' }
      table = tbl
      assistantMessageId = m.id
      {
        const meta = m.assistant_meta as Record<string, unknown> | undefined
        const fromMetaInsight =
          meta && typeof meta.viz_insight === 'string' ? meta.viz_insight : null
        insight =
          m.viz_insight != null && m.viz_insight !== ''
            ? m.viz_insight
            : fromMetaInsight
      }
      break
    }
    return { spec, table, insight, assistantMessageId }
  }, [messages])

  const requestVizInsight = useCallback(async () => {
    const sid = activeId
    const mid = vizFromMessages.assistantMessageId
    if (!sid || !mid || !apiReady) return
    setInsightLoading(true)
    setChatError(null)
    try {
      const { viz_insight: text } = await postMessageInsightApi(sid, mid)
      setMessagesBySession((prev) => ({
        ...prev,
        [sid]: (prev[sid] ?? []).map((m) =>
          m.id === mid
            ? {
                ...m,
                viz_insight: text,
                assistant_meta: {
                  ...(m.assistant_meta ?? {}),
                  viz_insight: text,
                },
              }
            : m,
        ),
      }))
    } catch (e) {
      const msg =
        e instanceof Error ? e.message : '生成数据洞察失败，请稍后重试'
      setChatError(msg)
    } finally {
      setInsightLoading(false)
    }
  }, [activeId, apiReady, vizFromMessages.assistantMessageId])

  useEffect(() => {
    if (!activeDrag) return
    const onMove = (e: MouseEvent) => {
      if (activeDrag === 'sidebar') {
        const dx = e.clientX - dragStartRef.current.clientX
        const sw = dragStartRef.current.sidebarW + dx
        const reserve =
          SPLIT_PX + MAIN_COL_MIN_TOTAL
        const maxSidebar = Math.min(
          SIDEBAR_MAX,
          Math.max(SIDEBAR_MIN, window.innerWidth - reserve),
        )
        setSidebarWidth(Math.round(Math.min(Math.max(sw, SIDEBAR_MIN), maxSidebar)))
        return
      }
      if (activeDrag === 'chat-pane') {
        const mainEl = mainColRef.current
        if (!mainEl) return
        const dx = e.clientX - dragStartRef.current.clientX
        const startW = dragStartRef.current.chatW
        const mainW = mainEl.getBoundingClientRect().width
        const maxChat = Math.min(
          CHAT_PANEL_MAX,
          mainW - SPLIT_PX - CHART_MIDDLE_MIN_WIDTH,
        )
        const minChat = CHAT_PANEL_MIN
        const next = Math.round(startW - dx)
        setRightChatWidth(Math.min(Math.max(next, minChat), maxChat))
      }
    }
    const onUp = () => setActiveDrag(null)
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'
    return () => {
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
    }
  }, [activeDrag])

  useEffect(() => {
    const clamp = () => {
      const reserve = SPLIT_PX + MAIN_COL_MIN_TOTAL
      const maxSidebar = Math.min(
        SIDEBAR_MAX,
        Math.max(SIDEBAR_MIN, window.innerWidth - reserve),
      )
      setSidebarWidth((w) =>
        Math.round(Math.min(Math.max(w, SIDEBAR_MIN), maxSidebar)),
      )
      const mainEl = mainColRef.current
      if (!mainEl) return
      const mainW = mainEl.getBoundingClientRect().width
      const maxChat = Math.min(
        CHAT_PANEL_MAX,
        Math.max(
          CHAT_PANEL_MIN,
          mainW - SPLIT_PX - CHART_MIDDLE_MIN_WIDTH,
        ),
      )
      setRightChatWidth((cw) =>
        Math.round(Math.min(Math.max(cw, CHAT_PANEL_MIN), maxChat)),
      )
    }
    window.addEventListener('resize', clamp)
    clamp()
    return () => window.removeEventListener('resize', clamp)
  }, [])

  const onSidebarSplitDown = useCallback(
    (e: ReactMouseEvent<HTMLButtonElement>) => {
      e.preventDefault()
      dragStartRef.current = {
        clientX: e.clientX,
        clientY: e.clientY,
        sidebarW: sidebarWidth,
        chatW: rightChatWidth,
      }
      setActiveDrag('sidebar')
    },
    [sidebarWidth, rightChatWidth],
  )

  const onMidChatSplitDown = useCallback(
    (e: ReactMouseEvent<HTMLButtonElement>) => {
      e.preventDefault()
      dragStartRef.current = {
        clientX: e.clientX,
        clientY: e.clientY,
        sidebarW: sidebarWidth,
        chatW: rightChatWidth,
      }
      setActiveDrag('chat-pane')
    },
    [sidebarWidth, rightChatWidth],
  )

  const onSelect = useCallback(
    async (id: string) => {
      setActiveId(id)
      persistActiveSession(id)
      if (!apiReady) return
      try {
        const rows = await listMessagesApi(id)
        setMessagesBySession((prev) => ({
          ...prev,
          [id]: rows.map(dtoToThreadMessage),
        }))
      } catch {
        /* 保留内存缓存 */
      }
    },
    [apiReady],
  )

  const onNew = useCallback(async () => {
    if (apiReady) {
      try {
        const s = await createSessionApi({})
        setSessions((prev) => [s, ...prev])
        setMessagesBySession((prev) => ({ ...prev, [s.id]: [] }))
        setActiveId(s.id)
        persistActiveSession(s.id)
        return
      } catch {
        /* 走本地 seed */
      }
    }
    const s = localFallbackSession()
    setSessions((prev) => [s, ...prev])
    setMessagesBySession((prev) => ({ ...prev, [s.id]: [] }))
    setActiveId(s.id)
    persistActiveSession(s.id)
  }, [apiReady])

  const onDelete = useCallback(
    async (id: string) => {
      if (apiReady) {
        try {
          await deleteSessionApi(id)
        } catch {
          /* 仍移除本地视图 */
        }
      }
      setMessagesBySession((prev) => {
        const next = { ...prev }
        delete next[id]
        return next
      })
      setSessions((prev) => {
        const nextSessions = prev.filter((s) => s.id !== id)
        setActiveId((cur) => {
          if (cur !== id) return cur
          const picked = nextSessions[0]?.id ?? null
          if (picked) persistActiveSession(picked)
          else {
            try {
              sessionStorage.removeItem(LS_SESSION)
            } catch {
              /* ignore */
            }
          }
          return picked
        })
        return nextSessions
      })
    },
    [apiReady],
  )

  const onRenameSession = useCallback(
    async (id: string, title: string) => {
      const trimmed = title.trim().slice(0, 200)
      if (!trimmed) return
      const now = Date.now()
      if (apiReady) {
        try {
          const row = await patchSessionApi(id, { title: trimmed })
          setSessions((prev) => prev.map((x) => (x.id === row.id ? row : x)))
        } catch {
          throw new Error('rename_failed')
        }
      } else {
        setSessions((prev) =>
          prev.map((s) =>
            s.id === id ? { ...s, title: trimmed, updated_at: now } : s,
          ),
        )
      }
    },
    [apiReady],
  )

  const pushMockAssistant = useCallback((sid: string, text: string) => {
    const reply = mockAnalysisReply(text)
    const assistantMsg: ChatThreadMessage = {
      id: crypto.randomUUID().replace(/-/g, ''),
      session_id: sid,
      role: 'assistant',
      content: reply.answer,
      sql_text: reply.sql,
      assistant_meta: reply.viz_spec ? { viz_spec: reply.viz_spec } : null,
      created_at: Date.now(),
      table: reply.table,
      viz_insight: reply.viz_insight,
    }
    setMessagesBySession((prev) => ({
      ...prev,
      [sid]: [...(prev[sid] ?? []), assistantMsg],
    }))
  }, [])

  const finalizeServerChat = useCallback(
    async (
      originalSessionId: string,
      resolvedSessionId: string,
      promptText: string,
      mapper: (msgs: ChatThreadMessage[]) => ChatThreadMessage[],
    ) => {
      let mapped = (await listMessagesApi(resolvedSessionId)).map(
        dtoToThreadMessage,
      )
      mapped = mapper(mapped)
      setMessagesBySession((prev) => {
        const next = { ...prev }
        if (resolvedSessionId !== originalSessionId) {
          delete next[originalSessionId]
        }
        next[resolvedSessionId] = mapped
        return next
      })
      try {
        const fresh = await listSessionsApi()
        setSessions(fresh)
      } catch {
        setSessions((prev) =>
          prev.map((s) =>
            s.id === resolvedSessionId
              ? { ...s, updated_at: Date.now() }
              : s,
          ),
        )
      }
      setActiveId(resolvedSessionId)
      persistActiveSession(resolvedSessionId)

      const titled = titleFromPrompt(promptText)
      if (titled !== '新会话') {
        try {
          const row = await patchSessionApi(resolvedSessionId, {
            title: titled,
          })
          setSessions((prev) =>
            prev.map((x) => (x.id === row.id ? row : x)),
          )
        } catch {
          /* 标题 PATCH 可选 */
        }
      }
    },
    [],
  )

  const onSend = useCallback(
    async (text: string) => {
      if (!activeId) return
      const sid = activeId
      const now = Date.now()
      const userLineId = crypto.randomUUID().replace(/-/g, '')
      const streamAsstId = `sse-${userLineId}`

      streamErrPayloadRef.current = null
      setChatError(null)

      /** 离线 Mock：仅占位用户消息 */
      if (!apiReady) {
        setMessagesBySession((prev) => ({
          ...prev,
          [sid]: [
            ...(prev[sid] ?? []),
            {
              id: userLineId,
              session_id: sid,
              role: 'user',
              content: text,
              created_at: now,
            },
          ],
        }))
        setSessions((prev) =>
          prev.map((s) =>
            s.id === sid
              ? {
                  ...s,
                  title:
                    s.title === '新会话' ? titleFromPrompt(text) : s.title,
                  updated_at: now,
                }
              : s,
          ),
        )
        setSendingId(sid)
        window.setTimeout(() => {
          pushMockAssistant(sid, text)
          setSendingId((cur) => (cur === sid ? null : cur))
        }, 380)
        return
      }

      const showStreamBubble = USE_CHAT_SSE
      const userMsg: ChatThreadMessage = {
        id: userLineId,
        session_id: sid,
        role: 'user',
        content: text,
        created_at: now,
      }
      const streamingTail: ChatThreadMessage | null = showStreamBubble
        ? {
            id: streamAsstId,
            session_id: sid,
            role: 'assistant',
            content: '',
            created_at: now,
          }
        : null

      setMessagesBySession((prev) => ({
        ...prev,
        [sid]: [
          ...(prev[sid] ?? []),
          userMsg,
          ...(streamingTail ? [streamingTail] : []),
        ],
      }))
      setSessions((prev) =>
        prev.map((s) =>
          s.id === sid
            ? {
                ...s,
                title:
                  s.title === '新会话' ? titleFromPrompt(text) : s.title,
                updated_at: now,
              }
            : s,
        ),
      )
      setSendingId(sid)

      const stripStreamingRow = (): void => {
        setMessagesBySession((prev) => ({
          ...prev,
          [sid]: (prev[sid] ?? []).filter((m) => !m.id.startsWith('sse-')),
        }))
      }

      try {
        if (!showStreamBubble) {
          const res = await postChatApi({
            session_id: sid,
            message: text,
          })
          await finalizeServerChat(sid, res.session_id, text, (mapped) =>
            mergeAssistantFromRestResponse(mapped, res),
          )
          return
        }

        sseTailRef.current = { sql: null, table: null, viz: null }
        let resolvedSid = sid

        await postChatStream(
          { session_id: sid, message: text },
          {
            onAnswer: ({ content }) => {
              const chunk = typeof content === 'string' ? content : ''
              if (!chunk) return
              setMessagesBySession((prev) => ({
                ...prev,
                [sid]: (prev[sid] ?? []).map((m) =>
                  m.id === streamAsstId
                    ? { ...m, content: `${m.content ?? ''}${chunk}` }
                    : m,
                ),
              }))
            },
            onSql: ({ sql }) => {
              const s = typeof sql === 'string' ? sql : null
              sseTailRef.current.sql = s
              setMessagesBySession((prev) => ({
                ...prev,
                [sid]: (prev[sid] ?? []).map((m) =>
                  m.id === streamAsstId ? { ...m, sql_text: s } : m,
                ),
              }))
            },
            onTable: (tbl) => {
              sseTailRef.current.table = tbl
              setMessagesBySession((prev) => ({
                ...prev,
                [sid]: (prev[sid] ?? []).map((m) =>
                  m.id === streamAsstId ? { ...m, table: tbl } : m,
                ),
              }))
            },
            onChart: ({ viz_spec }) => {
              if (!viz_spec) return
              sseTailRef.current.viz = viz_spec
              setMessagesBySession((prev) => ({
                ...prev,
                [sid]: (prev[sid] ?? []).map((m) =>
                  m.id === streamAsstId
                    ? {
                        ...m,
                        assistant_meta: {
                          ...(m.assistant_meta ?? {}),
                          viz_spec,
                        },
                      }
                    : m,
                ),
              }))
            },
            onDone: (p) => {
              resolvedSid = p.session_id
            },
            onError: (p) => {
              streamErrPayloadRef.current = p ?? null
            },
          },
        )

        const target = resolvedSid
        const tail = sseTailRef.current
        await finalizeServerChat(sid, target, text, (mapped) =>
          mergeAssistantTailPayload(mapped, {
            sql_text: tail.sql,
            table: tail.table,
            viz_spec: tail.viz,
          }),
        )
      } catch {
        setChatError(
          friendlyStreamError(streamErrPayloadRef.current ?? undefined),
        )
        stripStreamingRow()
        try {
          const rows = await listMessagesApi(sid)
          setMessagesBySession((prev) => ({
            ...prev,
            [sid]: rows.map(dtoToThreadMessage),
          }))
        } catch {
          /* 保持已去掉占位气泡后的内存状态 */
        }
      } finally {
        streamErrPayloadRef.current = null
        setSendingId((cur) => (cur === sid ? null : cur))
      }
    },
    [activeId, apiReady, finalizeServerChat, pushMockAssistant],
  )

  const sending = Boolean(activeId && sendingId === activeId)

  return (
    <div className="das-root">
      <div className="das-sidebar-col" style={{ width: sidebarWidth }}>
        <Sidebar
          sessions={sessions}
          activeId={activeId}
          onSelect={(id) => void onSelect(id)}
          onNew={() => void onNew()}
          onDelete={(id) => void onDelete(id)}
          onRename={(id, title) => void onRenameSession(id, title)}
        />
      </div>
      <button
        type="button"
        className={`das-split das-split-col${activeDrag === 'sidebar' ? ' is-active' : ''}`}
        aria-label="拖动调整侧栏宽度"
        onMouseDown={onSidebarSplitDown}
      />
      <div className="das-main-col" ref={mainColRef}>
        <div className="das-chart-pane">
          <div className="das-chart-shell">
            <ChartPanel
              analysisPending={sending}
              viz_spec={vizFromMessages.spec}
              table={vizFromMessages.table}
              viz_insight={vizFromMessages.insight}
              insightLoading={insightLoading}
              onRequestInsight={
                apiReady && activeId && vizFromMessages.assistantMessageId
                  ? requestVizInsight
                  : undefined
              }
            />
          </div>
        </div>
        <button
          type="button"
          className={`das-split das-split-mid-chat${activeDrag === 'chat-pane' ? ' is-active' : ''}`}
          aria-label="拖动调整可视化与右侧聊天宽度"
          onMouseDown={onMidChatSplitDown}
        />
        <div className="das-chat-pane-col" style={{ width: rightChatWidth }}>
          <div className="das-chat-shell">
            <ChatPanel
              messages={messages}
              sending={sending}
              errorBanner={chatError}
              sampleGroups={SAMPLE_QUERY_GROUPS}
              onSend={onSend}
            />
          </div>
        </div>
      </div>
    </div>
  )
}
