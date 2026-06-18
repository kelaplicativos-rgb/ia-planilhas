from __future__ import annotations

import bling_app_zero.ui.home_download_v2 as _impl
from bling_app_zero.core.send_validation_v2 import validate_before_bling_send

_impl.validate_before_bling_send = validate_before_bling_send

from bling_app_zero.ui.home_download_v2 import *  # noqa: F401,F403
