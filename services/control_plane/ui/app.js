/**
 * PIXEL Production Control Plane UI Client Engine
 */

// State Management
const state = {
  token: sessionStorage.getItem('pixel_token') || '',
  user: null,
  activeTab: 'overview',
  voiceState: 'IDLE',
  ws: null,
  wsReconnectTimer: null,
  pendingApproval: null,
};

// DOM Elements
const loginModal = document.getElementById('login-modal');
const loginForm = document.getElementById('login-form');
const loginError = document.getElementById('login-error');
const appContainer = document.getElementById('app-container');
const btnLogout = document.getElementById('btn-logout');
const wsStatusPill = document.getElementById('ws-status');
const wsStatusText = document.getElementById('ws-status-text');
const globalVoiceStateBadge = document.getElementById('global-voice-state');
const voiceOrbStateText = document.getElementById('voice-orb-state');
const currentUsername = document.getElementById('current-username');
const currentUserRole = document.getElementById('current-user-role');
const navTabs = document.querySelectorAll('.nav-tab');

// 1. Authentication
async function initAuth() {
  if (state.token) {
    try {
      const res = await apiRequest('/api/v1/auth/me');
      if (res && res.user_id) {
        state.user = res;
        showApp();
        return;
      }
    } catch (e) {
      console.warn('Saved token expired or invalid', e);
    }
  }
  showLogin();
}

function showLogin() {
  loginModal.style.display = 'flex';
  appContainer.style.display = 'none';
}

function showApp() {
  loginModal.style.display = 'none';
  appContainer.style.display = 'flex';
  currentUsername.textContent = state.user.username;
  currentUserRole.textContent = state.user.role;
  currentUserRole.className = `role-badge role-${state.user.role.toLowerCase().replace('_', '-')}`;
  initWebSocket();
  loadCurrentTabData();
  initVoiceOrb();
}

loginForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  loginError.style.display = 'none';
  const username = document.getElementById('username').value.trim();
  const password = document.getElementById('password').value;

  try {
    const res = await fetch('/api/v1/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
    if (!res.ok) {
      throw new Error((await res.json()).detail || 'Login failed');
    }
    const data = await res.json();
    state.token = data.access_token;
    state.user = data.user;
    sessionStorage.setItem('pixel_token', state.token);
    showApp();
    showToast('Signed in successfully', 'success');
  } catch (err) {
    loginError.textContent = err.message;
    loginError.style.display = 'block';
  }
});

btnLogout.addEventListener('click', async () => {
  try {
    await apiRequest('/api/v1/auth/logout', 'POST');
  } catch (e) {}
  state.token = '';
  state.user = null;
  sessionStorage.removeItem('pixel_token');
  if (state.ws) state.ws.close();
  showLogin();
  showToast('Logged out', 'info');
});

