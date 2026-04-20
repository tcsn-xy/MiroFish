"""
API路由模块
"""

from flask import Blueprint

graph_bp = Blueprint('graph', __name__)
simulation_bp = Blueprint('simulation', __name__)
report_bp = Blueprint('report', __name__)
world_info_bp = Blueprint('world_info', __name__)
consensus_bp = Blueprint('consensus', __name__)

from . import graph  # noqa: E402, F401
from . import simulation  # noqa: E402, F401
from . import report  # noqa: E402, F401
from . import world_info  # noqa: E402, F401
from . import consensus  # noqa: E402, F401

