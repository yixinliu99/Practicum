from datetime import datetime, timezone
import json
from flask import current_app
from globus_action_provider_tools import (
    ActionProviderDescription,
    ActionRequest,
    ActionStatus,
    ActionStatusValue,
    AuthState,
)
from globus_action_provider_tools.authorization import (
    authorize_action_access_or_404, authorize_action_management_or_404,
)
from globus_action_provider_tools.flask import ActionProviderBlueprint
from globus_action_provider_tools.flask.exceptions import ActionNotFound, ActionConflict
from globus_action_provider_tools.flask.types import (
    ActionCallbackReturn,
)
from thaw_action.backend import get_thaw_status, thaw_objects, check_thaw_status, update_thaw_status

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
        action_id=action_request.request_id,
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
    json_encoder = current_app.json
    action_status_dict = json_encoder.loads(json_encoder.dumps(action_status))
    thaw_objects(action_request.body['items'], action_status_dict)
    return _dict_to_action_status(action_status_dict)


@thaw_aptb.action_status
def thaw_action_status(action_id: str, auth: AuthState) -> ActionCallbackReturn:
    """
    Query for the action_id in some storage backend to return the up-to-date
    ActionStatus. It's possible that some ActionProviders will require querying
    an external system to get up to date information on an Action's status.
    """
    action_status, res = check_thaw_status(action_id)
    if res is None:
        raise ActionNotFound(f"No action with {action_id}")
    if res:
        update_thaw_status(action_id, ActionStatusValue.SUCCEEDED)
        action_status['status'] = ActionStatusValue.SUCCEEDED
        action_status['display_status'] = ActionStatusValue.SUCCEEDED
        action_status = _dict_to_action_status(action_status)

    authorize_action_access_or_404(action_status, auth)
    return action_status


@thaw_aptb.action_cancel
def thaw_action_cancel(action_id: str, auth: AuthState) -> ActionCallbackReturn:
    """
    Only Actions that are not in a completed state may be cancelled.
    Cancellations do not necessarily require that an Action's execution be
    stopped. Once cancelled, the ActionStatus object should be updated and
    stored.
    """
    action_status = get_thaw_status(action_id)
    if action_status is None:
        raise ActionNotFound(f"No action with {action_id}")
    action_status = _dict_to_action_status(action_status)
    authorize_action_management_or_404(action_status, auth)
    if action_status.is_complete():
        raise ActionConflict("Cannot cancel complete action")

    action_status.status = ActionStatusValue.FAILED
    action_status.display_status = f"Cancelled by {auth.effective_identity}"
    json_encoder = current_app.json
    update_thaw_status(action_id, json_encoder.loads(json_encoder.dumps(action_status)))
    return action_status


@thaw_aptb.action_release
def thaw_action_release(action_id: str, auth: AuthState) -> ActionCallbackReturn:
    """
    Only Actions that are in a completed state may be released. The release
    operation removes the ActionStatus object from the data store. The final, up
    to date ActionStatus is returned after a successful release.
    """
    action_status_dict = get_thaw_status(action_id)
    if action_status_dict is None:
        raise ActionNotFound(f"No action with {action_id}")
    action_status = _dict_to_action_status(action_status_dict)

    authorize_action_management_or_404(action_status, auth)
    if not action_status.is_complete():
        raise ActionConflict("Cannot release incomplete Action")

    action_status.display_status = f"Released by {auth.effective_identity}"
    json_encoder = current_app.json
    update_thaw_status(action_id, json_encoder.loads(json_encoder.dumps(action_status)))

    return action_status


def _dict_to_action_status(action_status_dict: dict) -> ActionStatus:
    return ActionStatus(
        action_id=action_status_dict['action_id'],
        status=action_status_dict['status'],
        creator_id=action_status_dict['creator_id'],
        label=action_status_dict['label'],
        monitor_by=action_status_dict['monitor_by'],
        manage_by=action_status_dict['manage_by'],
        start_time=action_status_dict['start_time'],
        completion_time=action_status_dict['completion_time'],
        release_after=action_status_dict['release_after'],
        display_status=action_status_dict['display_status'],
        details=action_status_dict['details'],
    )
