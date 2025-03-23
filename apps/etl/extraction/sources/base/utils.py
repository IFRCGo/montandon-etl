import hashlib
import json

from django.core.files.base import ContentFile

from apps.etl.models import ExtractionData, get_trace_id


def hash_file_content(content):
    """
    Compute the hash of a file using the specified algorithm.
    :return: Hexadecimal hash of the file
    """
    file_hash = hashlib.sha256(content).hexdigest()
    return file_hash


# FIXME: This is not correct. "revision_id" cannot be attached as such
def manage_duplicate_file_content(source, hash_content, instance, response_data, file_name):
    """
    if duplicate file content exists then do not create a new file, but point the url to
    the previous file.
    """
    if not isinstance(response_data, bytes):
        response_data = json.dumps(response_data, indent=2)

    duplicate_extraction_qs = ExtractionData.objects.filter(
        source=source,
        file_hash=hash_content,
        file_hash__isnull=False,
    )
    if instance.id:
        duplicate_extraction_qs.exclude(id=instance.id)

    duplicate_extraction_obj = duplicate_extraction_qs.first()
    if duplicate_extraction_obj:
        instance.resp_data = duplicate_extraction_obj.resp_data
        instance.revision_id = duplicate_extraction_obj.id
    else:
        instance.resp_data.save(file_name, ContentFile(response_data))

    instance.save()


# FIXME: reused by gdacs and usgs but this is not correct
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


# FIXME: move this function
def store_pdc_exposure_data(
    response,
    source=None,
    validate_source_func=None,
    instance_id=None,
    parent_id=None,
    hazard_type=None,
    metadata={}
):
    file_extension = "json"
    file_name = f"{instance_id}pdc.{file_extension}"
    data = json.dumps(response).encode("utf-8")

    instance = ExtractionData.objects.create(
        parent_id=parent_id.id,
        source=source,
        attempt_no=1,
        resp_code=200,
        status=ExtractionData.Status.SUCCESS,
        hazard_type=hazard_type,
        metadata=metadata,
        trace_id=get_trace_id(parent_id),
    )

    content_file = ContentFile(data)
    content_file.name = file_name
    instance.resp_data.save(content_file.name, content_file)

    return instance
