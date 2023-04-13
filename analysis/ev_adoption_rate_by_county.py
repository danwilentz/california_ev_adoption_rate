import contextily as cx
import geopandas as gpd
import geoplot
import geoplot.crs as gcrs
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
pd.options.mode.chained_assignment = None  # default='warn'
import sys
sys.path.append('../utils')
from helper_functions import combine_zip_codes_and_county_geos, total_vehicles_and_evs_by_zip, city_geos

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
print('Processing vehicle counts and ev counts data ...')

# Vehicle Counts - focus on 2022 and 2021
v_and_ev_by_zip_2022 = total_vehicles_and_evs_by_zip('../vehicle_data/vehicle-fuel-type-count-by-zip-code-2022.csv', 2022)
v_and_ev_by_zip_2021 = total_vehicles_and_evs_by_zip('../vehicle_data/vehicle-fuel-type-count-by-zip-code-2021.csv', 2021)

# Merge vehicle counts and evs to zip code mapper
zip_county_vehicles = zip_county_mapper_final.merge(v_and_ev_by_zip_2022, 
                                                    on='zip_code', 
                                                    how = 'left')
zip_county_vehicles.rename(columns = {'vehicles': 'vehicles_2022', 'evs': 'evs_2022'}, inplace = True)
zip_county_vehicles = zip_county_vehicles.merge(v_and_ev_by_zip_2021, 
                                                    on='zip_code', 
                                                    how = 'left')
zip_county_vehicles.rename(columns = {'vehicles': 'vehicles_2021', 'evs': 'evs_2021'}, inplace = True)

# Process data anomalies
# Some zip codes have no reported vehicles reported as NaN - we'll replace these with 0s
# Some zip codes (such as national forests or parks) have no population recorded with -99 as the flag for this. 
# We'll convert this to 0s as well
county_info = zip_county_vehicles[['county_name', 'pop_2017', 'pop_2021', 'vehicles_2022', 'evs_2022', 'vehicles_2021', 'evs_2021']]
county_info = county_info.fillna(0)
cols_to_convert = ['pop_2017', 'pop_2021', 'vehicles_2022', 'evs_2022', 'vehicles_2021', 'evs_2021']
county_info[cols_to_convert] = county_info[cols_to_convert].astype(int)
county_info['pop_2017'] = county_info['pop_2017'].clip(lower=0)

# Sum up all zip code populations and vehicles within a county
county_info = county_info.groupby(['county_name'])[cols_to_convert].sum().reset_index()

# Calculate EV adoption rates for each year
county_info['ev_rate_2022'] = round(county_info['evs_2022']/county_info['vehicles_2022']*100, 2)
county_info['ev_rate_2021'] = round(county_info['evs_2021']/county_info['vehicles_2021']*100, 2)

print('Processing expected EV adoption rates in 2026')
# Extrapolate which counties are on target for 2026
# Based on the difference between 2021 and 2022, if we assume the same linear increase each year,
# Do we see counties hitting the 35% target by 2026?
county_info['2022_yoy_improvement'] = county_info['ev_rate_2022'] - county_info['ev_rate_2021']
county_info['ev_rate_2026_extrap'] = county_info['2022_yoy_improvement']*4 + county_info['ev_rate_2022']
county_info['2026_target_hit'] = county_info['ev_rate_2026_extrap'] >= 35.0
county_info['color'] = np.where(county_info['2026_target_hit'], 'limegreen', 'tomato')



### GEOGRAPHY PROCESSING ###
print()
print('Processing county geography information ...')

# Read in county geojson - we will use this for plotting
counties = gpd.read_file(counties_path)
counties.columns= counties.columns.str.lower()

# Dedupping columns. There are multiple instances of slightly different geometries for:
# Los Angeles, Santa Barbara, and Ventura Counties
counties['rank'] = counties.groupby('county_name')['objectid'].rank(method='first')
counties = counties[counties['rank'] == 1]

# subset county gdf to only get county name and geometry
county_geoms = counties[['county_name', 'geometry']]

# merge county vehicle count info with geometries
county_df = county_info.merge(county_geoms, on = 'county_name', how = 'left')

