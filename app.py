from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import os
import json

app = Flask(__name__, static_folder='static', static_url_path='/static')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///samosval.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your-secret-key-here'

db = SQLAlchemy(app)
CORS(app)

# Модели данных
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # developer, operator, admin
    is_banned = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Application(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    developer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    git_repo = db.Column(db.String(500), nullable=False)
    branch = db.Column(db.String(100), nullable=False)
    base_image = db.Column(db.String(200), nullable=False)
    image_name = db.Column(db.String(200), nullable=True)  # Имя образа, заданное разработчиком
    run_commands = db.Column(db.Text)  # JSON array of commands
    entrypoint = db.Column(db.Text)
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected, building, ready
    operator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    developer = db.relationship('User', foreign_keys=[developer_id], backref='applications')
    operator = db.relationship('User', foreign_keys=[operator_id])

class Image(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey('application.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    tag = db.Column(db.String(100), default='latest')
    dockerfile_content = db.Column(db.Text)
    status = db.Column(db.String(20), default='building')  # building, ready, failed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    application = db.relationship('Application', backref='images')

class Deployment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    image_id = db.Column(db.Integer, db.ForeignKey('image.id'), nullable=False)
    requested_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    operator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    name = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(20), default='stopped')  # stopped, running, updating, failed
    port = db.Column(db.Integer)
    environment_vars = db.Column(db.Text)  # JSON object
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    image = db.relationship('Image', backref='deployments')
    requested_by = db.relationship('User', foreign_keys=[requested_by_id])
    operator = db.relationship('User', foreign_keys=[operator_id])

class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    action = db.Column(db.String(100), nullable=False)
    resource_type = db.Column(db.String(50))  # application, image, deployment, user
    resource_id = db.Column(db.Integer)
    details = db.Column(db.Text)  # JSON object
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='audit_logs')

# Вспомогательные функции
def create_audit_log(user_id, action, resource_type=None, resource_id=None, details=None):
    log = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=json.dumps(details) if details else None
    )
    db.session.add(log)
    db.session.commit()

def generate_dockerfile(application):
    """Генерирует Dockerfile на основе заявки"""
    dockerfile = f"FROM {application.base_image}\n\n"
    dockerfile += "# Клонирование репозитория\n"
    dockerfile += f"RUN git clone -b {application.branch} {application.git_repo} /app\n"
    dockerfile += "WORKDIR /app\n\n"
    
    if application.run_commands:
        commands = json.loads(application.run_commands) if isinstance(application.run_commands, str) else application.run_commands
        for cmd in commands:
            dockerfile += f"RUN {cmd}\n"
    
    if application.entrypoint:
        dockerfile += f"\nENTRYPOINT {application.entrypoint}\n"
    
    return dockerfile

# API Routes - Аутентификация
@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.json
    user = User.query.filter_by(username=data['username']).first()
    
    if user and check_password_hash(user.password_hash, data['password']):
        if user.is_banned:
            return jsonify({'error': 'Аккаунт заблокирован'}), 403
        
        create_audit_log(user.id, 'login', 'user', user.id)
        return jsonify({
            'success': True,
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'role': user.role
            }
        })
    
    return jsonify({'error': 'Неверные учетные данные'}), 401

@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.json
    if User.query.filter_by(username=data['username']).first():
        return jsonify({'error': 'Пользователь уже существует'}), 400
    
    user = User(
        username=data['username'],
        email=data['email'],
        password_hash=generate_password_hash(data['password']),
        role='developer'  # По умолчанию разработчик
    )
    db.session.add(user)
    db.session.commit()
    
    create_audit_log(user.id, 'register', 'user', user.id)
    return jsonify({'success': True, 'message': 'Пользователь создан'})

# API Routes - Разработчики
@app.route('/api/developer/applications', methods=['GET'])
def get_developer_applications():
    user_id = request.args.get('user_id', type=int)
    applications = Application.query.filter_by(developer_id=user_id).all()
    
    return jsonify([{
        'id': app.id,
        'git_repo': app.git_repo,
        'branch': app.branch,
        'base_image': app.base_image,
        'image_name': app.image_name,
        'status': app.status,
        'created_at': app.created_at.isoformat(),
        'updated_at': app.updated_at.isoformat()
    } for app in applications])

@app.route('/api/developer/applications', methods=['POST'])
def create_application():
    data = request.json
    application = Application(
        developer_id=data['developer_id'],
        git_repo=data['git_repo'],
        branch=data['branch'],
        base_image=data['base_image'],
        image_name=data.get('image_name', f"app-{data['developer_id']}"),
        run_commands=json.dumps(data.get('run_commands', [])),
        entrypoint=data.get('entrypoint', '')
    )
    db.session.add(application)
    db.session.commit()
    
    create_audit_log(data['developer_id'], 'create_application', 'application', application.id, {
        'git_repo': data['git_repo'],
        'branch': data['branch']
    })
    
    return jsonify({'success': True, 'application_id': application.id})

