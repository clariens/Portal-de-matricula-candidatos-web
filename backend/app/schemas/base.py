from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class ApiModel(BaseModel):
    """Modelos expostos ao front em camelCase."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
