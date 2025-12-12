// Глобальные переменные
let currentUser = null;
const API_BASE = '/api';

// Инициализация
document.addEventListener('DOMContentLoaded', () => {
    const loginForm = document.getElementById('login-form');
    if (loginForm) {
        loginForm.addEventListener('submit', handleLogin);
    }

    const newAppForm = document.getElementById('new-application-form');
    if (newAppForm) {
        newAppForm.addEventListener('submit', handleCreateApplication);
    }

    // Проверяем, есть ли сохранённый пользователь
    const savedUser = localStorage.getItem('currentUser');
    if (savedUser) {
        currentUser = JSON.parse(savedUser);
        showDashboard(currentUser.role);
    }
});

// Обработка входа
async function handleLogin(e) {
    e.preventDefault();
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    const errorDiv = document.getElementById('login-error');

    try {
        const response = await fetch(`${API_BASE}/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });

        const data = await response.json();

        if (response.ok) {
            currentUser = data.user;
            localStorage.setItem('currentUser', JSON.stringify(currentUser));
            showDashboard(currentUser.role);
            errorDiv.classList.remove('show');
        } else {
            errorDiv.textContent = data.error || 'Ошибка входа';
            errorDiv.classList.add('show');
        }
    } catch (error) {
        errorDiv.textContent = 'Ошибка соединения с сервером';
        errorDiv.classList.add('show');
    }
}

// Выход
function logout() {
    currentUser = null;
    localStorage.removeItem('currentUser');
    showPage('login-page');
}

// Показать нужную страницу
function showPage(pageId) {
    document.querySelectorAll('.page').forEach(page => {
        page.classList.remove('active');
    });
    document.getElementById(pageId).classList.add('active');
}

// Показать dashboard в зависимости от роли
function showDashboard(role) {
    showPage('login-page');
    
    setTimeout(() => {
        if (role === 'developer') {
            showPage('developer-dashboard');
            document.getElementById('nav-username').textContent = currentUser.username;
            loadDeveloperApplications();
            loadDeveloperDeployments();
        } else if (role === 'operator') {
            showPage('operator-dashboard');
            document.getElementById('nav-username-op').textContent = currentUser.username;
            loadOperatorApplications();
            loadImages();
            loadOperatorDeployments();
            loadMetrics();
        } else if (role === 'admin') {
            showPage('admin-dashboard');
            document.getElementById('nav-username-admin').textContent = currentUser.username;
            loadUsers();
            loadAuditLogs();
        }
    }, 100);
}

// ========== РАЗРАБОТЧИК ==========

function showDeveloperTab(tabName) {
    document.querySelectorAll('#developer-dashboard .tab-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('#developer-dashboard .tab-content').forEach(content => content.classList.remove('active'));
    
    if (event && event.target) {
        event.target.classList.add('active');
    } else {
        // Программный вызов - находим кнопку по data-tab
        const btn = document.querySelector(`#developer-dashboard .tab-btn[data-tab="${tabName}"]`);
        if (btn) btn.classList.add('active');
    }
    document.getElementById(`dev-${tabName}-tab`).classList.add('active');
}

function showNewApplicationForm() {
    document.getElementById('new-application-form-container').style.display = 'block';
    document.getElementById('new-application-form').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function closeNewApplicationForm() {
    document.getElementById('new-application-form-container').style.display = 'none';
    document.getElementById('new-application-form').reset();
}

async function loadDeveloperApplications() {
    try {
        const response = await fetch(`${API_BASE}/developer/applications?user_id=${currentUser.id}`);
        const applications = await response.json();
        
        const container = document.getElementById('applications-list');
        if (applications.length === 0) {
            container.innerHTML = '<div class="empty-state"><div class="empty-state-icon">📋</div><p>У вас пока нет заявок</p></div>';
            return;
        }
        
        container.innerHTML = applications.map(app => `
            <div class="card">
                <div class="card-header">
                    <div class="card-title">Заявка #${app.id}</div>
                    <span class="status-badge status-${app.status}">${getStatusText(app.status)}</span>
                </div>
                <div class="card-info">
                    <div class="info-item">
                        <span class="info-label">Репозиторий</span>
                        <span class="info-value">${app.git_repo}</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">Ветка</span>
                        <span class="info-value">${app.branch}</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">Имя образа</span>
                        <span class="info-value">${app.image_name || '-'}</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">Базовый образ</span>
                        <span class="info-value">${app.base_image}</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">Создано</span>
                        <span class="info-value">${new Date(app.created_at).toLocaleString('ru-RU')}</span>
                    </div>
                </div>
            </div>
        `).join('');
    } catch (error) {
        console.error('Ошибка загрузки заявок:', error);
    }
}

async function handleCreateApplication(e) {
    e.preventDefault();
    
    const runCommands = document.getElementById('run-commands').value
        .split('\n')
        .filter(cmd => cmd.trim());
    
    const data = {
        developer_id: currentUser.id,
        git_repo: document.getElementById('git-repo').value,
        branch: document.getElementById('branch').value,
        image_name: document.getElementById('image-name').value,
        base_image: document.getElementById('base-image').value,
        run_commands: runCommands,
        entrypoint: document.getElementById('entrypoint').value
    };
    
    try {
        const response = await fetch(`${API_BASE}/developer/applications`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        
        const result = await response.json();
        if (response.ok) {
            alert('Заявка успешно создана!');
            e.target.reset();
            closeNewApplicationForm();
            loadDeveloperApplications();
        } else {
            alert('Ошибка: ' + (result.error || 'Не удалось создать заявку'));
        }
    } catch (error) {
        console.error('Ошибка создания заявки:', error);
        alert('Ошибка соединения с сервером');
    }
}

async function loadDeveloperDeployments() {
    try {
        const response = await fetch(`${API_BASE}/developer/deployments?user_id=${currentUser.id}`);
        const deployments = await response.json();
        
        const container = document.getElementById('deployments-list');
        if (deployments.length === 0) {
            container.innerHTML = '<div class="empty-state"><div class="empty-state-icon">🚀</div><p>У вас пока нет развёртываний</p></div>';
            return;
        }
        
        container.innerHTML = deployments.map(dep => `
            <div class="card">
                <div class="card-header">
                    <div class="card-title">${dep.name}</div>
                    <span class="status-badge status-${dep.status}">${getStatusText(dep.status)}</span>
                </div>
                <div class="card-info">
                    <div class="info-item">
                        <span class="info-label">Образ</span>
                        <span class="info-value">${dep.image_name}</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">Создано</span>
                        <span class="info-value">${new Date(dep.created_at).toLocaleString('ru-RU')}</span>
                    </div>
                </div>
                <div class="card-actions">
                    ${dep.status !== 'running' ? `<button class="btn btn-success" onclick="startDeployment(${dep.id})">Запустить</button>` : ''}
                    ${dep.status === 'running' ? `<button class="btn btn-danger" onclick="stopDeployment(${dep.id})">Остановить</button>` : ''}
                    ${dep.status === 'running' ? `<button class="btn btn-warning" onclick="restartDeployment(${dep.id})">Перезапустить</button>` : ''}
                </div>
            </div>
        `).join('');
    } catch (error) {
        console.error('Ошибка загрузки развёртываний:', error);
    }
}

async function startDeployment(id) {
    try {
        const response = await fetch(`${API_BASE}/developer/deployments/${id}/start`, { method: 'POST' });
        const result = await response.json();
        if (response.ok) {
            alert('Развёртывание запущено');
            loadDeveloperDeployments();
        }
    } catch (error) {
        alert('Ошибка');
    }
}

async function stopDeployment(id) {
    try {
        const response = await fetch(`${API_BASE}/developer/deployments/${id}/stop`, { method: 'POST' });
        const result = await response.json();
        if (response.ok) {
            alert('Развёртывание остановлено');
            loadDeveloperDeployments();
        }
    } catch (error) {
        alert('Ошибка');
    }
}

async function restartDeployment(id) {
    try {
        const response = await fetch(`${API_BASE}/developer/deployments/${id}/restart`, { method: 'POST' });
        const result = await response.json();
        if (response.ok) {
            alert('Развёртывание перезапущено');
            loadDeveloperDeployments();
        }
    } catch (error) {
        alert('Ошибка');
    }
}

// ========== ОПЕРАТОР ==========

function showOperatorTab(tabName) {
    document.querySelectorAll('#operator-dashboard .tab-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('#operator-dashboard .tab-content').forEach(content => content.classList.remove('active'));
    
    event.target.classList.add('active');
    document.getElementById(`op-${tabName}-tab`).classList.add('active');
    
    // Загружаем данные при переключении вкладок
    if (tabName === 'applications') loadOperatorApplications();
    if (tabName === 'images') loadImages();
    if (tabName === 'deployments') loadOperatorDeployments();
    if (tabName === 'metrics') loadMetrics();
}

async function loadOperatorApplications() {
    try {
        const response = await fetch(`${API_BASE}/operator/applications`);
        const applications = await response.json();
        
        const container = document.getElementById('operator-applications-list');
        if (applications.length === 0) {
            container.innerHTML = '<div class="empty-state"><div class="empty-state-icon">📋</div><p>Нет заявок</p></div>';
            return;
        }
        
        container.innerHTML = applications.map(app => `
            <div class="card">
                <div class="card-header">
                    <div class="card-title">Заявка #${app.id} от ${app.developer}</div>
                    <span class="status-badge status-${app.status}">${getStatusText(app.status)}</span>
                </div>
                <div class="card-info">
                    <div class="info-item">
                        <span class="info-label">Репозиторий</span>
                        <span class="info-value">${app.git_repo}</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">Ветка</span>
                        <span class="info-value">${app.branch}</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">Имя образа</span>
                        <span class="info-value">${app.image_name || '-'}</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">Базовый образ</span>
                        <span class="info-value">${app.base_image}</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">Оператор</span>
                        <span class="info-value">${app.operator || 'Не назначен'}</span>
                    </div>
                </div>
                ${app.status === 'pending' ? `
                    <div class="card-actions">
                        <button class="btn btn-success" onclick="approveApplication(${app.id})">Одобрить</button>
                        <button class="btn btn-danger" onclick="rejectApplication(${app.id})">Отклонить</button>
                    </div>
                ` : ''}
            </div>
        `).join('');
    } catch (error) {
        console.error('Ошибка загрузки заявок:', error);
    }
}

async function approveApplication(appId) {
    try {
        const response = await fetch(`${API_BASE}/operator/applications/${appId}/approve`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ operator_id: currentUser.id })
        });
        
        const result = await response.json();
        if (response.ok) {
            alert('Заявка одобрена, образ создан!');
            loadOperatorApplications();
        }
    } catch (error) {
        alert('Ошибка');
    }
}

async function rejectApplication(appId) {
    if (!confirm('Вы уверены, что хотите отклонить эту заявку?')) return;
    
    try {
        const response = await fetch(`${API_BASE}/operator/applications/${appId}/reject`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ operator_id: currentUser.id })
        });
        
        const result = await response.json();
        if (response.ok) {
            alert('Заявка отклонена');
            loadOperatorApplications();
        }
    } catch (error) {
        alert('Ошибка');
    }
}