@app.route('/api/developer/deployments', methods=['GET'])
def get_developer_deployments():
    user_id = request.args.get('user_id', type=int)
    deployments = Deployment.query.filter_by(requested_by_id=user_id).all()
    
    return jsonify([{
        'id': dep.id,
        'name': dep.name,
        'status': dep.status,
        'image_name': dep.image.name,
        'created_at': dep.created_at.isoformat()
    } for dep in deployments])

@app.route('/api/developer/deployments/<int:deployment_id>/start', methods=['POST'])
def start_deployment(deployment_id):
    deployment = Deployment.query.get_or_404(deployment_id)
    deployment.status = 'running'
    db.session.commit()
    
    create_audit_log(deployment.requested_by_id, 'start_deployment', 'deployment', deployment_id)
    return jsonify({'success': True, 'message': 'Развёртывание запущено'})

@app.route('/api/developer/deployments/<int:deployment_id>/stop', methods=['POST'])
def stop_deployment(deployment_id):
    deployment = Deployment.query.get_or_404(deployment_id)
    deployment.status = 'stopped'
    db.session.commit()
    
    create_audit_log(deployment.requested_by_id, 'stop_deployment', 'deployment', deployment_id)
    return jsonify({'success': True, 'message': 'Развёртывание остановлено'})

@app.route('/api/developer/deployments/<int:deployment_id>/restart', methods=['POST'])
def restart_deployment(deployment_id):
    deployment = Deployment.query.get_or_404(deployment_id)
    deployment.status = 'running'
    deployment.updated_at = datetime.utcnow()
    db.session.commit()
    
    create_audit_log(deployment.requested_by_id, 'restart_deployment', 'deployment', deployment_id)
    return jsonify({'success': True, 'message': 'Развёртывание перезапущено'})

# API Routes - Операторы
@app.route('/api/operator/applications', methods=['GET'])
def get_operator_applications():
    applications = Application.query.all()
    
    return jsonify([{
        'id': app.id,
        'developer': app.developer.username,
        'git_repo': app.git_repo,
        'branch': app.branch,
        'base_image': app.base_image,
        'image_name': app.image_name,
        'status': app.status,
        'operator': app.operator.username if app.operator else None,
        'created_at': app.created_at.isoformat()
    } for app in applications])

@app.route('/api/operator/applications/<int:app_id>/approve', methods=['POST'])
def approve_application(app_id):
    data = request.json
    application = Application.query.get_or_404(app_id)
    application.status = 'approved'
    application.operator_id = data['operator_id']
    
    # Создаём образ
    dockerfile = generate_dockerfile(application)
    image = Image(
        application_id=application.id,
        name=application.image_name,
        tag='latest',
        dockerfile_content=dockerfile,
        status='ready'  # В реальной системе здесь была бы сборка
    )
    db.session.add(image)
    db.session.commit()
    
    create_audit_log(data['operator_id'], 'approve_application', 'application', app_id)
    return jsonify({'success': True, 'image_id': image.id})

@app.route('/api/operator/applications/<int:app_id>/reject', methods=['POST'])
def reject_application(app_id):
    data = request.json
    application = Application.query.get_or_404(app_id)
    application.status = 'rejected'
    application.operator_id = data['operator_id']
    db.session.commit()
    
    create_audit_log(data['operator_id'], 'reject_application', 'application', app_id)
    return jsonify({'success': True})

@app.route('/api/operator/images', methods=['GET'])
def get_images():
    images = Image.query.all()
    
    return jsonify([{
        'id': img.id,
        'name': img.name,
        'tag': img.tag,
        'status': img.status,
        'application_id': img.application_id,
        'deployments_count': len(img.deployments),
        'created_at': img.created_at.isoformat()
    } for img in images])

@app.route('/api/operator/images/<int:image_id>', methods=['GET'])
def get_image_details(image_id):
    image = Image.query.get_or_404(image_id)
    
    return jsonify({
        'id': image.id,
        'name': image.name,
        'tag': image.tag,
        'dockerfile_content': image.dockerfile_content,
        'status': image.status,
        'created_at': image.created_at.isoformat()
    })

@app.route('/api/operator/images/<int:image_id>/deployments', methods=['GET'])
def get_image_deployments(image_id):
    deployments = Deployment.query.filter_by(image_id=image_id).all()
    
    return jsonify([{
        'id': dep.id,
        'name': dep.name,
        'status': dep.status,
        'requested_by': dep.requested_by.username,
        'created_at': dep.created_at.isoformat()
    } for dep in deployments])

@app.route('/api/operator/deployments', methods=['GET'])
def get_operator_deployments():
    deployments = Deployment.query.all()
    
    return jsonify([{
        'id': dep.id,
        'name': dep.name,
        'status': dep.status,
        'image_name': dep.image.name,
        'requested_by': dep.requested_by.username,
        'operator': dep.operator.username if dep.operator else None,
        'port': dep.port,
        'created_at': dep.created_at.isoformat()
    } for dep in deployments])

