import contextily as cx
import geopandas as gpd
import geoplot
import geoplot.crs as gcrs
import matplotlib.pyplot as plt
import pandas as pd
import sys
sys.path.append('../utils')
from helper_functions import combine_zip_codes_and_county_geos, total_vehicles_by_zip, city_geos

### POPULATION PROCESSING ###
print()
print('Processing population data ...')

# Get a mapping of California zip codes to counties
# This also includes 2017 population
zip_code_path = "../geojsons/California_Zip_Codes.geojson"
counties_path = "../geojsons/California_County_Boundaries.geojson"
zip_county_mapper = combine_zip_codes_and_county_geos(zip_code_path, counties_path)[['zip_code', 'po_name', 'population', 'county_name', 'county_abbrev']]
zip_county_mapper.rename(columns = {'population': 'pop_2017'}, inplace = True)
zip_county_mapper.pop_2017 = zip_county_mapper.pop_2017.astype(str)

# Get California 2021 population
pop_2021 = pd.read_csv('../vehicle_data/california_pop_by_zip_code.csv', thousands=',')[['zip_code', 'population_2021']]
pop_2021.rename(columns = {'population_2021': 'pop_2021'}, inplace = True)
pop_2021 = pop_2021.astype({'zip_code': 'str', 'pop_2021': 'int64'})

# Join California 2021 population onto zip and county data
zip_county_mapper_final = zip_county_mapper.merge(pop_2021, on='zip_code', how='left')



### VEHICLE COUNTS PROCESSING ###
print()
print('Processing vehicle counts data ...')

# Read in vehicle counts information
vehicles_by_zip_2018 = total_vehicles_by_zip('../vehicle_data/vehicle-fuel-type-count-by-zip-code.csv')
vehicles_by_zip_2022 = total_vehicles_by_zip('../vehicle_data/vehicle-fuel-type-count-by-zip-code-2022.csv')

# merge vehicle counts with population information
zip_county_vehicles = zip_county_mapper_final.merge(vehicles_by_zip_2018, on='zip_code', how = 'left')
zip_county_vehicles.rename(columns = {'vehicles': 'vehicles_2018'}, inplace = True)

zip_county_vehicles = zip_county_vehicles.merge(vehicles_by_zip_2022, on='zip_code', how = 'left')
zip_county_vehicles.rename(columns = {'vehicles': 'vehicles_2022'}, inplace = True)

# Process data anomalies
# Some zip codes have no reported vehicles reported as NaN - we'll replace these with 0s
# Some zip codes (such as national forests or parks) have no population recorded with -99 as the flag for this. 
# We'll convert this to 0s as well
county_info = zip_county_vehicles[['county_name', 'pop_2017', 'pop_2021', 'vehicles_2018', 'vehicles_2022']]
county_info = county_info.fillna(0)
cols_to_convert = ['pop_2017', 'pop_2021', 'vehicles_2018', 'vehicles_2022']
county_info[cols_to_convert] = county_info[cols_to_convert].astype(int)
county_info['pop_2017'] = county_info['pop_2017'].clip(lower=0)

# Sum up all zip code populations and vehicles within a county
county_info = county_info.groupby(['county_name'])[cols_to_convert].sum().reset_index()



### GEOGRAPHY PROCESSING ###
print()
print('Processing county geography information ...')

# Read in county geojson - we will use this for plotting
counties = gpd.read_file(counties_path)
counties.columns= counties.columns.str.lower()

# Dedupping county geojson columns. There are multiple instances of slightly different geometries for:
# Los Angeles, Santa Barbara, and Ventura Counties
counties['rank'] = counties.groupby('county_name')['objectid'].rank(method='first')
counties = counties[counties['rank'] == 1]

# subset county gdf to only get county name and geometry
county_geoms = counties[['county_name', 'geometry']]

# merge county population and vehicle info with geometries
county_df = county_info.merge(county_geoms, on = 'county_name', how = 'left')