async function loadImages() {
    try {
        const response = await fetch(`${API_BASE}/operator/images`);
        const images = await response.json();
        
        const container = document.getElementById('images-list');
        if (images.length === 0) {
            container.innerHTML = '<div class="empty-state"><div class="empty-state-icon">🐳</div><p>Нет образов</p></div>';
            return;
        }
        
        container.innerHTML = images.map(img => `
            <div class="card">
                <div class="card-header">
                    <div class="card-title">${img.name}:${img.tag}</div>
                    <span class="status-badge status-${img.status}">${getStatusText(img.status)}</span>
                </div>
                <div class="card-info">
                    <div class="info-item">
                        <span class="info-label">Развёртываний</span>
                        <span class="info-value">${img.deployments_count}</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">Создано</span>
                        <span class="info-value">${new Date(img.created_at).toLocaleString('ru-RU')}</span>
                    </div>
                </div>
                <div class="card-actions">
                    <button class="btn btn-primary" onclick="showImageDetails(${img.id})">Подробности</button>
                    <button class="btn btn-success" onclick="showImageDeployments(${img.id})">Развёртывания</button>
                    <button class="btn btn-warning" onclick="rebuildImage(${img.id})">Пересобрать образ</button>
                </div>
            </div>
        `).join('');
    } catch (error) {
        console.error('Ошибка загрузки образов:', error);
    }
}

