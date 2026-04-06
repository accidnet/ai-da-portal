# visualizations 네이밍 규칙

- 파일명은 `디자인/형태` 기준으로 짧게 작성합니다.
- `Visualization`, `Component`, `Portal` 접미사는 붙이지 않습니다.
- 예시: `BarChart.vue`, `LineTrend.vue`, `AreaTrend.vue`, `ScatterPlot.vue`, `DonutShare.vue`
- 페이지/도메인 맥락은 상위 컴포넌트에서 담당하고, 시각화 파일은 표현 방식에만 집중합니다.
- 백엔드 계약은 `chart.id` + `chart.type` 조합을 사용합니다.
