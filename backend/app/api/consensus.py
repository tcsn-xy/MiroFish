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
from ..utils.locale import t

logger = get_logger("mirofish.api.consensus")


@consensus_bp.route("/task/start", methods=["POST"])
def start_consensus_task():
    try:
        data = request.get_json() or {}
        question = data.get("question")
        threshold_percent = data.get("threshold_percent")
        if question is None or str(question).strip() == "":
            return jsonify({"success": False, "error": t("api.consensusRequireQuestion")}), 400
        if not isinstance(threshold_percent, int):
            return jsonify({"success": False, "error": t("api.consensusThresholdInvalid")}), 400

        service = get_consensus_service()
        result = service.start_task(question=question, threshold_percent=threshold_percent)
        get_consensus_scheduler().wake()
        return jsonify({"success": True, "data": result})
    except ConsensusStorageError as exc:
        error_text = str(exc)
        if error_text == "consensus task already running":
            error_text = t("api.consensusTaskAlreadyRunning")
        return jsonify({"success": False, "error": error_text}), 409
    except (ValueError, ConsensusConfigurationError) as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception as exc:
        logger.error(f"start consensus task failed: {exc}")
        return jsonify({"success": False, "error": str(exc), "traceback": traceback.format_exc()}), 500


@consensus_bp.route("/task/current", methods=["GET"])
def get_current_consensus_task():
    try:
        service = get_consensus_service()
        data = service.get_current_task()
        return jsonify({"success": True, "data": data})
    except (ConsensusConfigurationError, ConsensusStorageError) as exc:
        return jsonify({"success": False, "error": str(exc)}), 503
    except Exception as exc:
        logger.error(f"get current consensus task failed: {exc}")
        return jsonify({"success": False, "error": str(exc), "traceback": traceback.format_exc()}), 500


@consensus_bp.route("/task/current/agents", methods=["GET"])
def get_current_consensus_agents():
    try:
        service = get_consensus_service()
        data = service.get_current_agents_view()
        return jsonify({"success": True, "data": data})
    except (ConsensusConfigurationError, ConsensusStorageError) as exc:
        return jsonify({"success": False, "error": str(exc)}), 503
    except Exception as exc:
        logger.error(f"get current consensus agents failed: {exc}")
        return jsonify({"success": False, "error": str(exc), "traceback": traceback.format_exc()}), 500


@consensus_bp.route("/task/stop", methods=["POST"])
def stop_consensus_task():
    try:
        service = get_consensus_service()
        service.stop_current_task()
        get_consensus_scheduler().wake()
        return jsonify({"success": True, "data": {"status": "stopped"}})
    except LookupError:
        return jsonify({"success": False, "error": t("api.consensusNoRunningTask")}), 404
    except (ConsensusConfigurationError, ConsensusStorageError) as exc:
        return jsonify({"success": False, "error": str(exc)}), 503
    except Exception as exc:
        logger.error(f"stop consensus task failed: {exc}")
        return jsonify({"success": False, "error": str(exc), "traceback": traceback.format_exc()}), 500