async function showImageDetails(imageId) {
    try {
        const response = await fetch(`${API_BASE}/operator/images/${imageId}`);
        const image = await response.json();
        
        const modalBody = document.getElementById('modal-body');
        modalBody.innerHTML = `
            <h3>Детали образа: ${image.name}:${image.tag}</h3>
            <div class="card" style="margin-top: 20px;">
                <div class="info-item" style="margin-bottom: 15px;">
                    <span class="info-label">Статус</span>
                    <span class="status-badge status-${image.status}">${getStatusText(image.status)}</span>
                </div>
                <div class="info-item" style="margin-bottom: 15px;">
                    <span class="info-label">Создано</span>
                    <span class="info-value">${new Date(image.created_at).toLocaleString('ru-RU')}</span>
                </div>
            </div>
            <h4 style="margin-top: 20px;">Dockerfile</h4>
            <div style="background: #1a1a1a; color: #0f0; padding: 20px; border-radius: 5px; font-family: monospace; max-height: 400px; overflow-y: auto; white-space: pre-wrap;">
${image.dockerfile_content || 'Dockerfile не найден'}
            </div>
        `;
        document.getElementById('modal-overlay').classList.add('show');
    } catch (error) {
        alert('Ошибка загрузки деталей образа');
    }
}

async function rebuildImage(imageId) {
    if (!confirm('Вы уверены, что хотите пересобрать этот образ? Это подтянет последние изменения из репозитория и пересоберёт образ.')) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/operator/images/${imageId}/rebuild`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ operator_id: currentUser.id })
        });
        
        const result = await response.json();
        if (response.ok) {
            alert('Образ поставлен в очередь на пересборку');
            loadImages();
        } else {
            alert('Ошибка: ' + (result.error || 'Не удалось запустить пересборку'));
        }
    } catch (error) {
        alert('Ошибка соединения с сервером');
    }
}

async function showImageDeployments(imageId) {
    try {
        const response = await fetch(`${API_BASE}/operator/images/${imageId}/deployments`);
        const deployments = await response.json();
        
        const modalBody = document.getElementById('modal-body');
        modalBody.innerHTML = `
            <h3>Развёртывания образа</h3>
            ${deployments.length === 0 ? '<p>Нет развёртываний</p>' : `
                <table class="table">
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Название</th>
                            <th>Статус</th>
                            <th>Запросил</th>
                            <th>Создано</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${deployments.map(dep => `
                            <tr>
                                <td>${dep.id}</td>
                                <td>${dep.name}</td>
                                <td><span class="status-badge status-${dep.status}">${getStatusText(dep.status)}</span></td>
                                <td>${dep.requested_by}</td>
                                <td>${new Date(dep.created_at).toLocaleString('ru-RU')}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            `}
        `;
        document.getElementById('modal-overlay').classList.add('show');
    } catch (error) {
        alert('Ошибка загрузки развёртываний');
    }
}

