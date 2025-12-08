import pandas as pd
import numpy as np
from pathlib import Path
from session_data import SessionData
from antenna_array import AntennaArray
from mikrotik_metadata import ordering_sets, valid_antennas

# Insert all data paths you want for a ML Dataset
data_paths = [
    "../data/2025-11-25/session_122307",
    "../data/2025-11-20/session_135938"
]

def process_data_path(data_path, dataset_name=None):
    """
    Process a single data path and extract features for ML.
    
    Args:
        data_path: Path to the session directory
        dataset_name: Optional name for the dataset (defaults to directory name)
    
    Returns:
        pandas DataFrame with columns: H, array_response, array_factor, magnitude, phase, dataset_name
    """
    data_path = Path(data_path)
    
    if dataset_name is None:
        dataset_name = data_path.name
    
    # Load session data
    session = SessionData.from_directory(data_path)
    router_batches = session.load_all_router_batches()
    
    # Calculate antenna array spacing
    spacing = 0.58 * session.frequency / 60.48
    
    # Initialize lists to store data
    all_H = []
    all_array_responses = []
    all_magnitudes = []
    all_phases = []
    all_dataset_names = []
    
    # Process each router batch
    for dp in session.data_points:
        if dp.router_batch is None:
            continue

        H = dp.router_batch.csi_processed_data
        
        # Get magnitude and phase data
        magnitude_data = dp.router_batch.get_all_magnitude_data()  # Shape: (num_samples, num_antennas)
        phase_data = dp.router_batch.get_all_phase_data()  # Shape: (num_samples, num_antennas)
        
        # Process each sample in the batch
        for sample_idx in range(H.shape[0]):
            # Get channel data for this sample
            H_sample = H[sample_idx, :]  # Shape: (num_antennas,)
            
            # Set up antenna array for this sample
            antenna_array = AntennaArray()
            for ant in range(32):
                if ant not in valid_antennas:
                    continue
                antenna_array.add_element(
                    ordering_sets[ant, 0] * spacing - np.sign(ordering_sets[ant, 0]) * spacing / 2,
                    0,
                    ordering_sets[ant, 1] * spacing - np.sign(ordering_sets[ant, 1]) * spacing / 2
                )
            
            antenna_array.set_weights(np.conjugate(H_sample))
            # Calculate array response at el=0 (geometric, doesn't depend on channel data)
            array_response, _, _ = antenna_array.get_array_pattern_azimuth(el=0)  # Shape: (num_antennas,)
            
            # Store data
            all_H.append(H_sample)
            all_array_responses.append(array_response)
            all_magnitudes.append(magnitude_data[sample_idx, :])
            all_phases.append(phase_data[sample_idx, :])
            all_dataset_names.append(dataset_name)
    
    # Create DataFrame
    df = pd.DataFrame({
        'H': all_H,
        'array_response': all_array_responses,
        'magnitude': all_magnitudes,
        'phase': all_phases,
        'dataset_name': all_dataset_names
    })
    
    return df

def create_ml_dataset(data_paths):
    """
    Create a pandas DataFrame for machine learning from multiple data paths.
    
    Args:
        data_paths: List of paths to session directories
    
    Returns:
        pandas DataFrame with all processed data
    """
    all_dataframes = []
    
    for data_path in data_paths:
        if not data_path or data_path == "":
            continue
        
        print(f"Processing {data_path}...")
        try:
            df = process_data_path(data_path)
            all_dataframes.append(df)
            print(f"  Processed {len(df)} samples")
        except Exception as e:
            print(f"  Error processing {data_path}: {e}")
            continue
    
    if not all_dataframes:
        print("No data was processed. Please check your data paths.")
        return pd.DataFrame()
    
    # Combine all DataFrames
    final_df = pd.concat(all_dataframes, ignore_index=True)
    print(f"\nTotal samples: {len(final_df)}")
    
    return final_df

if __name__ == "__main__":
    # Create the ML dataset
    ml_dataset = create_ml_dataset(data_paths)
    
    # Save to CSV (optional)
    if not ml_dataset.empty:
        output_path = "ml_dataset.csv"
        ml_dataset.to_csv(output_path, index=False)
        print(f"\nDataset saved to {output_path}")
        
        # Display summary
        print("\nDataset Summary:")
        print(f"Total samples: {len(ml_dataset)}")
        print(f"Columns: {ml_dataset.columns.tolist()}")
        print(f"\nDataset name distribution:")
        print(ml_dataset['dataset_name'].value_counts())
        
        # Display first few rows
        print("\nFirst few rows:")
        print(ml_dataset.head())
