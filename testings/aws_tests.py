from app import create_app


def test_thaw():
    from globus_action_provider_tools import ActionStatus, ActionStatusValue
    from thaw_action.utils import thaw_objects
    from datetime import datetime
    dummy_action_status = ActionStatus(action_id='1', status=ActionStatusValue.ACTIVE,
                                       display_status=ActionStatusValue.ACTIVE,
                                       completion_time=datetime.now().isoformat(),
                                       creator_id='urn:globus:auth:identity:123e4567-e89b-12d3-a456-426614174000',
                                       details='{}')
    app = create_app()
    json_encoder = app.json
    dummy_action_status = json_encoder.loads(json_encoder.dumps(dummy_action_status))
    res = thaw_objects(['/mpcs-practicum/testdata/'], dummy_action_status)


def test_check_thaw_status():
    from thaw_action.utils import check_thaw_status
    res = check_thaw_status('1')


def test_all():
    test_thaw()
    test_check_thaw_status()
