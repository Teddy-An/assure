# Assure

Evidence-based, full-project release verification for Codex.

> **Early beta:** Assure is usable today, but its manifest format and local
> installation flow may change.

[English](#english) | [한국어](#한국어)

<a id="english"></a>

## Why Assure

> Passing tests are not the same as verified release coverage.

A green test suite proves only that the tests you ran passed. It does not prove
that every product feature and user scenario is represented, that the
verification baseline still matches the current code, or that unanswered
manual checks were handled explicitly.

Assure builds and maintains an approved verification baseline, runs the full
registered population, and reports release readiness from bounded evidence.

## What makes it different

- Discovers product structures before asking the model to inspect source.
- Organizes verification by feature and user scenario.
- Maps existing tests before proposing new coverage.
- Requires explicit human approval for the baseline.
- Detects when an approved baseline is stale or damaged.
- Separates passed, failed, manual, indeterminate, and excluded results.
- Keeps model context bounded by using deterministic scripts and JSON
  summaries.

Assure complements your test framework and CI. It does not replace them.

## How it works

```text
Map → Human approval → Verify
```

1. **Map:** `assure-map` inventories the project, organizes product scenarios,
   and connects them to existing automated or manual verification.
2. **Human approval:** the proposed baseline remains in `review` until a person
   explicitly approves it.
3. **Verify:** `assure-verify` runs every registered automated check, collects
   manual responses, and produces an evidence-based verdict.

The `assure` dispatcher selects the correct workflow from the current project
state. Projects without an approved current baseline go to mapping; projects
with one go directly to verification.

## Requirements

- Git
- Python 3
- A Codex CLI version that provides `codex plugin`
- A Git repository for the project being verified
- The project's own test runners and dependencies

## Local installation

Assure is not currently distributed through a hosted marketplace. Install it
through a local Codex marketplace:

```bash
git clone https://github.com/Teddy-An/assure.git \
  ~/codex-marketplaces/assure-local/plugins/assure
mkdir -p ~/codex-marketplaces/assure-local/.agents/plugins
```

Create
`~/codex-marketplaces/assure-local/.agents/plugins/marketplace.json`:

```json
{
  "name": "assure-local",
  "interface": {
    "displayName": "Assure Local"
  },
  "plugins": [
    {
      "name": "assure",
      "source": {
        "source": "local",
        "path": "./plugins/assure"
      },
      "policy": {
        "installation": "AVAILABLE",
        "authentication": "ON_INSTALL"
      },
      "category": "Developer Tools"
    }
  ]
}
```

Register the marketplace and install the plugin:

```bash
codex plugin marketplace add ~/codex-marketplaces/assure-local
codex plugin add assure@assure-local
```

Start a new Codex thread after installation so the Assure skills are loaded.

## Quick start

Open the project you want to verify in Codex and ask:

```text
Run Assure for this project.
```

Assure routes the project to mapping or verification automatically. You can
also request either workflow explicitly:

```text
Update this project's Assure verification map.
Run the approved full verification baseline.
```

Mapping always stops for explicit human approval before an approved baseline
can be verified.

## Project state

Assure stores project-local state under `.assure/`:

- `.assure/verification-manifest.yaml` — the feature, scenario, risk, and
  verification baseline.
- `.assure/discovery-index.json` — deterministic inventory used for full or
  incremental mapping.
- `.assure/artifacts/` — verification evidence and generated reports.
- `.assure/adapters/` — optional read-only collectors for unsupported dynamic
  project structures.

Manifest status moves through `draft`, `review`, and `approved`. An approved
baseline is usable only when it still matches the current Git state. Assure
routes stale, incomplete, or damaged state back to mapping.

## Verdicts and safety boundaries

Scenario results distinguish:

- `O` — automated verification passed or a manual check was confirmed.
- `X` — verification failed.
- `👁` — a manual response is still required.
- `?` — the available evidence cannot support a conclusion.
- `—` — explicitly excluded with a reason, approver, and timestamp.

The final verdict can be `releasable`, `blocked`, `approval-required`, or a
warning depending on scenario risk and unresolved evidence.

Assure enforces these boundaries:

- A baseline cannot approve itself.
- Stale or damaged baselines cannot produce a release-ready verdict.
- Verification runs the complete registered population once.
- Verification reports failures without diagnosing or editing production code.
- Manual confirmation is never inferred from conversational context.

## Limitations

- Assure is early beta, and its manifest format may change.
- Initial mapping requires human review and approval.
- Dynamic structures and custom frameworks may require project adapters.
- Coverage quality depends on discoverable product structures and registered
  verification.
- Failure diagnosis and production fixes are separate tasks.

## Development

Run the complete test suite:

```bash
python3 -m unittest discover -s tests -v
```

The repository includes deterministic tests for project-state classification,
inventory collection, verification execution, workflow isolation, and this
README contract.

## License

Assure is available under the [MIT License](LICENSE).

Copyright (c) 2026 Teddy An

---

<a id="한국어"></a>

# Assure

Codex를 위한 증거 기반 전체 프로젝트 릴리스 검증 플러그인입니다.

> **Early beta:** 현재 사용할 수 있지만 manifest 형식과 로컬 설치
> 방식은 변경될 수 있습니다.

[English](#english) | [한국어](#한국어)

## 왜 Assure인가

> 테스트 통과가 곧 릴리스 범위 전체의 검증을 의미하지는 않습니다.

초록색 테스트 결과는 실행한 테스트가 통과했다는 사실만 증명합니다.
모든 제품 기능과 사용자 시나리오가 테스트에 포함됐는지, 검증 기준선이
현재 코드와 여전히 일치하는지, 답변되지 않은 수동 검사가 명시적으로
처리됐는지는 증명하지 못합니다.

Assure는 승인된 검증 기준선을 만들고 유지하며, 등록된 전체 항목을
실행하고 제한된 증거를 바탕으로 릴리스 준비 상태를 판정합니다.

## 무엇이 다른가

- 모델이 소스를 읽기 전에 결정적 방식으로 제품 구조를 발견합니다.
- 검증 항목을 기능과 사용자 시나리오 단위로 구성합니다.
- 새 테스트를 제안하기 전에 기존 테스트를 먼저 연결합니다.
- 검증 기준선에 사람의 명시적 승인을 요구합니다.
- 승인된 기준선이 오래됐거나 손상됐는지 감지합니다.
- 통과, 실패, 수동, 판단 불가, 제외 결과를 구분합니다.
- 결정적 스크립트와 JSON 요약으로 모델 컨텍스트 사용량을 제한합니다.

Assure는 기존 테스트 프레임워크와 CI를 보완하며, 이를 대체하지 않습니다.

## 작동 방식

```text
Map → Human approval → Verify
```

1. **Map:** `assure-map`이 프로젝트를 조사하고 제품 시나리오를 구성한
   뒤 기존 자동 또는 수동 검증과 연결합니다.
2. **Human approval:** 제안된 기준선은 사람이 명시적으로 승인하기 전까지
   `review` 상태로 유지됩니다.
3. **Verify:** `assure-verify`가 등록된 모든 자동 검사를 실행하고 수동
   응답을 수집한 뒤 증거 기반 판정을 생성합니다.

`assure` dispatcher는 현재 프로젝트 상태에 따라 올바른 workflow를
선택합니다. 승인된 최신 기준선이 없는 프로젝트는 mapping으로, 있는
프로젝트는 verification으로 바로 이동합니다.

## 요구 사항

- Git
- Python 3
- `codex plugin`을 제공하는 Codex CLI 버전
- 검증할 프로젝트의 Git 저장소
- 해당 프로젝트의 테스트 runner와 의존성

## 로컬 설치

Assure는 아직 호스팅 marketplace를 통해 배포되지 않습니다. 로컬 Codex
marketplace를 통해 설치하세요.

```bash
git clone https://github.com/Teddy-An/assure.git \
  ~/codex-marketplaces/assure-local/plugins/assure
mkdir -p ~/codex-marketplaces/assure-local/.agents/plugins
```

`~/codex-marketplaces/assure-local/.agents/plugins/marketplace.json`을
생성합니다.

```json
{
  "name": "assure-local",
  "interface": {
    "displayName": "Assure Local"
  },
  "plugins": [
    {
      "name": "assure",
      "source": {
        "source": "local",
        "path": "./plugins/assure"
      },
      "policy": {
        "installation": "AVAILABLE",
        "authentication": "ON_INSTALL"
      },
      "category": "Developer Tools"
    }
  ]
}
```

marketplace를 등록하고 플러그인을 설치합니다.

```bash
codex plugin marketplace add ~/codex-marketplaces/assure-local
codex plugin add assure@assure-local
```

설치 후 Assure 스킬이 로드되도록 새로운 Codex 대화를 시작하세요.

## 빠른 시작

Codex에서 검증할 프로젝트를 열고 다음과 같이 요청합니다.

```text
Run Assure for this project.
```

Assure가 프로젝트를 mapping 또는 verification workflow로 자동
라우팅합니다. 각 workflow를 직접 요청할 수도 있습니다.

```text
Update this project's Assure verification map.
Run the approved full verification baseline.
```

Mapping은 승인된 기준선을 검증하기 전에 항상 사람의 명시적 승인을
기다립니다.

## 프로젝트 상태

Assure는 프로젝트별 상태를 `.assure/` 아래에 저장합니다.

- `.assure/verification-manifest.yaml` — 기능, 시나리오, 위험도, 검증
  기준선입니다.
- `.assure/discovery-index.json` — 전체 또는 증분 mapping에 사용하는
  결정적 inventory입니다.
- `.assure/artifacts/` — 검증 증거와 생성된 report입니다.
- `.assure/adapters/` — 지원되지 않는 동적 프로젝트 구조를 위한 선택적
  읽기 전용 collector입니다.

Manifest 상태는 `draft`, `review`, `approved` 순서로 이동합니다. 승인된
기준선은 현재 Git 상태와 일치할 때만 사용할 수 있습니다. Assure는
오래됐거나 불완전하거나 손상된 상태를 mapping으로 되돌립니다.

## 판정과 안전 경계

시나리오 결과는 다음과 같이 구분합니다.

- `O` — 자동 검증이 통과했거나 수동 검사가 확인됐습니다.
- `X` — 검증이 실패했습니다.
- `👁` — 수동 응답이 아직 필요합니다.
- `?` — 현재 증거만으로 결론을 내릴 수 없습니다.
- `—` — 사유, 승인자, 시각을 기록하고 명시적으로 제외됐습니다.

최종 판정은 시나리오 위험도와 미해결 증거에 따라 `releasable`,
`blocked`, `approval-required` 또는 warning이 될 수 있습니다.

Assure는 다음 경계를 강제합니다.

- 기준선이 스스로를 승인할 수 없습니다.
- 오래됐거나 손상된 기준선은 release-ready 판정을 만들 수 없습니다.
- Verification은 등록된 전체 항목을 한 번 실행합니다.
- Verification은 실패를 보고하지만 운영 코드를 진단하거나 수정하지
  않습니다.
- 대화 맥락만으로 수동 확인을 추론하지 않습니다.

## 제한 사항

- Assure는 early beta이며 manifest 형식이 변경될 수 있습니다.
- 최초 mapping에는 사람의 검토와 승인이 필요합니다.
- 동적 구조와 custom framework에는 프로젝트 adapter가 필요할 수
  있습니다.
- Coverage 품질은 발견 가능한 제품 구조와 등록된 검증에 좌우됩니다.
- 실패 진단과 운영 코드 수정은 별도 작업입니다.

## 개발

전체 테스트 suite를 실행합니다.

```bash
python3 -m unittest discover -s tests -v
```

저장소에는 프로젝트 상태 분류, inventory 수집, verification 실행,
workflow 격리, README 계약을 검증하는 결정적 테스트가 포함되어 있습니다.

## 라이선스

Assure는 [MIT License](LICENSE)로 제공됩니다.

Copyright (c) 2026 Teddy An
