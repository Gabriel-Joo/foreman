// 패널 마크다운(11-05) — 표 · 목록 · 들여 쓴 코드블록 · 이스케이프
import test from 'node:test';
import assert from 'node:assert/strict';
import { renderMarkdown as md, inline } from '../../bridge/static/js/md.js';

test('표 — 정렬 · 셀 안 굵게 · 칸 모자란 줄', () => {
  const h = md('| 단계 | 결과 |\n|---|---:|\n| **빌드** | ✓ |\n| 배포 |');
  assert.ok(h.includes('<table class="md-table">') && h.includes('<th>단계</th>'));
  assert.ok(h.includes('<td><b>빌드</b></td>') && h.includes('style="text-align:right"'));
  assert.equal((h.match(/<tr>/g) || []).length, 3);
});

test('목록 — 중첩 · 번호 · 이어지는 줄', () => {
  const h = md('- 하나\n  - 안쪽\n- 둘\n  이어짐\n\n1. 첫째\n2. 둘째');
  assert.ok(h.startsWith('<ul class="md-list"><li>하나<ul class="md-list"><li>안쪽</li></ul></li><li>둘<br>이어짐</li></ul>'), h);
  assert.ok(h.includes('<ol class="md-list"><li>첫째</li><li>둘째</li></ol>'));
});

test('목록 — 번호 뒤 글머리는 새 글머리 목록, 번호는 처음 번호부터(11-08 사용자 보고)', () => {
  const h = md('1. 이름 바꾸기\n- 화면 이름표\n- 프로젝트 이름\n\n2. 노트\n- 설계 그대로');
  assert.equal(h, '<ol class="md-list"><li>이름 바꾸기</li></ol><ul class="md-list"><li>화면 이름표</li><li>프로젝트 이름</li></ul>'
    + '<ol class="md-list" start="2"><li>노트</li></ol><ul class="md-list"><li>설계 그대로</li></ul>');
  // 글머리 뒤 번호도 같다 · 중첩은 그대로
  assert.equal(md('- 가\n1. 나\n   - 다'), '<ul class="md-list"><li>가</li></ul><ol class="md-list"><li>나<ul class="md-list"><li>다</li></ul></li></ol>');
});

test('코드블록 — 맨 앞 · 목록 안 들여 쓴 것, 안은 그대로', () => {
  assert.ok(md('```bash\na < b && **x**\n```').includes('<pre class="md-code">a &lt; b &amp;&amp; **x**</pre>'));
  const h = md('- 실행:\n  ```\n  ls -la\n  ```\n- 끝');
  assert.ok(h.includes('<pre class="md-code">ls -la</pre>') && h.includes('<li>끝</li>'), h);
});

test('제목 · 인용 · 가로줄 · 문단', () => {
  const h = md('## 제목\n\n> 인용\n\n---\n첫 줄\n둘째 줄');
  assert.ok(h.includes('<div class="md-h md-h2">제목</div>') && h.includes('<blockquote class="md-quote"><p>인용</p></blockquote>'));
  assert.ok(h.includes('<hr class="md-hr">') && h.includes('<p>첫 줄<br>둘째 줄</p>'));
});

test('인라인 — HTML 통과 안 함, 코드 안은 바꾸지 않음, http 링크만', () => {
  assert.equal(inline('<b>x</b>'), '&lt;b&gt;x&lt;/b&gt;');
  assert.equal(inline('`**a**` *기울임*'), '<code class="md-i">**a**</code> <i>기울임</i>');
  assert.ok(inline('[a](https://x.y)').includes('href="https://x.y"'));
  assert.ok(!inline('[a](javascript:alert(1))').includes('href'));
  assert.equal(inline('2 * 3 * 4'), '2 * 3 * 4');            // 곱셈은 기울임이 아니다
});
