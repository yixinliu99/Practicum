from datetime import datetime, timezone
from typing import Dict, List, Set

from flask import request
from pydantic import BaseModel, Field

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


class ActionProviderInput(BaseModel):
    utc_offset: int = Field(
        ..., title="UTC Offset", description="An input value to this ActionProvider"
    )

    class Config:
        schema_extra = {"example": {"utc_offset": 10}}


description = ActionProviderDescription(
    globus_auth_scope="https://auth.globus.org/scopes/d3a66776-759f-4316-ba55-21725fe37323/action_all",
    title="What Time Is It Right Now?",
    admin_contact="support@whattimeisrightnow.example",
    synchronous=True,
    input_schema=ActionProviderInput,
    api_version="1.0",
    subtitle="Another exciting promotional tie-in for whattimeisitrightnow.com",
    description="",
    keywords=["time", "whattimeisitnow", "productivity"],
    visible_to=["public"],
    runnable_by=["all_authenticated_users"],
    administered_by=["support@whattimeisrightnow.example"],
)

aptb = ActionProviderBlueprint(
    name="apt",
    import_name=__name__,
    url_prefix="/apt",
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
    simple_backend[action_status.action_id] = action_status
    return action_status


@aptb.action_status
def my_action_status(action_id: str, auth: AuthState) -> ActionCallbackReturn:
    """
    Query for the action_id in some storage backend to return the up-to-date
    ActionStatus. It's possible that some ActionProviders will require querying
    an external system to get up to date information on an Action's status.
    """
    action_status = simple_backend.get(action_id)
    if action_status is None:
        raise ActionNotFound(f"No action with {action_id}")
    authorize_action_access_or_404(action_status, auth)
    return action_status
