import pandas as pd
import json
from celery import chain, shared_task

from apps.etl.extraction.sources.emdat.extract import import_hazard_data as import_emdat_data
# from apps.etl.transform.sources.glide import transform_glide_event_data
from apps.etl.transform.sources.base import transform_data
from apps.etl.models import ExtractionData
from apps.etl.utils import read_file_data

from pystac_monty.sources.emdat import EMDATDataSource, EMDATTransformer


# @shared_task
def import_emdat_hazard_data(**kwargs):

    ext_id = import_emdat_data()

    ext_instance = ExtractionData.objects.get(id=ext_id)
    # data = read_file_data(ext_instance.resp_data)
    # print("DATa type", type(data))
    # df = pd.DataFrame(json.load(data))
    with ext_instance.resp_data.open('r') as file:
        data = file.read()

    # print("Data", data)
    json_data = json.loads(data)

    # Convert to DataFrame
    data = json_data["data"]["public_emdat"]["data"]
    df = pd.DataFrame(data)
    print("DAta frame", df)

    transform_data(
        ExtractionData.Source.EMDAT,
        EMDATTransformer,
        EMDATDataSource,
        ext_id,
        df
    )
    # items = transformer.make_items()
    # print("Transform data", items)

    # event_workflow = chain(
    #     import_glide_data.s(
    #         hazard_type=hazard_type,
    #         hazard_type_str=hazard_type_str,
    #     ),
    #     transform_glide_event_data.s(),
    # )
    # event_workflow.apply_async()
