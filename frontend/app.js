const submitBtn = document.getElementById("submitBtn");
const resultEl = document.getElementById("result");
const loadingEl = document.getElementById("loading");
const historyListEl = document.getElementById("historyList");
const metaInfoEl = document.getElementById("metaInfo");
const searchReportsBtn = document.getElementById("searchReportsBtn");
const reportSearchListEl = document.getElementById("reportSearchList");
const compareBtn = document.getElementById("compareBtn");
const configBannerEl = document.getElementById("configBanner");
const structuredPanelEl = document.getElementById("structuredPanel");
const chatMessagesEl = document.getElementById("chatMessages");
const chatReferenceEl = document.getElementById("chatReference");
const chatLoadingEl = document.getElementById("chatLoading");
const chatQuestionInputEl = document.getElementById("chatQuestionInput");
const chatSendBtn = document.getElementById("chatSendBtn");
const followupCompanyEl = document.getElementById("followupCompany");

let configReady = true;
let currentReportState = null;
let chatMessages = [];
let chatReferenceState = null;

let sessionId = localStorage.getItem("session_id");
if (!sessionId) {
  sessionId = crypto.randomUUID();
  localStorage.setItem("session_id", sessionId);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function nl2br(value) {
  return escapeHtml(value).replace(/\n/g, "<br />");
}

function setInteractiveEnabled(enabled) {
  submitBtn.disabled = !enabled;
  searchReportsBtn.disabled = !enabled;
  compareBtn.disabled = !enabled;
  chatSendBtn.disabled = !enabled;
  followupCompanyEl.disabled = !enabled;
  chatQuestionInputEl.disabled = !enabled;
}

function renderActivityLog(messages) {
  const activityMessages = (messages || []).slice(-10);

  if (activityMessages.length === 0) {
    historyListEl.textContent = "아직 없음";
    return;
  }

  historyListEl.innerHTML = activityMessages
    .map(msg => {
      const preview = String(msg.content || "").slice(0, 120);
      return `<div class="history-item"><strong>${escapeHtml(msg.role)}</strong>: ${escapeHtml(preview)}</div>`;
    })
    .join("");
}

function isReportGenerationRequest(message) {
  const content = String(message?.content || "");
  return message?.role === "user" && content.includes("투자 보고서 생성 요청");
}

function toChatMessage(role, content, extra = {}) {
  return {
    role,
    content: content || "",
    summary: extra.summary || "",
    structured: extra.structured || null
  };
}

function buildChatMessagesFromHistory(messages) {
  const normalized = [];

  for (let index = 0; index < (messages || []).length; index += 1) {
    const current = messages[index];
    const next = messages[index + 1];

    if (isReportGenerationRequest(current)) {
      if (next && next.role === "assistant") {
        index += 1;
      }
      continue;
    }

    if (current.role !== "user" && current.role !== "assistant") {
      continue;
    }

    normalized.push(toChatMessage(current.role, current.content));
  }

  return normalized;
}

function updateChatReference() {
  if (!chatReferenceState) {
    chatReferenceEl.innerHTML = `
      <strong>현재 참조 보고서</strong>
      <span>아직 생성된 보고서가 없습니다.</span>
    `;
    return;
  }

  if (chatReferenceState.type === "compare") {
    chatReferenceEl.innerHTML = `
      <strong>현재 참조 보고서</strong>
      <span>
        비교 보고서: ${escapeHtml(chatReferenceState.companyLabel || "-")}
        ${chatReferenceState.overallWinner ? ` | 종합 우위: ${escapeHtml(chatReferenceState.overallWinner)}` : ""}
      </span>
    `;
    return;
  }

  chatReferenceEl.innerHTML = `
    <strong>현재 참조 보고서</strong>
    <span>
      회사: ${escapeHtml(chatReferenceState.company || "-")}
      ${chatReferenceState.reportMode ? ` | 모드: ${escapeHtml(chatReferenceState.reportMode)}` : ""}
      ${chatReferenceState.judgement ? ` | 판단: ${escapeHtml(chatReferenceState.judgement)}` : ""}
    </span>
  `;
}

function scrollChatToBottom() {
  requestAnimationFrame(() => {
    chatMessagesEl.scrollTop = chatMessagesEl.scrollHeight;
  });
}

function renderChatMessages() {
  if (!chatMessages.length) {
    chatMessagesEl.innerHTML = `
      <div class="chat-empty">후속 질문을 시작하면 여기에 대화가 쌓입니다.</div>
    `;
    updateChatReference();
    return;
  }

  chatMessagesEl.innerHTML = chatMessages
    .map(message => {
      const summary = message.summary
        ? `<div class="chat-message-summary">${escapeHtml(message.summary)}</div>`
        : "";
      const roleLabel = message.role === "user" ? "사용자" : "답변";
      return `
        <div class="chat-message ${escapeHtml(message.role)}">
          <span class="chat-message-role">${roleLabel}</span>
          <div>${nl2br(message.content)}</div>
          ${summary}
        </div>
      `;
    })
    .join("");

  updateChatReference();
  scrollChatToBottom();
}

function renderList(title, items) {
  if (!items || items.length === 0) return "";

  return `
    <div class="structured-card">
      <h3>${title}</h3>
      <ul>${items.map(item => `<li>${item}</li>`).join("")}</ul>
    </div>
  `;
}

function renderStructuredReport(data) {
  const structured = data.structured_report;
  if (!structured) {
    structuredPanelEl.classList.add("hidden");
    structuredPanelEl.innerHTML = "";
    return;
  }

  const keyPoints = (structured.key_points || []).map(point =>
    `<strong>${escapeHtml(point.title)}</strong>: ${escapeHtml(point.implication)} (근거: ${escapeHtml(point.evidence)})`
  );
  const risks = (structured.key_risks || []).map(risk =>
    `<strong>${escapeHtml(risk.risk_name)}</strong> [${escapeHtml(risk.importance)}] - ${escapeHtml(risk.current_signal)}`
  );

  structuredPanelEl.innerHTML = `
    <div class="structured-card structured-summary">
      <h3>구조화 요약</h3>
      <ul>
        <li><strong>판단</strong>: ${escapeHtml(structured.judgement || "-")}</li>
        <li><strong>한 줄 요약</strong>: ${escapeHtml(structured.one_line_summary || "-")}</li>
        <li><strong>판단 변경 조건</strong>: ${escapeHtml((structured.judgement_change_conditions || []).join(" / ") || "-")}</li>
      </ul>
    </div>
    ${renderList("핵심 투자 근거", structured.investment_thesis || [])}
    ${renderList("핵심 포인트", keyPoints)}
    ${renderList("핵심 리스크", risks)}
    ${renderList("관찰 체크리스트", structured.monitoring_checklist || [])}
    ${renderList("데이터 한계", structured.data_limitations ? [structured.data_limitations] : [])}
  `;

  structuredPanelEl.classList.remove("hidden");
}

function renderStructuredCompare(data) {
  const structured = data.structured_compare;
  if (!structured) {
    structuredPanelEl.classList.add("hidden");
    structuredPanelEl.innerHTML = "";
    return;
  }

  const comparisonPoints = (structured.comparison_points || []).map(point =>
    `<strong>${escapeHtml(point.topic)}</strong>: A(${escapeHtml(point.company_a_view)}) / B(${escapeHtml(point.company_b_view)}) / 우위: ${escapeHtml(point.winner)}`
  );

  structuredPanelEl.innerHTML = `
    <div class="structured-card structured-summary">
      <h3>비교 요약</h3>
      <ul>
        <li><strong>한 줄 요약</strong>: ${escapeHtml(structured.one_line_summary || "-")}</li>
        <li><strong>종합 우위</strong>: ${escapeHtml(structured.overall_winner || "-")}</li>
      </ul>
    </div>
    ${renderList("비교 포인트", comparisonPoints)}
    ${renderList("리스크 비교", structured.risk_comparison || [])}
    ${renderList("관찰 포인트", structured.monitoring_points || [])}
  `;

  structuredPanelEl.classList.remove("hidden");
}

function renderReportState() {
  if (!currentReportState) {
    metaInfoEl.innerHTML = "";
    structuredPanelEl.classList.add("hidden");
    structuredPanelEl.innerHTML = "";
    resultEl.textContent = "아직 생성된 보고서가 없습니다.";
    updateChatReference();
    return;
  }

  metaInfoEl.innerHTML = currentReportState.metaHtml || "";
  resultEl.textContent = currentReportState.bodyText || "";

  if (currentReportState.type === "compare") {
    renderStructuredCompare(currentReportState.raw);
  } else {
    renderStructuredReport(currentReportState.raw);
  }

  updateChatReference();
}

function setCurrentReportState(nextState) {
  currentReportState = nextState;
  renderReportState();
}

function setChatReferenceState(nextState) {
  chatReferenceState = nextState;
  updateChatReference();
}

async function loadHistory() {
  try {
    const res = await fetch(`/memory/${sessionId}`);
    const data = await res.json();
    const messages = data.messages || [];

    renderActivityLog(messages);
    chatMessages = buildChatMessagesFromHistory(messages);
    renderChatMessages();
  } catch (err) {
    historyListEl.textContent = "세션 기록을 불러오지 못했습니다.";
    chatMessages = [];
    renderChatMessages();
  }
}

async function loadConfigStatus() {
  try {
    const res = await fetch("/config-status");
    const data = await res.json();
    configReady = !!data.ready;

    if (!configReady) {
      const message = data.message || "서비스 설정이 아직 준비되지 않았습니다.";
      configBannerEl.classList.remove("hidden");
      configBannerEl.textContent = message;
      setInteractiveEnabled(false);
      resultEl.textContent = message;
      return;
    }

    configBannerEl.classList.add("hidden");
    configBannerEl.textContent = "";
    setInteractiveEnabled(true);
  } catch (err) {
    configReady = false;
    configBannerEl.classList.remove("hidden");
    configBannerEl.textContent = "설정 상태를 확인하지 못했습니다. 서비스 사용을 중단합니다.";
    setInteractiveEnabled(false);
  }
}

async function searchReports(company = "") {
  try {
    const query = new URLSearchParams();
    if (company) query.set("company", company);
    query.set("limit", "10");

    const res = await fetch(`/reports?${query.toString()}`);
    const data = await res.json();

    if (!res.ok) {
      reportSearchListEl.textContent = data.error || "보고서 검색에 실패했습니다.";
      return;
    }

    const items = data.items || [];

    if (items.length === 0) {
      reportSearchListEl.textContent = "검색 결과가 없습니다.";
      return;
    }

    reportSearchListEl.innerHTML = items
      .map(item => `
        <div class="history-item">
          <div class="report-item-title">${escapeHtml(item.company || "회사명 없음")}</div>
          <div class="report-item-meta">
            ${item.judgement ? `판단: ${escapeHtml(item.judgement)}` : ""}
            ${item.one_line_summary ? ` | ${escapeHtml(item.one_line_summary)}` : ""}
          </div>
          <div>${escapeHtml((item.final_report || "").slice(0, 120))}</div>
        </div>
      `)
      .join("");
  } catch (err) {
    reportSearchListEl.textContent = "보고서 검색에 실패했습니다.";
  }
}

function syncFollowupInputCompany(company) {
  if (!company) return;
  followupCompanyEl.value = company;
}

function getFollowupQuestion() {
  return chatQuestionInputEl.value.trim();
}

function clearFollowupInputs() {
  chatQuestionInputEl.value = "";
}

async function handleGenerateReport() {
  if (!configReady) return;

  const company = document.getElementById("company").value.trim();
  const sector = document.getElementById("sector").value.trim();
  const news = document.getElementById("news").value;
  const disclosures = document.getElementById("disclosures").value;
  const market_data = document.getElementById("market_data").value;
  const macro = document.getElementById("macro").value;

  loadingEl.classList.remove("hidden");

  try {
    const response = await fetch("/generate-report", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        session_id: sessionId,
        company,
        sector,
        news,
        disclosures,
        market_data,
        macro
      })
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "보고서 생성에 실패했습니다.");
    }

    const resolvedCompany = data.company || company;
    const resolvedJudgement = data.judgement || (data.structured_report || {}).judgement || "";
    const resolvedSummary = data.one_line_summary || (data.structured_report || {}).one_line_summary || "";
    const mode = data.report_mode || "unknown";

    setCurrentReportState({
      type: "report",
      company: resolvedCompany,
      reportMode: mode,
      judgement: resolvedJudgement,
      raw: data,
      metaHtml: `
        <span class="meta-badge">세션: ${escapeHtml(sessionId)}</span>
        <span class="meta-badge">모드: ${escapeHtml(mode)}</span>
        <span class="meta-badge">회사: ${escapeHtml(resolvedCompany)}</span>
        <span class="meta-badge">업종: ${escapeHtml(sector || "-")}</span>
        ${resolvedJudgement ? `<span class="meta-badge">판단: ${escapeHtml(resolvedJudgement)}</span>` : ""}
      `,
      bodyText: [
        resolvedSummary ? `[한 줄 요약] ${resolvedSummary}` : "",
        data.final_report || JSON.stringify(data, null, 2)
      ].filter(Boolean).join("\n\n")
    });
    setChatReferenceState({
      type: "report",
      company: resolvedCompany,
      reportMode: mode,
      judgement: resolvedJudgement
    });

    syncFollowupInputCompany(resolvedCompany);
    await loadHistory();
    await searchReports(resolvedCompany);
  } catch (error) {
    resultEl.textContent = "오류 발생: " + error.message;
  } finally {
    loadingEl.classList.add("hidden");
  }
}

