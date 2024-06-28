import pandas as pd


def load_data(folder_name: str):
    carbon_emissions = pd.read_csv(f'{folder_name}/carbon_emissions.csv')
    cost_profiles = pd.read_csv(f'{folder_name}/cost_profiles.csv')
    demand = pd.read_csv(f'{folder_name}/demand.csv')
    fuels = pd.read_csv(f'{folder_name}/fuels.csv')
    vehicles_fuels = pd.read_csv(f'{folder_name}/vehicles_fuels.csv')
    vehicles = pd.read_csv(f'{folder_name}/vehicles.csv')
    return carbon_emissions, cost_profiles, demand, fuels, vehicles_fuels, vehicles


def load_and_prepare_data(folder_name: str, years: int) -> dict:
    carbon_emissions, cost_profiles, demand, fuels, vehicles_fuels, vehicles = load_data(folder_name)
    data = {
        'years': years,
        'demand': {},
        'vehicles': {},
        'vehicle_fuels': {},
        'fuels': {},
        'carbon_limits': {},
        'cost_profiles': {}
    }

    # Populate demand data
    for _, row in demand.iterrows():
        year = row['Year']
        size_bucket = row['Size']
        distance_bucket = row['Distance']
        if year not in data['demand']:
            data['demand'][year] = {}
        data['demand'][year][(size_bucket, distance_bucket)] = row['Demand (km)']

    # Populate vehicle data
    for _, row in vehicles.iterrows():
        vehicle_id = row['ID']
        data['vehicles'][vehicle_id] = {
            'drivetrain': row['Vehicle'],
            'size_bucket': row['Size'],
            'purchase_cost': row['Cost ($)'],
            'yearly_range': row['Yearly range (km)'],
            'distance_bucket': row['Distance']
        }
    # Populate vehicle fuel data
    for _, row in vehicles_fuels.iterrows():
        vehicle_id = row['ID']
        fuel_type = row['Fuel']
        data['vehicle_fuels'][(vehicle_id, fuel_type)] = row['Consumption (unit_fuel/km)']
    # Populate fuels data
    for _, row in fuels.iterrows():
        fuel_type = row['Fuel']
        data['fuels'][fuel_type] = {
            'carbon_emission': row['Emissions (CO2/unit_fuel)'],
            'cost': row['Cost ($/unit_fuel)'],
            'uncertainty': row['Cost Uncertainty (±%)']
        }
    # Populate carbon emission limits
    for _, row in carbon_emissions.iterrows():
        year = row['Year']
        data['carbon_limits'][year] = row['Carbon emission CO2/kg']
    # Populate cost profiles data
    for _, row in cost_profiles.iterrows():
        year = row['End of Year']
        data['cost_profiles'][year] = {
            'resale_value': row['Resale Value %'],
            'insurance_cost': row['Insurance Cost %'],
            'maintenance_cost': row['Maintenance Cost %']
        }
    return data