async function loadOperatorDeployments() {
    try {
        const response = await fetch(`${API_BASE}/operator/deployments`);
        const deployments = await response.json();
        
        const container = document.getElementById('operator-deployments-list');
        if (deployments.length === 0) {
            container.innerHTML = '<div class="empty-state"><div class="empty-state-icon">🚀</div><p>Нет развёртываний</p></div>';
            return;
        }
        
        container.innerHTML = deployments.map(dep => `
            <div class="card">
                <div class="card-header">
                    <div class="card-title">${dep.name}</div>
                    <span class="status-badge status-${dep.status}">${getStatusText(dep.status)}</span>
                </div>
                <div class="card-info">
                    <div class="info-item">
                        <span class="info-label">Образ</span>
                        <span class="info-value">${dep.image_name}</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">Запросил</span>
                        <span class="info-value">${dep.requested_by}</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">Оператор</span>
                        <span class="info-value">${dep.operator || 'Не назначен'}</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">Порт</span>
                        <span class="info-value">${dep.port || '-'}</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">Создано</span>
                        <span class="info-value">${new Date(dep.created_at).toLocaleString('ru-RU')}</span>
                    </div>
                </div>
                <div class="card-actions">
                    <button class="btn btn-primary" onclick="showDeploymentLogs(${dep.id})">Логи</button>
                    ${dep.status === 'running' ? `<button class="btn btn-warning" onclick="restartDeploymentOp(${dep.id})">Перезапустить</button>` : ''}
                    ${dep.status === 'running' ? `<button class="btn btn-danger" onclick="stopDeploymentOp(${dep.id})">Остановить</button>` : ''}
                    ${dep.status === 'stopped' ? `<button class="btn btn-success" onclick="startDeploymentOp(${dep.id})">Запустить</button>` : ''}
                </div>
            </div>
        `).join('');
    } catch (error) {
        console.error('Ошибка загрузки развёртываний:', error);
    }
}

