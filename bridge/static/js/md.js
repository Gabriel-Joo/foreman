// 패널 대화용 작은 마크다운(11-05) — CC 답에 나오는 것만: 제목 · 굵게 · 기울임 · 인라인 코드 · 코드블록(들여 쓴 것도) ·
// 표 · 목록(중첩 · 번호) · 인용 · 가로줄 · 링크(http/https만). 먼저 이스케이프하고 그다음 태그를 붙인다 — 원문 HTML은 통과시키지 않는다.
// DOM을 모른다(node --test로 시험).

const ESC = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ESC[c]);

export function inline(s) {
  const codes = [];
  let t = esc(s).replace(/`([^`\n]+)`/g, (_, c) => { codes.push(c); return `\u0000${codes.length - 1}\u0000`; });
  t = t
    .replace(/\[([^\]\n]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>')
    .replace(/\*\*([^*\n]+?)\*\*/g, '<b>$1</b>')
    .replace(/__([^_\n]+?)__/g, '<b>$1</b>')
    .replace(/(^|[^*\w])\*([^*\s][^*\n]*?)\*(?!\w)/g, '$1<i>$2</i>')
    .replace(/~~([^~\n]+)~~/g, '<s>$1</s>');
  return t.replace(/\u0000(\d+)\u0000/g, (_, i) => `<code class="md-i">${codes[+i]}</code>`);
}

const FENCE = /^(\s*)(```|~~~)\s*([\w+-]*)\s*$/;
const TABLE_SEP = /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)+\|?\s*$/;
const LIST = /^(\s*)([-*+]|\d{1,3}[.)])\s+(.*)$/;
const HEAD = /^(#{1,6})\s+(.+?)\s*#*\s*$/;
const HR = /^\s*([-*_])(\s*\1){2,}\s*$/;
const QUOTE = /^\s*>\s?(.*)$/;

function cells(line) {
  let t = line.trim();
  if (t.startsWith('|')) t = t.slice(1);
  if (t.endsWith('|') && !t.endsWith('\\|')) t = t.slice(0, -1);
  return t.split(/(?<!\\)\|/).map((c) => c.trim().replace(/\\\|/g, '|'));
}

function listHtml(items) {
  // items: [{indent, ordered, text}] — 들여쓰기로 중첩
  let html = '', stack = [];
  for (const it of items) {
    while (stack.length && it.indent < stack[stack.length - 1].indent) html += `</li></${stack.pop().tag}>`;
    const top = stack[stack.length - 1];
    if (!top || it.indent > top.indent) {
      const tag = it.ordered ? 'ol' : 'ul';
      html += `<${tag} class="md-list">`;
      stack.push({ indent: it.indent, tag });
    } else {
      html += '</li>';
    }
    html += `<li>${it.body}`;
  }
  while (stack.length) html += `</li></${stack.pop().tag}>`;
  return html;
}

export function renderMarkdown(src) {
  const lines = String(src || '').replace(/\r\n?/g, '\n').split('\n');
  const out = [];
  let para = [];
  const flush = () => { if (para.length) { out.push(`<p>${para.map(inline).join('<br>')}</p>`); para = []; } };
  for (let i = 0; i < lines.length; i++) {
    const ln = lines[i];
    let m;
    if ((m = FENCE.exec(ln))) {                                   // 코드블록 — 들여 쓴 것도(목록 안)
      flush();
      const ind = m[1].length, mark = m[2], body = [];
      i++;
      while (i < lines.length && !(lines[i].trim().startsWith(mark) && lines[i].trim().replace(new RegExp(`^${mark}`), '').trim() === '')) {
        body.push(lines[i].slice(Math.min(ind, lines[i].length - lines[i].trimStart().length)));
        i++;
      }
      out.push(`<pre class="md-code">${esc(body.join('\n'))}</pre>`);
      continue;
    }
    if (ln.includes('|') && i + 1 < lines.length && TABLE_SEP.test(lines[i + 1])) {   // 표
      flush();
      const head = cells(ln);
      const aligns = cells(lines[i + 1]).map((c) => (c.startsWith(':') && c.endsWith(':') ? 'center' : c.endsWith(':') ? 'right' : ''));
      i += 2;
      const rows = [];
      while (i < lines.length && lines[i].includes('|') && lines[i].trim()) { rows.push(cells(lines[i])); i++; }
      i--;
      const td = (tag, c, k) => `<${tag}${aligns[k] ? ` style="text-align:${aligns[k]}"` : ''}>${inline(c)}</${tag}>`;
      out.push(`<div class="md-tablewrap"><table class="md-table"><thead><tr>${head.map((c, k) => td('th', c, k)).join('')}</tr></thead><tbody>${
        rows.map((r) => `<tr>${head.map((_, k) => td('td', r[k] ?? '', k)).join('')}</tr>`).join('')}</tbody></table></div>`);
      continue;
    }
    if ((m = HEAD.exec(ln))) { flush(); out.push(`<div class="md-h md-h${m[1].length}">${inline(m[2])}</div>`); continue; }
    if (HR.test(ln) && !LIST.test(ln.replace(/^\s*[-*]\s*$/, ''))) { flush(); out.push('<hr class="md-hr">'); continue; }
    if (QUOTE.test(ln)) {
      flush();
      const q = [];
      while (i < lines.length && (m = QUOTE.exec(lines[i]))) { q.push(m[1]); i++; }
      i--;
      out.push(`<blockquote class="md-quote">${renderMarkdown(q.join('\n'))}</blockquote>`);
      continue;
    }
    if (LIST.test(ln)) {                                           // 목록 — 이어지는 들여 쓴 줄은 앞 항목에 붙인다
      flush();
      const items = [];
      while (i < lines.length) {
        const l = lines[i];
        if ((m = LIST.exec(l))) {
          items.push({ indent: m[1].length, ordered: /\d/.test(m[2]), body: inline(m[3]), start: m[2] });
          i++;
        } else if (l.trim() && /^\s+/.test(l) && items.length && !FENCE.test(l)) {
          items[items.length - 1].body += '<br>' + inline(l.trim());
          i++;
        } else if (FENCE.test(l) && items.length) {                // 목록 안 코드블록
          const fm = FENCE.exec(l), ind = fm[1].length, body = [];
          i++;
          while (i < lines.length && !FENCE.test(lines[i])) { body.push(lines[i].slice(Math.min(ind, lines[i].length - lines[i].trimStart().length))); i++; }
          i++;
          items[items.length - 1].body += `<pre class="md-code">${esc(body.join('\n'))}</pre>`;
        } else break;
      }
      i--;
      out.push(listHtml(items));
      continue;
    }
    if (!ln.trim()) { flush(); continue; }
    para.push(ln);
  }
  flush();
  return out.join('');
}
