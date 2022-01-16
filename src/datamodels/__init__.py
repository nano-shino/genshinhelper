import json

from sqlalchemy import TypeDecorator, Text
from sqlalchemy.ext.declarative import declarative_base

from utils import serialization

Base = declarative_base()


class Jsonizable(TypeDecorator):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if not value:
            return None
        # Convert Python to SQL model
        return json.dumps(value, cls=serialization.EnhancedJSONEncoder)

    process_literal_param = process_bind_param

    def process_result_value(self, value, dialect):
        if not value:
            return None
        # Convert SQL to Python model
        return json.loads(value)

    @property
    def python_type(self):
        return object
