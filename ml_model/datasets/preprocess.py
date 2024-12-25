from sklearn.model_selection import train_test_split
import pandas as pd
import numpy as np
import os
from ..logs.logger import setup_logging

logger = setup_logging()

def derive_features(features):
    """
    Derive additional features for the dataset.

    Parameters:
    - features: pd.DataFrame, original feature data.

    Returns:
    - features: pd.DataFrame, with additional derived features.
    """
    logger.info("Deriving additional features...")

    try:
        # Add derived features
        features["VoltageError"] = features["TargetVoltage"] - features["MeasuredVoltage"]
        features["VoltageChangeRate"] = features["MeasuredVoltage"].diff() / features["Timestamp"].diff()
        features["VoltageChangeRate"] = features["VoltageChangeRate"].fillna(0)
        features["TimeDifference"] = features["Timestamp"].diff().fillna(0)
        features["RelativeResponseRate"] = features["VoltageChangeRate"] / features["Ramp-up rate"]
        features["RelativeResponseRate"] = features["RelativeResponseRate"].fillna(0)
        features["ControlSignalChangeRate"] = features["ControlSignal"].diff() / features["Timestamp"].diff()
        features["ControlSignalChangeRate"] = features["ControlSignalChangeRate"].fillna(0)
        logger.info("Additional features derived successfully.")
    except Exception as e:
        logger.error("Error deriving features: %s", str(e))
        raise

    return features

def clean_invalid_values(features, strategy="fill", fill_value=0):
    """
    Clean invalid values in the dataset.

    Parameters:
    - features: pd.DataFrame, feature data.
    - strategy: str, strategy for handling invalid values ("fill" or "drop").
        - "fill": Replace invalid values with `fill_value`.
        - "drop": Drop rows containing invalid values.
    - fill_value: value to use for replacing invalid values (default: 0).

    Returns:
    - features: pd.DataFrame, cleaned feature data.
    """
    if strategy == "fill":
        logger.info("Replacing invalid values with %s.", fill_value)
        features = features.replace([np.inf, -np.inf], np.nan)
        features = features.fillna(fill_value)
    elif strategy == "drop":
        logger.info("Dropping rows with invalid values...")
        features = features.replace([np.inf, -np.inf], np.nan)
        features = features.dropna()
    else:
        raise ValueError(f"Invalid cleaning strategy '{strategy}'. Use 'fill' or 'drop'.")

    logger.info("Invalid values handled successfully using strategy '%s'.", strategy)
    return features

def standardize_features(features, standardize=True):
    """
    Standardize feature data if needed.

    Parameters:
    - features: pd.DataFrame, original feature data.
    - standardize: bool, whether to standardize the features.

    Returns:
    - features: pd.DataFrame, standardized feature data (if `standardize=True`).
    """
    if standardize:
        logger.info("Standardizing features...")
        features = (features - features.mean()) / features.std()
        logger.info("Feature standardization completed.")
    return features

def preprocess_data(file_path, columns=None, clean_strategy="fill", fill_value=0, standardize=True):
    """
    Load and preprocess feedback gain optimization data.

    Parameters:
    - file_path: str, path to the input CSV file.
    - columns: dict, a mapping of required feature names to actual column names in the input file.
        Default: {
            "TargetVoltage": "TargetVoltage",
            "MeasuredVoltage": "MeasuredVoltage",
            "ControlSignal": "ControlSignal",
            "Sampling frequency": "Sampling frequency",
            "Ramp-up rate": "Ramp-up rate",
            "Timestamp": "Timestamp",
            "FeedforwardKp": "FeedforwardKp"
        }
    - clean_strategy: str, strategy for handling invalid values ("fill" or "drop").
    - fill_value: value to use for replacing invalid values (default: 0).
    - standardize: bool, whether to standardize the features.

    Returns:
    - features: pd.DataFrame, preprocessed feature data.
    - target: pd.Series, preprocessed target data.
    """
    logger.info("Starting data preprocessing...")

    # Step 1: Load data
    logger.info("Loading data from file: %s", file_path)
    df = pd.read_csv(file_path)
    logger.info("Data loaded successfully. Shape: %s", df.shape)

    # Step 2: Validate columns
    default_columns = {
        "TargetVoltage": "TargetVoltage",
        "MeasuredVoltage": "MeasuredVoltage",
        "ControlSignal": "ControlSignal",
        "Sampling frequency": "Sampling frequency",
        "Ramp-up rate": "Ramp-up rate",
        "Timestamp": "Timestamp",
        "FeedforwardKp": "FeedforwardKp"
    }
    columns = columns or default_columns

    for key, col in columns.items():
        if col not in df.columns:
            raise KeyError(f"Missing required column '{col}' for '{key}'. Check input file or column mapping.")

    # Step 3: Feature selection
    features = df[[columns["TargetVoltage"], columns["MeasuredVoltage"], columns["ControlSignal"],
                   columns["Sampling frequency"], columns["Ramp-up rate"], columns["Timestamp"]]]

    # Step 4: Derived features
    features = derive_features(features)

    # Step 5: Clean invalid values
    features = clean_invalid_values(features, strategy=clean_strategy, fill_value=fill_value)

    # Step 6: Standardize features
    features = standardize_features(features, standardize)

    # Step 7: Extract target
    target = df[columns["FeedforwardKp"]].astype(np.float64)

    logger.info("Preprocessing completed successfully.")
    return features, target
