import json
import logging

import requests
from celery import chain, shared_task

from apps.etl.extraction.sources.base.extract import Extraction
from apps.etl.extraction.sources.base.utils import store_extraction_data
from apps.etl.models import ExtractionData, HazardType

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def fetch_exposure_details(self, parent_id, detail_url, **kwargs):
    url = f"https://sentry.pdc.org/hp_srv/services/hazard/{detail_url}/exposure"
    instance_id = kwargs.get("instance_id", None)
    if not instance_id:
        pdc_instance = ExtractionData.objects.create(
            source=ExtractionData.Source.PDC,
            status=ExtractionData.Status.PENDING,
            source_validation_status=ExtractionData.ValidationStatus.NO_VALIDATION,
            attempt_no=0,
            resp_code=0,
            hazard_type="",
        )
    else:
        pdc_instance = ExtractionData.objects.get(id=instance_id)

    pdc_extraction = Extraction(
        url=url,
        headers={
            "Authorization": "Bearer {}".format(
                "eyJraWQiOiIyMDE4LTA4LTA5fGFwcHMucGRjLm9yZyIsImFsZyI6IlJTNTEyIn0.eyJqdGkiOiI3MjdlOTExZC0xNzI5LTRkOTAtYTc5OS04OWRhMzNhMzAwOGYiLCJpc3MiOiJodHRwczovL2FwcHMucGRjLm9yZy9qd3Qvandrcy5qc29uIiwiaWF0IjoxNjM5MDk5NDQ0LCJuYmYiOjE2MzkwOTk0NDQsInN1YiI6ImFwcHMucGRjLm9yZyIsImV4cCI6NDEwMjQ0NDgwMCwidXNlclJvbGVzIjpbIkxPR0lOIl0sInVzZXJHcm91cElkIjoiMSIsInRva2VuVHlwZSI6ImxvbmcifQ.VmwvfjkCYGOv-WLOFQJ1x4cIWnFW8infqte_qnVZOT0jXagX2_LPE_tagm9RnDW6vJSqGg4CexNR-WTEOSQN32ZW1UZ31PHYKtO2jbDZt2u6RZVkLPjuwdxomumTEdXWKs-MTlSwWNm0NelGMjwq2PrNeYjjv1No0FIJeJ3hhKAFpf3D27uhEJSwUxKcjdtC-ilpVvDO1eKlKWFwj8d3N6iqBVrxrhNBFYMmDGwFFPx7UZravaQVzdqvzv9OvSIMXH_l--LhimRSOKYfh6tH5P0o45iXEYSuWMZXWnG7akbMvckAnXzPCTjsDKc0o3Vi1k6PPyJllxMbg-ZUjM95rQ"
            )
        },
    )
    response = None
    try:
        response = pdc_extraction.pull_data(
            source=ExtractionData.Source.PDC,
            ext_object_id=pdc_instance.id,
            retry_count=0,
        )
        print(response, "In try block")
    except Exception as exc:
        self.retry(exc=exc, kwargs={"instance_id": pdc_instance.id, "retry_count": self.request.retries})
    print(response)
    if response:
        pdc_instance = store_extraction_data(
            response=response,
            source=ExtractionData.Source.PDC,
            instance_id=pdc_instance.id,
            parent_id=parent_id,
            hazard_type="",
        )
        return pdc_instance.id


@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def get_list_of_exposure(self, file, **kwargs):
    timestamp = []
    finaldata={}
    for j in file[:4]:
        url = f"https://sentry.pdc.org/hp_srv/services/hazard/{j['uuid']}/exposure"
        r = requests.get(
            url=url,
            headers={
                "Authorization": "Bearer {}".format(
                    "eyJraWQiOiIyMDE4LTA4LTA5fGFwcHMucGRjLm9yZyIsImFsZyI6IlJTNTEyIn0.eyJqdGkiOiI3MjdlOTExZC0xNzI5LTRkOTAtYTc5OS04OWRhMzNhMzAwOGYiLCJpc3MiOiJodHRwczovL2FwcHMucGRjLm9yZy9qd3Qvandrcy5qc29uIiwiaWF0IjoxNjM5MDk5NDQ0LCJuYmYiOjE2MzkwOTk0NDQsInN1YiI6ImFwcHMucGRjLm9yZyIsImV4cCI6NDEwMjQ0NDgwMCwidXNlclJvbGVzIjpbIkxPR0lOIl0sInVzZXJHcm91cElkIjoiMSIsInRva2VuVHlwZSI6ImxvbmcifQ.VmwvfjkCYGOv-WLOFQJ1x4cIWnFW8infqte_qnVZOT0jXagX2_LPE_tagm9RnDW6vJSqGg4CexNR-WTEOSQN32ZW1UZ31PHYKtO2jbDZt2u6RZVkLPjuwdxomumTEdXWKs-MTlSwWNm0NelGMjwq2PrNeYjjv1No0FIJeJ3hhKAFpf3D27uhEJSwUxKcjdtC-ilpVvDO1eKlKWFwj8d3N6iqBVrxrhNBFYMmDGwFFPx7UZravaQVzdqvzv9OvSIMXH_l--LhimRSOKYfh6tH5P0o45iXEYSuWMZXWnG7akbMvckAnXzPCTjsDKc0o3Vi1k6PPyJllxMbg-ZUjM95rQ"
                )
            },
        )
        if r.status_code == 200:
           

            for i in r.json():
                url = f"https://sentry.pdc.org/hp_srv/services/hazard/{j['uuid']}/exposure/{i}"
                r = requests.get(
                    url=url,
                    headers={
                        "Authorization": "Bearer {}".format(
                            "eyJraWQiOiIyMDE4LTA4LTA5fGFwcHMucGRjLm9yZyIsImFsZyI6IlJTNTEyIn0.eyJqdGkiOiI3MjdlOTExZC0xNzI5LTRkOTAtYTc5OS04OWRhMzNhMzAwOGYiLCJpc3MiOiJodHRwczovL2FwcHMucGRjLm9yZy9qd3Qvandrcy5qc29uIiwiaWF0IjoxNjM5MDk5NDQ0LCJuYmYiOjE2MzkwOTk0NDQsInN1YiI6ImFwcHMucGRjLm9yZyIsImV4cCI6NDEwMjQ0NDgwMCwidXNlclJvbGVzIjpbIkxPR0lOIl0sInVzZXJHcm91cElkIjoiMSIsInRva2VuVHlwZSI6ImxvbmcifQ.VmwvfjkCYGOv-WLOFQJ1x4cIWnFW8infqte_qnVZOT0jXagX2_LPE_tagm9RnDW6vJSqGg4CexNR-WTEOSQN32ZW1UZ31PHYKtO2jbDZt2u6RZVkLPjuwdxomumTEdXWKs-MTlSwWNm0NelGMjwq2PrNeYjjv1No0FIJeJ3hhKAFpf3D27uhEJSwUxKcjdtC-ilpVvDO1eKlKWFwj8d3N6iqBVrxrhNBFYMmDGwFFPx7UZravaQVzdqvzv9OvSIMXH_l--LhimRSOKYfh6tH5P0o45iXEYSuWMZXWnG7akbMvckAnXzPCTjsDKc0o3Vi1k6PPyJllxMbg-ZUjM95rQ"
                        )
                    },
                )
                timestamp.append({i:r.json()})
                finaldata[j['uuid']]= timestamp
        f = open("data.json",'w')
        f.write(str(finaldata))
        f.close()
    return finaldata

