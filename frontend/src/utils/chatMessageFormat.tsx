import { toPlainAssistantDisplay } from './plainAssistantText'

/** 问答区助手气泡：纯文本，不渲染 Markdown */
export function AssistantMessageContent({ text }: { text: string }) {
  const plain = toPlainAssistantDisplay(text)
  return <div className="das-assistant-plain">{plain}</div>
}
