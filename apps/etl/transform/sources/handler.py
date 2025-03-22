import abc
import logging
import typing
import uuid

from django.conf import settings
from pystac_monty.geocoding import GAULGeocoder
from pystac_monty.sources.common import MontyDataTransformer

from apps.etl.models import ExtractionData, PyStacLoadData, Transform, get_trace_id
from main.celery import app
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
}


Transformer = typing.TypeVar("Transformer", bound=MontyDataTransformer)


class BaseTransformerHandler(abc.ABC, typing.Generic[Transformer]):
    transformer_class: typing.Type[Transformer]

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if getattr(cls, "transformer_class", None) is None:
            raise NotImplementedError(f"Please define transformer_class for {cls}")
        if getattr(cls, "get_schema_data", None) is None:
            raise NotImplementedError(f"Please define get_schema_data method for {cls}")

    @classmethod
    @abc.abstractmethod
    def get_schema_data(cls, extraction_obj: ExtractionData):
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
            status=Transform.Status.PENDING,
            trace_id=get_trace_id(extraction_obj),
        )

        try:
            geocoder = GAULGeocoder(gpkg_path=None, service_base_url=settings.GEOCODER_URL)

            schema = cls.get_schema_data(extraction_obj)
            transformer = cls.transformer_class(schema, geocoder)

            transformed_items = transformer.make_items()

            transform_obj.status = Transform.Status.SUCCESS
            transform_obj.save(update_fields=["status"])

            cls.load_stac_item_to_queue(transformed_items, transform_obj.id)
            logger.info("Transformation ended")
        except Exception as e:
            logger.error("Transformation failed", exc_info=True, extra=log_extra({"extraction_id": extraction_obj.id}))
            transform_obj.status = Transform.Status.FAILED
            transform_obj.save(update_fields=["status"])
            # FIXME: Check if this creates duplicate entry in Sentry. if yes, remove this.
            raise e

    @classmethod
    def load_stac_item_to_queue(cls, transform_items, transform_obj_id):
        logger.info("Loading data into queue")

        transform_obj = Transform.objects.get(id=transform_obj_id)

        bulk_mgr = BulkCreateManager(chunk_size=1000)
        for item in transform_items:
            item_type = ITEM_TYPE_COLLECTION_ID_MAP[item.collection_id]
            transformed_item_dict = item.to_dict()
            transformed_item_dict["properties"]["monty:etl_id"] = str(uuid.uuid4())
            bulk_mgr.add(
                PyStacLoadData(
                    transform_id=transform_obj,
                    item=transformed_item_dict,
                    collection_id=item.collection_id,
                    item_type=item_type,
                    load_status=PyStacLoadData.LoadStatus.PENDING,
                    trace_id=get_trace_id(transform_obj),
                )
            )

        bulk_mgr.done()

        transform_obj.is_loaded = True
        transform_obj.save(update_fields=["is_loaded"])

        logger.info("Loading data into queue successfull")

    @staticmethod
    @app.task
    def task(extraction_id: int):
        """
        Not NotImplemented due to celery limitation with classmethod
        Eg: return XYZTransformHandler.handle_transformation(extraction_id)
        """
        raise NotImplementedError()
