import logging
from flask import Flask
from thaw_action.profile import thaw_aptb
from globus_action_provider_tools.flask.helpers import assign_json_provider
from DataTypes import DataTypes
import json


def create_app():
    app = Flask(__name__)
    app.datatypes = set_env()
    app.config.from_object(app.datatypes)
    assign_json_provider(app)
    app.logger.setLevel(logging.DEBUG)
    app.register_blueprint(thaw_aptb)

    return app


def set_env() -> DataTypes:
    with open("./.env", 'r') as file:
        vs = json.load(file)
    dt = DataTypes(vs)
    return dt


app = create_app()

if __name__ == '__main__':
    app.run()
