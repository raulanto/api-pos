from typing import ClassVar

from pydantic import BaseModel, ConfigDict, model_serializer


class EmbeddableModel(BaseModel):
    """Base para respuestas con relaciones embebidas opcionales (`?include=`).

    La subclase declara `_embed_fields` con los nombres de los campos de
    relación. En la serialización, esos campos se OMITEN si valen None (no se
    pidieron en `include`, o la relación está vacía). El resto de campos None
    del recurso se conservan tal cual.
    """

    model_config = ConfigDict(from_attributes=True)

    _embed_fields: ClassVar[tuple[str, ...]] = ()

    @model_serializer(mode="wrap")
    def _drop_absent_embeds(self, handler):
        data = handler(self)
        for campo in self._embed_fields:
            if data.get(campo) is None:
                data.pop(campo, None)
        return data