@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def import_hazard_data(self, **kwargs):
    """
    Import hazard data from pdc api
    """
    logger.info(f"Importing PDC data")
    pdc_url = "https://sentry.pdc.org/hp_srv/services/hazards/t/json/get_active_hazards"

    # Create a Extraction object in the beginning
    instance_id = kwargs.get("instance_id", None)
    retry_count = kwargs.get("retry_count", None)

    pdc_instance = (
        ExtractionData.objects.get(id=instance_id)
        if instance_id
        else ExtractionData.objects.create(
            source=ExtractionData.Source.PDC,
            status=ExtractionData.Status.PENDING,
            source_validation_status=ExtractionData.ValidationStatus.NO_VALIDATION,
            hazard_type="",
            attempt_no=0,
            resp_code=0,
        )
    )

    # Extract the data from api.
    pdc_extraction = Extraction(
        url=pdc_url,
        headers={
            "Authorization": "Bearer {}".format(
                "eyJraWQiOiIyMDE4LTA4LTA5fGFwcHMucGRjLm9yZyIsImFsZyI6IlJTNTEyIn0.eyJqdGkiOiI3MjdlOTExZC0xNzI5LTRkOTAtYTc5OS04OWRhMzNhMzAwOGYiLCJpc3MiOiJodHRwczovL2FwcHMucGRjLm9yZy9qd3Qvandrcy5qc29uIiwiaWF0IjoxNjM5MDk5NDQ0LCJuYmYiOjE2MzkwOTk0NDQsInN1YiI6ImFwcHMucGRjLm9yZyIsImV4cCI6NDEwMjQ0NDgwMCwidXNlclJvbGVzIjpbIkxPR0lOIl0sInVzZXJHcm91cElkIjoiMSIsInRva2VuVHlwZSI6ImxvbmcifQ.VmwvfjkCYGOv-WLOFQJ1x4cIWnFW8infqte_qnVZOT0jXagX2_LPE_tagm9RnDW6vJSqGg4CexNR-WTEOSQN32ZW1UZ31PHYKtO2jbDZt2u6RZVkLPjuwdxomumTEdXWKs-MTlSwWNm0NelGMjwq2PrNeYjjv1No0FIJeJ3hhKAFpf3D27uhEJSwUxKcjdtC-ilpVvDO1eKlKWFwj8d3N6iqBVrxrhNBFYMmDGwFFPx7UZravaQVzdqvzv9OvSIMXH_l--LhimRSOKYfh6tH5P0o45iXEYSuWMZXWnG7akbMvckAnXzPCTjsDKc0o3Vi1k6PPyJllxMbg-ZUjM95rQ"
            )
        },
    )
    response = None
    try:
        response = pdc_extraction.pull_data(
            source=ExtractionData.Source.PDC,
            ext_object_id=pdc_instance.id,
            retry_count=retry_count if retry_count else 1,
        )
    except requests.exceptions.RequestException as exc:
        self.retry(exc=exc, kwargs={"instance_id": pdc_instance.id, "retry_count": self.request.retries})

    if response:
        # Save the extracted data into the existing pdc object
        pdc_instance = store_extraction_data(
            response=response,
            source=ExtractionData.Source.PDC,
            validate_source_func=None,
            instance_id=pdc_instance.id,
        )
        if pdc_instance.resp_code == 200:
            response_data = json.loads(pdc_instance.resp_data.read())
            data = get_list_of_exposure(response_data)
            print(data)
                
                
                # pdc_instance.metadata = {"exposure": data, "hazard_uuid": feature["uuid"]}
                # pdc_instance.save()

                # fetch_exposure_details(pdc_instance)

        logger.info(f"PDC data imported sucessfully")
        return pdc_instance.id
