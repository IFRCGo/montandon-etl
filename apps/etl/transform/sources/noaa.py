from pystac_monty.source.noaa_ibtracs import (
    NoaaIbtracsSource,
    NoaaIbtracsTransformer,
)

@shared_task
def transform_event_data(event_extraction_data):
    logger.info("Transform started for event data for noaa")
    noaa_instance = ExtractionData.objects.get(id=event_extraction_data["extraction_id"])
    data = read_file_data(noaa_instance.resp_data)
    transform_obj = Tranform.objects.create(
        extraction=noaa_instance,
        status=Transform.Status.PENDING,
    )

    bulk_mgr = BulkCreateManager(chunk_size=1000)
    try:
        transformer = NoaaIbtracsTransformer(NoaaIbtracsSource(source_url=noaa_instance.url, data=data))
        transformed_event_items = transformer.make_items()

        transform_obj.status = Transform.Status.SUCCESS
        transform_obj.save(update_fields=["status"])
    except Exception as e:
        logger.error("Noaa  transformation failed", exc_info=True, extra={"extraction_id": noaa_instance.id})
        transform_obj.status = Transform.Status.FAILED
        transform_obj.save(update_fields=["status"])
        raise e


    bulk_mgr.done()

    transform_obj.is_loaded = True
    transform_obj.save(update_fields=["is_loaded"])

    logger.info("Transformation ended for noaa  data")


