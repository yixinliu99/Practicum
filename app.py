import logging
from flask import Flask
import config
from thaw_action.profile import thaw_aptb
from globus_action_provider_tools.flask.helpers import assign_json_provider


def create_app():
    app = Flask(__name__)
    assign_json_provider(app)
    app.logger.setLevel(logging.DEBUG)
    app.config.from_object(config)
    app.register_blueprint(thaw_aptb)
    return app


#
# app = create_app()
# app.run()

if __name__ == '__main__':
    from testings import aws_tests
    aws_tests.test_all()