async function handleCompareReport() {
  if (!configReady) return;

  const companyA = document.getElementById("companyA").value.trim();
  const sectorA = document.getElementById("sectorA").value.trim() || "반도체";
  const companyB = document.getElementById("companyB").value.trim();
  const sectorB = document.getElementById("sectorB").value.trim() || "반도체";

  loadingEl.classList.remove("hidden");

  try {
    const response = await fetch("/compare-report", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        company_a: companyA,
        sector_a: sectorA,
        company_b: companyB,
        sector_b: sectorB
      })
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "비교 보고서 생성에 실패했습니다.");
    }

    setCurrentReportState({
      type: "compare",
      companyLabel: `${companyA} vs ${companyB}`,
      overallWinner: data.overall_winner || (data.structured_compare || {}).overall_winner || "",
      raw: data,
      metaHtml: `
        <span class="meta-badge">비교 A: ${escapeHtml(companyA)}</span>
        <span class="meta-badge">비교 B: ${escapeHtml(companyB)}</span>
        <span class="meta-badge">방식: ${escapeHtml(data.comparison_mode || "compare")}</span>
        ${data.overall_winner ? `<span class="meta-badge">종합 우위: ${escapeHtml(data.overall_winner)}</span>` : ""}
      `,
      bodyText: data.final_report || JSON.stringify(data, null, 2)
    });
  } catch (error) {
    resultEl.textContent = "오류 발생: " + error.message;
  } finally {
    loadingEl.classList.add("hidden");
  }
}

