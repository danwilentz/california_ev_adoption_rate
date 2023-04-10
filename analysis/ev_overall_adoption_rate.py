from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
import geopandas as gpd
import geoplot
import geoplot.crs as gcrs
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import pandas as pd
import sys
sys.path.append('../utils')
from helper_functions import ev_adoption_rate

# Calculate EV adoption rates for each year we have data:
summary_2018 = ev_adoption_rate('../vehicle_data/vehicle-fuel-type-count-by-zip-code.csv', 2018)
summary_2020 = ev_adoption_rate('../vehicle_data/vehicle-count-as-of-1-1-2020.csv', 2020)
summary_2021 = ev_adoption_rate('../vehicle_data/vehicle-fuel-type-count-by-zip-code-2021.csv', 2021)
summary_2022 = ev_adoption_rate('../vehicle_data/vehicle-fuel-type-count-by-zip-code-2022.csv', 2022)

# Combine results into a single dataframe:
df_final = pd.concat([summary_2018, summary_2020, summary_2021, summary_2022])

# Separate the dataframe by fuel type from plotting purposes:
evs_only = df_final[df_final['Fuel'] != 'Fuel']
evs_overall = evs_only.groupby('Date')['Pct New Vehicles Registered'].sum()
hybrids = evs_only[evs_only['Fuel'] == 'Hybrid'].groupby('Date')['Pct New Vehicles Registered'].sum()
ZEVs = evs_only[evs_only['Fuel'] == 'ZEV'].groupby('Date')['Pct New Vehicles Registered'].sum()

# Create target horizonal line as pandas.dataframe (also for plotting purposes)
original_date = date(2018, 10, 1)
curr_date = date(2019, 1, 1)
years_list = [original_date, curr_date]
for i in range(7):
    curr_date = curr_date + relativedelta(years=1)
    years_list.append(curr_date)
goal = pd.Series([35.0 for x in range(len(years_list))], index = years_list)

## Plot Results
# Plot formatting
fig, ax = plt.subplots(figsize = (12, 8))
ax.set_ylabel('Pct. new registered vehicles that are EVs', fontsize = 14)
ax.set_ylim([0, 40])
ax.yaxis.set_major_formatter(mtick.PercentFormatter(decimals = 1))
ax.set_title('California EV Adoption Rate (using DMV new Registered Vehicles)', fontsize = 16)

# Plot overall EV progress
evs_overall.plot(kind = 'line', 
                 label = 'Overall EVs',
                 color = 'b',
                 linewidth = 2,
                 ax=ax)

# Plot hybrid progress
hybrids.plot(kind = 'line', 
                 label = 'Hybrids',
                 color = 'tab:pink',
                 linewidth = 1,
                 ax=ax)

# Plot ZEV progress
ZEVs.plot(kind = 'line', 
                 label = 'ZEV',
                 color = 'tab:purple',
                 linewidth = 1,
                 ax=ax)

# Plot goal line
goal.plot(kind = 'line', 
          label = 'Goal Percentage',
          color = 'r', 
          linestyle = 'dashed',
          linewidth = 2,
          ax = ax)

# Plot goal marker
ax.plot(date(2026, 1, 1), 35.0, 'rx', mfc='none', markersize = 20, label='2026 Goal') 

# Additional Formatting
ax.set_xlabel('Year', fontsize = 14)
ax.legend(loc = 'lower right')
ax.grid(color='#DDDDDD', linestyle=':', linewidth=0.8)

# Save plot
fig.savefig('../pics/overall_ev_progress.png')
plt.close(fig)
