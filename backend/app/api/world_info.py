import traceback

from flask import jsonify, request

from . import world_info_bp
from ..models.project import ProjectManager
from ..utils.logger import get_logger
from ..utils.locale import t
from ..world_info import WorldInfoDependencyError, WorldInfoStorageError, get_world_info_service

logger = get_logger("mirofish.api.world_info")


def _require_project(project_id: str):
    project = ProjectManager.get_project(project_id)
    if not project:
        return None, (
            jsonify({"success": False, "error": t("api.projectNotFound", id=project_id)}),
            404,
        )
    return project, None


@world_info_bp.route("/ingest", methods=["POST"])
def ingest_world_info():
    try:
        data = request.get_json() or {}
        project_id = data.get("project_id")
        content = data.get("content")

        if not project_id:
            return jsonify({"success": False, "error": t("api.requireProjectId")}), 400
        if not content:
            return jsonify({"success": False, "error": "content is required"}), 400

        _, error_response = _require_project(project_id)
        if error_response:
            return error_response

        service = get_world_info_service()
        result = service.ingest(
            project_id=project_id,
            content=content,
            title=data.get("title"),
            source=data.get("source"),
            source_type=data.get("source_type"),
            published_at=data.get("published_at"),
            metadata=data.get("metadata") or {},
        )
        return jsonify({"success": True, "data": result})

    except (ValueError, WorldInfoDependencyError, WorldInfoStorageError) as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception as exc:
        logger.error(f"world info ingest failed: {exc}")
        return jsonify(
            {"success": False, "error": str(exc), "traceback": traceback.format_exc()}
        ), 500


@world_info_bp.route("/search", methods=["POST"])
def search_world_info():
    try:
        data = request.get_json() or {}
        project_id = data.get("project_id")
        query = data.get("query")
        top_k = data.get("top_k")

        if not project_id:
            return jsonify({"success": False, "error": t("api.requireProjectId")}), 400
        if not query:
            return jsonify({"success": False, "error": "query is required"}), 400

        _, error_response = _require_project(project_id)
        if error_response:
            return error_response

        service = get_world_info_service()
        hits = service.search(project_id=project_id, query=query, top_k=top_k)
        return jsonify({"success": True, "data": {"hits": [hit.to_dict() for hit in hits]}})

    except (ValueError, WorldInfoDependencyError, WorldInfoStorageError) as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception as exc:
        logger.error(f"world info search failed: {exc}")
        return jsonify(
            {"success": False, "error": str(exc), "traceback": traceback.format_exc()}
        ), 500


@world_info_bp.route("/project/<project_id>/items", methods=["GET"])
def list_world_info_items(project_id: str):
    try:
        _, error_response = _require_project(project_id)
        if error_response:
            return error_response

        page = request.args.get("page", 1, type=int)
        page_size = request.args.get("page_size", 20, type=int)
        service = get_world_info_service()
        data = service.list_items(project_id=project_id, page=page, page_size=page_size)
        return jsonify({"success": True, "data": data})

    except (ValueError, WorldInfoDependencyError, WorldInfoStorageError) as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception as exc:
        logger.error(f"world info list failed: {exc}")
        return jsonify(
            {"success": False, "error": str(exc), "traceback": traceback.format_exc()}
        ), 500


@world_info_bp.route("/project/<project_id>/stats", methods=["GET"])
def world_info_stats(project_id: str):
    try:
        _, error_response = _require_project(project_id)
        if error_response:
            return error_response

        service = get_world_info_service()
        return jsonify({"success": True, "data": service.stats(project_id)})

    except (ValueError, WorldInfoDependencyError, WorldInfoStorageError) as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception as exc:
        logger.error(f"world info stats failed: {exc}")
        return jsonify(
            {"success": False, "error": str(exc), "traceback": traceback.format_exc()}
        ), 500
