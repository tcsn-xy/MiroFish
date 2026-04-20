"""MiroFish backend application factory."""

from __future__ import annotations

import os
import warnings

from flask import Flask, request
from flask_cors import CORS

from .config import Config
from .consensus import get_consensus_scheduler, get_consensus_service
from .utils.logger import get_logger, setup_logger

warnings.filterwarnings("ignore", message=".*resource_tracker.*")


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    if hasattr(app, "json") and hasattr(app.json, "ensure_ascii"):
        app.json.ensure_ascii = False

    logger = setup_logger("mirofish")

    is_reloader_process = os.environ.get("WERKZEUG_RUN_MAIN") == "true"
    debug_mode = app.config.get("DEBUG", False)
    should_log_startup = not debug_mode or is_reloader_process

    if should_log_startup:
        logger.info("=" * 50)
        logger.info("MiroFish Backend starting")
        logger.info("=" * 50)

    CORS(app, resources={r"/api/*": {"origins": "*"}})

    from .services.simulation_runner import SimulationRunner

    SimulationRunner.register_cleanup()
    if should_log_startup:
        logger.info("Registered simulation cleanup hooks")

    @app.before_request
    def log_request():
        request_logger = get_logger("mirofish.request")
        request_logger.debug(f"Request: {request.method} {request.path}")
        if request.content_type and "json" in request.content_type:
            request_logger.debug(f"Request body: {request.get_json(silent=True)}")

    @app.after_request
    def log_response(response):
        request_logger = get_logger("mirofish.request")
        request_logger.debug(f"Response: {response.status_code}")
        return response

    from .api import consensus_bp, graph_bp, report_bp, simulation_bp, world_info_bp

    app.register_blueprint(graph_bp, url_prefix="/api/graph")
    app.register_blueprint(simulation_bp, url_prefix="/api/simulation")
    app.register_blueprint(report_bp, url_prefix="/api/report")
    app.register_blueprint(world_info_bp, url_prefix="/api/world-info")
    app.register_blueprint(consensus_bp, url_prefix="/api/consensus")

    @app.route("/health")
    def health():
        return {"status": "ok", "service": "MiroFish Backend"}

    if Config.CONSENSUS_ENABLED and should_log_startup:
        try:
            interrupted_count = get_consensus_service().interrupt_running_tasks()
            if interrupted_count:
                logger.info(
                    f"Interrupted {interrupted_count} stale consensus task(s) on startup"
                )
        except Exception as exc:
            logger.error(f"Failed to interrupt stale consensus tasks: {exc}")

        try:
            get_consensus_scheduler().start()
        except Exception as exc:
            logger.error(f"Failed to start consensus scheduler: {exc}")

    if should_log_startup:
        logger.info("MiroFish Backend startup complete")

    return app

