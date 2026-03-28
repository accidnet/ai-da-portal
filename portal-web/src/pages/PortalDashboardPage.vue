<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";

import PortalAnalyticsPane from "../features/portal/components/PortalAnalyticsPane.vue";
import PortalConversationPane from "../features/portal/components/PortalConversationPane.vue";
import PortalDatasetLibrary from "../features/portal/components/PortalDatasetLibrary.vue";
import PortalHeader from "../features/portal/components/PortalHeader.vue";
import PortalSessionHub from "../features/portal/components/PortalSessionHub.vue";
import PortalSidebar from "../features/portal/components/PortalSidebar.vue";
import type {
  AnalyticsData,
  ChatMessage,
  ComposerChip,
  ComposerData,
  ConversationData,
  DatasetLibraryItem,
  HeaderData,
  MessageAttachmentPreview,
  OpenAiAuthStatus,
  PortalScreen,
  SessionItem,
  SidebarData,
} from "../features/portal/types";
import {
  type SessionRuntimeState,
  mapDatasetAsset,
  mapDatasetDetailToAsset,
  mapSnapshotToSessionState,
} from "../features/portal/utils/sessionState";
import {
  attachDatasetToSession,
  authorizeOpenAi,
  createAnalysis,
  createSession,
  deleteDataset,
  deleteSession,
  detachDatasetFromSession,
  fetchDatasetPreview,
  fetchDatasetProfile,
  fetchDatasets,
  fetchHealthcheck,
  fetchOpenAiAuthStatus,
  fetchSessionSnapshot,
  fetchSessions,
  sendChatInteraction,
  sendChatMessage,
  type ChatInteractionResponse,
  updateSessionTitle,
  uploadDataset,
} from "../shared/api/portalApi";

interface OpenAiPopupMessage {
  source?: string;
  status?: "success" | "error";
  error?: string;
  account_email?: string;
}

const OPENAI_AUTH_POPUP_SOURCE = "portal-openai-auth";
const ANALYTICS_PANE_WIDTH_STORAGE_KEY = "portal.analyticsPaneWidth";
const DEFAULT_SESSION_TITLE = "ChatGPT 분석 세션";
const LOCAL_SESSION_ID = "local-session";
const SCREEN_HASHES: Record<PortalScreen, `#/${PortalScreen}`> = {
  dashboard: "#/dashboard",
  sessions: "#/sessions",
  datasets: "#/datasets",
};

const shellSidebar: SidebarData = {
  productName: "데이터 분석 AI",
  productTagline: "데이터 인텔리전스",
  primaryNav: [
    { label: "새 분석", icon: "add_chart", screen: "dashboard" },
    { label: "기록", icon: "history", screen: "sessions" },
    { label: "데이터 소스", icon: "database", screen: "datasets" },
  ],
  recentSessions: [],
  secondaryNav: [
    { label: "설정", icon: "settings" },
    { label: "도움말", icon: "help" },
  ],
  profile: {
    name: "Alex Architect",
    plan: "Pro Plan",
    initials: "AA",
  },
};

const shellHeader: HeaderData = {
  searchPlaceholder: "분석, 데이터셋, 프롬프트 검색",
  actions: ["notifications", "ios_share", "account_circle"],
};

const shellAnalytics: AnalyticsData = {
  title: "분석 작업공간",
  chartTitle: "실시간 분석 대기 중",
  chartChange: "아직 분석 결과가 없어요",
  chartPoints: [],
  metrics: [],
  tableRows: [],
  insight: {
    title: "여기서 시작해 보세요",
    body: "데이터셋을 업로드하거나 프롬프트를 보내면 이 영역에 실시간 분석 결과가 채워집니다.",
    actionLabel: "분석 실행",
  },
};

function resolveScreenFromHash(hash = window.location.hash): PortalScreen {
  const normalizedHash = hash.trim().toLowerCase();
  if (normalizedHash === SCREEN_HASHES.sessions) return "sessions";
  if (normalizedHash === SCREEN_HASHES.datasets) return "datasets";
  return "dashboard";
}

const connectionStatus = ref<"checking" | "connected" | "offline">("checking");
const currentScreen = ref<PortalScreen>(resolveScreenFromHash());
const authStatus = ref<OpenAiAuthStatus>({
  state: "disconnected",
  connected: false,
  pending: false,
  accountEmail: null,
  accountId: null,
  expiresAt: null,
  scopes: [],
});
const isConnecting = ref(false);
const chatError = ref<string | null>(null);
const uploadError = ref<string | null>(null);
const analyticsError = ref<string | null>(null);
const authError = ref<string | null>(null);
const exportMessage = ref<string | null>(null);
const sessionHubError = ref<string | null>(null);
const datasetLibraryError = ref<string | null>(null);
const searchQuery = ref("");
const sessionHubSearchQuery = ref("");
const datasetLibrarySearchQuery = ref("");
const analyticsPaneWidth = ref(420);
const isResizingAnalyticsPane = ref(false);
const isAnalyticsFullscreen = ref(false);
const isSending = ref(false);
const isUploading = ref(false);
const isRunningAnalysis = ref(false);
const isSendingInteraction = ref(false);
const isSessionMutating = ref(false);
const isDatasetMutating = ref(false);
const activeSessionId = ref<string | null>(null);
const sessionSummaries = ref<SessionItem[]>([]);
const sessionStates = ref<Record<string, SessionRuntimeState>>({});
const hydratedSessionIds = ref<Record<string, boolean>>({});
const datasetsLibrary = ref<DatasetLibraryItem[]>([]);
const selectedDatasetId = ref<string | null>(null);
const datasetPickerRef = ref<HTMLInputElement | null>(null);
const interactionPickerRef = ref<HTMLInputElement | null>(null);
const pendingAttachment = ref<File | null>(null);
let authPollTimer: number | null = null;
let authPopup: Window | null = null;
let latestSnapshotRequestId = 0;

function clampAnalyticsPaneWidth(width: number): number {
  return Math.min(Math.max(width, 320), 720);
}

function mapSessionSummary(session: {
  id: string;
  title: string;
  created_at?: string;
  updated_at?: string;
  message_count?: number;
  dataset_count?: number;
  preferred_dataset_id?: string | null;
  last_dataset?: { id: string; filename: string } | null;
}): SessionItem {
  return {
    id: session.id,
    title: session.title,
    createdAt: session.created_at,
    updatedAt: session.updated_at,
    messageCount: session.message_count ?? 0,
    datasetCount: session.dataset_count ?? 0,
    preferredDatasetId: session.preferred_dataset_id ?? null,
    lastDataset: session.last_dataset ?? null,
  };
}

