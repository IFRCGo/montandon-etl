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
        duplicate_extraction_qs = duplicate_extraction_qs.exclude(id=instance.id)

    duplicate_extraction_obj = duplicate_extraction_qs.first()
    if duplicate_extraction_obj:
        instance.resp_data = duplicate_extraction_obj.resp_data
        instance.revision_id = duplicate_extraction_obj.id
    else:
        instance.resp_data.save(file_name, ContentFile(response_data))

    instance.save()
