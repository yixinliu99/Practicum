import logging
from flask import Flask
import config
from thaw_action.profile import thaw_aptb
from globus_action_provider_tools.flask.helpers import assign_json_provider
from DataTypes import DataTypes


def create_app():
    app = Flask(__name__)
    assign_json_provider(app)
    app.logger.setLevel(logging.DEBUG)
    app.config.from_object(config)
    app.register_blueprint(thaw_aptb)
    app.datatypes = set_env()

    return app


def set_env() -> DataTypes:
    vs = {}
    with open("./.env", 'r') as file:
        for line in file:
            key, value = line.strip().split(' = ')
            vs[key] = value
    dt = DataTypes(vs)

    return dt


app = create_app()
app.run()
