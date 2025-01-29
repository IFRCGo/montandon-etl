from pystac_monty.sources.idu import IDUDataSource, IDUTransformer

from apps.etl.transform.sources.handler import BaseTransformer


class IDUTransformHandler(BaseTransformer):
    def __init__(self, extraction_id: str, transformer_schema: IDUDataSource, transformer=IDUTransformer):
        super().__init__(extraction_id, transformer, transformer_schema)
