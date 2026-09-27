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
  else if (state.activeTab === 'plugins') { loadMarketplace(); loadPlugins(); }
  else if (state.activeTab === 'backups') loadBackups();
  else if (state.activeTab === 'connectors') { loadConnectors(); loadDeliveries(); }
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

// 8. Phase 11: Marketplace & Plugins
async function loadMarketplace() {
  try {
    const skills = await apiRequest('/api/v1/marketplace/skills');
    const grid = document.getElementById('marketplace-grid');
    grid.innerHTML = '';

    if (!skills || skills.length === 0) {
      grid.innerHTML = '<div class="empty-state">No skills available in catalog.</div>';
      return;
    }

    skills.forEach((item) => {
      const s = item.skill;
      const card = document.createElement('div');
      card.className = 'skill-card';
      const triggers = s.triggers ? s.triggers.map(t => `<span class="skill-trigger-tag">${t}</span>`).join('') : '';
      card.innerHTML = `
        <div>
          <div class="skill-header">
            <span class="skill-title">${s.display_name}</span>
            <span class="badge ${item.verified ? 'badge-success' : 'badge-warning'}">${item.verified ? 'VERIFIED' : 'COMMUNITY'}</span>
          </div>
          <div class="skill-publisher">by <code>${s.publisher}</code> | v${s.version}</div>
          <div class="skill-desc">${s.description}</div>
          <div class="skill-meta">
            <span>⭐ ${item.rating.toFixed(1)}</span>
            <span>⬇️ ${item.downloads_count} installs</span>
            <span>Caps: <code>${s.capabilities.length}</code></span>
          </div>
          <div class="skill-triggers">${triggers}</div>
        </div>
        <button class="btn btn-sm btn-primary" onclick="installSkill('${s.skill_id}')">Install & Enable</button>
      `;
      grid.appendChild(card);
    });
  } catch (err) {
    console.error('Error loading marketplace', err);
  }
}

window.installSkill = async function (skillId) {
  try {
    await apiRequest('/api/v1/marketplace/install', 'POST', { skill_id: skillId, auto_enable: true });
    showToast(`Installed skill '${skillId}'`, 'success');
    loadPlugins();
    loadMarketplace();
  } catch (err) {
    showToast(err.message, 'error');
  }
};

