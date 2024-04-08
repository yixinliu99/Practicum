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
def my_action_run(action_request: ActionRequest, auth: AuthState):
    pass


@aptb.action_status
def my_action_status(action_id: str, auth: AuthState):
    pass


@aptb.action_cancel
def my_action_cancel(action_id: str, auth: AuthState):
    pass


@aptb.action_release
def my_action_release(action_id: str, auth: AuthState):
    pass


@aptb.action_log
def my_action_log(action_id: str, auth: AuthState):
    pass
