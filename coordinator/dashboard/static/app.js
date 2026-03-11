// NEXUS Dashboard Application

const API_BASE = '/api';
let ws = null;
let reconnectAttempts = 0;

// Get API Key
let API_KEY = localStorage.getItem('nexus_api_key');
if (!API_KEY) {
    API_KEY = prompt('Enter Nexus API Key:');
    if (API_KEY) {
        localStorage.setItem('nexus_api_key', API_KEY);
    }
}

// Initialize on load
document.addEventListener('DOMContentLoaded', () => {
    initNavigation();
    connectWebSocket();
    loadInitialData();
});

// Navigation
function initNavigation() {
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', () => {
            const page = item.dataset.page;
            switchPage(page);
        });
    });
}

function switchPage(page) {
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.toggle('active', item.dataset.page === page);
    });

    document.querySelectorAll('.page').forEach(p => {
        p.classList.toggle('active', p.id === `page-${page}`);
    });

    // Refresh data when switching pages
    switch (page) {
        case 'activity': loadActivity(); break;
        case 'objectives': loadObjectives(); break;
        case 'validations': loadValidations(); break;
        case 'memory': loadMemory(); break;
    }
}

// WebSocket
function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${protocol}//${window.location.host}/ws?key=${encodeURIComponent(API_KEY)}`);

    ws.onopen = () => {
        console.log('WebSocket connected');
        updateConnectionStatus(true);
        reconnectAttempts = 0;
    };

    ws.onclose = () => {
        console.log('WebSocket disconnected');
        updateConnectionStatus(false);
        scheduleReconnect();
    };

    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
    };

    ws.onmessage = (event) => {
        const message = JSON.parse(event.data);
        handleWebSocketMessage(message);
    };
}

function scheduleReconnect() {
    const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 30000);
    reconnectAttempts++;
    setTimeout(connectWebSocket, delay);
}

function updateConnectionStatus(connected) {
    const status = document.getElementById('connection-status');
    const dot = status.querySelector('.status-dot');
    const text = status.querySelector('span:last-child');

    dot.className = `status-dot ${connected ? 'connected' : 'disconnected'}`;
    text.textContent = connected ? 'Connected' : 'Disconnected';
}

function handleWebSocketMessage(message) {
    console.log('WS message:', message);

    switch (message.type) {
        case 'activity':
            prependActivity(message.data);
            break;
        case 'objective_created':
        case 'objective_updated':
            loadObjectives();
            break;
        case 'objective_deleted':
            loadObjectives();
            break;
        case 'validation_request':
            loadValidations();
            updateValidationBadge();
            break;
        case 'validation_updated':
            loadValidations();
            updateValidationBadge();
            break;
    }
}

// API helpers
async function api(endpoint, options = {}) {
    const headers = {
        'Content-Type': 'application/json',
        'X-API-Key': API_KEY,
        ...options.headers
    };

    const response = await fetch(`${API_BASE}${endpoint}`, {
        headers,
        ...options
    });

    if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
    }

    if (response.status === 204) {
        return null;
    }

    return response.json();
}

// Load initial data
async function loadInitialData() {
    await Promise.all([
        loadActivity(),
        loadObjectives(),
        loadValidations(),
        loadMemory()
    ]);
    updateValidationBadge();
}

// Activity
async function loadActivity() {
    try {
        const activities = await api('/activity?limit=50');
        renderActivities(activities);
    } catch (error) {
        console.error('Failed to load activity:', error);
    }
}

function renderActivities(activities) {
    const container = document.getElementById('activity-feed');

    if (!activities || activities.length === 0) {
        container.innerHTML = '<div class="empty-state">No activity yet</div>';
        return;
    }

    container.innerHTML = activities.map(activity => `
        <div class="activity-item">
            <div class="activity-icon ${activity.level || 'info'}">
                ${getAgentIcon(activity.agent_type)}
            </div>
            <div class="activity-content">
                <div class="activity-message">${escapeHtml(activity.message)}</div>
                <div class="activity-time">${formatTime(activity.created_at)} · ${activity.agent_type}</div>
            </div>
        </div>
    `).join('');
}