async function loadPlugins() {
  try {
    const plugins = await apiRequest('/api/v1/plugins');
    const tbody = document.getElementById('plugins-table-body');
    tbody.innerHTML = '';

    if (!plugins || plugins.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" class="empty-state">No plugins currently installed.</td></tr>';
      return;
    }

    plugins.forEach((p) => {
      const isEnabled = p.state === 'enabled';
      const isRevoked = p.state === 'revoked';
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td><code>${p.plugin_id}</code></td>
        <td><strong>${p.name}</strong></td>
        <td>v${p.version}</td>
        <td>${p.publisher}</td>
        <td><span class="badge ${isEnabled ? 'badge-success' : isRevoked ? 'badge-danger' : 'badge-warning'}">${p.state}</span></td>
        <td><code>${p.granted_capabilities.join(', ') || 'None'}</code></td>
        <td>
          ${!isRevoked ? (isEnabled ? `<button class="btn btn-sm btn-outline" onclick="togglePlugin('${p.plugin_id}', 'disable')">Disable</button>` : `<button class="btn btn-sm btn-primary" onclick="togglePlugin('${p.plugin_id}', 'enable')">Enable</button>`) : ''}
          ${!isRevoked ? `<button class="btn btn-sm btn-danger" onclick="revokePlugin('${p.plugin_id}')">Revoke</button>` : '<span style="color:var(--state-error);">REVOKED</span>'}
        </td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error('Error loading plugins', err);
  }
}

window.togglePlugin = async function (pluginId, action) {
  try {
    await apiRequest(`/api/v1/plugins/${pluginId}/${action}`, 'POST');
    showToast(`Plugin '${pluginId}' ${action}d`, 'success');
    loadPlugins();
  } catch (err) {
    showToast(err.message, 'error');
  }
};

window.revokePlugin = async function (pluginId) {
  if (!confirm(`Permanently revoke plugin '${pluginId}'?`)) return;
  try {
    await apiRequest(`/api/v1/plugins/${pluginId}/revoke`, 'POST');
    showToast(`Plugin '${pluginId}' revoked`, 'info');
    loadPlugins();
  } catch (err) {
    showToast(err.message, 'error');
  }
};

document.getElementById('btn-refresh-plugins').addEventListener('click', loadPlugins);
document.getElementById('btn-search-marketplace').addEventListener('click', async () => {
  const q = document.getElementById('marketplace-search-input').value.trim();
  try {
    const skills = await apiRequest(`/api/v1/marketplace/skills?query=${encodeURIComponent(q)}`);
    const grid = document.getElementById('marketplace-grid');
    grid.innerHTML = '';
    skills.forEach((item) => {
      const s = item.skill;
      const card = document.createElement('div');
      card.className = 'skill-card';
      card.innerHTML = `
        <div>
          <div class="skill-header">
            <span class="skill-title">${s.display_name}</span>
            <span class="badge ${item.verified ? 'badge-success' : 'badge-warning'}">${item.verified ? 'VERIFIED' : 'COMMUNITY'}</span>
          </div>
          <div class="skill-desc">${s.description}</div>
        </div>
        <button class="btn btn-sm btn-primary" onclick="installSkill('${s.skill_id}')">Install & Enable</button>
      `;
      grid.appendChild(card);
    });
  } catch (err) {
    showToast(err.message, 'error');
  }
});

// 9. Phase 11: Zero-Knowledge Backups
async function loadBackups() {
  try {
    const backups = await apiRequest('/api/v1/backups');
    const tbody = document.getElementById('backups-table-body');
    tbody.innerHTML = '';

    if (!backups || backups.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" class="empty-state">No encrypted backup envelopes available.</td></tr>';
      return;
    }

    backups.forEach((b) => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td><code>${b.backup_id}</code></td>
        <td><span class="badge badge-info">${b.scope}</span></td>
        <td>rev ${b.revision}</td>
        <td>${(b.size_bytes / 1024).toFixed(1)} KB</td>
        <td><code>${b.ciphertext_sha256.substring(0, 12)}...</code></td>
        <td>${new Date(b.timestamp).toLocaleString()}</td>
        <td>
          <button class="btn btn-sm btn-primary" onclick="openRestoreModal('${b.backup_id}')">Restore</button>
          <button class="btn btn-sm btn-danger" onclick="deleteBackup('${b.backup_id}')">Delete</button>
        </td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error('Error loading backups', err);
  }
}

window.openRestoreModal = function (backupId) {
  document.getElementById('restore-target-backup-id').value = backupId;
  document.getElementById('restore-backup-modal').style.display = 'flex';
};

window.deleteBackup = async function (backupId) {
  if (!confirm(`Permanently delete encrypted backup envelope '${backupId}'?`)) return;
  try {
    await apiRequest(`/api/v1/backups/${backupId}`, 'DELETE');
    showToast('Backup deleted', 'info');
    loadBackups();
  } catch (err) {
    showToast(err.message, 'error');
  }
};

const createBackupModal = document.getElementById('create-backup-modal');
document.getElementById('btn-open-create-backup').addEventListener('click', () => { createBackupModal.style.display = 'flex'; });
document.getElementById('btn-close-backup-modal').addEventListener('click', () => { createBackupModal.style.display = 'none'; });

document.getElementById('create-backup-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const passphrase = document.getElementById('backup-passphrase').value;
  const scope = document.getElementById('backup-scope').value;

  try {
    await apiRequest('/api/v1/backups/create', 'POST', { passphrase, scope });
    createBackupModal.style.display = 'none';
    showToast('Created client-side encrypted backup', 'success');
    loadBackups();
  } catch (err) {
    showToast(err.message, 'error');
  }
});

const restoreBackupModal = document.getElementById('restore-backup-modal');
document.getElementById('btn-close-restore-modal').addEventListener('click', () => { restoreBackupModal.style.display = 'none'; });

document.getElementById('restore-backup-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const backup_id = document.getElementById('restore-target-backup-id').value;
  const passphrase = document.getElementById('restore-passphrase').value;

  try {
    const res = await apiRequest('/api/v1/backups/restore', 'POST', { backup_id, passphrase });
    restoreBackupModal.style.display = 'none';
    if (res.success) {
      showToast(`Restored ${res.restored_items_count} items in ${res.duration_ms.toFixed(1)}ms`, 'success');
    } else {
      showToast(`Restore failed: ${res.error}`, 'error');
    }
  } catch (err) {
    showToast(err.message, 'error');
  }
});

// 10. Phase 11: Connectors & Webhooks
async function loadConnectors() {
  try {
    const connectors = await apiRequest('/api/v1/connectors');
    const grid = document.getElementById('connectors-grid');
    grid.innerHTML = '';

    if (!connectors || connectors.length === 0) {
      grid.innerHTML = '<div class="empty-state">No outbound connectors registered.</div>';
      return;
    }

    connectors.forEach((c) => {
      const card = document.createElement('div');
      card.className = 'connector-card';
      card.innerHTML = `
        <div class="connector-card-header">
          <span style="font-weight:600;">${c.name}</span>
          <span class="connector-type-badge">${c.connector_type}</span>
        </div>
        <div style="font-size:12px;color:var(--text-muted);word-break:break-all;margin-bottom:8px;">${c.target_url}</div>
        <div style="font-size:11px;color:var(--text-secondary);margin-bottom:12px;">Rate limit: ${c.rate_limit_per_min} req/min | Retries: ${c.max_retries}</div>
        <div style="display:flex;gap:8px;">
          <button class="btn btn-sm btn-outline" onclick="testConnector('${c.connector_id}')">Send Test Ping</button>
          <button class="btn btn-sm btn-danger" onclick="deleteConnector('${c.connector_id}')">Delete</button>
        </div>
      `;
      grid.appendChild(card);
    });
  } catch (err) {
    console.error('Error loading connectors', err);
  }
}

window.testConnector = async function (connectorId) {
  try {
    const res = await apiRequest(`/api/v1/connectors/test?connector_id=${connectorId}`, 'POST');
    if (res.success) {
      showToast(`Test ping successful (${res.latency_ms.toFixed(1)}ms)`, 'success');
    } else {
      showToast(`Test failed: ${res.error_message}`, 'error');
    }
    loadDeliveries();
  } catch (err) {
    showToast(err.message, 'error');
  }
};

window.deleteConnector = async function (connectorId) {
  if (!confirm(`Delete connector '${connectorId}'?`)) return;
  try {
    await apiRequest(`/api/v1/connectors/${connectorId}`, 'DELETE');
    showToast('Connector deleted', 'info');
    loadConnectors();
  } catch (err) {
    showToast(err.message, 'error');
  }
};

async function loadDeliveries() {
  try {
    const deliveries = await apiRequest('/api/v1/connectors/deliveries?limit=30');
    const tbody = document.getElementById('deliveries-table-body');
    tbody.innerHTML = '';

    if (!deliveries || deliveries.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" class="empty-state">No webhook deliveries recorded.</td></tr>';
      return;
    }

    deliveries.forEach((d) => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td><code>${d.delivery_id}</code></td>
        <td><strong>${d.connector_id}</strong></td>
        <td><code>${d.event_type}</code></td>
        <td><span class="badge ${d.success ? 'badge-success' : 'badge-danger'}">${d.status_code || 'ERR'}</span></td>
        <td>${d.latency_ms.toFixed(1)}ms</td>
        <td>${new Date(d.timestamp).toLocaleTimeString()}</td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error('Error loading deliveries', err);
  }
}

document.getElementById('btn-refresh-deliveries').addEventListener('click', loadDeliveries);

const addConnectorModal = document.getElementById('add-connector-modal');
document.getElementById('btn-open-add-connector').addEventListener('click', () => { addConnectorModal.style.display = 'flex'; });
document.getElementById('btn-close-connector-modal').addEventListener('click', () => { addConnectorModal.style.display = 'none'; });

document.getElementById('add-connector-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const name = document.getElementById('connector-name').value.trim();
  const connector_type = document.getElementById('connector-type').value;
  const target_url = document.getElementById('connector-target-url').value.trim();
  const signing_secret = document.getElementById('connector-secret').value.trim() || null;
  const rate_limit_per_min = parseInt(document.getElementById('connector-rate-limit').value);
  const connector_id = `conn_${name.toLowerCase().replace(/[^a-z0-9]/g, '_')}_${Date.now()}`;

  try {
    await apiRequest('/api/v1/connectors', 'POST', {
      connector_id,
      name,
      connector_type,
      target_url,
      signing_secret,
      rate_limit_per_min,
      status: 'active',
    });
    addConnectorModal.style.display = 'none';
    showToast('Connector registered', 'success');
    loadConnectors();
  } catch (err) {
    showToast(err.message, 'error');
  }
});


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
