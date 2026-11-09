// 폭 maxW에 맞춰 낱말(띄어쓰기) 단위로 줄을 나눈다. 낱말 하나가 폭보다 길면 글자로 자른다. measure(s) = 그 글의 폭.
// 11-09 한 방 볼 때의 경고 배너(office.js) — 자르지(…) 않고 줄을 바꾸고, 줄 수만큼 배너가 높아져 방이 내려간다
export function wrapWords(t, maxW, measure) {
  if (measure(t) <= maxW) return [t];
  const out = [];
  let cur = '';
  for (const w of t.split(/(?<= )|(?=[(（])/)) {           // 띄어쓰기 뒤 · 여는 괄호 앞("라운지(떠돌이)" → "라운지" / "(떠돌이)")
    if (cur && measure(cur + w) > maxW) { out.push(cur.trimEnd()); cur = ''; }
    cur += w;
    while (measure(cur) > maxW && cur.length > 1) {
      let n = cur.length - 1;
      while (n > 1 && measure(cur.slice(0, n)) > maxW) n--;
      out.push(cur.slice(0, n)); cur = cur.slice(n);
    }
  }
  if (cur.trim()) out.push(cur.trimEnd());
  return out;
}