function mapDatasetLibraryItem(dataset: {
  id: string;
  filename: string;
  content_type: string | null;
  storage_path: string;
  created_at: string;
  row_count: number;
  column_count: number;
  linked_session_count: number;
  linked_session_ids: string[];
  latest_used_at: string | null;
}): DatasetLibraryItem {
  return {
    id: dataset.id,
    filename: dataset.filename,
    contentType: dataset.content_type,
    storagePath: dataset.storage_path,
    createdAt: dataset.created_at,
    rowCount: dataset.row_count,
    columnCount: dataset.column_count,
    linkedSessionCount: dataset.linked_session_count,
    linkedSessionIds: dataset.linked_session_ids,
    latestUsedAt: dataset.latest_used_at,
    preview: null,
    profile: null,
  };
}

function createWelcomeMessages(): ChatMessage[] {
  return [
    {
      role: "assistant",
      author: "AI 데이터 분석가",
      text: "데이터셋을 업로드하면 바로 분석을 시작할 수 있어요.",
      bullets: [
        { text: "CSV 또는 스프레드시트 파일 업로드하기" },
        { text: "추세, 상관관계, 이상치 분석 요청하기" },
        { text: "간단한 그래프 시각화하기" },
      ],
    },
  ];
}

function normalizeAssistantMessage(message: string): string {
  let normalizedMessage = message.trim();
  normalizedMessage = normalizedMessage.replace(/^\[(?:Pasted?|Past)\s*/i, "");
  return normalizedMessage
    .split(/\r?\n/)
    .map((line) => line.replace(/^[-*]\s+/, "").trim())
    .filter(Boolean)
    .join("\n")
    .replace(/\s{2,}/g, " ")
    .trim();
}

function createSessionState(title: string): SessionRuntimeState {
  return {
    title,
    messages: createWelcomeMessages(),
    analyticsPayload: null,
    workspacePayload: null,
    datasets: [],
    preferredDatasetId: null,
  };
}

function resolvePreferredDatasetId(
  state: SessionRuntimeState | null | undefined,
): string | null {
  if (!state) {
    return null;
  }

  if (
    state.preferredDatasetId &&
    state.datasets.some((dataset) => dataset.id === state.preferredDatasetId)
  ) {
    return state.preferredDatasetId;
  }

  return state.datasets[0]?.id ?? null;
}

function ensureSessionState(
  sessionId: string,
  title: string,
): SessionRuntimeState {
  const existing = sessionStates.value[sessionId];
  if (existing) {
    existing.title = title;
    return existing;
  }

  const created = createSessionState(title);
  sessionStates.value[sessionId] = created;
  return created;
}

function updateSessionSummary(sessionId: string, patch: Partial<SessionItem>) {
  const current = sessionSummaries.value.find(
    (session) => session.id === sessionId,
  );
  if (!current) {
    return;
  }

  Object.assign(current, patch);
  sessionSummaries.value = [...sessionSummaries.value];
}

function syncSessionSummaryWithState(sessionId: string) {
  const state = sessionStates.value[sessionId];
  if (!state) {
    return;
  }

  updateSessionSummary(sessionId, {
    title: state.title,
    messageCount: state.messages.length,
    datasetCount: state.datasets.length,
    preferredDatasetId: resolvePreferredDatasetId(state),
    lastDataset: state.datasets[0]
      ? {
          id: state.datasets[0].id,
          filename: state.datasets[0].filename,
        }
      : null,
    updatedAt: new Date().toISOString(),
  });
}

function buildSessionTitle(): string {
  return `분석 세션 ${sessionSummaries.value.length + 1}`;
}

function handleAnalyticsPaneResize(event: PointerEvent) {
  if (!isResizingAnalyticsPane.value || window.innerWidth <= 1280) {
    return;
  }

  analyticsPaneWidth.value = clampAnalyticsPaneWidth(
    window.innerWidth - event.clientX - 48,
  );
}

function stopAnalyticsPaneResize() {
  isResizingAnalyticsPane.value = false;
  window.removeEventListener("pointermove", handleAnalyticsPaneResize);
  window.removeEventListener("pointerup", stopAnalyticsPaneResize);
}

function startAnalyticsPaneResize(event: PointerEvent) {
  if (window.innerWidth <= 1280) {
    return;
  }

  event.preventDefault();
  isResizingAnalyticsPane.value = true;
  window.addEventListener("pointermove", handleAnalyticsPaneResize);
  window.addEventListener("pointerup", stopAnalyticsPaneResize);
}

function restoreAnalyticsPaneWidth() {
  const storedWidth = window.localStorage.getItem(
    ANALYTICS_PANE_WIDTH_STORAGE_KEY,
  );
  if (!storedWidth) {
    return;
  }

  const parsedWidth = Number(storedWidth);
  if (!Number.isFinite(parsedWidth)) {
    return;
  }

  analyticsPaneWidth.value = clampAnalyticsPaneWidth(parsedWidth);
}

function syncAuthPolling() {
  if (
    authStatus.value.connected ||
    (!authStatus.value.pending && !isConnecting.value)
  ) {
    if (authPollTimer !== null) {
      window.clearInterval(authPollTimer);
      authPollTimer = null;
    }
    return;
  }

  if (authPollTimer === null) {
    authPollTimer = window.setInterval(async () => {
      await loadAuthStatus();
    }, 3000);
  }
}

async function loadAuthStatus() {
  try {
    const status = await fetchOpenAiAuthStatus();
    authStatus.value = {
      state: status.state,
      connected: status.connected,
      pending: status.pending,
      accountEmail: status.account_email,
      accountId: status.account_id,
      expiresAt: status.expires_at,
      scopes: status.scopes,
    };
    isConnecting.value = status.pending;
    if (status.connected) {
      authError.value = null;
      authPopup = null;
    } else if (!status.pending) {
      authPopup = null;
    }
  } catch {
    authError.value = "ChatGPT 연결 상태를 불러오지 못했어요.";
  } finally {
    syncAuthPolling();
  }
}

async function handleOpenAiAuthMessage(
  event: MessageEvent<OpenAiPopupMessage>,
) {
  if (
    !authPopup ||
    event.source !== authPopup ||
    event.data?.source !== OPENAI_AUTH_POPUP_SOURCE
  ) {
    return;
  }

  authPopup = null;
  if (event.data.status === "error") {
    isConnecting.value = false;
    authError.value = event.data.error ?? "ChatGPT 연결을 완료하지 못했어요.";
  }
  await loadAuthStatus();
}

function handleWindowFocus() {
  if (authStatus.value.pending || isConnecting.value) {
    void loadAuthStatus();
  }
}

function buildPopupFeatures() {
  const width = 560;
  const height = 720;
  const left = Math.max(
    window.screenX + Math.round((window.outerWidth - width) / 2),
    0,
  );
  const top = Math.max(
    window.screenY + Math.round((window.outerHeight - height) / 2),
    0,
  );
  return `popup=yes,width=${width},height=${height},left=${left},top=${top}`;
}

async function ensureDatasetLibraryDetails(datasetId: string) {
  const target = datasetsLibrary.value.find(
    (dataset) => dataset.id === datasetId,
  );
  if (!target || (target.preview && target.profile)) {
    return target ?? null;
  }

  try {
    const [preview, profile] = await Promise.all([
      fetchDatasetPreview(datasetId),
      fetchDatasetProfile(datasetId),
    ]);
    target.preview = { columns: preview.columns, rows: preview.rows };
    target.profile = {
      rowCount: profile.profile.row_count,
      columnCount: profile.profile.column_count,
      columns: profile.profile.columns.map((column) => ({
        name: column.name,
        dtype: column.dtype,
        nullRatio: column.null_ratio,
        sampleValues: column.sample_values,
      })),
      suggestedPrompts: profile.profile.suggested_prompts,
    };
    datasetsLibrary.value = [...datasetsLibrary.value];
  } catch {
    datasetLibraryError.value = "데이터셋 상세 정보를 불러오지 못했어요.";
  }

  return target;
}

async function loadDatasets() {
  try {
    const datasets = await fetchDatasets();
    datasetsLibrary.value = datasets.map(mapDatasetLibraryItem);
    if (
      !selectedDatasetId.value ||
      !datasetsLibrary.value.some(
        (dataset) => dataset.id === selectedDatasetId.value,
      )
    ) {
      selectedDatasetId.value = datasetsLibrary.value[0]?.id ?? null;
    }
    if (selectedDatasetId.value) {
      await ensureDatasetLibraryDetails(selectedDatasetId.value);
    }
    datasetLibraryError.value = null;
  } catch {
    datasetLibraryError.value = "데이터 소스 목록을 불러오지 못했어요.";
  }
}

async function loadSessions() {
  try {
    const sessions = await fetchSessions();
    sessionSummaries.value = sessions.map(mapSessionSummary);
    if (sessionSummaries.value.length === 0) {
      const created = await createSession(DEFAULT_SESSION_TITLE);
      sessionSummaries.value = [mapSessionSummary(created)];
      activeSessionId.value = created.id;
      ensureSessionState(created.id, created.title);
      hydratedSessionIds.value[created.id] = true;
      return;
    }

    for (const session of sessionSummaries.value) {
      if (session.id) {
        ensureSessionState(session.id, session.title);
      }
    }

    if (
      !activeSessionId.value ||
      !sessionSummaries.value.some(
        (session) => session.id === activeSessionId.value,
      )
    ) {
      activeSessionId.value = sessionSummaries.value[0]?.id ?? null;
    }
    if (activeSessionId.value) {
      await hydrateSessionSnapshot(activeSessionId.value);
    }
    sessionHubError.value = null;
  } catch {
    if (!activeSessionId.value) {
      activeSessionId.value = LOCAL_SESSION_ID;
      sessionSummaries.value = [
        {
          id: LOCAL_SESSION_ID,
          title: DEFAULT_SESSION_TITLE,
          messageCount: 1,
          datasetCount: 0,
        },
      ];
      ensureSessionState(LOCAL_SESSION_ID, DEFAULT_SESSION_TITLE);
      hydratedSessionIds.value[LOCAL_SESSION_ID] = true;
    }
    sessionHubError.value =
      "세션 목록을 서버에서 불러오지 못해 로컬 세션으로 전환했어요.";
  }
}

function getActiveSessionId(): string {
  if (activeSessionId.value) {
    return activeSessionId.value;
  }

  activeSessionId.value = LOCAL_SESSION_ID;
  ensureSessionState(LOCAL_SESSION_ID, DEFAULT_SESSION_TITLE);
  if (
    !sessionSummaries.value.some((session) => session.id === LOCAL_SESSION_ID)
  ) {
    sessionSummaries.value = [
      { id: LOCAL_SESSION_ID, title: DEFAULT_SESSION_TITLE },
      ...sessionSummaries.value,
    ];
  }
  hydratedSessionIds.value[LOCAL_SESSION_ID] = true;
  return LOCAL_SESSION_ID;
}

async function ensureActiveSession() {
  const currentSessionId = getActiveSessionId();
  if (sessionStates.value[currentSessionId]) {
    return currentSessionId;
  }

  const created = await createSession(DEFAULT_SESSION_TITLE);
  activeSessionId.value = created.id;
  sessionSummaries.value = [
    mapSessionSummary(created),
    ...sessionSummaries.value,
  ];
  ensureSessionState(created.id, created.title);
  hydratedSessionIds.value[created.id] = true;
  return created.id;
}

async function hydrateSessionSnapshot(sessionId: string, force = false) {
  if (!sessionId || sessionId === LOCAL_SESSION_ID) {
    return;
  }

  const summary = sessionSummaries.value.find(
    (session) => session.id === sessionId,
  );
  ensureSessionState(sessionId, summary?.title ?? DEFAULT_SESSION_TITLE);
  if (hydratedSessionIds.value[sessionId] && !force) {
    return;
  }

  const requestId = ++latestSnapshotRequestId;
  try {
    const snapshot = await fetchSessionSnapshot(sessionId);
    if (requestId !== latestSnapshotRequestId) {
      return;
    }

    const state = mapSnapshotToSessionState(snapshot, createWelcomeMessages);
    sessionStates.value[sessionId] = state;
    updateSessionSummary(sessionId, {
      title: state.title,
      messageCount: state.messages.length,
      datasetCount: state.datasets.length,
      lastDataset: state.datasets[0]
        ? { id: state.datasets[0].id, filename: state.datasets[0].filename }
        : null,
      updatedAt: snapshot.session.updated_at,
      createdAt: snapshot.session.created_at,
    });
    hydratedSessionIds.value[sessionId] = true;
  } catch {
    hydratedSessionIds.value[sessionId] = true;
  }
}

async function createAndSelectSession() {
  chatError.value = null;
  uploadError.value = null;
  analyticsError.value = null;
  try {
    isSessionMutating.value = true;
    const created = await createSession(buildSessionTitle());
    activeSessionId.value = created.id;
    ensureSessionState(created.id, created.title);
    sessionSummaries.value = [
      mapSessionSummary(created),
      ...sessionSummaries.value,
    ];
    hydratedSessionIds.value[created.id] = true;
    currentScreen.value = "dashboard";
    sessionHubSearchQuery.value = "";
  } catch {
    sessionHubError.value =
      "새 분석 세션을 만들지 못했어요. 잠시 후 다시 시도해 주세요.";
  } finally {
    isSessionMutating.value = false;
  }
}

async function connectOpenAi() {
  if (authPopup && !authPopup.closed) {
    authPopup.focus();
    return;
  }

  isConnecting.value = true;
  authError.value = null;
  try {
    const authorization = await authorizeOpenAi();
    const popup = window.open(
      authorization.authorization_url,
      "portal-openai-auth",
      buildPopupFeatures(),
    );
    if (!popup) {
      window.location.assign(authorization.authorization_url);
      return;
    }
    authPopup = popup;
    authStatus.value = {
      ...authStatus.value,
      state: "pending",
      pending: true,
      connected: false,
    };
  } catch {
    isConnecting.value = false;
    authError.value = "ChatGPT 연결을 시작하지 못했어요.";
  } finally {
    syncAuthPolling();
  }
}

async function selectSession(
  sessionId: string,
  targetScreen: PortalScreen = currentScreen.value,
) {
  activeSessionId.value = sessionId;
  currentScreen.value = targetScreen;
  const summary = sessionSummaries.value.find(
    (session) => session.id === sessionId,
  );
  ensureSessionState(sessionId, summary?.title ?? DEFAULT_SESSION_TITLE);
  await hydrateSessionSnapshot(sessionId, true);
}

async function handleScreenChange(screen: PortalScreen) {
  currentScreen.value = screen;
  if (screen === "datasets") {
    await loadDatasets();
  }
}

function handleSessionHubSearchChange(value: string) {
  sessionHubSearchQuery.value = value;
}

function handleDatasetLibrarySearchChange(value: string) {
  datasetLibrarySearchQuery.value = value;
}

function handleHeaderSearchChange(value: string) {
  if (currentScreen.value === "sessions") {
    sessionHubSearchQuery.value = value;
    return;
  }
  if (currentScreen.value === "datasets") {
    datasetLibrarySearchQuery.value = value;
    return;
  }
  searchQuery.value = value;
}

function toggleAnalyticsFullscreen() {
  isAnalyticsFullscreen.value = !isAnalyticsFullscreen.value;
}

function sanitizeFileNameSegment(value: string): string {
  return (
    value
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9가-힣]+/g, "-")
      .replace(/^-+|-+$/g, "") || "analysis-report"
  );
}