async function showDeploymentLogs(deploymentId) {
    try {
        const response = await fetch(`${API_BASE}/operator/deployments/${deploymentId}/logs`);
        const data = await response.json();
        
        const modalBody = document.getElementById('modal-body');
        modalBody.innerHTML = `
            <h3>Логи развёртывания #${deploymentId}</h3>
            <div style="background: #1a1a1a; color: #0f0; padding: 20px; border-radius: 5px; font-family: monospace; max-height: 400px; overflow-y: auto;">
                ${data.logs.map(log => `<div>${log}</div>`).join('')}
            </div>
        `;
        document.getElementById('modal-overlay').classList.add('show');
    } catch (error) {
        alert('Ошибка загрузки логов');
    }
}

async function restartDeploymentOp(id) {
    try {
        const response = await fetch(`${API_BASE}/developer/deployments/${id}/restart`, { method: 'POST' });
        if (response.ok) {
            alert('Развёртывание перезапущено');
            loadOperatorDeployments();
        }
    } catch (error) {
        alert('Ошибка');
    }
}

async function startDeploymentOp(id) {
    try {
        const response = await fetch(`${API_BASE}/developer/deployments/${id}/start`, { method: 'POST' });
        if (response.ok) {
            alert('Развёртывание запущено');
            loadOperatorDeployments();
        }
    } catch (error) {
        alert('Ошибка');
    }
}

async function stopDeploymentOp(id) {
    try {
        const response = await fetch(`${API_BASE}/developer/deployments/${id}/stop`, { method: 'POST' });
        if (response.ok) {
            alert('Развёртывание остановлено');
            loadOperatorDeployments();
        }
    } catch (error) {
        alert('Ошибка');
    }
}

function showCreateDeploymentModal() {
    // Загружаем список образов и разработчиков
    Promise.all([
        fetch(`${API_BASE}/operator/images`).then(res => res.json()),
        fetch(`${API_BASE}/operator/developers`).then(res => res.json())
    ]).then(([images, developers]) => {
        const modalBody = document.getElementById('modal-body');
        modalBody.innerHTML = `
            <h3>Создать развёртывание</h3>
            <form id="create-deployment-form" onsubmit="handleCreateDeployment(event)">
                <div class="form-group">
                    <label>Название</label>
                    <input type="text" id="dep-name" required>
                </div>
                <div class="form-group">
                    <label>Образ</label>
                    <select id="dep-image-id" required>
                        ${images.map(img => `<option value="${img.id}">${img.name}:${img.tag}</option>`).join('')}
                    </select>
                </div>
                <div class="form-group">
                    <label>Запросил (разработчик)</label>
                    <select id="dep-requested-by" required>
                        ${developers.map(dev => `<option value="${dev.id}">${dev.username} (${dev.email})</option>`).join('')}
                    </select>
                </div>
                <div class="form-group">
                    <label>Порт</label>
                    <input type="number" id="dep-port" value="8080">
                </div>
                <div class="form-group">
                    <label>Переменные окружения (JSON, опционально)</label>
                    <textarea id="dep-env-vars" rows="3" placeholder='{"KEY": "value"}'></textarea>
                </div>
                <button type="submit" class="btn btn-primary">Создать</button>
            </form>
        `;
        document.getElementById('modal-overlay').classList.add('show');
    });
}

