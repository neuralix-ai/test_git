import pandas as pd
from ortools.linear_solver import pywraplp

from data import load_and_prepare_data



if __name__ == '__main__':
    # read input files - data
    # choose a solver or set up a sovler
    # define decision varibles
    # define objective function
    # define constraints
    # solve
    # extract solution

    num_years = 16
    start_year = 2023
    end_year = start_year + num_years
    years = list(range(start_year, end_year))

    data = load_and_prepare_data('data', years)

    # Define constants

    vehicle_ids = list(set([k for k, v in data['vehicles'].items()]))
    size_buckets =  list(set([v['size_bucket'] for k, v in data['vehicles'].items()]))
    distance_buckets = ['D1', 'D2', 'D3', 'D4']
    num_scenarios = 1

    # Generate all combinations of size and distance buckets
    all_combinations = [(size, distance) for size in size_buckets for distance in distance_buckets]

    # Create the solver
    solver = pywraplp.Solver.CreateSolver('SCIP')

    # Decision Variables
    buy = {}
    use = {}
    sell = {}

    for year in years:
        for vehicle_id in vehicle_ids:
            # Extract the purchase year from the vehicle ID
            purchase_year = int(vehicle_id.split('_')[-1])

            if purchase_year == year:
                # Buy decision variable: integer indicating the number of vehicles bought in the given year
                buy[(vehicle_id, year)] = solver.IntVar(0, solver.infinity(), f'buy_{vehicle_id}_{year}')

            for fuel_type in data['fuels']:
                if (vehicle_id, fuel_type) in data['vehicle_fuels']:
                    for distance_bucket in distance_buckets:
                        # Use decision variable: integer indicating the number of vehicles used in the given year with specific fuel type and distance bucket
                        use[(vehicle_id, fuel_type, distance_bucket, year)] = solver.IntVar(0, solver.infinity(),
                                                                                            f'use_{vehicle_id}_{fuel_type}_{distance_bucket}_{year}')

            # Sell decision variable: integer indicating the number of vehicles sold in the given year
            sell[(vehicle_id, year)] = solver.IntVar(0, solver.infinity(), f'sell_{vehicle_id}_{year}')

    # Ensure vehicles can only be used if they have been bought and not sold
    for year in years:
        for vehicle_id in vehicle_ids:
            # Calculate the number of vehicles available for this ID in this year
            available_vehicles = solver.Sum(
                [buy[(vehicle_id, y)] for y in years if y <= year and (vehicle_id, y) in buy]) - \
                                 solver.Sum(
                                     [sell[(vehicle_id, y)] for y in years if y < year and (vehicle_id, y) in sell])

            # Ensure that the number of vehicles used does not exceed the available vehicles
            solver.Add(
                solver.Sum([use[(vehicle_id, fuel_type, distance_bucket, year)]
                            for fuel_type in data['fuels']
                            for distance_bucket in distance_buckets
                            if (vehicle_id, fuel_type) in data['vehicle_fuels']]) <= available_vehicles)

            # Ensure that the number of vehicles used is exactly equal to available vehicles
            solver.Add(
                solver.Sum([use[(vehicle_id, fuel_type, distance_bucket, year)]
                            for fuel_type in data['fuels']
                            for distance_bucket in distance_buckets
                            if (vehicle_id, fuel_type) in data['vehicle_fuels']]) == available_vehicles)

    # Ensure vehicles sold do not exceed the number of vehicles in the fleet
    for year in years:
        for vehicle_id in vehicle_ids:
            available_vehicles = solver.Sum(
                [buy[(vehicle_id, y)] for y in years if y <= year and (vehicle_id, y) in buy]) - \
                                 solver.Sum(
                                     [sell[(vehicle_id, y)] for y in years if y < year and (vehicle_id, y) in sell])

            # Ensure that the number of vehicles sold does not exceed the available vehicles
            solver.Add(
                sell[(vehicle_id, year)] <= available_vehicles)

    # Add Vehicle Size and Distance Bucket Constraint
    for year in years:
        for size_bucket in size_buckets:
            for distance_bucket in distance_buckets:
                if (size_bucket, distance_bucket) in data['demand'][year]:
                    demand_value = data['demand'][year][(size_bucket, distance_bucket)]
                    solver.Add(
                        solver.Sum([use[(vehicle_id, fuel_type, distance_bucket, year)] * data['vehicles'][vehicle_id][
                            'yearly_range']
                                    for vehicle_id in data['vehicles']
                                    for fuel_type in data['fuels']
                                    if data['vehicles'][vehicle_id]['size_bucket'] == size_bucket and
                                    distance_buckets.index(
                                        data['vehicles'][vehicle_id]['distance_bucket']) >= distance_buckets.index(
                                distance_bucket) and
                                    (vehicle_id, fuel_type) in data['vehicle_fuels']]
                                   ) >= demand_value
                    )

    # Add Carbon Emission Limits Constraint
    for year in years:
        carbon_emission_limit = data['carbon_limits'][year]
        total_emissions = solver.Sum([
            use[(vehicle_id, fuel_type, distance_bucket, year)] * data['vehicle_fuels'][(vehicle_id, fuel_type)] *
            data['fuels'][fuel_type]['carbon_emission'] * data['vehicles'][vehicle_id]['yearly_range']
            for vehicle_id in data['vehicles']
            for fuel_type in data['fuels']
            for distance_bucket in distance_buckets
            if (vehicle_id, fuel_type) in data['vehicle_fuels']
        ])
        solver.Add(total_emissions <= carbon_emission_limit)

    # Add Vehicle Purchase Year Constraint
    for vehicle_id in data['vehicles']:
        purchase_year = int(vehicle_id.split('_')[-1])
        if purchase_year in years:
            solver.Add(buy[(vehicle_id, purchase_year)] >= 1)

    # Add Vehicle Lifespan Constraint
    for vehicle_id in data['vehicles']:
        purchase_year = int(vehicle_id.split('_')[-1])
        if purchase_year + 10 in years:
            solver.Add(
                solver.Sum([sell[(vehicle_id, y)] for y in range(purchase_year, min(purchase_year + 11, end_year))]) >=
                buy[(vehicle_id, purchase_year)]
            )

    # Add Fleet Sell Limit Constraint
    for year in years:
        # Calculate the fleet size at the beginning of the year
        fleet_size = solver.Sum([
            buy[(vehicle_id, y)] for vehicle_id in data['vehicles'] for y in years if
            y <= year and (vehicle_id, y) in buy
        ]) - solver.Sum([
            sell[(vehicle_id, y)] for vehicle_id in data['vehicles'] for y in years if
            y < year and (vehicle_id, y) in sell
        ])
        # Ensure that at most 20% of the fleet can be sold each year
        solver.Add(
            solver.Sum([sell[(vehicle_id, year)] for vehicle_id in data['vehicles'] if
                        (vehicle_id, year) in sell]) <= 0.2 * fleet_size
        )

    # Add Vehicle Usage Year Constraint
    for year in years:
        for vehicle_id in vehicle_ids:
            purchase_year = int(vehicle_id.split('_')[-1])
            if year >= purchase_year and year < purchase_year + 10:
                solver.Add(solver.Sum([use[(vehicle_id, fuel_type, distance_bucket, year)]
                                       for fuel_type in data['fuels']
                                       for distance_bucket in distance_buckets
                                       if (vehicle_id, fuel_type) in data['vehicle_fuels']]) >= 0)
            else:
                solver.Add(solver.Sum([use[(vehicle_id, fuel_type, distance_bucket, year)]
                                       for fuel_type in data['fuels']
                                       for distance_bucket in distance_buckets
                                       if (vehicle_id, fuel_type) in data['vehicle_fuels']]) == 0)

    # Initialize the objective function
    objective = solver.Objective()

    # Add Purchase Costs
    for year in years:
        for vehicle_id in vehicle_ids:
            if (vehicle_id, year) in buy:
                purchase_cost = data['vehicles'][vehicle_id]['purchase_cost']
                objective.SetCoefficient(buy[(vehicle_id, year)], purchase_cost)

    # Add Fuel Costs
    for year in years:
        for vehicle_id in vehicle_ids:
            for fuel_type in data['fuels']:
                for distance_bucket in distance_buckets:
                    if (vehicle_id, fuel_type, distance_bucket, year) in use:
                        fuel_cost_per_km = data['vehicle_fuels'][(vehicle_id, fuel_type)] * data['fuels'][fuel_type][
                            'cost']
                        yearly_range = data['vehicles'][vehicle_id]['yearly_range']
                        total_fuel_cost = fuel_cost_per_km * yearly_range
                        objective.SetCoefficient(use[(vehicle_id, fuel_type, distance_bucket, year)], total_fuel_cost)

    # Add Maintenance and Insurance Costs
    for year in years:
        if year in data['cost_profiles']:
            for vehicle_id in vehicle_ids:
                if vehicle_id in data['vehicles']:
                    purchase_cost = data['vehicles'][vehicle_id]['purchase_cost']
                    maintenance_cost_percent = data['cost_profiles'][year]['maintenance_cost']
                    insurance_cost_percent = data['cost_profiles'][year]['insurance_cost']

                    maintenance_cost = (maintenance_cost_percent / 100) * purchase_cost
                    insurance_cost = (insurance_cost_percent / 100) * purchase_cost

                    total_maintenance_and_insurance_cost = maintenance_cost + insurance_cost

                    # Add maintenance and insurance costs to the use variable
                    for fuel_type in data['fuels']:
                        if (vehicle_id, fuel_type) in data['vehicle_fuels']:
                            for distance_bucket in distance_buckets:
                                if (vehicle_id, fuel_type, distance_bucket, year) in use:
                                    objective.SetCoefficient(use[(vehicle_id, fuel_type, distance_bucket, year)],
                                                             total_maintenance_and_insurance_cost)

    # Set the objective to minimize the total cost
    objective.SetMinimization()

    # Solve the problem
    status = solver.Solve()

    solution = []

    for year in years:
        for size_bucket, distance_bucket in all_combinations:
            # Initialize distance per vehicle to 0 for all combinations
            distance_per_vehicle = 0
            used_vehicle = False  # Flag to track if any vehicle is used for this combination

            # Check if there are any vehicles used for this combination
            for vehicle_id in vehicle_ids:
                for fuel_type in data['fuels']:
                    if (vehicle_id, fuel_type, distance_bucket, year) in use and use[
                        (vehicle_id, fuel_type, distance_bucket, year)].solution_value() > 0:
                        vehicle_size_bucket = data['vehicles'][vehicle_id]['size_bucket']
                        vehicle_distance_bucket = data['vehicles'][vehicle_id]['distance_bucket']
                        if vehicle_size_bucket == size_bucket and distance_buckets.index(
                                vehicle_distance_bucket) >= distance_buckets.index(distance_bucket):
                            distance_per_vehicle += data['vehicles'][vehicle_id]['yearly_range'] * use[
                                (vehicle_id, fuel_type, distance_bucket, year)].solution_value()

                            # Add the solution entry
                            solution.append([year, vehicle_id,
                                             int(use[(vehicle_id, fuel_type, distance_bucket, year)].solution_value()),
                                             'Use', fuel_type, distance_bucket,
                                             data['vehicles'][vehicle_id]['yearly_range']])
                            used_vehicle = True

            # If no vehicle is used for this combination, add a row with Num_Vehicles = 0
            if not used_vehicle:
                solution.append([year, '', 0, 'Use', '', distance_bucket, 0])

    # Add buy and sell decisions to the solution
    for year in years:
        for vehicle_id in vehicle_ids:
            if (vehicle_id, year) in buy and buy[(vehicle_id, year)].solution_value() > 0:
                solution.append([year, vehicle_id, int(buy[(vehicle_id, year)].solution_value()), 'Buy', '', '', ''])

            if (vehicle_id, year) in sell and sell[(vehicle_id, year)].solution_value() > 0:
                solution.append([year, vehicle_id, int(sell[(vehicle_id, year)].solution_value()), 'Sell', '', '', ''])

    # Create the solution dataframe
    solution_df = pd.DataFrame(solution, columns=['Year', 'ID', 'Num_Vehicles', 'Type', 'Fuel', 'Distance_bucket',
                                                  'Distance_per_vehicle(km)'])

    # Save the solution to a CSV file
    solution_df.to_csv('solution.csv', index=False)
    print('Solution saved to solution.csv')

    float_convert = pd.read_csv('solution.csv')

    print(float_convert.columns)
    print(float_convert.dtypes)
    if 'Distance_per_vehicle(km)' in float_convert.columns:
        float_convert['Distance_per_vehicle(km)'] = float_convert['Distance_per_vehicle(km)'].fillna(0.0)
    else:
        print("Column 'Distance_per_vehicle(km)' does not exist in the DataFrame")
    float_convert.to_csv('float_convert.csv', index=False)