// 2. HTTP API Request Helper
async function apiRequest(endpoint, method = 'GET', body = null) {
  const headers = { 'Content-Type': 'application/json' };
  if (state.token) {
    headers['Authorization'] = `Bearer ${state.token}`;
  }
  const opts = { method, headers };
  if (body) {
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(endpoint, opts);
  if (res.status === 401) {
    state.token = '';
    sessionStorage.removeItem('pixel_token');
    showLogin();
    throw new Error('Unauthorized');
  }
  if (!res.ok) {
    const errData = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(errData.detail || 'API request failed');
  }
  return await res.json();
}

// 3. Navigation Tabs
navTabs.forEach((tab) => {
  tab.addEventListener('click', () => {
    navTabs.forEach((t) => t.classList.remove('active'));
    document.querySelectorAll('.tab-pane').forEach((p) => p.classList.remove('active'));
    tab.classList.add('active');
    const target = tab.getAttribute('data-tab');
    state.activeTab = target;
    document.getElementById(`tab-${target}`).classList.add('active');
    loadCurrentTabData();
  });
});

function loadCurrentTabData() {
  if (state.activeTab === 'overview') loadOverview();
  else if (state.activeTab === 'voice') loadConversations();
  else if (state.activeTab === 'tasks') loadTasks();
  else if (state.activeTab === 'scheduler') loadScheduler();
  else if (state.activeTab === 'memory') loadMemory();
  else if (state.activeTab === 'devices') loadDevices();
  else if (state.activeTab === 'audit') loadAuditLogs();
}

// 4. WebSocket Real-time Stream
function initWebSocket() {
  if (state.ws) {
    state.ws.close();
  }
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/ws/control-plane?token=${state.token}`;
  state.ws = new WebSocket(wsUrl);

  state.ws.onopen = () => {
    wsStatusPill.className = 'status-pill connected';
    wsStatusText.textContent = 'Live Stream Active';
  };

  state.ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      handleWebSocketMessage(data);
    } catch (e) {
      console.error('Failed to parse WS event', e);
    }
  };

  state.ws.onclose = () => {
    wsStatusPill.className = 'status-pill disconnected';
    wsStatusText.textContent = 'Disconnected (Reconnecting...)';
    clearTimeout(state.wsReconnectTimer);
    state.wsReconnectTimer = setTimeout(initWebSocket, 3000);
  };

  state.ws.onerror = (err) => {
    console.warn('WS error', err);
  };
}

function handleWebSocketMessage(msg) {
  // Add to live event stream UI
  const logContainer = document.getElementById('live-event-log');
  if (logContainer) {
    const item = document.createElement('div');
    item.className = 'event-log-item';
    item.textContent = `[${new Date().toLocaleTimeString()}] ${msg.event_type || msg.type}: ${JSON.stringify(msg.payload || msg)}`;
    logContainer.prepend(item);
    if (logContainer.children.length > 50) logContainer.lastChild.remove();
  }

  if (msg.event_type === 'CONVERSATION_UPDATE') {
    if (msg.payload && msg.payload.session) {
      updateVoiceState(msg.payload.session.voice_state || 'LISTENING');
      if (state.activeTab === 'voice') loadConversations();
    }
  } else if (msg.event_type === 'TASK_STATE_CHANGED') {
    if (state.activeTab === 'tasks') loadTasks();
    if (state.activeTab === 'overview') loadOverview();
  } else if (msg.event_type === 'DEVICE_PRESENCE') {
    if (state.activeTab === 'devices') loadDevices();
    if (state.activeTab === 'overview') loadOverview();
  } else if (msg.event_type === 'APPROVAL_REQUIRED') {
    promptApprovalCard(msg.payload);
  }
}

function updateVoiceState(newState) {
  state.voiceState = newState;
  globalVoiceStateBadge.textContent = newState;
  globalVoiceStateBadge.className = `state-badge state-${newState.toLowerCase()}`;
  voiceOrbStateText.textContent = newState;
}

// 5. Data Loaders

// Overview
async function loadOverview() {
  try {
    const overview = await apiRequest('/api/v1/overview/system');
    document.getElementById('metric-sys-status').textContent = overview.is_online ? 'HEALTHY' : 'DEGRADED';
    document.getElementById('metric-devices-count').textContent = overview.active_devices_count;
    document.getElementById('metric-tasks-count').textContent = overview.active_tasks_count;
    document.getElementById('metric-audit-count').textContent = overview.resource_stats.total_audit_records || 0;

    const tbody = document.getElementById('services-health-body');
    tbody.innerHTML = '';
    overview.services.forEach((s) => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td><strong>${s.service_name}</strong></td>
        <td><span class="badge ${s.is_healthy ? 'badge-success' : 'badge-danger'}">${s.is_healthy ? 'ONLINE' : 'OFFLINE'}</span></td>
        <td><code>${s.latency_ms.toFixed(2)}ms</code></td>
        <td><pre style="margin:0;font-size:11px;">${JSON.stringify(s.details)}</pre></td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error('Error loading overview', err);
  }
}

document.getElementById('btn-refresh-health').addEventListener('click', loadOverview);

// Voice & Conversations
async function loadConversations() {
  try {
    const sessions = await apiRequest('/api/v1/conversations/sessions');
    const container = document.getElementById('conversations-list');
    const transcriptFeed = document.getElementById('live-transcript-feed');
    container.innerHTML = '';

    if (!sessions || sessions.length === 0) {
      container.innerHTML = '<div class="empty-state">No active sessions.</div>';
      transcriptFeed.innerHTML = '<div class="empty-state">No dialogue history.</div>';
      return;
    }

    sessions.forEach((s) => {
      const card = document.createElement('div');
      card.className = 'device-card';
      card.style.marginBottom = '10px';
      card.innerHTML = `
        <div class="device-card-header">
          <span class="device-name">${s.session_id}</span>
          <span class="badge badge-info">${s.voice_state}</span>
        </div>
        <div class="device-stats">
          <div>Device: <code>${s.device_id}</code></div>
          <div>Turns: <strong>${s.turn_count}</strong></div>
          <div>Last Activity: ${new Date(s.last_activity).toLocaleTimeString()}</div>
        </div>
      `;
      container.appendChild(card);
    });

    const active = sessions[0];
    if (active && active.recent_turns) {
      transcriptFeed.innerHTML = '';
      active.recent_turns.forEach((turn) => {
        const item = document.createElement('div');
        item.className = 'transcript-turn';
        item.innerHTML = `
          <div class="transcript-user"><strong>User:</strong> ${turn.user_query}</div>
          <div class="transcript-assistant"><strong>Pixel:</strong> ${turn.assistant_response}</div>
        `;
        transcriptFeed.appendChild(item);
      });
    }
  } catch (err) {
    console.error('Error loading conversations', err);
  }
}

// Tasks
async function loadTasks() {
  try {
    const tasks = await apiRequest('/api/v1/tasks');
    const tbody = document.getElementById('tasks-table-body');
    tbody.innerHTML = '';

    if (!tasks || tasks.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" class="empty-state">No autonomous tasks found.</td></tr>';
      return;
    }

    tasks.forEach((t) => {
      const tr = document.createElement('tr');
      const stateBadge = getTaskBadge(t.state);
      tr.innerHTML = `
        <td><code>${t.task_id}</code></td>
        <td><strong>${t.objective}</strong></td>
        <td>${stateBadge}</td>
        <td><code>${t.schedule_type}</code></td>
        <td>${t.budget_consumed_steps} / ${t.budget_max_steps}</td>
        <td>
          <button class="btn btn-sm btn-ghost" onclick="triggerTaskAction('${t.task_id}', 'TRIGGER_NOW')">Run</button>
          ${t.is_paused ? `<button class="btn btn-sm btn-ghost" onclick="triggerTaskAction('${t.task_id}', 'RESUME')">Resume</button>` : `<button class="btn btn-sm btn-ghost" onclick="triggerTaskAction('${t.task_id}', 'PAUSE')">Pause</button>`}
          <button class="btn btn-sm btn-ghost text-danger" onclick="triggerTaskAction('${t.task_id}', 'CANCEL')">Cancel</button>
        </td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error('Error loading tasks', err);
  }
}