function prependActivity(activity) {
    const container = document.getElementById('activity-feed');
    const empty = container.querySelector('.empty-state');
    if (empty) empty.remove();

    const item = document.createElement('div');
    item.className = 'activity-item';
    item.innerHTML = `
        <div class="activity-icon ${activity.level || 'info'}">
            ${getAgentIcon(activity.agent_type)}
        </div>
        <div class="activity-content">
            <div class="activity-message">${escapeHtml(activity.message)}</div>
            <div class="activity-time">${formatTime(activity.created_at)} · ${activity.agent_type}</div>
        </div>
    `;

    container.insertBefore(item, container.firstChild);
}

// Objectives
async function loadObjectives() {
    try {
        const objectives = await api('/objectives');
        renderObjectives(objectives);
    } catch (error) {
        console.error('Failed to load objectives:', error);
    }
}

function renderObjectives(objectives) {
    const container = document.getElementById('objectives-list');

    if (!objectives || objectives.length === 0) {
        container.innerHTML = '<div class="empty-state">No objectives yet</div>';
        return;
    }

    container.innerHTML = objectives.map(obj => `
        <div class="card">
            <div class="card-header">
                <div>
                    <div class="card-title">${escapeHtml(obj.title)}</div>
                    <div class="card-meta">${obj.agent_type} · ${formatTime(obj.created_at)}</div>
                </div>
                <span class="status status-${obj.status}">${obj.status}</span>
            </div>
            <div class="card-body">
                ${obj.description ? escapeHtml(obj.description) : '<em>No description</em>'}
                ${obj.schedule ? `<div style="margin-top: 8px; font-size: 12px; color: var(--text-muted);">Schedule: ${escapeHtml(obj.schedule)}</div>` : ''}
            </div>
            <div class="card-actions">
                ${obj.status === 'pending' ? `<button class="btn btn-primary btn-sm" onclick="executeObjective('${obj.id}')">Execute</button>` : ''}
                <button class="btn btn-danger btn-sm" onclick="deleteObjective('${obj.id}')">Delete</button>
            </div>
        </div>
    `).join('');
}

function showObjectiveModal() {
    document.getElementById('objective-modal').classList.add('active');
}

async function submitObjective(event) {
    event.preventDefault();

    const objective = {
        title: document.getElementById('obj-title').value,
        description: document.getElementById('obj-description').value,
        agent_type: document.getElementById('obj-agent').value,
        priority: parseInt(document.getElementById('obj-priority').value),
        schedule: document.getElementById('obj-schedule').value || undefined
    };

    try {
        await api('/objectives', {
            method: 'POST',
            body: JSON.stringify(objective)
        });

        closeModal('objective-modal');
        document.getElementById('objective-form').reset();
        loadObjectives();
    } catch (error) {
        alert('Failed to create objective: ' + error.message);
    }
}

async function executeObjective(id) {
    try {
        await api(`/objectives/${id}/execute`, { method: 'POST' });
        loadObjectives();
    } catch (error) {
        alert('Failed to execute objective: ' + error.message);
    }
}

async function deleteObjective(id) {
    if (!confirm('Are you sure you want to delete this objective?')) return;

    try {
        await api(`/objectives/${id}`, { method: 'DELETE' });
        loadObjectives();
    } catch (error) {
        alert('Failed to delete objective: ' + error.message);
    }
}

// Validations
async function loadValidations() {
    try {
        const validations = await api('/validations');
        renderValidations(validations);
    } catch (error) {
        console.error('Failed to load validations:', error);
    }
}

function renderValidations(validations) {
    const container = document.getElementById('validations-list');

    if (!validations || validations.length === 0) {
        container.innerHTML = '<div class="empty-state">No pending validations</div>';
        return;
    }

    container.innerHTML = validations.map(val => `
        <div class="card">
            <div class="card-header">
                <div>
                    <div class="card-title">${escapeHtml(val.action)}</div>
                    <div class="card-meta">${val.agent_type} · Expires ${formatTime(val.expires_at)}</div>
                </div>
            </div>
            <div class="card-body">
                <p>${escapeHtml(val.description)}</p>
                ${val.data ? `<div class="validation-data">${escapeHtml(JSON.stringify(val.data, null, 2))}</div>` : ''}
            </div>
            <div class="card-actions">
                <button class="btn btn-success btn-sm" onclick="approveValidation('${val.id}')">Approve</button>
                <button class="btn btn-danger btn-sm" onclick="rejectValidation('${val.id}')">Reject</button>
            </div>
        </div>
    `).join('');
}

