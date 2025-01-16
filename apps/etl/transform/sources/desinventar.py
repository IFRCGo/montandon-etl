import logging
from pathlib import Path

from geopandas import gpd
from lxml import etree

logger = logging.getLogger(__name__)


def get_list_item_safe(list, index, default_value=None):
    try:
        return list[index]
    except IndexError:
        return default_value


def transform_country_data(country_code: str, iso3: str):
    logger.info(f"Desinventar: Transform started for {country_code}")
    print(f"Desinventar: Transform started for {country_code}")

    # TODO: this should come from utils
    output_dir = "/tmp/desinventar/{country_code}"
    xml_file_path = f"{output_dir}/DI_export_{country_code}.xml"

    if Path(xml_file_path).exists():
        tree = etree.parse(xml_file_path)
        root = tree.getroot()

        # Admin level mappings
        level_maps = root.xpath("//level_maps/TR")
        geo_data = {}

        for level_row in level_maps:
            file_path = get_list_item_safe(level_row.xpath("filename/text()"), 0)
            level = get_list_item_safe(level_row.xpath("map_level/text()"), 0)
            property_code = get_list_item_safe(level_row.xpath("lev_code/text()"), 0)

            if file_path is not None:
                file_name = Path(str(file_path)).name
                current_file_path = f"{output_dir}/{file_name}"
                # TODO: check if file exists
                if Path(current_file_path).exists():
                    shapefile_data = gpd.read_file(current_file_path)
                else:
                    shapefile_data = None
            else:
                shapefile_data = None

            geo_data[f"level{level}"] = {"level": level, "property_code": property_code, "shapefile_data": shapefile_data}

        # TODO: only extract necessary fields
        columns = {
            "serial": "serial",
            "muertos": "deaths",
            "hay_muertos": "flag_deaths",
            "heridos": "injured",
            "hay_heridos": "flag_injured",
            "desaparece": "missing",
            "hay_deasparece": "flag_missing",
            "vivdest": "houses_destroyed",
            "hay_vivdest": "flag_houses_destroyed",
            "vivafec": "houses_damaged",
            "hay_vivafec": "flag_houses_damaged",
            "damnificados": "directly_affected",
            "hay_damnificados": "flag_directly_affected",
            "afectados": "indirectly_affected",
            "hay_afectados": "flag_indirectly_affected",
            "reubicados": "relocated",
            "hay_reubicados": "flag_relocated",
            "evacuados": "evacuated",
            "hay_evacuados": "flag_evacuated",
            "valorus": "losses_in_dollar",
            "valorloc": "losses_local_currency",
            "nescuelas": "education_centers",
            "nhospitales": "hospitals",
            "nhectareas": "damages_in_crops_ha",
            "cabezas": "lost_cattle",
            "kmvias": "damages_in_roads_mts",
            "level0": "level0",
            "level1": "level1",
            "level2": "level2",
            "name0": "name0",
            "name1": "name1",
            "name2": "name2",
            "latitude": "latitude",
            "longitude": "longitude",
            "evento": "event",
            "glide": "glide",
            "lugar": "location",
            "magnitud2": "haz_maxvalue",
            "duracion": "duration",
            "fechano": "year",
            "fechames": "month",
            "fechadia": "day",
        }

        # TODO: calculate it dynamically
        applicable_geo_levels = ["level2", "level1", "level0"]

        events = root.xpath("//fichas/TR")
        data = []
        for event_row in events:
            row_data = {}

            for desinventar_key, mapped_key in columns.items():
                values = event_row.xpath(f"{desinventar_key}/text()")
                row_data[mapped_key] = get_list_item_safe(values, 0)

            for level in applicable_geo_levels:
                if row_data[level]:
                    gfd = geo_data[level]["shapefile_data"]

                    if gfd is not None:
                        code = geo_data[level]["property_code"]
                        filtered_gdf = gfd[gfd[code] == row_data[level]]

                        # Use a tolerance value for simplification (smaller values will keep more detail)
                        filtered_gdf["geometry"] = filtered_gdf["geometry"].apply(
                            lambda geom: geom.simplify(tolerance=0.01, preserve_topology=True)
                        )

                        row_data["geometry"] = filtered_gdf.to_json()

                    row_data["desinventar_country_code"] = country_code
                    row_data["iso3"] = iso3

                    break

            data.append(row_data)

        # print(json.dumps(data, indent=4))

        logger.info(f"Desinventar: Transform successful for {country_code}")
        print(f"Desinventar: Transform successful for {country_code}")
    else:
        logger.info(f"Desinventar: Cannot find required file for the transformation for {country_code}")
        print(f"Desinventar: Cannot find required file for the transformation for {country_code}")

    logger.info(f"Desinventar: Transform ended for {country_code}")
    print(f"Desinventar: Transform ended for {country_code}")
