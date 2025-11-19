from django.utils.functional import cached_property

from apps.etl.dataloaders import ExtractionDataLoader, PystacDataLoader


class GlobalDataLoader:
    @cached_property
    def extraction(self):
        return ExtractionDataLoader()

    @cached_property
    def pystac(self):
        return PystacDataLoader()