function buildReportContent() {
  const sessionState = activeSessionState.value;
  const dataset = activeDataset.value;
  const analytics = analyticsPayload.value;
  const workspace = workspacePayload.value;
  const lines: string[] = [];
  lines.push(
    `# ${workspace?.title ?? sessionState?.title ?? DEFAULT_SESSION_TITLE}`,
  );
  if (workspace?.description) {
    lines.push("", workspace.description);
  }
  if (dataset) {
    lines.push(
      "",
      "## 데이터셋",
      `- 파일명: ${dataset.filename}`,
      `- 생성 시각: ${dataset.createdAt}`,
    );
    if (dataset.profile) {
      lines.push(
        `- 행/열: ${dataset.profile.rowCount}행 / ${dataset.profile.columnCount}열`,
      );
    }
  }
  if (analytics?.summary_cards?.length) {
    lines.push("", "## 핵심 지표");
    for (const card of analytics.summary_cards) {
      lines.push(
        `- ${card.label}: ${card.value}${card.detail ? ` (${card.detail})` : ""}`,
      );
    }
  }
  if (analytics?.insights?.length) {
    lines.push("", "## 인사이트");
    for (const insight of analytics.insights) {
      lines.push(`### ${insight.title}`, insight.body);
      if (insight.action_label) {
        lines.push(`- 제안 액션: ${insight.action_label}`);
      }
      lines.push("");
    }
    while (lines.at(-1) === "") lines.pop();
  }
  if (analytics?.charts?.length) {
    lines.push("", "## 차트");
    for (const chart of analytics.charts) {
      lines.push(`### ${chart.title}`);
      for (const series of chart.series) {
        lines.push(
          `- ${series.name}: ${series.data.map((value, index) => `${chart.x[index] ?? index}=${value ?? "-"}`).join(", ")}`,
        );
      }
    }
  }
  if (analytics?.tables?.length) {
    lines.push("", "## 표");
    for (const table of analytics.tables) {
      lines.push(
        `### ${table.title}`,
        table.columns.map((column) => column.label).join(" | "),
        table.columns.map(() => "---").join(" | "),
      );
      for (const row of table.rows) {
        lines.push(
          table.columns
            .map((column) => String(row[column.key] ?? "-"))
            .join(" | "),
        );
      }
      lines.push("");
    }
    while (lines.at(-1) === "") lines.pop();
  }
  if (dataset?.profile?.columns?.length) {
    lines.push("", "## 컬럼 프로파일");
    for (const column of dataset.profile.columns) {
      const samples = column.sampleValues.length
        ? ` / 예시: ${column.sampleValues.join(", ")}`
        : "";
      lines.push(
        `- ${column.name}: ${column.dtype} / 결측 ${Math.round(column.nullRatio * 100)}%${samples}`,
      );
    }
  }
  if (sessionState?.messages?.length) {
    lines.push("", "## 최근 대화");
    for (const message of sessionState.messages.slice(-6)) {
      const speaker =
        message.role === "assistant"
          ? (message.author ?? "AI 데이터 분석가")
          : "사용자";
      lines.push(`- ${speaker}: ${message.text}`);
    }
  }
  return lines.join("\n");
}