async function handleCreateDeployment(e) {
    e.preventDefault();
    
    let envVars = {};
    const envVarsText = document.getElementById('dep-env-vars').value.trim();
    if (envVarsText) {
        try {
            envVars = JSON.parse(envVarsText);
        } catch (e) {
            alert('Неверный формат JSON для переменных окружения');
            return;
        }
    }
    
    const data = {
        operator_id: currentUser.id,
        requested_by_id: parseInt(document.getElementById('dep-requested-by').value),
        image_id: parseInt(document.getElementById('dep-image-id').value),
        name: document.getElementById('dep-name').value,
        port: parseInt(document.getElementById('dep-port').value),
        environment_vars: envVars
    };
    
    try {
        const response = await fetch(`${API_BASE}/operator/deployments`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        
        const result = await response.json();
        if (response.ok) {
            alert('Развёртывание создано!');
            closeModal();
            loadOperatorDeployments();
        } else {
            alert('Ошибка: ' + (result.error || 'Не удалось создать развёртывание'));
        }
    } catch (error) {
        alert('Ошибка соединения с сервером');
    }
}

async function loadMetrics() {
    try {
        const response = await fetch(`${API_BASE}/operator/metrics`);
        const metrics = await response.json();
        
        const container = document.getElementById('metrics-content');
        container.innerHTML = `
            <div class="metrics-grid">
                <div class="metric-card">
                    <div class="metric-value">${metrics.total_applications}</div>
                    <div class="metric-label">Всего заявок</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">${metrics.pending_applications}</div>
                    <div class="metric-label">Ожидают рассмотрения</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">${metrics.total_images}</div>
                    <div class="metric-label">Docker образов</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">${metrics.total_deployments}</div>
                    <div class="metric-label">Всего развёртываний</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">${metrics.running_deployments}</div>
                    <div class="metric-label">Активных</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">${metrics.stopped_deployments}</div>
                    <div class="metric-label">Остановленных</div>
                </div>
            </div>
        `;
    } catch (error) {
        console.error('Ошибка загрузки метрик:', error);
    }
}

// ========== АДМИНИСТРАТОР ==========

function showAdminTab(tabName) {
    document.querySelectorAll('#admin-dashboard .tab-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('#admin-dashboard .tab-content').forEach(content => content.classList.remove('active'));
    
    event.target.classList.add('active');
    document.getElementById(`admin-${tabName}-tab`).classList.add('active');
    
    if (tabName === 'users') loadUsers();
    if (tabName === 'audit') loadAuditLogs();
}

async function loadUsers() {
    try {
        const response = await fetch(`${API_BASE}/admin/users`);
        const users = await response.json();
        
        const container = document.getElementById('users-list');
        container.innerHTML = `
            <table class="table">
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Имя пользователя</th>
                        <th>Email</th>
                        <th>Роль</th>
                        <th>Статус</th>
                        <th>Действия</th>
                    </tr>
                </thead>
                <tbody>
                    ${users.map(user => `
                        <tr>
                            <td>${user.id}</td>
                            <td>${user.username}</td>
                            <td>${user.email}</td>
                            <td>${getRoleText(user.role)}</td>
                            <td>${user.is_banned ? '<span class="status-badge status-rejected">Заблокирован</span>' : '<span class="status-badge status-approved">Активен</span>'}</td>
                            <td>
                                ${user.is_banned ? 
                                    `<button class="btn btn-sm btn-success" onclick="unbanUser(${user.id})">Разблокировать</button>` :
                                    `<button class="btn btn-sm btn-danger" onclick="banUser(${user.id})">Заблокировать</button>`
                                }
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    } catch (error) {
        console.error('Ошибка загрузки пользователей:', error);
    }
}

function showCreateUserModal() {
    const modalBody = document.getElementById('modal-body');
    modalBody.innerHTML = `
        <h3>Добавить пользователя</h3>
        <form id="create-user-form" onsubmit="handleCreateUser(event)">
            <div class="form-group">
                <label>Имя пользователя</label>
                <input type="text" id="new-username" required>
            </div>
            <div class="form-group">
                <label>Email</label>
                <input type="email" id="new-email" required>
            </div>
            <div class="form-group">
                <label>Пароль</label>
                <input type="password" id="new-password" required>
            </div>
            <div class="form-group">
                <label>Роль</label>
                <select id="new-role" required>
                    <option value="developer">Разработчик</option>
                    <option value="operator">Оператор</option>
                    <option value="admin">Администратор</option>
                </select>
            </div>
            <button type="submit" class="btn btn-primary">Создать</button>
        </form>
    `;
    document.getElementById('modal-overlay').classList.add('show');
}

async function handleCreateUser(e) {
    e.preventDefault();
    const data = {
        admin_id: currentUser.id,
        username: document.getElementById('new-username').value,
        email: document.getElementById('new-email').value,
        password: document.getElementById('new-password').value,
        role: document.getElementById('new-role').value
    };
    
    try {
        const response = await fetch(`${API_BASE}/admin/users`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        
        const result = await response.json();
        if (response.ok) {
            alert('Пользователь создан!');
            closeModal();
            loadUsers();
        } else {
            alert('Ошибка: ' + (result.error || 'Не удалось создать пользователя'));
        }
    } catch (error) {
        alert('Ошибка');
    }
}

async function banUser(userId) {
    if (!confirm('Заблокировать этого пользователя?')) return;
    
    try {
        const response = await fetch(`${API_BASE}/admin/users/${userId}/ban`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ admin_id: currentUser.id })
        });
        
        if (response.ok) {
            alert('Пользователь заблокирован');
            loadUsers();
        }
    } catch (error) {
        alert('Ошибка');
    }
}

