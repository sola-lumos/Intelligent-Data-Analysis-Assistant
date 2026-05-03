/**
 * 问答区展示用：将助手原始文案转为纯文本，弱化/移除常见 Markdown 语法符号，
 * 使界面中尽量不出现 **、*、`、#、```、列表符号、管道表格等。
 */

/** 解析 Markdown 表格行中的单元格（支持首尾 `|`） */
function parsePipeCells(line: string): string[] {
  const t = line.trim()
  if (!t.includes('|')) return []
  const cells = t.split('|').map((c) => c.trim())
  while (cells.length && cells[0] === '') cells.shift()
  while (cells.length && cells[cells.length - 1] === '') cells.pop()
  return cells
}

/** `|---|---|` 分隔行 */
function isMarkdownTableSeparatorRow(cells: string[]): boolean {
  if (cells.length < 2) return false
  return cells.every((c) => /^:?-{2,}:?$/.test(c.replace(/\s/g, '')))
}

/** 将连续管道行组成的 Markdown 表格转为中文短句（无 |、无表格线） */
function markdownTablesToPlainDescription(text: string): string {
  const lines = text.split('\n')
  const out: string[] = []
  let i = 0

  while (i < lines.length) {
    const line = lines[i]
    const cells0 = parsePipeCells(line)
    const looksLikeTableRow =
      cells0.length >= 2 && line.includes('|')

    if (looksLikeTableRow) {
      const block: string[] = []
      let j = i
      while (j < lines.length) {
        const L = lines[j]
        if (!L.trim()) break
        const c = parsePipeCells(L)
        if (c.length >= 2 && L.includes('|')) {
          block.push(L)
          j += 1
          continue
        }
        break
      }

      if (block.length >= 2) {
        const rowCells = block.map(parsePipeCells).filter((r) => r.length >= 2)
        const bodyRows = rowCells.filter((r) => !isMarkdownTableSeparatorRow(r))
        if (bodyRows.length >= 2) {
          const headers = bodyRows[0]
          const dataRows = bodyRows.slice(1)
          const sentences = dataRows.map((row) =>
            headers
              .map((h, idx) => `${h}为${row[idx] ?? ''}`)
              .join('，'),
          )
          out.push(sentences.join('；') + '。')
          i = j
          continue
        }
      }
    }

    out.push(line)
    i += 1
  }

  return out.join('\n')
}

export function toPlainAssistantDisplay(raw: string): string {
  if (!raw) return ''
  let s = raw.replace(/\r\n/g, '\n')

  // Markdown 表格 → 纯文字与数字描述（去掉 | 与表线）
  s = markdownTablesToPlainDescription(s)

  // 围栏代码块：保留内部文本，去掉 ```
  s = s.replace(/```[\w.-]*\r?\n?([\s\S]*?)```/g, (_, inner: string) => {
    const body = inner.replace(/\r\n/g, '\n').trimEnd()
    return body ? `\n${body}\n` : '\n'
  })

  // 行内 `code`
  s = s.replace(/`([^`\r\n]*)`/g, '$1')

  // 链接 / 图片
  s = s.replace(/!\[([^\]]*)\]\([^)]*\)/g, '$1')
  s = s.replace(/\[([^\]]+)\]\([^)]*\)/g, '$1')

  // 分隔线（独立成行）
  s = s.replace(/^\s*(?:[-*_]\s*){3,}\s*$/gm, '')

  // ATX 标题
  s = s.replace(/^#{1,6}\s+/gm, '')

  // 块引用
  s = s.replace(/^>\s?/gm, '')

  // 无序 / 有序列表行首（保留缩进，去掉 - * + 与 1. ）
  s = s.replace(/^(\s*)(?:[-*+]|[0-9]+[.)])\s+/gm, '$1')

  // 删除线
  s = s.replace(/~~([^~]+)~~/g, '$1')

  // 粗体、双下划线粗体（多轮以处理嵌套）
  for (let n = 0; n < 12; n++) {
    const next = s
      .replace(/\*\*([^*]+)\*\*/g, '$1')
      .replace(/__([^_\n]+)__/g, '$1')
    if (next === s) break
    s = next
  }

  // 单星号强调、单下划线强调
  s = s.replace(/\*([^*\n]+)\*/g, '$1')
  s = s.replace(/_([^_\n]+)_/g, '$1')

  // 用户要求：最终不得残留这些 Markdown 符号
  s = s.replace(/```/g, '')
  s = s.replace(/\*\*/g, '')
  s = s.replace(/\*/g, '')
  s = s.replace(/`/g, '')
  s = s.replace(/^#+\s*/gm, '')

  s = s.replace(/\n{3,}/g, '\n\n').trimEnd()
  return s
}
