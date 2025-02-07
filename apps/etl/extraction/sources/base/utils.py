import hashlib
import json

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
    gdacs_instance = ExtractionData.objects.get(id=instance_id)
    for key, value in response.items():
        setattr(gdacs_instance, key, value)
    gdacs_instance.save()

    # save parent id if it is child extraction object
    if parent_id:
        gdacs_instance.parent_id = parent_id
        gdacs_instance.save(update_fields=["parent_id"])

    # Validate the non empty response data.
    if resp_data and not response["resp_code"] == 204:
        resp_data_content = resp_data.content
        # Source validation
        # if the validate function requires hazard type as argument pass it as argument else don't.
        if validate_source_func:
            if requires_hazard_type:
                gdacs_instance.source_validation_status = validate_source_func(resp_data_content, hazard_type)["status"]
                gdacs_instance.content_validation = validate_source_func(resp_data_content, hazard_type)["validation_error"]
            else:
                gdacs_instance.source_validation_status = validate_source_func(resp_data_content)["status"]
                gdacs_instance.content_validation = validate_source_func(resp_data_content)["validation_error"]

        # manage duplicate file content.
        hash_content = hash_file_content(resp_data_content)
        manage_duplicate_file_content(
            source=source,
            hash_content=hash_content,
            instance=gdacs_instance,
            response_data=resp_data_content,
            file_name=file_name,
        )
    return gdacs_instance


def store_pdc_exposure_data(
    response, source=None, validate_source_func=None, instance_id=None, parent_id=None, hazard_type=None
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
        metadata={
            "uuid": response["uuid"],
            "exosure": str(response["exposure"].keys()),
        },
    )

    content_file = ContentFile(data)
    content_file.name = file_name
    instance.resp_data.save(content_file.name, content_file)

    return instance
