import logging

from celery import shared_task

from apps.etl.extraction.sources.desinventar.extract import (
    DesinventarExtractionMetadata,
    DesInventarExtractionParamsMetadata,
    DesinventarExtractionV2,
    DesiventarMetadataType,
)
from main.configs import etl_config

logger = logging.getLogger(__name__)

# list of countries which has same country_code and iso3
country_code_iso3_list = [
    "ago",
    "alb",
    "arg",
    "arm",
    "atg",
    "bfa",
    "bdi",
    "blr",
    "blz",
    "bol",
    "brb",
    "btn",
    "chl",
    "col",
    "com",
    "cpv",
    "cri",
    "dji",
    "dma",
    "dom",
    "ecu",
    "egy",
    "esp",
    "eth",
    "gha",
    "gin",
    "gmb",
    "gnb",
    "gnq",
    "grd",
    "gtm",
    "guy",
    "hnd",
    "idn",
    "irn",
    "irq",
    "jam",
    "jor",
    "ken",
    "khm",
    "kna",
    "lao",
    "lbn",
    "lbr",
    "lca",
    "lka",
    "mar",
    "mdg",
    "mdv",
    "mex",
    "mli",
    "mmr",
    "mne",
    "mng",
    "moz",
    "mus",
    "mwi",
    "nam",
    "ner",
    "nga",
    "nic",
    "npl",
    "pac",
    "pak",
    "pan",
    "per",
    "prt",
    "pry",
    "pse",
    "rwa",
    "sdn",
    "sen",
    "sle",
    "slv",
    "som",
    "srb",
    "swz",
    "syc",
    "syr",
    "tgo",
    "tls",
    "tto",
    "tun",
    "tur",
    "tza",
    "uga",
    "ury",
    "vct",
    "ven",
    "vnm",
    "xkx",
    "yem",
    "zmb",
]

# list of countries / regions which has different country_code and iso3
additional_region_code_to_iso3_map = {
    "etm": "tls",
    "mal": "mdv",
    "sy11": "syr",
    "znz": "tza",
    "019": "ind",
    "033": "ind",
    "005": "ind",
}


# @shared_task
# def ext_and_transform_desinventar_historical_data():
#     for country_code in country_code_iso3_list:
#         metadata = DesInventarExtractionInputMetadata(
#             country_code=country_code,
#             iso3=country_code,
#         ).model_dump()
#         chain(
#             DesinventarExtraction.task.s(metadata),
#             DesinventarTransformHandler.task.s(),
#         ).apply_async()

#     # FIXME: country_code should be region_code
#     for country_code, iso3 in additional_region_code_to_iso3_map.items():
#         metadata = DesInventarExtractionInputMetadata(
#             country_code=country_code,
#             iso3=iso3,
#         ).model_dump()
#         chain(
#             DesinventarExtraction.task.s(metadata),
#             DesinventarTransformHandler.task.s(),
#         ).apply_async()


@shared_task
def ext_and_transform_desinventar_historical_data():
    for country_code in country_code_iso3_list:
        url = f"{etl_config.DESINVENTAR_DATA_URL}/DesInventar/download/DI_export_{country_code}.zip"
        DesinventarExtractionV2.init_extraction(
            metadata=DesinventarExtractionMetadata(
                url=url,
                type=DesiventarMetadataType.QUERY,
                params=DesInventarExtractionParamsMetadata(country_code=country_code, iso3=country_code),
            )
        )
    for country_code, iso3 in additional_region_code_to_iso3_map.items():
        url = f"{etl_config.DESINVENTAR_DATA_URL}/DesInventar/download/DI_export_{country_code}.zip"
        DesinventarExtractionV2.init_extraction(
            metadata=DesinventarExtractionMetadata(
                url=url,
                type=DesiventarMetadataType.QUERY,
                params=DesInventarExtractionParamsMetadata(country_code=country_code, iso3=country_code),
            )
        )
