-- 0033 포스트잇(11-15 사용자, 서기 구조 다시 짜기 2번 — log/foreman-6_postit_proposal_20261115.md, log/foreman-5_postit_20261115.md)
-- 받는 함(todo_inbox, 0027 · 0028 · 0031)이 곧 포스트잇이다. 「받은 할 일」과 포스트잇은 같은 것(사용자 답 6).
-- 서기가 README 「나중에 할 일」로 옮기는 단계가 없어진다 — 열린 포스트잇이 할 일 목록 그 자체다.
--
-- todo_inbox
--   source         어디서 왔나: note(포스트잇에 바로 적음) · todo([＋ 할 일]) · said(대화에서 사람이 말해 관리자가 올림) ·
--                  chat(브리지 그물이 대화에서 찾음 — 확인 전) · promote(옮기기 「문서에 넣을 것 고르기」의 미완)
--   source_ref     근거: t:<턴 id>(said · chat) · pr:<promotion id>:<항목 id>(promote). 같은 근거로 두 번 올리지 않는다
--   confirmed      0 = 확인 전(그물에서 온 것 — 화면에 흐리게, 사람이 [저장] 또는 [x]). 나머지는 1
--   closed_reason  닫힌 까닭: drop([x] 안 하기로 함) · limit([→] README 「알려진 한계」로 보냄) · done(끝남 — [갱신] 근거나 사람)
--   closed_at      닫은 시각
--   closed_note    닫은 근거([갱신]의 파일:줄 · 시험, 사람 한 줄)
--   limit으로 닫힌 것은 README에 쓰는 서기 세션(「알려진 한계 쓰기」, 옛 「나중에 할 일 정리」)이 taken_by로 가져가 합쳐지면 다 쓴 것이다
--
-- postit_check — [갱신](점검 세션)의 판정 한 줄. 판정은 제안이다 — 사람이 줄마다 닫거나 남긴다(resolved)
--   item      p:<todo_inbox.id> 또는 L:<README 「알려진 한계」 줄 앞부분>
--   verdict   done(끝남 — 근거가 코드 자리일 때만) · left(남음) · unknown(모름)
--   coder     코더에게 맡길 만한가(남음일 때만 뜻이 있다)
--
-- 데이터 맞추기(스키마는 더하기만):
--   - 버린 것(dropped_at)은 drop으로 닫는다
--   - 서기가 가져가 합쳐진 것(옛 상태 「옮김」)은 이미 README 표에 있으니 done으로 닫는다. 코더 몫이 합쳐진 것(「끝남」)도 done
--   - 합치기 카드 글(브리지가 관리자 입력 칸에 넣은 `[FOREMAN 합치기`)은 사람 말이 아니다 — 턴 출처를 merge_card로(bridge/assembler.py _origin)
-- 되돌리기:
--   ALTER TABLE todo_inbox DROP KEY ix_inbox_ref, DROP COLUMN source, DROP COLUMN source_ref, DROP COLUMN confirmed,
--     DROP COLUMN closed_reason, DROP COLUMN closed_at, DROP COLUMN closed_note;
--   DROP TABLE postit_check;
--   UPDATE turn SET origin = 'human' WHERE origin = 'merge_card';
--   (0032 코드는 이 칸들을 모른다 — 지우지 않아도 돈다. 다만 0032 코드는 닫힌 것을 다시 「새로」로 본다)
ALTER TABLE todo_inbox
  ADD COLUMN source VARCHAR(8) NOT NULL DEFAULT 'todo' AFTER assignee,
  ADD COLUMN source_ref VARCHAR(64) NULL AFTER source,
  ADD COLUMN confirmed BOOLEAN NOT NULL DEFAULT TRUE AFTER source_ref,
  ADD COLUMN closed_reason VARCHAR(8) NULL,
  ADD COLUMN closed_at DATETIME(3) NULL,
  ADD COLUMN closed_note VARCHAR(2000) NULL,
  ADD KEY ix_inbox_ref (source_ref);

CREATE TABLE postit_check (
  id           BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  project      VARCHAR(64) NOT NULL,
  session_id   BIGINT UNSIGNED NOT NULL,      -- 판정한 점검 세션(character_session.id)
  item         VARCHAR(80) NOT NULL,
  item_text    VARCHAR(500) NULL,             -- 판정할 때의 글 앞부분(README 줄은 DB에 없어 여기만 남는다)
  verdict      VARCHAR(8) NOT NULL,
  evidence     VARCHAR(1000) NULL,
  reason       VARCHAR(1000) NULL,
  coder        BOOLEAN NOT NULL DEFAULT FALSE,
  created_at   DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  resolved     VARCHAR(8) NULL,               -- closed(사람이 닫음) · kept(사람이 남김)
  resolved_at  DATETIME(3) NULL,
  PRIMARY KEY (id),
  KEY ix_check_project (project, resolved),
  KEY ix_check_session (session_id)
) ENGINE=InnoDB;

UPDATE todo_inbox SET closed_reason = 'drop', closed_at = dropped_at WHERE dropped_at IS NOT NULL;

UPDATE todo_inbox i SET i.closed_reason = 'done', i.closed_at = COALESCE(i.taken_at, i.created_at),
  i.closed_note = CASE WHEN i.assignee = 'coder' THEN CONCAT('포스트잇 전: 코더 세션 ', i.taken_by, '이 합쳐짐')
                       ELSE CONCAT('포스트잇 전: 서기 세션 ', i.taken_by, '이 README 「나중에 할 일」 표로 옮김') END
WHERE i.closed_reason IS NULL AND i.taken_by IS NOT NULL
  AND EXISTS (SELECT 1 FROM session_action m WHERE m.session_id = i.taken_by AND m.action = 'wt-merge' AND m.ok);

UPDATE todo_inbox i SET i.closed_reason = 'done', i.closed_at = COALESCE(i.taken_at, i.created_at),
  i.closed_note = CONCAT('포스트잇 전: 코더 세션 ', i.taken_by, '이 끝남(원본 폴더)')
WHERE i.closed_reason IS NULL AND i.taken_by IS NOT NULL AND i.assignee = 'coder'
  AND EXISTS (SELECT 1 FROM character_session t WHERE t.id = i.taken_by AND t.worktree_path IS NULL AND t.detached_at IS NOT NULL);

UPDATE turn SET origin = 'merge_card'
WHERE origin = 'human' AND LOCATE('[FOREMAN 합치기', LEFT(TRIM(LEADING '\n' FROM TRIM(prompt_text)), 120)) > 0;
