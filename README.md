# Assure

**테스트 통과를 넘어, 제품 전체의 릴리스 준비 상태를 검증합니다.**

Assure는 Codex가 프로젝트의 기능과 사용자 시나리오를 파악하고, 기존
테스트와 연결하고, 빠진 검증을 드러낸 뒤, 등록된 전체 검증을 실행해
릴리스 판정을 내리도록 만드는 플러그인입니다.

[English](README.en.md) | **한국어**

> **Early beta:** 현재 사용할 수 있지만 manifest 형식과 설치 방식은
> 변경될 수 있습니다.

## 왜 Assure가 필요한가

테스트 runner는 **등록된 테스트가 통과했는가**를 알려줍니다.

하지만 릴리스 전에 필요한 질문은 더 큽니다.

- 제품의 주요 기능과 사용자 흐름이 모두 검증 대상에 들어갔는가?
- 테스트가 없는 기능은 무엇인가?
- 현재 테스트가 지금 코드와 여전히 연결되는가?
- 자동화할 수 없는 항목은 누가 확인해야 하는가?
- 실패와 미확인 항목의 위험도를 고려할 때 지금 릴리스해도 되는가?

Assure는 이 질문을 프로젝트 전체 범위에서 반복 가능한 검증 기준으로
관리합니다.

```text
기능 발견 → 시나리오 구성 → 기존 테스트 연결 → 누락 식별
         → 전체 검증 실행 → 위험도 기반 릴리스 판정
```

## 무엇이 다른가

| | 일반 테스트 runner | 일회성 에이전트 검증 | Assure |
|---|---|---|---|
| 출발점 | 이미 작성된 테스트 | 현재 요청과 대화 | 제품 기능과 사용자 시나리오 |
| 검증 범위 | 실행한 테스트 | 에이전트가 선택한 범위 | 등록된 전체 기준 |
| 빠진 검증 | 알 수 없음 | 놓칠 수 있음 | `uncovered`로 명시 |
| 수동 확인 | 별도 관리 | 대화에 남음 | 기준과 결과에 포함 |
| 변경 추적 | 테스트 결과 중심 | 세션이 끝나면 소실 | Git과 source snapshot으로 추적 |
| 실행 안전성 | 호스트 환경에 의존 | 작업 방식에 따라 다름 | 원본과 분리된 임시 복사본 |
| 최종 결과 | pass/fail | 설명 또는 수정 결과 | 위험도 기반 릴리스 판정 |

Assure는 테스트 프레임워크나 CI를 대체하지 않습니다. Vitest, Jest,
pytest 같은 기존 도구 위에 **검증 범위, 누락, 수동 확인, 릴리스 판단**을
더합니다.

## 한 번의 요청으로 하는 일

Codex에서 다음과 같이 요청합니다.

```text
이 프로젝트를 Assure로 전체 검증해줘.
```

Assure는 프로젝트 상태에 따라 필요한 과정을 자동으로 이어갑니다.

1. 프로젝트 구조와 테스트 환경을 조사합니다.
2. 기능별 사용자 시나리오를 구성합니다.
3. 기존 테스트를 먼저 연결합니다.
4. 안전하게 자동화할 수 있는 누락 테스트를 추가합니다.
5. 현재 source snapshot을 검증 기준으로 기록합니다.
6. 등록된 자동 검증 전체를 실행합니다.
7. 수동 확인과 미커버 항목을 함께 보고합니다.
8. 릴리스 판정을 반환합니다.

운영 코드는 자동으로 수정하지 않습니다. 테스트가 기존 결함을 발견하면
수정 대신 검증 결과로 보고합니다.

## 결과 예시

```text
릴리스 판정: blocked

| 결과 | 개수 |
|---|---:|
| 통과 | 18 |
| 실패 | 1 |
| 확인 | 2 |
| 미검증 | 1 |

| 번호 | 위험도 | 영역 | ID | 검증 항목 | 방식 | 결과 | 상세 |
|---:|---|---|---|---|---|---|---|
| 1 | critical | 결제 | `payments.refund-idempotency` | 환불이 중복 처리되지 않는다 | 자동 | 실패 | 종료 코드 1 |
| 2 | critical | 보안 | `security.admin-access` | 관리자 권한을 확인한다 | 수동 | 확인 | 수동 확인 대기 |
```

각 시나리오는 다음 상태 중 하나를 가집니다.

