# data-analysis feature

AI 데이터 분석 화면의 독립 기능 영역입니다. 웹서비스 전체를 뜻하는 `portal` 대신, 데이터셋 업로드, 분석 대화, 세션 관리, 분석 결과 시각화를 하나의 도메인으로 묶습니다.

- `components`: 화면 조각과 기능 단위 Vue 컴포넌트
- `components/visualizations`: 분석 차트 렌더링 컴포넌트
- `composables`: 세션, 데이터셋, 인증, 상호작용 상태 관리
- `constants`: 데이터 분석 화면 전용 상수
- `utils`: API 응답 매핑, 공유, 파일/리포트 유틸리티
- `types.ts`: 데이터 분석 기능에서 공유하는 타입