@app.route('/api/operator/deployments', methods=['POST'])
def create_deployment():
    data = request.json
    deployment = Deployment(
        image_id=data['image_id'],
        requested_by_id=data.get('requested_by_id', data['operator_id']),
        operator_id=data['operator_id'],
        name=data['name'],
        port=data.get('port'),
        environment_vars=json.dumps(data.get('environment_vars', {}))
    )
    db.session.add(deployment)
    db.session.commit()
    
    create_audit_log(data['operator_id'], 'create_deployment', 'deployment', deployment.id)
    return jsonify({'success': True, 'deployment_id': deployment.id})

@app.route('/api/operator/images/<int:image_id>/rebuild', methods=['POST'])
def rebuild_image(image_id):
    data = request.json
    image = Image.query.get_or_404(image_id)
    application = image.application
    
    # Обновляем Dockerfile (подтягиваем последние изменения из заявки)
    dockerfile = generate_dockerfile(application)
    image.dockerfile_content = dockerfile
    image.status = 'building'
    image.updated_at = datetime.utcnow()
    db.session.commit()
    
    create_audit_log(data['operator_id'], 'rebuild_image', 'image', image_id)
    
    # В реальной системе здесь был бы асинхронный процесс сборки
    # Пока симулируем успешную пересборку - меняем статус на ready
    image.status = 'ready'
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Образ успешно пересобран'})

@app.route('/api/operator/developers', methods=['GET'])
def get_developers():
    developers = User.query.filter_by(role='developer', is_banned=False).all()
    
    return jsonify([{
        'id': dev.id,
        'username': dev.username,
        'email': dev.email
    } for dev in developers])

@app.route('/api/operator/metrics', methods=['GET'])
def get_metrics():
    return jsonify({
        'total_applications': Application.query.count(),
        'pending_applications': Application.query.filter_by(status='pending').count(),
        'total_images': Image.query.count(),
        'total_deployments': Deployment.query.count(),
        'running_deployments': Deployment.query.filter_by(status='running').count(),
        'stopped_deployments': Deployment.query.filter_by(status='stopped').count()
    })

@app.route('/api/operator/deployments/<int:deployment_id>/logs', methods=['GET'])
def get_deployment_logs(deployment_id):
    # В реальной системе здесь были бы реальные логи
    return jsonify({
        'logs': [
            f"[{datetime.utcnow().isoformat()}] Deployment {deployment_id} started",
            f"[{datetime.utcnow().isoformat()}] Container initialized",
            f"[{datetime.utcnow().isoformat()}] Application ready"
        ]
    })

# API Routes - Администраторы
@app.route('/api/admin/users', methods=['GET'])
def get_users():
    users = User.query.all()
    
    return jsonify([{
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'role': user.role,
        'is_banned': user.is_banned,
        'created_at': user.created_at.isoformat()
    } for user in users])

@app.route('/api/admin/users', methods=['POST'])
def create_user():
    data = request.json
    if User.query.filter_by(username=data['username']).first():
        return jsonify({'error': 'Пользователь уже существует'}), 400
    
    user = User(
        username=data['username'],
        email=data['email'],
        password_hash=generate_password_hash(data['password']),
        role=data['role']
    )
    db.session.add(user)
    db.session.commit()
    
    create_audit_log(data['admin_id'], 'create_user', 'user', user.id, {'role': data['role']})
    return jsonify({'success': True, 'user_id': user.id})

@app.route('/api/admin/users/<int:user_id>/ban', methods=['POST'])
def ban_user(user_id):
    data = request.json
    user = User.query.get_or_404(user_id)
    user.is_banned = True
    db.session.commit()
    
    create_audit_log(data['admin_id'], 'ban_user', 'user', user_id)
    return jsonify({'success': True})

@app.route('/api/admin/users/<int:user_id>/unban', methods=['POST'])
def unban_user(user_id):
    data = request.json
    user = User.query.get_or_404(user_id)
    user.is_banned = False
    db.session.commit()
    
    create_audit_log(data['admin_id'], 'unban_user', 'user', user_id)
    return jsonify({'success': True})

@app.route('/api/admin/audit', methods=['GET'])
def get_audit_logs():
    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(100).all()
    
    return jsonify([{
        'id': log.id,
        'user': log.user.username,
        'action': log.action,
        'resource_type': log.resource_type,
        'resource_id': log.resource_id,
        'details': json.loads(log.details) if log.details else None,
        'created_at': log.created_at.isoformat()
    } for log in logs])

# Статические файлы
@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        
        # Создаём тестовых пользователей
        if not User.query.filter_by(username='admin').first():
            admin = User(
                username='admin',
                email='admin@samosval.local',
                password_hash=generate_password_hash('admin123'),
                role='admin'
            )
            db.session.add(admin)
        
        if not User.query.filter_by(username='operator').first():
            operator = User(
                username='operator',
                email='operator@samosval.local',
                password_hash=generate_password_hash('operator123'),
                role='operator'
            )
            db.session.add(operator)
        
        if not User.query.filter_by(username='developer').first():
            developer = User(
                username='developer',
                email='developer@samosval.local',
                password_hash=generate_password_hash('developer123'),
                role='developer'
            )
            db.session.add(developer)
        
        db.session.commit()
    
    app.run(debug=True, port=5000)