async function unbanUser(userId) {
    try {
        const response = await fetch(`${API_BASE}/admin/users/${userId}/unban`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ admin_id: currentUser.id })
        });
        
        if (response.ok) {
            alert('Пользователь разблокирован');
            loadUsers();
        }
    } catch (error) {
        alert('Ошибка');
    }
}

async function loadAuditLogs() {
    try {
        const response = await fetch(`${API_BASE}/admin/audit`);
        const logs = await response.json();
        
        const container = document.getElementById('audit-logs');
        container.innerHTML = `
            <table class="table">
                <thead>
                    <tr>
                        <th>Время</th>
                        <th>Пользователь</th>
                        <th>Действие</th>
                        <th>Ресурс</th>
                        <th>Детали</th>
                    </tr>
                </thead>
                <tbody>
                    ${logs.map(log => `
                        <tr>
                            <td>${new Date(log.created_at).toLocaleString('ru-RU')}</td>
                            <td>${log.user}</td>
                            <td>${getActionText(log.action)}</td>
                            <td>${log.resource_type ? `${log.resource_type} #${log.resource_id}` : '-'}</td>
                            <td>${log.details ? JSON.stringify(log.details) : '-'}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    } catch (error) {
        console.error('Ошибка загрузки логов:', error);
    }
}

// Вспомогательные функции
function getStatusText(status) {
    const statusMap = {
        'pending': 'Ожидает',
        'approved': 'Одобрено',
        'rejected': 'Отклонено',
        'building': 'Сборка',
        'ready': 'Готово',
        'running': 'Запущено',
        'stopped': 'Остановлено',
        'updating': 'Обновление',
        'failed': 'Ошибка'
    };
    return statusMap[status] || status;
}

function getRoleText(role) {
    const roleMap = {
        'developer': 'Разработчик',
        'operator': 'Оператор',
        'admin': 'Администратор'
    };
    return roleMap[role] || role;
}

function getActionText(action) {
    const actionMap = {
        'login': 'Вход в систему',
        'register': 'Регистрация',
        'create_application': 'Создание заявки',
        'approve_application': 'Одобрение заявки',
        'reject_application': 'Отклонение заявки',
        'create_deployment': 'Создание развёртывания',
        'start_deployment': 'Запуск развёртывания',
        'stop_deployment': 'Остановка развёртывания',
        'restart_deployment': 'Перезапуск развёртывания',
        'rebuild_image': 'Пересборка образа',
        'create_user': 'Создание пользователя',
        'ban_user': 'Блокировка пользователя',
        'unban_user': 'Разблокировка пользователя'
    };
    return actionMap[action] || action;
}

function closeModal() {
    document.getElementById('modal-overlay').classList.remove('show');
}