| 상태 | 의미 |
|---|---|
| `O` | 자동 검증 통과 또는 수동 확인 완료 |
| `X` | 검증 실패 |
| `👁` | 수동 확인 대기 |
| `?` | 환경·권한·데이터·미커버로 판단 불가 |
| `—` | 사유와 승인자를 기록하고 제외 |

최종 판정은 시나리오 위험도와 미해결 증거에 따라 `releasable`,
`blocked`, `approval-required`, `warning` 중 하나가 됩니다.

## 안전하게 실행되는 방식

Assure의 안전 원칙은 특정 외부 도구가 아니라 모든 실행 경로에
적용됩니다.

- 자동 검증은 Assure가 만든 임시 프로젝트 복사본에서 실행합니다.
- 원본 작업 트리에서 테스트를 실행하거나 운영 코드를 수정하지 않습니다.
- `.env`, 클라우드 자격증명, 비밀키를 복사하거나 상속하지 않습니다.
- 잠금 파일 기반 의존성만 임시 복사본에 준비합니다.
- package lifecycle script와 binary link를 비활성화합니다.
- 허용된 test runner와 인자 배열만 실행합니다.
- 테스트 실행 중 일반 네트워크 접근을 차단합니다.
- timeout 발생 시 하위 프로세스까지 종료합니다.
- 실행 후 Assure가 만든 임시 디렉터리만 정리합니다.

Docker 또는 Podman 데몬을 사용할 수 있으면 더 강한 격리를 위해 우선
사용합니다. 사용할 수 없거나 데몬이 중지돼 있어도 Assure 자체
`local-isolated` runner로 동작합니다.

외부 도구는 선택적 provider이며 Assure의 필수 실행 조건이 아닙니다.

## 원하는 작업만 실행하기

검증 기준을 만들거나 업데이트하려면:

```text
이 프로젝트의 Assure verification map을 업데이트해줘.
```

승인된 최신 기준으로 다시 검증하려면:

```text
승인된 Assure 기준으로 전체 재검증해줘.
```

영문 요청도 사용할 수 있습니다.

```text
Run Assure for this project.
Update this project's Assure verification map.
Run the approved full verification baseline.
```

## 요구사항

- Git
- Python 3.9 이상
- `codex plugin`을 지원하는 Codex CLI
- Git 저장소로 관리되는 검증 대상 프로젝트
- 프로젝트의 test runner와 잠금 파일

Docker와 Podman은 선택 사항입니다.

## 설치

Assure는 현재 호스팅 marketplace가 아닌 로컬 Codex marketplace 방식으로
설치합니다.

```bash
git clone https://github.com/Teddy-An/assure.git \
  ~/codex-marketplaces/assure-local/plugins/assure
mkdir -p ~/codex-marketplaces/assure-local/.agents/plugins
```

<details>
<summary>marketplace.json 설정 보기</summary>

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

</details>

marketplace를 등록하고 플러그인을 설치합니다.

```bash
codex plugin marketplace add ~/codex-marketplaces/assure-local
codex plugin add assure@assure-local
```

설치 후 새 Codex 대화를 시작해야 Assure skill이 로드됩니다.

## 프로젝트에 생성되는 파일

```text
.assure/
├── verification-manifest.yaml  # 기능, 시나리오, 위험도, 검증 기준
├── discovery-index.json        # 전체·증분 조사 inventory
├── adapters/                   # 선택적 읽기 전용 collector
├── artifacts/                  # 자동 검증 증거
└── reports/                    # JSON 및 Markdown 결과
```

승인된 기준은 Git commit과 deterministic source snapshot을 함께 기록합니다.
제품이나 테스트가 변경되면 Assure가 오래된 기준을 감지하고 mapping부터
갱신합니다.

핵심 기준은 `.assure/verification-manifest.yaml`에, 조사 inventory는
`.assure/discovery-index.json`에 저장됩니다.

## 현재 제한 사항

- 아직 early beta이며 manifest 형식이 변경될 수 있습니다.
- 동적 구조와 custom framework에는 project adapter가 필요할 수 있습니다.
- 브라우저 사용성, 실제 권한, 운영 데이터처럼 자동화하기 어려운 항목은
  수동 확인으로 남습니다.
- 발견할 수 없는 제품 구조까지 완전한 coverage를 보장하지는 않습니다.
- 실패 진단과 운영 코드 수정은 검증과 분리된 작업입니다.

## 개발

```bash
python3 -m unittest discover -s tests -v
```

## 라이선스

[MIT License](LICENSE)

Copyright (c) 2026 Teddy An