async function handleFollowupQuestion() {
  if (!configReady) return;

  const company = followupCompanyEl.value.trim();
  const question = getFollowupQuestion();

  if (!company || !question) {
    return;
  }

  chatLoadingEl.classList.remove("hidden");
  chatSendBtn.disabled = true;

  try {
    const response = await fetch("/chat-followup", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        session_id: sessionId,
        company,
        question
      })
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "후속 질문에 실패했습니다.");
    }

    chatMessages.push(toChatMessage("user", question));
    chatMessages.push(
      toChatMessage(
        "assistant",
        data.answer || "",
        {
          summary: data.short_answer || (data.structured_followup || {}).short_answer || ""
        }
      )
    );

    setChatReferenceState({
      type: "report",
      company,
      reportMode: currentReportState?.type === "report" && currentReportState.company === company
        ? currentReportState.reportMode
        : "",
      judgement: currentReportState?.type === "report" && currentReportState.company === company
        ? currentReportState.judgement
        : ""
    });
    renderChatMessages();
    clearFollowupInputs();
    await loadHistory();
  } catch (error) {
    chatMessages.push(
      toChatMessage("assistant", `오류 발생: ${error.message}`)
    );
    renderChatMessages();
  } finally {
    chatLoadingEl.classList.add("hidden");
    chatSendBtn.disabled = !configReady;
  }
}

submitBtn.addEventListener("click", handleGenerateReport);
compareBtn.addEventListener("click", handleCompareReport);
chatSendBtn.addEventListener("click", handleFollowupQuestion);

chatQuestionInputEl.addEventListener("keydown", event => {
  if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
    event.preventDefault();
    handleFollowupQuestion();
  }
});

searchReportsBtn.addEventListener("click", async () => {
  if (!configReady) return;
  const company = document.getElementById("reportSearchCompany").value.trim();
  await searchReports(company);
});

loadConfigStatus().then(() => {
  renderReportState();
  renderChatMessages();

  if (configReady) {
    loadHistory();
    searchReports();
  }
});