function exportAnalyticsReport() {
  const content = buildReportContent().trim();
  if (!content) return;
  const fileName = `${sanitizeFileNameSegment(activeSessionState.value?.title ?? DEFAULT_SESSION_TITLE)}.md`;
  const blob = new Blob([content], { type: "text/markdown;charset=utf-8" });
  const url = window.URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = fileName;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  window.URL.revokeObjectURL(url);
  exportMessage.value = `${fileName} 리포트를 다운로드했어요.`;
}

function formatFileSize(size: number): string {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

function createAttachmentPreview(
  filename: string,
  size: number,
  preview: {
    columns: string[];
    rows: Array<Record<string, string | number | null>>;
  },
): MessageAttachmentPreview {
  return {
    filename,
    meta: `${formatFileSize(size)} · ${preview.rows.length}행 미리보기`,
    columns: preview.columns,
    rows: preview.rows,
  };
}

async function handleSendMessage(message: string) {
  chatError.value = null;
  uploadError.value = null;
  analyticsError.value = null;
  exportMessage.value = null;
  const sessionId = await ensureActiveSession();
  const sessionState = ensureSessionState(sessionId, DEFAULT_SESSION_TITLE);
  const attachedFile = pendingAttachment.value;
  const userMessage =
    message ||
    (attachedFile ? `${attachedFile.name} 파일을 업로드해서 분석해줘.` : "");
  const userMessageEntry: ChatMessage = {
    role: "user",
    text: userMessage,
    attachmentPreview: attachedFile
      ? {
          filename: attachedFile.name,
          meta: `${formatFileSize(attachedFile.size)} · 업로드 중`,
          columns: [],
          rows: [],
        }
      : undefined,
  };
  sessionState.messages = [...sessionState.messages, userMessageEntry];
  isSending.value = true;
  isSendingInteraction.value = Boolean(attachedFile);
  pendingAttachment.value = null;

  try {
    const response = attachedFile
      ? await sendChatInteraction({
          sessionId,
          message: userMessage,
          datasetIds: sessionState.datasets.map((dataset) => dataset.id),
          file: attachedFile,
        })
      : await sendChatMessage({
          sessionId,
          message: userMessage,
          datasetIds: sessionState.datasets.map((dataset) => dataset.id),
        });
    const interactionResponse = attachedFile
      ? (response as ChatInteractionResponse)
      : null;

    if (interactionResponse?.dataset) {
      const uploadedDataset = interactionResponse.dataset;
      const dataset = mapDatasetAsset(uploadedDataset);
      sessionState.datasets = [
        dataset,
        ...sessionState.datasets.filter((item) => item.id !== dataset.id),
      ];
      sessionState.messages = sessionState.messages.map((entry) =>
        entry === userMessageEntry
          ? {
              ...entry,
              attachmentPreview: createAttachmentPreview(
                uploadedDataset.detail.filename,
                attachedFile?.size ?? 0,
                uploadedDataset.preview,
              ),
            }
          : entry,
      );
      await loadDatasets();
    }

    sessionState.messages = [
      ...sessionState.messages,
      {
        role: "assistant",
        author: "AI 데이터 분석가",
        text: normalizeAssistantMessage(response.assistant_message),
      },
    ];
    sessionState.analyticsPayload = response.analytics;
    sessionState.workspacePayload = response.workspace;
    syncSessionSummaryWithState(sessionId);
  } catch (error) {
    chatError.value =
      error instanceof Error
        ? error.message
        : "메시지를 보내지 못했어요. ChatGPT 연결과 백엔드 상태를 확인해 주세요.";
    pendingAttachment.value = attachedFile;
  } finally {
    isSending.value = false;
    isSendingInteraction.value = false;
  }
}

function openDatasetPicker() {
  datasetPickerRef.value?.click();
}

function openInteractionPicker() {
  interactionPickerRef.value?.click();
}

function clearPendingAttachment() {
  pendingAttachment.value = null;
}

function queueInteractionFile(file: File) {
  if (
    !file.name.toLowerCase().endsWith(".csv") &&
    !file.type.includes("csv") &&
    !file.type.startsWith("text/") &&
    !file.name.toLowerCase().endsWith(".tsv") &&
    !file.name.toLowerCase().endsWith(".xls") &&
    !file.name.toLowerCase().endsWith(".xlsx") &&
    !file.name.toLowerCase().endsWith(".json")
  ) {
    uploadError.value = "CSV 또는 스프레드시트 파일만 업로드할 수 있어요.";
    return;
  }
  uploadError.value = null;
  pendingAttachment.value = file;
}

function handleInteractionFileChange(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = "";
  if (file) queueInteractionFile(file);
}

function handleDatasetFileChange(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = "";
  if (file) void processDatasetFile(file);
}

async function processDatasetFile(file: File) {
  if (
    !file.name.toLowerCase().endsWith(".csv") &&
    !file.type.includes("csv") &&
    !file.type.startsWith("text/") &&
    !file.name.toLowerCase().endsWith(".tsv") &&
    !file.name.toLowerCase().endsWith(".xls") &&
    !file.name.toLowerCase().endsWith(".xlsx") &&
    !file.name.toLowerCase().endsWith(".json")
  ) {
    uploadError.value = "CSV 또는 스프레드시트 파일만 업로드할 수 있어요.";
    return;
  }

  analyticsError.value = null;
  uploadError.value = null;
  exportMessage.value = null;
  isUploading.value = true;

  try {
    const sessionId = await ensureActiveSession();
    const detail = await uploadDataset(file, sessionId);
    const [preview, profile] = await Promise.all([
      fetchDatasetPreview(detail.id),
      fetchDatasetProfile(detail.id),
    ]);
    const dataset = mapDatasetDetailToAsset({ detail, preview, profile });
    const sessionState = ensureSessionState(sessionId, DEFAULT_SESSION_TITLE);
    sessionState.datasets = [
      dataset,
      ...sessionState.datasets.filter((item) => item.id !== dataset.id),
    ];
    sessionState.analyticsPayload = null;
    sessionState.workspacePayload = null;
    sessionState.messages = [
      ...sessionState.messages,
      {
        role: "assistant",
        author: "AI 데이터 분석가",
        text: `${dataset.filename} 업로드를 완료했어요. 이제 같은 데이터셋 ID로 채팅과 분석을 이어서 실행할 수 있어요.`,
        bullets: [
          {
            text: `${dataset.profile?.rowCount ?? 0}행 / ${dataset.profile?.columnCount ?? 0}열 프로파일을 반영했어요`,
          },
          { text: "오른쪽 패널에 서버 기준 미리보기와 프로파일이 반영돼요" },
          { text: "이제 프롬프트 전송과 분석 실행이 같은 데이터셋을 사용해요" },
        ],
      },
    ];
    activeSessionId.value = sessionId;
    syncSessionSummaryWithState(sessionId);
    await loadDatasets();
  } catch {
    uploadError.value =
      "데이터셋 업로드에 실패했어요. CSV 또는 스프레드시트 파일로 다시 시도해 주세요.";
  } finally {
    isUploading.value = false;
  }
}

async function runAnalysis() {
  analyticsError.value = null;
  exportMessage.value = null;
  const sessionId = await ensureActiveSession();
  const sessionState = ensureSessionState(sessionId, DEFAULT_SESSION_TITLE);
  const primaryDataset = sessionState.datasets[0];
  if (!primaryDataset) {
    analyticsError.value = "분석을 실행하려면 먼저 데이터셋을 업로드해 주세요.";
    return;
  }

  isRunningAnalysis.value = true;
  try {
    const analysis = await createAnalysis({
      sessionId,
      datasetId: primaryDataset.id,
      analysisType: "dataset_profile",
      prompt: `Generate a dashboard-ready profile for ${primaryDataset.filename}.`,
    });
    sessionState.analyticsPayload = analysis.analytics;
    sessionState.workspacePayload = analysis.workspace;
    sessionState.messages = [
      ...sessionState.messages,
      {
        role: "assistant",
        author: "AI 데이터 분석가",
        text:
          analysis.analytics?.insights[0]?.body ??
          "분석이 완료되어 실시간 분석 패널을 업데이트했어요.",
      },
    ];
    syncSessionSummaryWithState(sessionId);
  } catch {
    analyticsError.value =
      "분석을 시작하지 못했어요. 잠시 후 다시 시도해 주세요.";
  } finally {
    isRunningAnalysis.value = false;
  }
}

async function handleSuggestedPrompt(prompt: string) {
  if (
    !prompt ||
    isSending.value ||
    isUploading.value ||
    isRunningAnalysis.value
  )
    return;
  await handleSendMessage(prompt);
}

async function handleInsightAction() {
  if (isSending.value || isUploading.value || isRunningAnalysis.value) return;
  if (activeDataset.value) {
    await runAnalysis();
    return;
  }
  openDatasetPicker();
}

async function handleRenameSession(payload: {
  sessionId: string;
  title: string;
}) {
  try {
    isSessionMutating.value = true;
    const updated = await updateSessionTitle(payload.sessionId, payload.title);
    updateSessionSummary(payload.sessionId, {
      title: updated.title,
      updatedAt: updated.updated_at,
    });
    const state = sessionStates.value[payload.sessionId];
    if (state) {
      state.title = updated.title;
    }
    sessionHubError.value = null;
  } catch (error) {
    sessionHubError.value =
      error instanceof Error ? error.message : "세션 제목을 수정하지 못했어요.";
  } finally {
    isSessionMutating.value = false;
  }
}

async function handleDeleteSession(sessionId: string) {
  try {
    isSessionMutating.value = true;
    await deleteSession(sessionId);
    sessionSummaries.value = sessionSummaries.value.filter(
      (session) => session.id !== sessionId,
    );
    delete sessionStates.value[sessionId];
    delete hydratedSessionIds.value[sessionId];
    datasetsLibrary.value = datasetsLibrary.value.map((dataset) => ({
      ...dataset,
      linkedSessionIds: dataset.linkedSessionIds.filter(
        (id) => id !== sessionId,
      ),
      linkedSessionCount: dataset.linkedSessionIds.filter(
        (id) => id !== sessionId,
      ).length,
    }));
    if (activeSessionId.value === sessionId) {
      const nextSessionId = sessionSummaries.value[0]?.id ?? null;
      activeSessionId.value = nextSessionId;
      if (nextSessionId) {
        await selectSession(nextSessionId, "dashboard");
      } else {
        await createAndSelectSession();
      }
    }
    sessionHubError.value = null;
  } catch (error) {
    sessionHubError.value =
      error instanceof Error ? error.message : "세션을 삭제하지 못했어요.";
  } finally {
    isSessionMutating.value = false;
  }
}

async function handleSelectDataset(datasetId: string) {
  selectedDatasetId.value = datasetId;
  await ensureDatasetLibraryDetails(datasetId);
}

async function handleAttachDataset(datasetId: string) {
  const sessionId = await ensureActiveSession();
  try {
    isDatasetMutating.value = true;
    const linked = await attachDatasetToSession(sessionId, datasetId);
    const details = await ensureDatasetLibraryDetails(datasetId);
    if (details) {
      const state = ensureSessionState(
        sessionId,
        activeSessionSummary.value?.title ?? DEFAULT_SESSION_TITLE,
      );
      const asset = mapDatasetDetailToAsset({
        detail: {
          id: details.id,
          filename: details.filename,
          content_type: details.contentType,
          storage_path: details.storagePath,
          created_at: details.createdAt,
        },
        preview: details.preview
          ? {
              dataset_id: details.id,
              columns: details.preview.columns,
              rows: details.preview.rows,
            }
          : null,
        profile: details.profile
          ? {
              dataset_id: details.id,
              profile: {
                row_count: details.profile.rowCount,
                column_count: details.profile.columnCount,
                columns: details.profile.columns.map((column) => ({
                  name: column.name,
                  dtype: column.dtype,
                  null_ratio: column.nullRatio,
                  sample_values: column.sampleValues,
                })),
                suggested_prompts: details.profile.suggestedPrompts,
              },
            }
          : null,
      });
      const byId = new Map(
        [...state.datasets, asset].map((dataset) => [dataset.id, dataset]),
      );
      state.datasets = linked.dataset_ids
        .map((id) => byId.get(id))
        .filter((dataset): dataset is NonNullable<typeof dataset> =>
          Boolean(dataset),
        );
      syncSessionSummaryWithState(sessionId);
    }
    await loadDatasets();
    datasetLibraryError.value = null;
  } catch (error) {
    datasetLibraryError.value =
      error instanceof Error ? error.message : "데이터셋 연결에 실패했어요.";
  } finally {
    isDatasetMutating.value = false;
  }
}

async function handleDetachDataset(datasetId: string) {
  const sessionId = activeSessionId.value;
  if (!sessionId) {
    datasetLibraryError.value =
      "활성 세션이 없어 연결 해제를 진행할 수 없어요.";
    return;
  }
  try {
    isDatasetMutating.value = true;
    const linked = await detachDatasetFromSession(sessionId, datasetId);
    const state = ensureSessionState(
      sessionId,
      activeSessionSummary.value?.title ?? DEFAULT_SESSION_TITLE,
    );
    state.datasets = state.datasets.filter((dataset) =>
      linked.dataset_ids.includes(dataset.id),
    );
    syncSessionSummaryWithState(sessionId);
    await loadDatasets();
    datasetLibraryError.value = null;
  } catch (error) {
    datasetLibraryError.value =
      error instanceof Error
        ? error.message
        : "데이터셋 연결 해제에 실패했어요.";
  } finally {
    isDatasetMutating.value = false;
  }
}

async function handleDeleteDataset(datasetId: string) {
  try {
    isDatasetMutating.value = true;
    await deleteDataset(datasetId);
    datasetsLibrary.value = datasetsLibrary.value.filter(
      (dataset) => dataset.id !== datasetId,
    );
    for (const state of Object.values(sessionStates.value)) {
      state.datasets = state.datasets.filter(
        (dataset) => dataset.id !== datasetId,
      );
    }
    if (selectedDatasetId.value === datasetId) {
      selectedDatasetId.value = datasetsLibrary.value[0]?.id ?? null;
    }
    if (activeSessionId.value) {
      syncSessionSummaryWithState(activeSessionId.value);
    }
    datasetLibraryError.value = null;
  } catch (error) {
    datasetLibraryError.value =
      error instanceof Error
        ? error.message
        : "연결된 데이터셋은 삭제할 수 없어요.";
  } finally {
    isDatasetMutating.value = false;
  }
}

const activeSessionState = computed(() => {
  const sessionId = activeSessionId.value;
  return sessionId ? (sessionStates.value[sessionId] ?? null) : null;
});
const activeSessionSummary = computed(
  () =>
    sessionSummaries.value.find(
      (session) => session.id === activeSessionId.value,
    ) ?? null,
);
const activeDataset = computed(
  () => activeSessionState.value?.datasets[0] ?? null,
);

const recentSessions = computed<SessionItem[]>(() => {
  const keyword = searchQuery.value.trim().toLowerCase();
  if (!keyword) return sessionSummaries.value;
  return sessionSummaries.value.filter((session) =>
    session.title.toLowerCase().includes(keyword),
  );
});

const conversation = computed<ConversationData>(() => ({
  messages: activeSessionState.value?.messages ?? createWelcomeMessages(),
  thinkingLabel: isSending.value
    ? isSendingInteraction.value
      ? "파일을 업로드하고 데이터를 분석하고 있어요..."
      : "ChatGPT가 응답을 준비하고 있어요..."
    : isUploading.value
      ? "데이터셋을 업로드하고 있어요..."
      : isRunningAnalysis.value
        ? "분석을 실행하고 있어요..."
        : "다음 분석 요청을 입력해 주세요",
  isThinking: isSending.value || isUploading.value || isRunningAnalysis.value,
}));

const composer = computed<ComposerData>(() => {
  const chips: ComposerChip[] = [];
  chips.push({
    icon: authStatus.value.connected ? "smart_toy" : "analytics",
    label: authStatus.value.connected ? "ChatGPT 연결됨" : "백엔드 분석 모드",
    tone: authStatus.value.connected ? "primary" : "neutral",
  });
  if (activeSessionState.value?.title)
    chips.push({
      icon: "forum",
      label: activeSessionState.value.title,
      tone: "neutral",
    });
  if (activeDataset.value)
    chips.push({
      icon: "database",
      label: `${activeDataset.value.filename} · 활성`,
      tone: "primary",
    });
  const extraDatasetCount = Math.max(
    (activeSessionState.value?.datasets.length ?? 0) - 1,
    0,
  );
  if (extraDatasetCount > 0)
    chips.push({
      icon: "dataset",
      label: `추가 ${extraDatasetCount}개`,
      tone: "neutral",
    });
  if (isUploading.value)
    chips.push({
      icon: "progress_activity",
      label: "업로드 중",
      tone: "neutral",
    });
  return {
    chips,
    placeholder: activeDataset.value
      ? `${activeDataset.value.filename} 데이터에 대해 질문하거나 다른 파일을 추가해보세요...`
      : "분석 요청을 입력하고 CSV 같은 파일을 함께 첨부해보세요...",
  };
});

const analyticsPayload = computed(
  () => activeSessionState.value?.analyticsPayload ?? null,
);
const workspacePayload = computed(
  () => activeSessionState.value?.workspacePayload ?? null,
);
const canExportReport = computed(() =>
  Boolean(
    activeDataset.value ||
    analyticsPayload.value?.summary_cards?.length ||
    analyticsPayload.value?.charts?.length ||
    analyticsPayload.value?.tables?.length ||
    analyticsPayload.value?.insights?.length ||
    activeSessionState.value?.messages?.length,
  ),
);
const effectiveHeaderSearchQuery = computed(() =>
  currentScreen.value === "sessions"
    ? sessionHubSearchQuery.value
    : currentScreen.value === "datasets"
      ? datasetLibrarySearchQuery.value
      : searchQuery.value,
);

watch(analyticsPaneWidth, (width) => {
  window.localStorage.setItem(
    ANALYTICS_PANE_WIDTH_STORAGE_KEY,
    String(clampAnalyticsPaneWidth(width)),
  );
});

watch(activeSessionId, () => {
  exportMessage.value = null;
});

watch(currentScreen, async (screen) => {
  if (screen === "datasets" && datasetsLibrary.value.length === 0) {
    await loadDatasets();
  }
});

onMounted(async () => {
  const controller = new AbortController();
  restoreAnalyticsPaneWidth();
  window.addEventListener("message", handleOpenAiAuthMessage);
  window.addEventListener("focus", handleWindowFocus);
  try {
    const health = await fetchHealthcheck(controller.signal);
    connectionStatus.value = health.status === "ok" ? "connected" : "offline";
  } catch {
    connectionStatus.value = "offline";
  }
  await loadAuthStatus();
  await loadSessions();
  await loadDatasets();
});

onUnmounted(() => {
  if (authPollTimer !== null) window.clearInterval(authPollTimer);
  stopAnalyticsPaneResize();
  window.removeEventListener("message", handleOpenAiAuthMessage);
  window.removeEventListener("focus", handleWindowFocus);
  authPopup = null;
});
</script>

<template>
  <div class="portal-layout">
    <PortalSidebar
      :sidebar="{ ...shellSidebar, recentSessions }"
      :active-screen="currentScreen"
      :active-session-id="activeSessionId"
      @primary-action="handleScreenChange"
      @select-session="(sessionId) => selectSession(sessionId, 'dashboard')"
    />

    <div class="portal-main-shell">
      <PortalHeader
        :header="shellHeader"
        :search-query="effectiveHeaderSearchQuery"
        :connection-status="connectionStatus"
        :auth-status="authStatus"
        :is-connecting="isConnecting"
        @connect-open-ai="connectOpenAi"
        @search-change="handleHeaderSearchChange"
      />

      <div v-if="authError || exportMessage" class="portal-status-messages">
        <p v-if="authError" class="auth-error">{{ authError }}</p>
        <p v-if="exportMessage" class="export-message">{{ exportMessage }}</p>
      </div>

      <div class="portal-screen-shell">
        <template v-if="currentScreen === 'dashboard'">
          <div
            class="portal-main-grid"
            :class="{
              'portal-main-grid--resizing': isResizingAnalyticsPane,
              'portal-main-grid--analytics-fullscreen': isAnalyticsFullscreen,
            }"
            :style="{ '--analytics-pane-width': `${analyticsPaneWidth}px` }"
          >
            <PortalConversationPane
              :conversation="conversation"
              :composer="composer"
              :send-disabled="isSending || isRunningAnalysis"
              :attach-disabled="isUploading || isRunningAnalysis"
              :error-message="chatError || uploadError"
              :attached-file-name="pendingAttachment?.name ?? null"
              :attached-file-meta="
                pendingAttachment
                  ? `${formatFileSize(pendingAttachment.size)} · 메시지와 함께 전송`
                  : null
              "
              @attach="openInteractionPicker"
              @drop-file="queueInteractionFile"
              @remove-attachment="clearPendingAttachment"
              @send="handleSendMessage"
            />
            <button
              class="pane-resizer"
              type="button"
              aria-label="분석 패널 너비 조절"
              @pointerdown="startAnalyticsPaneResize"
            >
              <span></span>
            </button>
            <PortalAnalyticsPane
              :analytics="shellAnalytics"
              :analytics-payload="analyticsPayload"
              :workspace-payload="workspacePayload"
              :dataset-asset="activeDataset"
              :is-loading="isSending || isUploading || isRunningAnalysis"
              :error-message="analyticsError"
              :is-fullscreen="isAnalyticsFullscreen"
              :export-disabled="!canExportReport"
              @prompt-click="handleSuggestedPrompt"
              @insight-action="handleInsightAction"
              @toggle-fullscreen="toggleAnalyticsFullscreen"
              @export-report="exportAnalyticsReport"
            />
          </div>
        </template>

        <PortalSessionHub
          v-else-if="currentScreen === 'sessions'"
          :sessions="sessionSummaries"
          :active-session-id="activeSessionId"
          :search-query="sessionHubSearchQuery"
          :is-busy="isSessionMutating"
          :error-message="sessionHubError"
          @search-change="handleSessionHubSearchChange"
          @open-session="(sessionId) => selectSession(sessionId, 'dashboard')"
          @rename-session="handleRenameSession"
          @delete-session="handleDeleteSession"
          @create-session="createAndSelectSession"
        />

        <PortalDatasetLibrary
          v-else
          :datasets="datasetsLibrary"
          :selected-dataset-id="selectedDatasetId"
          :active-session-id="activeSessionId"
          :search-query="datasetLibrarySearchQuery"
          :is-busy="isDatasetMutating"
          :error-message="datasetLibraryError"
          @search-change="handleDatasetLibrarySearchChange"
          @select-dataset="handleSelectDataset"
          @attach-dataset="handleAttachDataset"
          @detach-dataset="handleDetachDataset"
          @delete-dataset="handleDeleteDataset"
        />
      </div>
    </div>

    <input
      ref="interactionPickerRef"
      class="dataset-picker"
      type="file"
      accept=".csv,.tsv,.xls,.xlsx,.json,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
      @change="handleInteractionFileChange"
    />
    <input
      ref="datasetPickerRef"
      class="dataset-picker"
      type="file"
      accept=".csv,.tsv,.xls,.xlsx,.json,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
      @change="handleDatasetFileChange"
    />
  </div>
