// 입력 칸 높이 손잡이 끌기 계산(11-15 사용자). 처음 누른 지점과 지금 지점의 차이로 높이를 잡는다.
// 끝(위 끝 · 아래 끝)에 닿으면 기준점(y0 · h0)을 그 자리로 옮긴다 — 끝을 넘어 더 끈 거리가 쌓이지 않아서
// 되돌릴 때 손잡이가 바로 마우스를 따라온다(옮기지 않으면 넘긴 거리만큼 되돌려야 움직인다).
// st = {y0, h0}(처음 누른 화면 y · 그때 높이), z = 글씨 배율(마우스 화면 px를 CSS px로 바꿀 때 나눈다), 위로 끌면 커진다.
export function gripDrag(st, clientY, min, max, z = 1) {
  const raw = st.h0 + (st.y0 - clientY) / (z || 1);
  if (raw > max) return { h: max, st: { y0: clientY, h0: max } };
  if (raw < min) return { h: min, st: { y0: clientY, h0: min } };
  return { h: raw, st };
}
