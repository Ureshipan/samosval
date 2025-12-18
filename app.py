import os

from flask import Flask, redirect, url_for

from samosval.db import init_app as init_db_app, init_db_if_needed
from samosval.auth import login_manager
from samosval.simulator.engine import SimulationEngine
from samosval.routes.auth_routes import auth_bp
from samosval.routes.dashboard_routes import dashboard_bp
from samosval.routes.request_routes import requests_bp
from samosval.routes.build_routes import builds_bp
from samosval.routes.image_routes import images_bp
from samosval.routes.deployment_routes import deployments_bp
from samosval.routes.admin_routes import admin_bp
from samosval.routes.api_routes import api_bp


def create_app() -> Flask:
    app = Flask(
        __name__,
        instance_relative_config=True,
        template_folder="samosval/templates",
        static_folder="samosval/static",
    )

    # Basic config
    app.config.from_mapping(
        SECRET_KEY="dev-secret-change-me",
        DATABASE=os.path.join(app.instance_path, "samosval.sqlite3"),
    )

    os.makedirs(app.instance_path, exist_ok=True)

    # DB / auth
    init_db_app(app)
    login_manager.init_app(app)

    # Blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(requests_bp)
    app.register_blueprint(builds_bp)
    app.register_blueprint(images_bp)
    app.register_blueprint(deployments_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(api_bp, url_prefix="/api")

    # Default route
    @app.route("/")
    def index():
        return redirect(url_for("dashboard.dashboard"))

    # Init DB and root user
    with app.app_context():
        init_db_if_needed()

    # Start simulation engine
    engine = SimulationEngine(app)
    engine.start()

    return app


if __name__ == "__main__":
    application = create_app()
    application.run(debug=True)


