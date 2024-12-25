import matplotlib.pyplot as plt
import seaborn as sns
import os
from ..logs.logger import setup_logging

logger = setup_logging()
def plot_feature_target_relationship(data, target_column, features=None, save_path=None):
    """
    Plot scatter plots showing the relationship between features and the target.

    Parameters:
    - data: pd.DataFrame, the dataset to visualize.
    - target_column: str, the name of the target column.
    - features: list of str, specific feature columns to plot against the target (default: all except target).
    - save_path: str, directory to save the plots (default: None, no saving).
    """
    logger.info("Plotting feature-target relationships...")
    if features is None:
        features = [col for col in data.columns if col != target_column]

    for feature in features:
        plt.figure(figsize=(8, 5))
        sns.scatterplot(x=data[feature], y=data[target_column], alpha=0.7, color="green")
        plt.title(f"{feature} vs {target_column}")
        plt.xlabel(feature)
        plt.ylabel(target_column)
        if save_path:
            os.makedirs(save_path, exist_ok=True)
            file_path = os.path.join(save_path, f"{feature}_vs_{target_column}.png")
            plt.savefig(file_path)
            logger.info(f"Saved feature-target relationship plot for {feature} to {file_path}")
        plt.show()

def plot_feature_distribution(data, columns=None, save_path=None):
    """
    Plot the distribution of features in the dataset.

    Parameters:
    - data: pd.DataFrame, the dataset to visualize.
    - columns: list of str, specific columns to plot (default: all columns in `data`).
    - save_path: str, directory to save the plots (default: None, no saving).
    """
    logger.info("Plotting feature distributions...")
    if columns is None:
        columns = data.columns

    for column in columns:
        plt.figure(figsize=(8, 5))
        sns.histplot(data[column], kde=True, bins=30, color="blue")
        plt.title(f"Distribution of {column}")
        plt.xlabel(column)
        plt.ylabel("Frequency")
        if save_path:
            os.makedirs(save_path, exist_ok=True)
            file_path = os.path.join(save_path, f"{column}_distribution.png")
            plt.savefig(file_path)
            logger.info(f"Saved distribution plot for {column} to {file_path}")
        plt.show()

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

def plot_feature_target_relationship(data, target_column, features=None, save_path=None):
    """
    Plot scatter plots showing the relationship between features and the target.

    Parameters:
    - data: pd.DataFrame, the dataset to visualize.
    - target_column: str, the name of the target column.
    - features: list of str, specific feature columns to plot against the target (default: all except target).
    - save_path: str, directory to save the plots (default: None, no saving).
    """
    logger.info("Plotting feature-target relationships...")
    if features is None:
        features = [col for col in data.columns if col != target_column]

    for feature in features:
        plt.figure(figsize=(8, 5))
        sns.scatterplot(x=data[feature], y=data[target_column], alpha=0.7, color="green")
        plt.title(f"{feature} vs {target_column}")
        plt.xlabel(feature)
        plt.ylabel(target_column)
        if save_path:
            os.makedirs(save_path, exist_ok=True)
            file_path = os.path.join(save_path, f"{feature}_vs_{target_column}.png")
            plt.savefig(file_path)
            logger.info(f"Saved feature-target relationship plot for {feature} to {file_path}")
        plt.show()

def plot_model_performance(y_true, y_pred, save_path=None):
    """
    Plot the performance of the model by comparing true and predicted values.

    Parameters:
    - y_true: array-like, true target values.
    - y_pred: array-like, predicted target values.
    - save_path: str, directory to save the plot (default: None, no saving).
    """
    logger.info("Plotting model performance...")
    plt.figure(figsize=(8, 5))
    sns.scatterplot(x=y_true, y=y_pred, alpha=0.7, color="purple")
    plt.plot([min(y_true), max(y_true)], [min(y_true), max(y_true)], color="red", linestyle="--")
    plt.title("True vs Predicted Values")
    plt.xlabel("True Values")
    plt.ylabel("Predicted Values")
    if save_path:
        os.makedirs(save_path, exist_ok=True)
        file_path = os.path.join(save_path, "model_performance.png")
        plt.savefig(file_path)
        logger.info(f"Saved model performance plot to {file_path}")
    plt.show()
