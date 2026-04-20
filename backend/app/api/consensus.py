import traceback

from flask import jsonify, request

from . import consensus_bp
from ..consensus import (
    ConsensusConfigurationError,
    ConsensusStorageError,
    get_consensus_scheduler,
    get_consensus_service,
)
from ..utils.logger import get_logger

logger = get_logger("mirofish.api.consensus")


@consensus_bp.route("/task/start", methods=["POST"])
def start_consensus_task():
    try:
        data = request.get_json() or {}
        service = get_consensus_service()
        task = service.start_task(
            simulation_id=data.get("simulation_id", ""),
            question_text=data.get("question_text", ""),
            threshold_percent=int(data.get("threshold_percent", 0)),
            poll_interval_seconds=data.get("poll_interval_seconds"),
        )
        get_consensus_scheduler().wake()
        return jsonify({"success": True, "data": task})
    except (ValueError, ConsensusConfigurationError, ConsensusStorageError) as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception as exc:
        logger.error(f"start consensus task failed: {exc}")
        return jsonify(
            {"success": False, "error": str(exc), "traceback": traceback.format_exc()}
        ), 500


@consensus_bp.route("/task/current", methods=["GET"])
def get_current_consensus_task():
    try:
        simulation_id = request.args.get("simulation_id", "")
        service = get_consensus_service()
        task = service.get_current_task(simulation_id)
        return jsonify({"success": True, "data": task})
    except (ValueError, ConsensusConfigurationError, ConsensusStorageError) as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception as exc:
        logger.error(f"get current consensus task failed: {exc}")
        return jsonify(
            {"success": False, "error": str(exc), "traceback": traceback.format_exc()}
        ), 500


@consensus_bp.route("/task/<task_uid>", methods=["GET"])
def get_consensus_task(task_uid: str):
    try:
        task = get_consensus_service().get_task(task_uid)
        if not task:
            return jsonify({"success": False, "error": "task not found"}), 404
        return jsonify({"success": True, "data": task})
    except (ValueError, ConsensusConfigurationError, ConsensusStorageError) as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception as exc:
        logger.error(f"get consensus task failed: {exc}")
        return jsonify(
            {"success": False, "error": str(exc), "traceback": traceback.format_exc()}
        ), 500


@consensus_bp.route("/task/<task_uid>/agents", methods=["GET"])
def get_consensus_task_agents(task_uid: str):
    try:
        service = get_consensus_service()
        task = service.get_task(task_uid)
        if not task:
            return jsonify({"success": False, "error": "task not found"}), 404
        cards = service.get_agents_view(task_uid)
        return jsonify({"success": True, "data": {"task": task, "agents": cards}})
    except (ValueError, ConsensusConfigurationError, ConsensusStorageError) as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception as exc:
        logger.error(f"get consensus task agents failed: {exc}")
        return jsonify(
            {"success": False, "error": str(exc), "traceback": traceback.format_exc()}
        ), 500


@consensus_bp.route("/task/stop", methods=["POST"])
def stop_consensus_task():
    try:
        data = request.get_json() or {}
        task_uid = data.get("task_uid", "")
        task = get_consensus_service().stop_task(task_uid)
        if not task:
            return jsonify({"success": False, "error": "task not found"}), 404
        return jsonify({"success": True, "data": task})
    except (ValueError, ConsensusConfigurationError, ConsensusStorageError) as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception as exc:
        logger.error(f"stop consensus task failed: {exc}")
        return jsonify(
            {"success": False, "error": str(exc), "traceback": traceback.format_exc()}
        ), 500


@consensus_bp.route("/tasks", methods=["GET"])
def list_consensus_tasks():
    try:
        simulation_id = request.args.get("simulation_id", "")
        tasks = get_consensus_service().list_tasks(simulation_id)
        return jsonify({"success": True, "data": tasks, "count": len(tasks)})
    except (ValueError, ConsensusConfigurationError, ConsensusStorageError) as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception as exc:
        logger.error(f"list consensus tasks failed: {exc}")
        return jsonify(
            {"success": False, "error": str(exc), "traceback": traceback.format_exc()}
        ), 500


@consensus_bp.route("/catalog/default", methods=["GET"])
def get_default_consensus_catalog():
    try:
        catalog = get_consensus_service().get_default_catalog()
        return jsonify({"success": True, "data": catalog})
    except (ValueError, ConsensusConfigurationError, ConsensusStorageError) as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception as exc:
        logger.error(f"get default consensus catalog failed: {exc}")
        return jsonify(
            {"success": False, "error": str(exc), "traceback": traceback.format_exc()}
        ), 500
