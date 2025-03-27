import abc
import logging
import typing
import uuid

from pystac import Item as PyStacItem
from pystac_monty.geocoding import TheirGeocoder
from pystac_monty.sources.common import MontyDataTransformer

from apps.etl.models import ExtractionData, PyStacLoadData, Transform, get_trace_id
from main.celery import app
from main.configs import etl_config
from main.logging import log_extra
from main.managers import BulkCreateManager

logger = logging.getLogger(__name__)

# FIXME: Instead of literal use enum from pystac
ITEM_TYPE_COLLECTION_ID_MAP = {
    "idmc-idu-events": PyStacLoadData.ItemType.EVENT,
    "idmc-idu-impacts": PyStacLoadData.ItemType.IMPACT,
    "idmc-gidd-events": PyStacLoadData.ItemType.EVENT,
    "idmc-gidd-impacts": PyStacLoadData.ItemType.IMPACT,
    "gfd-events": PyStacLoadData.ItemType.EVENT,
    "gfd-impacts": PyStacLoadData.ItemType.IMPACT,
    "gfd-hazards": PyStacLoadData.ItemType.HAZARD,
    "ifrcevent-events": PyStacLoadData.ItemType.EVENT,
    "ifrcevent-impacts": PyStacLoadData.ItemType.IMPACT,
    "desinventar-events": PyStacLoadData.ItemType.EVENT,
    "desinventar-impacts": PyStacLoadData.ItemType.IMPACT,
    "desinventar-hazards": PyStacLoadData.ItemType.HAZARD,
    "pdc-events": PyStacLoadData.ItemType.EVENT,
    "pdc-hazards": PyStacLoadData.ItemType.HAZARD,
    "pdc-impacts": PyStacLoadData.ItemType.IMPACT,
    "glide-events": PyStacLoadData.ItemType.EVENT,
    "glide-hazards": PyStacLoadData.ItemType.HAZARD,
    "emdat-events": PyStacLoadData.ItemType.EVENT,
    "emdat-hazards": PyStacLoadData.ItemType.HAZARD,
    "emdat-impacts": PyStacLoadData.ItemType.IMPACT,
    "ibtracs-events": PyStacLoadData.ItemType.EVENT,
    "ibtracs-hazards": PyStacLoadData.ItemType.HAZARD,
    "usgs-events": PyStacLoadData.ItemType.EVENT,
    "usgs-hazards": PyStacLoadData.ItemType.HAZARD,
    "usgs-impacts": PyStacLoadData.ItemType.IMPACT,
    "gdacs-events": PyStacLoadData.ItemType.EVENT,
    "gdacs-impacts": PyStacLoadData.ItemType.IMPACT,
    "gdacs-hazards": PyStacLoadData.ItemType.HAZARD,
}


Transformer = typing.TypeVar("Transformer", bound=MontyDataTransformer)
TransformerSchema = typing.TypeVar("TransformerSchema")


class BaseTransformerHandler(abc.ABC, typing.Generic[Transformer, TransformerSchema]):
    transformer_class: typing.Type[Transformer]
    transformer_schema: typing.Type[TransformerSchema]

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if getattr(cls, "transformer_class", None) is None:
            raise NotImplementedError(f"Please define transformer_class for {cls}")
        if getattr(cls, "get_schema_data", None) is None:
            raise NotImplementedError(f"Please define get_schema_data method for {cls}")

    @classmethod
    @abc.abstractmethod
    def get_schema_data(cls, extraction_obj: ExtractionData) -> TransformerSchema:
        raise NotImplementedError()

    @classmethod
    def handle_transformation(cls, extraction_id: int):
        logger.info("Transformation started")
        extraction_obj = ExtractionData.objects.get(id=extraction_id)

        if not extraction_obj.resp_data:
            logger.info("Transformation ended because there is no data")
            return

        transform_obj = Transform.objects.create(
            extraction=extraction_obj,
            trace_id=get_trace_id(extraction_obj),
        )

        transform_obj.mark_as_started()
        try:
            geocoder = TheirGeocoder(etl_config.GEOCODER_URL)

            schema = cls.get_schema_data(extraction_obj)
            transformer = cls.transformer_class(schema, geocoder)

            transformed_items = transformer.make_items()

            cls.load_stac_item_to_queue(transform_obj, transformed_items)

            summary = transformer.transform_summary
            transform_obj.metadata["summary"] = {
                "failed_rows": summary.failed_rows,
                "total_rows": summary.total_rows,
            }
            transform_obj.mark_as_ended(Transform.Status.SUCCESS, update_fields=["metadata"])
            logger.info("Transformation ended")
        except Exception as e:
            logger.error(
                "Transformation failed",
                exc_info=True,
                extra=log_extra({"extraction_id": extraction_obj.id}),
            )
            transform_obj.mark_as_ended(Transform.Status.FAILED)
            # FIXME: Check if this creates duplicate entry in Sentry. if yes, remove this.
            raise e

    @classmethod
    def load_stac_item_to_queue(cls, transform_obj: Transform, transform_items: list[PyStacItem]):
        logger.info("Loading data into queue")

        bulk_mgr = BulkCreateManager(chunk_size=1000)
        for item in transform_items:
            # FIXME: We need to check if we have collection_id
            item_type = ITEM_TYPE_COLLECTION_ID_MAP[item.collection_id]
            transformed_item_dict = item.to_dict()
            transformed_item_dict["properties"]["monty:etl_id"] = str(uuid.uuid4())
            bulk_mgr.add(
                PyStacLoadData(
                    transform_id=transform_obj,
                    item=transformed_item_dict,
                    collection_id=item.collection_id,
                    item_type=item_type,
                    trace_id=get_trace_id(transform_obj),
                )
            )

        bulk_mgr.done()

        logger.info("Loading data into queue successfull")

    @staticmethod
    @app.task
    def task(extraction_id: int) -> None:
        """
        Not NotImplemented due to celery limitation with classmethod
        Eg: return XYZTransformHandler.handle_transformation(extraction_id)
        """
        raise NotImplementedError()
