import { Fragment } from 'react'

type InlineToken =
  | { type: 'text'; text: string }
  | { type: 'bold'; text: string }
  | { type: 'code'; text: string }

type Block =
  | { type: 'heading'; level: number; text: string }
  | { type: 'paragraph'; children: InlineToken[] }
  | { type: 'list'; items: InlineToken[][]; ordered: boolean }
  | { type: 'divider' }

function parseInline(text: string): InlineToken[] {
  const tokens: InlineToken[] = []
  let i = 0
  let current = ''

  while (i < text.length) {
    if (text[i] === '*' && text[i + 1] === '*' && text[i + 2] !== ' ') {
      // Bold: **text**
      if (current) { tokens.push({ type: 'text', text: current }); current = '' }
      const end = text.indexOf('**', i + 2)
      if (end !== -1) {
        tokens.push({ type: 'bold', text: text.slice(i + 2, end) })
        i = end + 2
      } else {
        current += '**'
        i += 2
      }
      continue
    }
    if (text[i] === '`') {
      if (current) { tokens.push({ type: 'text', text: current }); current = '' }
      const end = text.indexOf('`', i + 1)
      if (end !== -1) {
        tokens.push({ type: 'code', text: text.slice(i + 1, end) })
        i = end + 1
      } else {
        current += '`'
        i += 1
      }
      continue
    }
    current += text[i]
    i++
  }
  if (current) tokens.push({ type: 'text', text: current })
  return tokens
}

export default function Markdown({ content }: { content: string }) {
  if (!content) return null

  const lines = content.split('\n')
  const blocks: Block[] = []
  let i = 0

  while (i < lines.length) {
    const line = lines[i]

    // Divider
    if (/^---+$/.test(line.trim())) {
      blocks.push({ type: 'divider' })
      i++
      continue
    }

    // Heading
    const headingMatch = line.match(/^(#{1,3})\s+(.+)/)
    if (headingMatch) {
      blocks.push({ type: 'heading', level: headingMatch[1].length, text: headingMatch[2] })
      i++
      continue
    }

    // Unordered list
    if (/^[\-\*]\s+/.test(line)) {
      const items: InlineToken[][] = []
      while (i < lines.length && /^[\-\*]\s+/.test(lines[i])) {
        items.push(parseInline(lines[i].replace(/^[\-\*]\s+/, '')))
        i++
      }
      blocks.push({ type: 'list', items, ordered: false })
      continue
    }

    // Ordered list
    if (/^\d+[\.\)]\s+/.test(line)) {
      const items: InlineToken[][] = []
      while (i < lines.length && /^\d+[\.\)]\s+/.test(lines[i])) {
        items.push(parseInline(lines[i].replace(/^\d+[\.\)]\s+/, '')))
        i++
      }
      blocks.push({ type: 'list', items, ordered: true })
      continue
    }

    // Paragraph (consume until blank line or next block element)
    if (line.trim()) {
      const paraLines: string[] = []
      while (i < lines.length && lines[i].trim() &&
             !/^(#{1,3})\s+/.test(lines[i]) &&
             !/^[\-\*]\s+/.test(lines[i]) &&
             !/^\d+[\.\)]\s+/.test(lines[i]) &&
             !/^---+$/.test(lines[i].trim())) {
        paraLines.push(lines[i])
        i++
      }
      blocks.push({ type: 'paragraph', children: parseInline(paraLines.join(' ')) })
      continue
    }

    i++
  }

  return (
    <div className="space-y-3">
      {blocks.map((block, idx) => {
        if (block.type === 'divider') {
          return <hr key={idx} className="border-[rgba(255,255,255,0.06)] my-2" />
        }
        if (block.type === 'heading') {
          const cls = block.level === 1
            ? 'text-base font-bold text-[#E8ECF2] mb-1'
            : block.level === 2
            ? 'text-sm font-bold text-[#E8ECF2] mt-3 mb-1 flex items-center gap-1.5'
            : 'text-[13px] font-semibold text-[#C8CCD8] mt-2 mb-1'
          return <h3 key={idx} className={cls}><RenderInline tokens={parseInline(block.text)} /></h3>
        }
        if (block.type === 'paragraph') {
          return <p key={idx} className="text-sm leading-relaxed text-[#C8CCD8]"><RenderInline tokens={block.children} /></p>
        }
        if (block.type === 'list') {
          const Tag = block.ordered ? 'ol' : 'ul'
          return (
            <Tag key={idx} className={block.ordered ? 'list-decimal list-inside space-y-1' : 'space-y-1 pl-0'}>
              {block.items.map((item, j) => (
                <li key={j} className="text-sm text-[#C8CCD8] flex items-start gap-2">
                  <span className="text-[#5A6080] mt-0.5 shrink-0">
                    {block.ordered ? `${j + 1}.` : '•'}
                  </span>
                  <span className="leading-relaxed"><RenderInline tokens={item} /></span>
                </li>
              ))}
            </Tag>
          )
        }
        return null
      })}
    </div>
  )
}

function RenderInline({ tokens }: { tokens: InlineToken[] }) {
  return (
    <>
      {tokens.map((t, i) => {
        if (t.type === 'bold') return <strong key={i} className="font-bold text-[#E8ECF2]">{t.text}</strong>
        if (t.type === 'code') return <code key={i} className="px-1 py-0.5 bg-[rgba(255,255,255,0.06)] rounded text-[13px] font-mono text-red-300">{t.text}</code>
        return <Fragment key={i}>{t.text}</Fragment>
      })}
    </>
  )
}
