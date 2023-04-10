import geopandas as gpd
import geoplot
import geoplot.crs as gcrs
import pandas as pd

def combine_zip_codes_and_counties(zip_code_geojson_path, county_geojson_path):
    """
    Combines a zip_code geojson with a county geojson. 
    Meant to be run on California but could be used for other regions. 
    Combination occurs via a spatial join using zip code centroids intersecting with county polygons

    Inputs:
    zip_code_geojson_path
        type: string
        description: path to zip code geojson
    county_geojson_path
        type: string
        description: path to county geojson

    Returns:
    zip_code_and_county_gdf
        type: geopandas.geodataframe.GeoDataFrame
        description: GeoDataFrame with both zip code and county geometry
    """
    print("Reading in geojson files...")
    zip_codes = gpd.read_file(zip_code_geojson_path)
    counties = gpd.read_file(county_geojson_path)

    print(f'California has {len(zip_codes)} zip codes and {len(counties)} counties')

    # Drop unecessary columns
    zip_codes.drop(columns = ['OBJECTID', 'STATE', 'SHAPE_Length', 'SHAPE_Area'], inplace = True)
    counties.drop(columns = ['OBJECTID', 'COUNTY_NUM', 'COUNTY_CODE'], inplace = True)

    # Lowercase columns 
    zip_codes.columns= zip_codes.columns.str.lower()
    counties.columns = counties.columns.str.lower()

    # rename zip_code geom column
    zip_codes.rename_geometry('zip_code_geometry', inplace=True)

    # create duplicate county geometry column, because original county geometry column will be lost during the join
    counties['county_geometry'] = counties.geometry

    # Reset CRS from 4326 to 3857
    # This effectively sets our coordinate system from a globe to a map, which is necessary before we compute centroids
    zip_codes.to_crs(3857, inplace = True)
    counties.to_crs(3857, inplace = True)

    # Calculate zip code centroids - each centroid will be mapped to a county
    zip_codes['zip_code_centroid'] = zip_codes.centroid

    # Set the zip code active geometry to the centroid column
    # Then join counties onto zip codes by using zip code centroids intersecting with county polygons
    zip_codes.set_geometry('zip_code_centroid', inplace=True)
    zip_codes_with_county=gpd.sjoin(zip_codes, counties, how='inner',predicate='intersects')

    lost_num_zips = len(zip_codes) - len(zip_codes_with_county)
    print(f'Our join lost us {lost_num_zips} zip codes out of {len(zip_codes)}')

    return zip_codes_with_county