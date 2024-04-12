from datetime import datetime, timezone
from typing import Dict, List, Set
import utils
import json

from flask import request

from globus_action_provider_tools import (
    ActionProviderDescription,
    ActionRequest,
    ActionStatus,
    ActionStatusValue,
    AuthState,
)
from globus_action_provider_tools.authorization import (
    authorize_action_access_or_404,
    authorize_action_management_or_404,
)
from globus_action_provider_tools.flask import ActionProviderBlueprint
from globus_action_provider_tools.flask.exceptions import ActionConflict, ActionNotFound
from globus_action_provider_tools.flask.types import (
    ActionCallbackReturn,
    ActionLogReturn,
)


schema = json.load(open('schema.json', 'r'))


description = ActionProviderDescription(
    globus_auth_scope="https://auth.globus.org/scopes/8e163f0f-2ab9-4898-bb7f-69d6c7e5ac45/action_all",
    title="Thaw files",
    admin_contact="yixinliu@uchicago.edu",
    synchronous=False,
    input_schema=schema,
    api_version="1.0",
    subtitle="",
    description="",
    keywords=[],
    visible_to=["public"],
    runnable_by=["all_authenticated_users"],
    administered_by=["yixinliu@uchicago.edu"],
)

aptb = ActionProviderBlueprint(
    name="apt",
    import_name=__name__,
    url_prefix="/thaw",
    provider_description=description,
)


@aptb.action_run
def my_action_run(
        action_request: ActionRequest, auth: AuthState
) -> ActionCallbackReturn:
    """
    Implement custom business logic related to instantiating an Action here.
    Once launched, collect details on the Action and create an ActionStatus
    which records information on the instantiated Action and gets stored.
    """
    action_status = ActionStatus(
        status=ActionStatusValue.ACTIVE,
        creator_id=str(auth.effective_identity),
        label=action_request.label or None,
        monitor_by=action_request.monitor_by or auth.identities,
        manage_by=action_request.manage_by or auth.identities,
        start_time=datetime.now(timezone.utc).isoformat(),
        completion_time=None,
        release_after=action_request.release_after or "P30D",
        display_status=ActionStatusValue.ACTIVE,
        details={},
    )
    # simple_backend[action_status.action_id] = action_status
    return action_status


@aptb.action_status
def my_action_status(action_id: str, auth: AuthState) -> ActionCallbackReturn:
    """
    Query for the action_id in some storage backend to return the up-to-date
    ActionStatus. It's possible that some ActionProviders will require querying
    an external system to get up to date information on an Action's status.
    """
    action_status = True
    if action_status is None:
        raise ActionNotFound(f"No action with {action_id}")
    authorize_action_access_or_404(action_status, auth)
    return action_status