### FINAL PROCESSING ###

# convert county df to county gdf
county_gdf = gpd.GeoDataFrame(county_df[['county_name', 'pop_2017', 'pop_2021', 'vehicles_2018', 'vehicles_2022']], 
                 geometry=county_df['geometry'])

# Calculate yearly vehicles per capita
county_gdf['vehicles_per_capita_2018'] = county_gdf['vehicles_2018']/county_gdf['pop_2017']
county_gdf['vehicles_per_capita_2022'] = county_gdf['vehicles_2022']/county_gdf['pop_2021']

# set gdf crs to 3857
county_gdf.to_crs(3857, inplace=True)

# Grab city information for plotting
cities_path = "../geojsons/City_Boundaries.geojson"
cities = city_geos(cities_path)

# Overall stats
california_summary = county_gdf[['pop_2017', 'pop_2021', 'vehicles_2018', 'vehicles_2022']].sum()
vpc_2018 = round(california_summary['vehicles_2018']/california_summary['pop_2017'], 3)
vpc_2022 = round(california_summary['vehicles_2022']/california_summary['pop_2021'], 3)
pct_change = round((vpc_2022-vpc_2018)/vpc_2018*100, 2)

print()
print(f'Overall, California had {vpc_2018} vehicles per person in 2018 and {vpc_2022} in 2022')
print(f"That's a total percent change of {pct_change}%")

# Counties with the lowest vpc in 2022
print()
print('Here are the 5 counties with the lowest VPCs in 2022:')
print(county_gdf.sort_values(by=['vehicles_per_capita_2022']).head(5))

# Counties with the highest vpc in 2022
print()
print('Here are the 5 counties with the highest VPCs in 2022:')
print(county_gdf.sort_values(by=['vehicles_per_capita_2022'], ascending = False).head(5))

# Incorporate pct_change in vpc for each county
county_gdf['vpc_pct_change'] = ((county_gdf['vehicles_per_capita_2022'] - county_gdf['vehicles_per_capita_2018'])/
                                county_gdf['vehicles_per_capita_2018'])*100



### PLOTS ###

# Plot 2022 VPC rates
fig, ax = plt.subplots(figsize = (10, 10))
county_gdf.plot(ax=ax, 
                column='vehicles_per_capita_2022', 
                legend=True, 
                legend_kwds={'shrink':0.5},
                cmap = 'PiYG_r')
cities.plot(ax=ax,
           color = 'orange',
           markersize = 10)

for idx, row in cities.iterrows():
    plt.annotate(text=row['city'], xy=row['coords'], horizontalalignment='center', color='Black')

ax.get_xaxis().set_visible(False)
ax.get_yaxis().set_visible(False)

for edge in ['right', 'bottom', 'top','left']:
    ax.spines[edge].set_visible(False)
    
ax.set_title('CA Vehicles per Capita (2022)', size=18, weight='bold')

# Save plot
fig.savefig('../pics/vpc_2022_2.png')
plt.close(fig)


# Plot VPC % change from 2018 to 2022
fig, ax = plt.subplots(figsize = (10, 10))
county_gdf.plot(ax=ax, 
                column='vpc_pct_change', 
                legend=True, 
                legend_kwds={'shrink':0.5},
                cmap = 'PiYG_r')

cities.plot(ax=ax,
           color = 'orange',
           markersize = 10)

for idx, row in cities.iterrows():
    plt.annotate(text=row['city'], xy=row['coords'], horizontalalignment='center', color='Black')

ax.get_xaxis().set_visible(False)
ax.get_yaxis().set_visible(False)

for edge in ['right', 'bottom', 'top','left']:
    ax.spines[edge].set_visible(False)
    
ax.set_title('CA Vehicles per Capita Pct. Change from 2018 to 2022', size=18, weight='bold')

# Save plot
fig.savefig('../pics/vpc_pct_change_2018_2022_2.png')
plt.close(fig)