"""트랜스크립트 파일 읽기 — 동기 함수(스레드에서 부른다). DB를 모른다.

- 경로 규칙: <root>/<프로젝트 디렉토리>/<sessionId>.jsonl
             <root>/<프로젝트 디렉토리>/<sessionId>/subagents/agent-<agentId>.jsonl (+ .meta.json)
- offset tail: 저장된 offset부터 읽는다. inode가 바뀌었거나 크기가 offset보다 작으면 처음부터(같은 파일이 아니다)
- 개행으로 끝나지 않은 마지막 줄은 보류한다(CC가 쓰는 중). offset은 마지막 완성 줄 뒤까지만 간다
- api-request · api-request-blob 줄은 JSON 파싱 전에 바이트 비교로 버린다(트랜스크립트 용량의 76%).
  JSON 문자열 안에서는 따옴표가 \\"로 이스케이프되므로 '"type":"api-request'는 대화 내용과 겹치지 않는다
"""

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

API_REQUEST = b'"type":"api-request'
UUID_RE = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
MAIN_RE = re.compile(rf"^(?P<sid>{UUID_RE})\.jsonl$")
SUB_RE = re.compile(r"^agent-(?P<aid>[A-Za-z0-9_-]+)\.jsonl$")


@dataclass(frozen=True)
class FileKey:
    path: str
    project_dir: str          # ~/.claude/projects 아래 디렉토리 이름(cwd를 바꾼 것)
    cc_session_id: str
    agent_id: str | None      # 서브에이전트 파일이면

    @property
    def is_sub(self) -> bool:
        return self.agent_id is not None

    @property
    def meta_path(self) -> str | None:
        return self.path[: -len(".jsonl")] + ".meta.json" if self.is_sub else None


def classify(path: str | Path, root: str | Path) -> FileKey | None:
    """트랜스크립트 파일이면 FileKey, 아니면 None."""
    p = Path(path)
    try:
        rel = p.relative_to(root).parts
    except ValueError:
        return None
    if len(rel) == 2 and (m := MAIN_RE.match(rel[1])):
        return FileKey(str(p), rel[0], m["sid"], None)
    if len(rel) == 4 and rel[2] == "subagents" and re.fullmatch(UUID_RE, rel[1]) and (m := SUB_RE.match(rel[3])):
        return FileKey(str(p), rel[0], rel[1], m["aid"])
    return None


@dataclass
class Chunk:
    key: FileKey
    inode: int
    start: int                 # 이번에 읽기 시작한 offset (처음부터 다시면 0)
    end: int                   # 마지막 완성 줄 바로 뒤
    records: list[tuple[int, dict[str, Any]]] = field(default_factory=list)  # (줄 시작 offset, 파싱한 줄)
    skipped_api: int = 0
    bad_lines: int = 0
    reset: bool = False        # inode 변경 · 잘림으로 처음부터 다시 읽었다
    at_eof: bool = True        # 파일 끝까지 읽었나(아니면 같은 파일을 이어서 또 읽는다)


def read_chunk(key: FileKey, offset: int, inode: int | None, max_bytes: int = 8 << 20) -> Chunk | None:
    """offset부터 완성된 줄을 최대 max_bytes 남짓 읽는다. 새 줄이 없으면 None(파일이 없어도 None)."""
    try:
        st = os.stat(key.path)
    except FileNotFoundError:
        return None
    reset = False
    if inode is not None and (st.st_ino != inode or st.st_size < offset):
        offset, reset = 0, True
    if st.st_size <= offset and not reset:
        return None
    with open(key.path, "rb") as f:
        f.seek(offset)
        want = max_bytes
        while True:
            buf = f.read(want)
            nl = buf.rfind(b"\n")
            if nl != -1:
                break
            if len(buf) < want:   # 파일 끝까지 왔는데 개행이 없다 → 쓰는 중인 줄 하나뿐. 보류
                return None if not reset else Chunk(key, st.st_ino, 0, 0, reset=True)
            f.seek(offset)        # 한 줄이 max_bytes보다 길다 → 더 크게 다시
            want *= 2
    body = buf[: nl + 1]
    end = offset + len(body)
    chunk = Chunk(key, st.st_ino, offset, end, reset=reset, at_eof=end >= st.st_size)
    pos = offset
    for line in body.split(b"\n")[:-1]:
        line_off = pos
        pos += len(line) + 1
        if not line.strip():
            continue
        if API_REQUEST in line:
            chunk.skipped_api += 1
            continue
        try:
            chunk.records.append((line_off, json.loads(line)))
        except ValueError:
            chunk.bad_lines += 1
    return chunk


def read_meta(key: FileKey) -> dict[str, Any]:
    """서브에이전트 meta.json(agentType · description · toolUseId · spawnDepth · requestShape · isFork · finished)."""
    if not key.meta_path:
        return {}
    try:
        with open(key.meta_path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def iter_transcripts(root: str | Path) -> list[FileKey]:
    """백필 순서: 본 세션 파일을 먼저(수정 시각 순), 그다음 서브에이전트 파일.
    서브에이전트 행은 부모의 Agent tool_result에서 먼저 생기므로 이 순서면 띄운 턴이 바로 붙는다."""
    root = Path(root)
    mains: list[tuple[float, FileKey]] = []
    subs: list[tuple[float, FileKey]] = []
    if not root.is_dir():
        return []
    for proj in root.iterdir():
        if not proj.is_dir():
            continue
        for p in proj.iterdir():
            if p.is_file() and (k := classify(p, root)):
                mains.append((p.stat().st_mtime, k))
            elif p.is_dir() and (p / "subagents").is_dir():
                for s in (p / "subagents").iterdir():
                    if s.is_file() and (k := classify(s, root)):
                        subs.append((s.stat().st_mtime, k))
    return [k for _, k in sorted(mains, key=lambda x: x[0])] + [k for _, k in sorted(subs, key=lambda x: x[0])]