async function approveValidation(id) {
    try {
        await api(`/validations/${id}/approve`, { method: 'POST' });
        loadValidations();
        updateValidationBadge();
    } catch (error) {
        alert('Failed to approve validation: ' + error.message);
    }
}

async function rejectValidation(id) {
    const response = prompt('Reason for rejection (optional):');

    try {
        await api(`/validations/${id}/reject`, {
            method: 'POST',
            body: JSON.stringify({ response })
        });
        loadValidations();
        updateValidationBadge();
    } catch (error) {
        alert('Failed to reject validation: ' + error.message);
    }
}

async function updateValidationBadge() {
    try {
        const validations = await api('/validations');
        const badge = document.getElementById('validation-count');
        const count = validations ? validations.length : 0;

        if (count > 0) {
            badge.textContent = count;
            badge.style.display = 'inline';
        } else {
            badge.style.display = 'none';
        }
    } catch (error) {
        console.error('Failed to update validation badge:', error);
    }
}

// Memory
async function loadMemory() {
    try {
        const memories = await api('/memory');
        renderMemory(memories);
    } catch (error) {
        console.error('Failed to load memory:', error);
    }
}

function renderMemory(memories) {
    const container = document.getElementById('memory-list');

    if (!memories || memories.length === 0) {
        container.innerHTML = '<div class="empty-state">No memory entries</div>';
        return;
    }

    container.innerHTML = memories.map(mem => `
        <div class="card memory-item">
            <div>
                <div class="memory-key">${escapeHtml(mem.key)}</div>
                <div class="memory-value">${escapeHtml(mem.value)}</div>
                ${mem.category ? `<div class="memory-category">Category: ${escapeHtml(mem.category)}</div>` : ''}
            </div>
            <button class="btn btn-danger btn-sm" onclick="deleteMemory('${mem.key}')">Delete</button>
        </div>
    `).join('');
}

function showMemoryModal() {
    document.getElementById('memory-modal').classList.add('active');
}

async function submitMemory(event) {
    event.preventDefault();

    const key = document.getElementById('mem-key').value;
    const memory = {
        value: document.getElementById('mem-value').value,
        category: document.getElementById('mem-category').value || undefined
    };

    try {
        await api(`/memory/${encodeURIComponent(key)}`, {
            method: 'PUT',
            body: JSON.stringify(memory)
        });

        closeModal('memory-modal');
        document.getElementById('memory-form').reset();
        loadMemory();
    } catch (error) {
        alert('Failed to save memory: ' + error.message);
    }
}

async function deleteMemory(key) {
    if (!confirm('Are you sure you want to delete this memory entry?')) return;

    try {
        await api(`/memory/${encodeURIComponent(key)}`, { method: 'DELETE' });
        loadMemory();
    } catch (error) {
        alert('Failed to delete memory: ' + error.message);
    }
}

// Helpers
function closeModal(id) {
    document.getElementById(id).classList.remove('active');
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatTime(timestamp) {
    if (!timestamp) return '';
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now - date;

    if (diff < 60000) return 'just now';
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;

    return date.toLocaleDateString();
}

function getAgentIcon(agentType) {
    switch (agentType) {
        case 'email_agent': return '✉';
        case 'calendar_agent': return '📅';
        case 'memory_agent': return '🧠';
        default: return '◈';
    }
}

// Close modals on escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        document.querySelectorAll('.modal.active').forEach(modal => {
            modal.classList.remove('active');
        });
    }
});

// Close modals on backdrop click
document.querySelectorAll('.modal').forEach(modal => {
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.classList.remove('active');
        }
    });
});