</template>

<style scoped>
.portal-layout {
  position: relative;
  height: 100vh;
  display: grid;
  grid-template-columns: 288px minmax(0, 1fr);
  grid-template-rows: minmax(0, 1fr);
  gap: 24px;
  padding: 24px;
  overflow: hidden;
}

.portal-main-shell {
  min-width: 0;
  min-height: 0;
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 20px;
  overflow: hidden;
}

.portal-status-messages {
  display: grid;
  gap: 8px;
}

.portal-screen-shell {
  min-height: 0;
  height: 100%;
  flex: 1;
  display: grid;
  gap: 18px;
  overflow: hidden;
}

.portal-main-grid {
  min-height: 0;
  height: 100%;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 20px minmax(
      320px,
      var(--analytics-pane-width, 420px)
    );
  grid-template-rows: minmax(0, 1fr);
  gap: 0;
  align-items: stretch;
}

.portal-main-grid :deep(.conversation-shell),
.portal-main-grid :deep(.analytics-shell) {
  min-height: 0;
  height: 100%;
}

.portal-main-grid--resizing {
  user-select: none;
  cursor: col-resize;
}

.pane-resizer {
  position: relative;
  width: 20px;
  height: 100%;
  cursor: col-resize;
}

.pane-resizer span {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 3px;
  height: 3px;
  border-radius: 999px;
  transform: translate(-50%, -50%);
  background: rgba(24, 74, 140, 0.22);
  box-shadow:
    0 -7px 0 rgba(24, 74, 140, 0.22),
    0 7px 0 rgba(24, 74, 140, 0.22);
}

.auth-error,
.export-message {
  margin: -8px 4px 0;
  font-size: 0.86rem;
}

.auth-error {
  color: #9b3b3b;
}
.export-message {
  color: #1d6b45;
}

.portal-main-grid--analytics-fullscreen {
  grid-template-columns: minmax(0, 1fr);
}

.portal-main-grid--analytics-fullscreen :deep(.conversation-shell),
.portal-main-grid--analytics-fullscreen .pane-resizer {
  display: none;
}

.dataset-picker {
  position: absolute;
  width: 1px;
  height: 1px;
  opacity: 0;
  pointer-events: none;
}

@media (max-width: 1280px) {
  .portal-layout {
    grid-template-columns: 248px minmax(0, 1fr);
  }

  .portal-main-grid {
    grid-template-columns: minmax(0, 1fr);
    gap: 20px;
  }

  .pane-resizer {
    display: none;
  }
}

@media (max-width: 960px) {
  .portal-layout {
    grid-template-columns: minmax(0, 1fr);
    padding: 16px;
    height: auto;
    min-height: 100vh;
    overflow: auto;
  }

  .portal-main-shell,
  .portal-screen-shell {
    overflow: visible;
  }
}
</style>
