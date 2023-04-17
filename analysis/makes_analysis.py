import contextily as cx
import geopandas as gpd
import geoplot
import geoplot.crs as gcrs
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import sys
sys.path.append('../utils')
from helper_functions import combine_zip_codes_and_county_geos, total_vehicles_and_evs_by_zip, city_geos

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
            'Hybrid Gasoline': 'Fuel',
            'Hydrogen Fuel Cell': 'ZEV',
            'Natural Gas': 'Fuel',
            'Other': 'Fuel',
            'Plug-in Hybrid': 'Hybrid'
}

newest_years = ['2022', '2021', '2020']

raw = pd.read_csv('../vehicle_data/vehicle-fuel-type-count-by-zip-code-2022.csv', dtype = dtype_dict)

# process data
raw.columns= raw.columns.str.lower()
raw['date']= pd.to_datetime(raw['date'])
raw['fuel (broad)'] = raw['fuel'].map(fuel_dict)
raw.rename(columns = {'fuel': 'fuel (specific)', 'zip code': 'zip_code'}, inplace = True)

# Grab only newest years
raw_newest = raw[raw['model year'].isin(newest_years)]

# Grab column for ev counts
raw_newest['evs'] = np.where(raw_newest['fuel (broad)'].isin(['ZEV', 'Hybrid']), raw_newest['vehicles'], 0)



### OVERALL ANALYSIS ###

# Who is selling the most EVs?
print('Who is selling the most EVs?')
makes_summary_2022 = raw_newest.groupby('make')[['evs', 'vehicles']].sum().sort_values(by = 'evs', ascending = False).reset_index()
makes_summary_2022['ev_rate_2022'] = round(makes_summary_2022['evs']/makes_summary_2022['vehicles']*100, 2)
total_evs = makes_summary_2022['evs'].sum()
makes_summary_2022['pct_of_total_evs'] = round(makes_summary_2022['evs']/total_evs*100, 2)
print(makes_summary_2022[makes_summary_2022['make'] != 'OTHER/UNK'].head(10))
print()

# Who's selling the most cars, overall
print('Who is selling the most cars, overall?')
print(makes_summary_2022[makes_summary_2022['make'] != 'OTHER/UNK'].sort_values(by = 'vehicles', ascending = False).head(10))
print()

# Who has the highest rate of EV sales of all car sales?
print('Who has the highest EV sell rate?')
print(makes_summary_2022[makes_summary_2022['make'] != 'OTHER/UNK'].sort_values(by = 'ev_rate_2022', ascending = False).head(10))
print()



### COUNTY LEVEL ANALYSIS ###

# Get everything on a zip-code level first
zip_makes_df = raw_newest.groupby(['zip_code', 'make'])[['vehicles', 'evs']].sum().reset_index()

# Merge make data with zip and county mapper
zip_county_makes_vehicles = zip_county_mapper_final.merge(zip_makes_df, 
                                                    on='zip_code', 
                                                    how = 'left')
zip_county_makes_vehicles.rename(columns = {'vehicles': 'vehicles_2022', 'evs': 'evs_2022'}, inplace = True)

# Group by county:
zip_county_makes_vehicles.fillna(0, inplace = True)
county_makes_vehicles = zip_county_makes_vehicles.groupby(['county_name', 'make'])[['vehicles_2022', 'evs_2022']].sum().reset_index()

# Filter out "OTHER/UNK"
county_makes_vehicles_without_other = county_makes_vehicles[county_makes_vehicles['make'] != 'OTHER/UNK']

# Grab the largest EV seller for each county
county_largest_makers = county_makes_vehicles_without_other.sort_values(['evs_2022']).groupby('county_name').tail(1)
county_largest_makers.rename(columns = {'make': 'largest_maker', 
                                        'vehicles_2022': 'maker_vehicles_2022',
                                        'evs_2022': 'maker_evs_2022'},
                            inplace = True)

# Merge the above result with county overall vehicle information
county_summary = county_makes_vehicles.groupby('county_name')[['vehicles_2022', 'evs_2022']].sum().reset_index()
county_info = county_summary.merge(county_largest_makers, on = 'county_name', how = 'left')

# Compute additional metrics:
county_info['maker_share_of_evs'] = round(county_info['maker_evs_2022']/county_info['evs_2022']*100, 2)
county_info['maker_ev_rate'] = round(county_info['maker_evs_2022']/county_info['maker_vehicles_2022']*100, 2)

# Add in geography data:
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
                                         'vehicles_2022', 
                                         'evs_2022', 
                                         'largest_maker', 
                                         'maker_vehicles_2022', 
                                         'maker_evs_2022',
                                         'maker_share_of_evs',
                                         'maker_ev_rate']], 
                 geometry=county_df['geometry'])

# Change '0' to 'Other'
def largest_maker_helper_func(largest_maker):
    if largest_maker == 0:
        return 'OTHER'
    else:
        return largest_maker

county_gdf['largest_maker'] = county_gdf['largest_maker'].apply(lambda x: largest_maker_helper_func(x))

# set gdf crs to 3857
county_gdf.to_crs(3857, inplace=True)

# Grab city information
cities_path = "../geojsons/City_Boundaries.geojson"
cities = city_geos(cities_path)

# Plot
# Who sells the most EVs per county?

fig, ax = plt.subplots(figsize = (10, 10))
county_gdf.plot(ax=ax,
                categorical = True,
                column='largest_maker',
                legend = True,
                cmap = 'Pastel2')
cities.plot(ax=ax,
           color = 'orange',
           markersize = 10)

for idx, row in cities.iterrows():
    plt.annotate(text=row['city'], xy=row['coords'], horizontalalignment='center', color='Black')

ax.get_xaxis().set_visible(False)
ax.get_yaxis().set_visible(False)

for edge in ['right', 'bottom', 'top','left']:
    ax.spines[edge].set_visible(False)
    
ax.set_title('Largest EV sellers per County', size=18, weight='bold')

# Save plot
fig.savefig('../pics/largest_ev_sellers_per_county_2.png')
plt.close(fig)