# convert county df to county gdf
county_gdf = gpd.GeoDataFrame(county_df[['county_name', 
                                         'pop_2017', 
                                         'pop_2021', 
                                         'vehicles_2022', 
                                         'evs_2022', 
                                         'vehicles_2021',
                                         'evs_2021',
                                         'ev_rate_2022',
                                         'ev_rate_2021',
                                         '2022_yoy_improvement',
                                         'ev_rate_2026_extrap',
                                         '2026_target_hit',
                                         'color']], 
                 geometry=county_df['geometry'])

# set gdf crs to 3857
county_gdf.to_crs(3857, inplace=True)

# Grab city information
cities_path = "../geojsons/City_Boundaries.geojson"
cities = city_geos(cities_path)



### PLOTS ###

# EV Adoption Rate 2022
fig, ax = plt.subplots(figsize = (10, 10))
county_gdf.plot(ax=ax,
                column='ev_rate_2022', 
                legend=True, 
                legend_kwds={'shrink':0.5},
                cmap = 'Greens')
cities.plot(ax=ax,
           color = 'orange',
           markersize = 10)

for idx, row in cities.iterrows():
    plt.annotate(text=row['city'], xy=row['coords'], horizontalalignment='center', color='Black')

ax.get_xaxis().set_visible(False)
ax.get_yaxis().set_visible(False)

for edge in ['right', 'bottom', 'top','left']:
    ax.spines[edge].set_visible(False)
    
ax.set_title('CA EV Adoption Rate (2022) by County', size=18, weight='bold')

# Save plot
fig.savefig('../pics/ev_rate_2022.png')
plt.close(fig)


# Plot Which counties are on track to hit target of 35% EV rate by 2026
fig, ax = plt.subplots(figsize = (10, 10))
county_gdf.plot(ax=ax,
                categorical = True,
                column='2026_target_hit', 
                color = county_gdf['color'])
cities.plot(ax=ax,
           color = 'orange',
           markersize = 10)

for idx, row in cities.iterrows():
    plt.annotate(text=row['city'], xy=row['coords'], horizontalalignment='center', color='Black')

ax.get_xaxis().set_visible(False)
ax.get_yaxis().set_visible(False)

for edge in ['right', 'bottom', 'top','left']:
    ax.spines[edge].set_visible(False)
    
ax.set_title('Expected Outcome by County: 35% Car Sales are EVs by 2026', size=16, weight='bold')

# Save plot
fig.savefig('../pics/ev_rate_2026_expectations.png')
plt.close(fig)



### Overall stats ###
california_summary = county_gdf[['vehicles_2022', 'evs_2022', 'vehicles_2021', 'evs_2021']].sum()
ev_rate_2022 = round(california_summary['evs_2022']/california_summary['vehicles_2022']*100, 2)
ev_rate_2021 = round(california_summary['evs_2021']/california_summary['vehicles_2021']*100, 2)
pct_change = round((ev_rate_2022 - ev_rate_2021)/ev_rate_2021*100, 2)

important_columns = ['county_name', 'pop_2021', 'vehicles_2022', 'evs_2022', 'ev_rate_2022', 'ev_rate_2026_extrap']

print(f'Overall, California had an EV adoption rate of {ev_rate_2022}% in 2022 and {ev_rate_2021} in 2021')
print(f"That's a percent change of {pct_change} year over year.")
print()

print('Counties with the lowest ev_rate in 2022:')
print(county_gdf.sort_values(by=['ev_rate_2022'])[important_columns].head(5))
print()

print('Counties with the highest ev_rate in 2022')
print(county_gdf.sort_values(by=['ev_rate_2022'], ascending = False)[important_columns].head(5))
print()

# We'll take the counties who will miss the target by 2026,
# And multiply how much we project they will miss their target by their 2021 population
# To get a weighted importance factor
county_gdf['importance_factor'] = round(county_gdf['pop_2021']*(county_gdf['ev_rate_2026_extrap'] - 35.0)/100, 2)

print('The 5 most important counties to focus on:')
print(county_gdf.sort_values(by=['importance_factor'])[important_columns].head(5))

