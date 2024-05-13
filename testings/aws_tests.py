from app import create_app


def test_thaw():
    from globus_action_provider_tools import ActionStatus, ActionStatusValue
    from thaw_action.backend import thaw_objects
    from datetime import datetime
    dummy_action_status = {'action_id': 'UWt6fUdVZLZ5', 'completion_time': None,
                           'creator_id': 'urn:globus:auth:identity:cbfba6c9-1a8f-4d42-9041-c73fa6e7d87d', 'details': {},
                           'display_status': 'ACTIVE', 'label': None,
                           'manage_by': ['urn:globus:auth:identity:cbfba6c9-1a8f-4d42-9041-c73fa6e7d87d'],
                           'monitor_by': ['urn:globus:auth:identity:cbfba6c9-1a8f-4d42-9041-c73fa6e7d87d'],
                           'release_after': 'P30D',
                           'start_time': '2024-05-13T19:42:06.795219+00:00', 'status': 'ACTIVE'}
    dummy_action_status = ActionStatus(action_id='UWt6fUdVZLZ5', completion_time=None, creator_id='urn:globus:auth:identity:cbfba6c9-1a8f-4d42-9041-c73fa6e7d87d',
                                       details={}, display_status='ACTIVE', label=None, manage_by=['urn:globus:auth:identity:cbfba6c9-1a8f-4d42-9041-c73fa6e7d87d'],
                                       monitor_by=['urn:globus:auth:identity:cbfba6c9-1a8f-4d42-9041-c73fa6e7d87d'], release_after='P30D',
                                       start_time=datetime.fromisoformat('2024-05-13T19:42:06.795219+00:00'), status='ACTIVE')
    app = create_app()
    json_encoder = app.json
    dummy_action_status = json_encoder.loads(json_encoder.dumps(dummy_action_status))
    res = thaw_objects(['/mpcs-practicum/testdata/'], dummy_action_status)


def test_check_thaw_status():
    from thaw_action.backend import check_thaw_status
    res = check_thaw_status('1')


def test_all():
    test_thaw()
    test_check_thaw_status()
