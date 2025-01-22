import pandas as pd
from shapely.geometry import Point, mapping
from typing import List, Optional
from pystac import Item

STAC_EVENT_ID_PREFIX = "emdat-"

class EmdatProcessor:
    def make_source_event_items(self) -> List:
        """Create source event items from EMDAT data"""
        event_items = []
        # Assuming `self.data` is a DataFrame containing the EMDAT data
        for _, row in self.data.iterrows():
            try:
                event_item = self._create_event_item_from_row(row)
                if event_item:
                    event_items.append(event_item)
            except Exception as e:
                print(f"Error creating event item for SID {row.get('SID', 'unknown')}: {str(e)}")
                break

        return event_items

    def _create_event_item_from_row(self, row):
        if pd.isna(row.get("SID")):
            return None

        geometry = None
        bbox = None
        if geometry is None and not pd.isna(row.get("LAT")) and not pd.isna(row.get("LON")):
            point = Point(float(row["LON"]), float(row["LAT"]))
            geometry = mapping(point)
            bbox = [float(row["LON"]), float(row["LAT"]), float(row["LON"]), float(row["LAT"])]

        item = Item(
            id=f"{STAC_EVENT_ID_PREFIX}{row['SID']}",
            geometry=geometry,
            bbox=bbox,
            datetime="2022-02-02",
            properties={},
        )
        item.set_collection(self.get_event_collection())

        return item

    def make_hazard_event_items(self) -> List:
        """Create hazard items based on event items"""
        hazard_items = []
        event_items = self.make_source_event_items()

        for event_item in event_items:
            hazard_item = self._create_hazard_item_from_event(event_item)
            if hazard_item:
                hazard_items.append(hazard_item)

        return hazard_items

    def _create_hazard_item_from_event(self, event_item: Item) -> Optional[Item]:
        # Implementation for creating hazard item from event item
        pass