function getTaskBadge(taskState) {
  if (taskState === 'COMPLETED') return `<span class="badge badge-success">${taskState}</span>`;
  if (taskState === 'RUNNING') return `<span class="badge badge-info">${taskState}</span>`;
  if (taskState === 'AWAITING_APPROVAL') return `<span class="badge badge-warning">${taskState}</span>`;
  if (taskState === 'FAILED' || taskState === 'CANCELLED' || taskState === 'DRIFT_DETECTED' || taskState === 'BUDGET_EXCEEDED') return `<span class="badge badge-danger">${taskState}</span>`;
  return `<span class="badge">${taskState}</span>`;
}

window.triggerTaskAction = async function (taskId, action) {
  try {
    const res = await apiRequest(`/api/v1/tasks/${taskId}/action`, 'POST', { action });
    showToast(res.message, res.success ? 'success' : 'error');
    loadTasks();
  } catch (err) {
    showToast(err.message, 'error');
  }
};

// Scheduler
async function loadScheduler() {
  try {
    const jobs = await apiRequest('/api/v1/scheduler/jobs');
    const tbody = document.getElementById('scheduler-table-body');
    tbody.innerHTML = '';

    if (!jobs || jobs.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" class="empty-state">No scheduled jobs registered.</td></tr>';
      return;
    }

    jobs.forEach((j) => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td><code>${j.task_id}</code></td>
        <td><strong>${j.objective}</strong></td>
        <td><span class="badge">${j.schedule_type}</span></td>
        <td><code>${j.schedule_expr || 'Immediate'}</code></td>
        <td>${j.next_run_at ? new Date(j.next_run_at).toLocaleString() : 'N/A'}</td>
        <td>
          <button class="btn btn-sm btn-ghost" onclick="triggerTaskAction('${j.task_id}', 'TRIGGER_NOW')">Run</button>
          <button class="btn btn-sm btn-ghost" onclick="triggerTaskAction('${j.task_id}', 'CANCEL')">Cancel</button>
        </td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error('Error loading scheduler', err);
  }
}

// Memory
async function loadMemory() {
  try {
    const facts = await apiRequest('/api/v1/memory/facts');
    const container = document.getElementById('memory-facts-list');
    container.innerHTML = '';

    if (!facts || facts.length === 0) {
      container.innerHTML = '<div class="empty-state">No semantic facts currently stored.</div>';
      return;
    }

    facts.forEach((f) => {
      const card = document.createElement('div');
      card.className = 'device-card';
      card.style.marginBottom = '10px';
      card.innerHTML = `
        <div class="device-card-header">
          <span class="badge badge-info">${f.category}</span>
          <span style="font-size:11px;color:var(--text-muted);">${(f.confidence * 100).toFixed(0)}% Confidence</span>
        </div>
        <div style="font-size:13px;margin:6px 0;">${f.fact_text}</div>
        <div style="font-size:11px;color:var(--text-muted);">Source: ${f.source} | ${new Date(f.created_at).toLocaleDateString()}</div>
      `;
      container.appendChild(card);
    });
  } catch (err) {
    console.error('Error loading memory facts', err);
  }
}

document.getElementById('btn-search-memory').addEventListener('click', async () => {
  const query = document.getElementById('memory-search-input').value.trim();
  if (!query) return;
  try {
    const res = await apiRequest('/api/v1/memory/search', 'POST', { query });
    const container = document.getElementById('memory-search-results');
    container.innerHTML = '';
    const facts = res.facts || [];
    const episodes = res.episodes || [];

    let html = `<h4>Semantic Facts (${facts.length})</h4>`;
    facts.forEach((f) => {
      html += `<div class="event-log-item" style="margin-bottom:6px;">${f.fact_text}</div>`;
    });
    html += `<h4 style="margin-top:14px;">Episodic Interactions (${episodes.length})</h4>`;
    episodes.forEach((ep) => {
      html += `<div class="transcript-turn" style="margin-bottom:6px;"><strong>Q:</strong> ${ep.user_query}<br><strong>A:</strong> ${ep.assistant_response}</div>`;
    });
    container.innerHTML = html;
  } catch (err) {
    showToast(err.message, 'error');
  }
});

// Devices Topology
async function loadDevices() {
  try {
    const devices = await apiRequest('/api/v1/devices');
    const container = document.getElementById('devices-grid');
    container.innerHTML = '';

    if (!devices || devices.length === 0) {
      container.innerHTML = '<div class="empty-state">No registered nodes in topology.</div>';
      return;
    }

    devices.forEach((d) => {
      const id = d.identity;
      const pres = d.presence;
      const isOnline = pres && pres.presence_state === 'ONLINE';
      const card = document.createElement('div');
      card.className = 'device-card';
      card.innerHTML = `
        <div class="device-card-header">
          <span class="device-name">${id.device_name}</span>
          <span class="badge ${isOnline ? 'badge-success' : 'badge-danger'}">${isOnline ? 'ONLINE' : 'OFFLINE'}</span>
        </div>
        <div class="device-stats">
          <div>Role: <code>${id.device_type}</code></div>
          <div>Trust State: <span class="badge">${id.trust_state}</span></div>
          <div>Capabilities: ${id.capabilities.join(', ')}</div>
          <div>RTT: <code>${pres ? pres.rtt_ms.toFixed(1) : 0}ms</code> | Battery: ${pres && pres.battery_level ? pres.battery_level + '%' : 'Mains'}</div>
        </div>
        <div style="margin-top:12px;display:flex;gap:8px;">
          ${id.trust_state === 'TRUSTED' ? `<button class="btn btn-sm btn-danger" onclick="revokeDevice('${id.device_id}')">Revoke Trust</button>` : ''}
        </div>
      `;
      container.appendChild(card);
    });
  } catch (err) {
    console.error('Error loading devices', err);
  }
}

window.revokeDevice = async function (deviceId) {
  if (!confirm(`Are you sure you want to revoke device '${deviceId}'?`)) return;
  try {
    const res = await apiRequest(`/api/v1/devices/${deviceId}/action`, 'POST', { action: 'REVOKE' });
    showToast(res.message, 'success');
    loadDevices();
  } catch (err) {
    showToast(err.message, 'error');
  }
};

// Audit Logs
async function loadAuditLogs() {
  try {
    const logs = await apiRequest('/api/v1/audit/logs');
    const tbody = document.getElementById('audit-table-body');
    tbody.innerHTML = '';

    if (!logs || logs.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" class="empty-state">Audit ledger is empty.</td></tr>';
      return;
    }

    logs.reverse().forEach((l) => {
      const tr = document.createElement('tr');
      const isAllowed = l.verdict === 'ALLOW';
      tr.innerHTML = `
        <td>${new Date(l.timestamp).toLocaleTimeString()}</td>
        <td><code>${l.actor_id}</code></td>
        <td><strong>${l.tool_name}</strong></td>
        <td><span class="badge">${l.risk_class}</span></td>
        <td><span class="badge ${isAllowed ? 'badge-success' : 'badge-danger'}">${l.verdict}</span></td>
        <td>${l.execution_success === true ? '✅ SUCCESS' : l.execution_success === false ? '❌ FAILED' : '—'}</td>
        <td><code>${l.trace_id.substring(0, 10)}...</code></td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error('Error loading audit logs', err);
  }
}

document.getElementById('btn-refresh-audit').addEventListener('click', loadAuditLogs);

// 6. Modals & Action Approval Card Handling
const taskModal = document.getElementById('task-modal');
document.getElementById('btn-open-task-modal').addEventListener('click', () => { taskModal.style.display = 'flex'; });
document.getElementById('btn-close-task-modal').addEventListener('click', () => { taskModal.style.display = 'none'; });

document.getElementById('create-task-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const objective = document.getElementById('task-objective').value.trim();
  const schedule_type = document.getElementById('task-schedule-type').value;
  const schedule_expr = document.getElementById('task-schedule-expr').value.trim() || null;
  const max_steps = parseInt(document.getElementById('task-max-steps').value);
  const max_tool_calls = parseInt(document.getElementById('task-max-tools').value);

  try {
    await apiRequest('/api/v1/tasks', 'POST', {
      objective,
      schedule_type,
      schedule_expr,
      max_steps,
      max_tool_calls,
    });
    taskModal.style.display = 'none';
    showToast('Task created and scheduled', 'success');
    loadTasks();
  } catch (err) {
    showToast(err.message, 'error');
  }
});

const forgetModal = document.getElementById('forget-modal');
document.getElementById('btn-open-forget-modal').addEventListener('click', () => { forgetModal.style.display = 'flex'; });
document.getElementById('btn-close-forget-modal').addEventListener('click', () => { forgetModal.style.display = 'none'; });

document.getElementById('forget-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const keyword = document.getElementById('forget-keyword').value.trim();
  try {
    const res = await apiRequest('/api/v1/memory/forget', 'POST', { keyword });
    forgetModal.style.display = 'none';
    showToast(`Purged ${res.deleted_records_count} records for '${keyword}'`, 'success');
    loadMemory();
  } catch (err) {
    showToast(err.message, 'error');
  }
});

function promptApprovalCard(payload) {
  state.pendingApproval = payload;
  document.getElementById('approval-tool-name').textContent = payload.tool_name || 'System Command';
  document.getElementById('approval-risk-class').textContent = payload.risk_class || 'HIGH_IMPACT';
  document.getElementById('approval-task-id').textContent = payload.task_id || 'N/A';
  document.getElementById('approval-tool-reason').textContent = payload.reason || 'Action requires operator sign-off.';
  document.getElementById('approval-card-modal').style.display = 'flex';
}

document.getElementById('btn-confirm-approval').addEventListener('click', async () => {
  if (!state.pendingApproval) return;
  const taskId = state.pendingApproval.task_id;
  try {
    await apiRequest(`/api/v1/tasks/${taskId}/action`, 'POST', {
      action: 'APPROVE',
      confirmation_token: state.pendingApproval.confirmation_token,
    });
    showToast('Action approved by operator', 'success');
  } catch (err) {
    showToast(err.message, 'error');
  }
  document.getElementById('approval-card-modal').style.display = 'none';
});

document.getElementById('btn-reject-approval').addEventListener('click', async () => {
  if (!state.pendingApproval) return;
  const taskId = state.pendingApproval.task_id;
  try {
    await apiRequest(`/api/v1/tasks/${taskId}/action`, 'POST', { action: 'REJECT' });
    showToast('Action rejected', 'info');
  } catch (err) {
    showToast(err.message, 'error');
  }
  document.getElementById('approval-card-modal').style.display = 'none';
});

// Toast Utility
function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 4000);
}

// 7. Dynamic VoiceOrb Canvas Visualizer
function initVoiceOrb() {
  const canvas = document.getElementById('voice-orb-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  let angle = 0;

  function render() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const cx = canvas.width / 2;
    const cy = canvas.height / 2;
    const r = 70;

    let color1 = 'rgba(100, 116, 139, 0.4)';
    let color2 = 'rgba(6, 182, 212, 0.6)';

    if (state.voiceState === 'LISTENING') {
      color1 = 'rgba(6, 182, 212, 0.8)';
      color2 = 'rgba(34, 211, 238, 1)';
    } else if (state.voiceState === 'THINKING') {
      color1 = 'rgba(99, 102, 241, 0.8)';
      color2 = 'rgba(168, 85, 247, 1)';
    } else if (state.voiceState === 'SPEAKING') {
      color1 = 'rgba(16, 185, 129, 0.8)';
      color2 = 'rgba(52, 211, 153, 1)';
    } else if (state.voiceState === 'EXECUTING') {
      color1 = 'rgba(245, 158, 11, 0.8)';
      color2 = 'rgba(251, 191, 36, 1)';
    }

    // Outer Glow Ring
    ctx.beginPath();
    ctx.arc(cx, cy, r + Math.sin(angle * 2) * 5, 0, Math.PI * 2);
    ctx.strokeStyle = color1;
    ctx.lineWidth = 4;
    ctx.stroke();

    // Inner Pulsing Orb
    const grad = ctx.createRadialGradient(cx, cy, 10, cx, cy, r);
    grad.addColorStop(0, color2);
    grad.addColorStop(1, 'rgba(8, 9, 12, 0)');
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.arc(cx, cy, r - 5, 0, Math.PI * 2);
    ctx.fill();

    angle += 0.03;
    requestAnimationFrame(render);
  }

  render();
}

// Start
document.addEventListener('DOMContentLoaded', initAuth);
