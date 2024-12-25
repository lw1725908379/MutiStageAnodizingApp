from sklearn.model_selection import train_test_split
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import os
from ..logs.logger import setup_logging


logger = setup_logging()


def split_data(features, target, test_size=0.2, random_state=42):
    """
    Split data into training and testing sets.

    Parameters:
    - features: Feature data, must be a Pandas DataFrame or Numpy array.
    - target: Target values, must be a Pandas Series or Numpy array.
    - test_size: Proportion of the dataset to include in the test split (default: 0.2).
    - random_state: Random seed for reproducibility (default: 42).

    Returns:
    - X_train, X_test, y_train, y_test: Training and testing sets.
    """
    logger.info("Starting dataset split...")

    # Validate input data types
    if not isinstance(features, (pd.DataFrame, np.ndarray)):
        logger.error("features must be a Pandas DataFrame or Numpy array.")
        raise TypeError("features must be a Pandas DataFrame or Numpy array.")
    if not isinstance(target, (pd.Series, np.ndarray)):
        logger.error("target must be a Pandas Series or Numpy array.")
        raise TypeError("target must be a Pandas Series or Numpy array.")

    # Validate data length
    if len(features) != len(target):
        logger.error("Mismatch in number of samples between features and target.")
        raise ValueError("features and target must have the same number of samples.")
    if len(features) < int(1 / test_size):
        logger.error("Insufficient samples to split with test_size=%.2f", test_size)
        raise ValueError("Insufficient samples to split with test_size={}".format(test_size))

    # Split the dataset
    try:
        X_train, X_test, y_train, y_test = train_test_split(
            features, target, test_size=test_size, random_state=random_state
        )
        logger.info("Dataset split successfully: Training set size=%d, Testing set size=%d", len(X_train), len(X_test))
    except Exception as e:
        logger.error("Error during dataset split: %s", str(e))
        raise

    return X_train, X_test, y_train, y_test


def plot_correlation_heatmap(data, save_path=None, figsize=None, font_scale=1.0):
    """
    Plot a correlation heatmap for the dataset.

    Parameters:
    - data: pd.DataFrame, the dataset to visualize.
    - save_path: str, directory to save the plot (default: None, no saving).
    - figsize: tuple, size of the figure (default: dynamically determined).
    - font_scale: float, scaling factor for font size (default: 1.0).
    """
    logger.info("Plotting correlation heatmap...")

    # Calculate correlation matrix
    correlation_matrix = data.corr()

    # Dynamically adjust figure size based on the number of features
    if figsize is None:
        num_features = len(correlation_matrix.columns)
        figsize = (num_features, num_features)  # Make the heatmap square-like

    # Adjust font scale for large heatmaps
    sns.set(font_scale=font_scale)

    # Plot heatmap
    plt.figure(figsize=figsize)
    sns.heatmap(
        correlation_matrix,
        annot=True,
        cmap="coolwarm",
        fmt=".2f",
        linewidths=0.5,
        xticklabels=correlation_matrix.columns,
        yticklabels=correlation_matrix.columns
    )
    plt.title("Correlation Heatmap", fontsize=16)

    # Ensure labels are not cropped
    plt.tight_layout()

    # Save the plot if a path is provided
    if save_path:
        os.makedirs(save_path, exist_ok=True)
        file_path = os.path.join(save_path, "correlation_heatmap.png")
        plt.savefig(file_path)
        logger.info(f"Saved correlation heatmap to {file_path}")

    plt.show()
