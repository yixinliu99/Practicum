from datetime import datetime, timezone
from thaw_action import utils
import json

from globus_action_provider_tools import (
    ActionProviderDescription,
    ActionRequest,
    ActionStatus,
    ActionStatusValue,
    AuthState,
)
from globus_action_provider_tools.authorization import (
    authorize_action_access_or_404,
)
from globus_action_provider_tools.flask import ActionProviderBlueprint
from globus_action_provider_tools.flask.exceptions import ActionNotFound
from globus_action_provider_tools.flask.types import (
    ActionCallbackReturn,
)

thaw_schema = json.load(open('./thaw_action/action_definition/input_schema.json', 'r'))
auth_scope = "https://auth.globus.org/scopes/8e163f0f-2ab9-4898-bb7f-69d6c7e5ac45/action_all"

thaw_description = ActionProviderDescription(
    globus_auth_scope=auth_scope,
    title="Thaw Glacier Objects",
    admin_contact="yixinliu@uchicago.edu",
    synchronous=False,
    input_schema=thaw_schema,
    api_version="1.0",
    subtitle="",
    description="",
    keywords=[],
    visible_to=["public"],
    runnable_by=["all_authenticated_users"],
    administered_by=["yixinliu@uchicago.edu"],
)

thaw_aptb = ActionProviderBlueprint(
    name="apt",
    import_name=__name__,
    url_prefix="/thaw",
    provider_description=thaw_description,
)


@thaw_aptb.action_run
def thaw_action_run(
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
    print(action_request.body)#todo del
    print('\n\n\n\n\n')
    utils.thaw_objects(action_request.body['items'], action_status)
    return action_status

# todo status
@thaw_aptb.action_status
def thaw_action_status(action_id: str, auth: AuthState) -> ActionCallbackReturn:
    """
    Query for the action_id in some storage backend to return the up-to-date
    ActionStatus. It's possible that some ActionProviders will require querying
    an external system to get up to date information on an Action's status.
    """
    res = utils.check_thaw_status(action_id)
    if res is None:
        raise ActionNotFound(f"No action with {action_id}")
    action_status = ActionStatus(
        status=res['status'],
        creator_id=res['creator_id'],
        label=res['label'],
        monitor_by=res['monitor_by'],
        manage_by=res['manage_by'],
        start_time=res['start_time'],
        completion_time=res['completion_time'],
        release_after=res['release_after'],
        display_status=res['display_status'],
        details=res['details'],
    )
    authorize_action_access_or_404(action_status, auth)
    return action_status
