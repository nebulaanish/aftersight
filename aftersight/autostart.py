import os

from aftersight import constants

if os.environ.get(constants.ENV_AUTOSTART) == "1":
    import aftersight

    aftersight.start(session_id=os.environ.get(constants.ENV_SESSION) or None)
