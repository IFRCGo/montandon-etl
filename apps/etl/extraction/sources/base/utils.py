import hashlib
import json
import os

from django.conf import settings
from django.core.files.base import ContentFile

from apps.etl.models import ExtractionData


def hash_file_content(content):
    """
    Compute the hash of a file using the specified algorithm.
    :return: Hexadecimal hash of the file
    """
    file_hash = hashlib.sha256(content).hexdigest()
    return file_hash


def manage_duplicate_file_content(source, hash_content, instance, response_data, file_name):
    """
    if duplicate file content exists then do not create a new file, but point the url to
    the previous file.
    """
    if not isinstance(response_data, bytes):
        response_data = json.dumps(response_data, indent=2)

    duplicate_file_content = ExtractionData.objects.filter(source=source, file_hash=hash_content)
    if duplicate_file_content:
        instance.resp_data = duplicate_file_content.first().resp_data
        instance.revision_id = duplicate_file_content.first()
    else:
        instance.resp_data.save(file_name, ContentFile(response_data))
    instance.save()


def store_extraction_data(
    response,
    source=None,
    validate_source_func=None,
    parent_id=None,
    instance_id=None,
    hazard_type=None,
    requires_hazard_type=False,
):
    file_extension = response.pop("file_extension")
    file_name = f"gdacs.{file_extension}"
    resp_data = response.pop("resp_data")

    # save the additional response data after the data is fetched from api.
    extraction_instance = ExtractionData.objects.get(id=instance_id)
    for key, value in response.items():
        setattr(extraction_instance, key, value)
    extraction_instance.save()

    # save parent id if it is child extraction object
    if parent_id:
        extraction_instance.parent_id = parent_id
        extraction_instance.save(update_fields=["parent_id"])

    # Validate the non empty response data.
    if resp_data and not response["resp_code"] == 204:
        resp_data_content = resp_data.content
        # Source validation
        # if the validate function requires hazard type as argument pass it as argument else don't.
        if validate_source_func:
            if requires_hazard_type:
                extraction_instance.source_validation_status = validate_source_func(resp_data_content, hazard_type)["status"]
                extraction_instance.content_validation = validate_source_func(resp_data_content, hazard_type)[
                    "validation_error"
                ]
            else:
                extraction_instance.source_validation_status = validate_source_func(resp_data_content)["status"]
                extraction_instance.content_validation = validate_source_func(resp_data_content)["validation_error"]

        # manage duplicate file content.
        hash_content = hash_file_content(resp_data_content)
        manage_duplicate_file_content(
            source=source,
            hash_content=hash_content,
            instance=extraction_instance,
            response_data=resp_data_content,
            file_name=file_name,
        )
    return extraction_instance


def store_pdc_exposure_data(
    response, source=None, validate_source_func=None, instance_id=None, parent_id=None, hazard_type=None, metadata=None
):
    file_extension = "json"
    file_name = f"{instance_id}pdc.{file_extension}"
    data = json.dumps(response).encode("utf-8")

    instance = ExtractionData.objects.create(
        parent_id=parent_id,
        source=source,
        attempt_no=1,
        resp_code=200,
        status=ExtractionData.Status.SUCCESS,
        hazard_type=hazard_type,
        metadata=metadata,
    )

    content_file = ContentFile(data)
    content_file.name = file_name
    instance.resp_data.save(content_file.name, content_file)

    return instance


def store_geojson_file(response, source=None, validate_source_func=None, instance_id=None, hazard_type=None, metadata=None):
    file_extension = "geojson"
    file_name = f"{instance_id}pdc.{file_extension}"
    instance = ExtractionData.objects.get(id=instance_id.id)
    file_path = os.path.join(settings.MEDIA_ROOT, "source_raw_data", file_name)
    with open(file_path, "w") as f:
        json.dump(response, f)
    instance.metadata["geojson_file_path"] = file_path
    instance.save()
    return instance.id
