from datetime import datetime
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



def ev_adoption_rate(vehicle_data_year_csv_path, input_year):
    """
    Analyzes a csv of yearly dmv vehicle data and returns a dataframe
    demonstrating the percentage of registered vehicles in the 3 most recent years
    which are fuel-only vehicles, hybrids, and ZEVs (Zero emission vehicles)

    Inputs:
    vehicle_data_year_csv_path:
        type: string
        description: path to vehicle data csv
    input_year:
        type: int
        description: year csv path corresponds to
    """

    # Column type dictionary for reading in vehicle csv data:
    dtype_dict = {'Date': 'object', 
                'Zip Code': 'object',
                'Model Year': 'object',
                'Fuel': 'object',
                'Make': 'object',
                'Duty': 'object',
                'Vehicles': 'int64'
    }

    # Fuel type dictionary:
    fuel_dict = {'Battery Electric': 'ZEV',
                'Diesel and Diesel Hybrid': 'Fuel',
                'Flex-Fuel': 'Fuel',
                'Gasoline': 'Fuel',
                'Hybrid Gasoline': 'Hybrid',
                'Hydrogen Fuel Cell': 'ZEV',
                'Natural Gas': 'Fuel',
                'Other': 'Fuel',
                'Plug-in Hybrid': 'Hybrid'
    }

    # Read in CSV and perform some transformations
    raw = pd.read_csv(vehicle_data_year_csv_path, dtype = dtype_dict)
    raw['Date']= pd.to_datetime(raw['Date'])
    raw['Fuel (Broad)'] = raw['Fuel'].map(fuel_dict)
    raw.rename({'Fuel': 'Fuel (Specific)'})

    # Determine the newest 3 years for this particluar year:
    newest_years_dict = {
        2018: ['2017', '2018', '2019'],
        2020: ['2020', '2019', '2018'],
        2021: ['2021', '2020', '2019'],
        2022: ['2022', '2021', '2020']
    }
    newest_years = newest_years_dict[input_year]
    raw_newest = raw[raw['Model Year'].isin(newest_years)]

    # Total number of vehicles registed in the 3 newest years
    total_vehicles = raw_newest['Vehicles'].sum() 
    print(f'Total number of new vehicles for {input_year}: {total_vehicles}')
    print()

    # Put together dataframe to return
    return_df = pd.DataFrame(raw_newest.groupby('Fuel (Broad)')['Vehicles'].sum()/total_vehicles*100)
    return_df['Date'] = raw['Date'].min()
    return_df = return_df.reset_index()
    return_df.rename(columns = {'Fuel (Broad)': 'Fuel', 'Vehicles': 'Pct New Vehicles Registered'}, inplace = True)
    return return_df

